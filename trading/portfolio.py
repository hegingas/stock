"""持仓管理 + 盈亏跟踪。"""
import datetime
import pandas as pd
from database import query, get_conn


class Portfolio:
    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        conn = get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                code       TEXT PRIMARY KEY,
                name       TEXT,
                buy_date   TEXT,
                buy_price  REAL,
                quantity   INTEGER,
                stop_loss  REAL,
                take_profit REAL,
                note       TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                code       TEXT,
                name       TEXT,
                buy_date   TEXT,
                sell_date  TEXT,
                buy_price  REAL,
                sell_price REAL,
                quantity   INTEGER,
                pnl        REAL,
                pnl_pct    REAL,
                hold_days  INTEGER
            );
        """)
        conn.commit()
        conn.close()

    def open_position(self, code, name, buy_price, quantity,
                      stop_loss=None, take_profit=None, buy_date=None):
        buy_date = buy_date or datetime.date.today().strftime("%Y-%m-%d")
        conn = get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO positions
            (code, name, buy_date, buy_price, quantity, stop_loss, take_profit)
            VALUES (?,?,?,?,?,?,?)
        """, [code, name, buy_date, buy_price, quantity, stop_loss, take_profit])
        conn.commit()
        conn.close()

    def close_position(self, code, sell_price, sell_date=None):
        sell_date = sell_date or datetime.date.today().strftime("%Y-%m-%d")
        pos = query("SELECT * FROM positions WHERE code=?", [code])
        if pos.empty:
            return None

        p = pos.iloc[0]
        pnl = (sell_price - p["buy_price"]) * p["quantity"]
        pnl_pct = (sell_price / p["buy_price"] - 1) * 100 if p["buy_price"] else 0
        # 计算持有天数
        try:
            bd = datetime.date.fromisoformat(p["buy_date"])
            sd = datetime.date.fromisoformat(sell_date)
            hold_days = (sd - bd).days
        except ValueError:
            hold_days = 0

        conn = get_conn()
        conn.execute("""
            INSERT INTO trades (code, name, buy_date, sell_date, buy_price,
                sell_price, quantity, pnl, pnl_pct, hold_days)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [code, p["name"], p["buy_date"], sell_date, p["buy_price"],
              sell_price, p["quantity"], round(pnl, 2), round(pnl_pct, 2), hold_days])
        conn.execute("DELETE FROM positions WHERE code=?", [code])
        conn.commit()
        conn.close()
        return {"pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "hold_days": hold_days}

    def get_positions(self):
        df = query("SELECT * FROM positions ORDER BY buy_date")
        if df.empty:
            return df

        # 补充实时价格
        realtime = query("SELECT code, price FROM realtime")
        if not realtime.empty:
            rt_map = dict(zip(realtime["code"], realtime["price"]))
            df["current_price"] = df["code"].map(rt_map)
            mask = df["current_price"].notna() & (df["buy_price"] > 0)
            df.loc[mask, "pnl"] = (
                (df.loc[mask, "current_price"] - df.loc[mask, "buy_price"])
                * df.loc[mask, "quantity"]
            ).round(2)
            df.loc[mask, "pnl_pct"] = (
                (df.loc[mask, "current_price"] / df.loc[mask, "buy_price"] - 1) * 100
            ).round(2)

        return df

    def get_trades(self, limit=50):
        return query(f"SELECT * FROM trades ORDER BY sell_date DESC LIMIT {limit}")

    def get_summary(self):
        trades = self.get_trades(1000)
        positions = self.get_positions()

        total_pnl = trades["pnl"].sum() if not trades.empty else 0
        win_trades = (trades["pnl"] > 0).sum() if not trades.empty else 0
        total_trades = len(trades)

        unrealized = positions["pnl"].sum() if not positions.empty and "pnl" in positions.columns else 0

        return {
            "total_trades": total_trades,
            "win_trades": win_trades,
            "win_rate": round(win_trades / total_trades * 100, 1) if total_trades else 0,
            "total_pnl": round(total_pnl, 2),
            "unrealized_pnl": round(float(unrealized), 2),
            "open_positions": len(positions),
        }
