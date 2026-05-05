"""模拟账户 + 订单管理 + 简单撮合引擎。"""
import datetime
import pandas as pd
import numpy as np
from database import query, get_conn, table_exists


class SimAccount:
    def __init__(self):
        self._init_tables()

    def _init_tables(self):
        conn = get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sim_account (
                id INTEGER PRIMARY KEY CHECK (id=1),
                cash REAL DEFAULT 100000,
                initial_cash REAL DEFAULT 100000
            );
            INSERT OR IGNORE INTO sim_account (id, cash, initial_cash) VALUES (1, 100000, 100000);

            CREATE TABLE IF NOT EXISTS sim_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                direction TEXT,        -- buy/sell
                order_type TEXT,       -- market/limit
                price REAL,            -- 委托价
                quantity INTEGER,
                status TEXT DEFAULT 'pending',  -- pending/filled/cancelled
                fill_price REAL,
                fill_time TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS sim_positions (
                code TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER,
                avg_cost REAL,
                current_price REAL,
                market_value REAL,
                pnl REAL,
                pnl_pct REAL
            );

            CREATE TABLE IF NOT EXISTS sim_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                direction TEXT,
                quantity INTEGER,
                price REAL,
                amount REAL,
                trade_time TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.commit()
        conn.close()

    # ── 账户操作 ──────────────────────────────────
    def reset(self, initial_cash=100000):
        conn = get_conn()
        conn.execute("UPDATE sim_account SET cash=?, initial_cash=? WHERE id=1",
                     [initial_cash, initial_cash])
        conn.execute("DELETE FROM sim_orders")
        conn.execute("DELETE FROM sim_positions")
        conn.execute("DELETE FROM sim_trades")
        conn.commit()
        conn.close()

    def get_account(self):
        df = query("SELECT * FROM sim_account WHERE id=1")
        if df.empty:
            return {"cash": 100000, "initial_cash": 100000}
        return df.iloc[0].to_dict()

    # ── 订单管理 ──────────────────────────────────
    def submit_order(self, code, direction, quantity, order_type="market",
                     price=None, name=None):
        """提交订单。返回 order id。"""
        if name is None:
            rt = query("SELECT name FROM realtime WHERE code=?", [code])
            name = rt.iloc[0]["name"] if not rt.empty else code

        # 价格为空时取最新价
        if price is None:
            rt = query("SELECT price FROM realtime WHERE code=?", [code])
            price = rt.iloc[0]["price"] if not rt.empty else 0

        # 检查资金/持仓
        if direction == "buy":
            acct = self.get_account()
            cost = price * quantity * 1.0003
            if acct["cash"] < cost:
                return {"error": f"资金不足: 需要 {cost:.2f}, 可用 {acct['cash']:.2f}"}
        else:  # sell
            pos = self.get_positions()
            if pos.empty:
                return {"error": "无持仓"}
            holding = pos[pos["code"] == code]
            if holding.empty or holding.iloc[0]["quantity"] < quantity:
                return {"error": f"持仓不足: {code}"}

        conn = get_conn()
        conn.execute("""
            INSERT INTO sim_orders (code, name, direction, order_type, price, quantity)
            VALUES (?,?,?,?,?,?)
        """, [code, name, direction, order_type, price, quantity])
        order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()

        # 市价单立即成交
        if order_type == "market":
            self._fill_order(order_id, price)
        return {"order_id": order_id, "status": "filled" if order_type == "market" else "pending"}

    def cancel_order(self, order_id):
        conn = get_conn()
        conn.execute("UPDATE sim_orders SET status='cancelled' WHERE id=? AND status='pending'",
                     [order_id])
        conn.commit()
        conn.close()

    def _fill_order(self, order_id, fill_price):
        df = query("SELECT id,code,name,direction,order_type,price,quantity,status FROM sim_orders WHERE id=?", [order_id])
        if df.empty:
            return
        o = df.iloc[0].to_dict()
        if o["status"] != "pending":
            return

        conn = get_conn()

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE sim_orders SET status='filled', fill_price=?, fill_time=?
            WHERE id=?
        """, [fill_price, now, order_id])

        # 更新持仓
        if o["direction"] == "buy":
            # 扣款
            cost = fill_price * o["quantity"] * 1.0003
            conn.execute("UPDATE sim_account SET cash=cash-? WHERE id=1", [cost])
            # 更新持仓
            existing = conn.execute(
                "SELECT quantity, avg_cost FROM sim_positions WHERE code=?", [o["code"]]
            ).fetchone()
            if existing:
                new_qty = existing[0] + o["quantity"]
                new_avg = (existing[0] * existing[1] + o["quantity"] * fill_price) / new_qty
                conn.execute(
                    "UPDATE sim_positions SET quantity=?, avg_cost=? WHERE code=?",
                    [new_qty, new_avg, o["code"]],
                )
            else:
                conn.execute(
                    "INSERT INTO sim_positions (code, name, quantity, avg_cost) VALUES (?,?,?,?)",
                    [o["code"], o["name"], o["quantity"], fill_price],
                )
        else:  # sell
            revenue = fill_price * o["quantity"] * 0.9987  # 佣金+印花税
            conn.execute("UPDATE sim_account SET cash=cash+? WHERE id=1", [revenue])
            existing = conn.execute(
                "SELECT quantity FROM sim_positions WHERE code=?", [o["code"]]
            ).fetchone()
            if existing:
                new_qty = existing[0] - o["quantity"]
                if new_qty <= 0:
                    conn.execute("DELETE FROM sim_positions WHERE code=?", [o["code"]])
                else:
                    conn.execute(
                        "UPDATE sim_positions SET quantity=? WHERE code=?",
                        [new_qty, o["code"]],
                    )

        # 记录成交
        conn.execute("""
            INSERT INTO sim_trades (code, name, direction, quantity, price, amount)
            VALUES (?,?,?,?,?,?)
        """, [o["code"], o["name"], o["direction"], o["quantity"],
              fill_price, fill_price * o["quantity"]])

        conn.commit()
        conn.close()

    # ── 日终处理 — 限价单撮合 ────────────────────
    def process_eod(self, code=None):
        """处理所有 pending 限价单，用最新行情撮合。"""
        orders = query("SELECT * FROM sim_orders WHERE status='pending'")
        if orders.empty:
            return

        for _, o in orders.iterrows():
            if code and o["code"] != code:
                continue
            rt = query("SELECT price, high, low FROM realtime WHERE code=?", [o["code"]])
            if rt.empty:
                continue
            p = rt.iloc[0]
            # 限价买单: 最低价 <= 委托价 即成交
            if o["direction"] == "buy" and o["price"] and p["low"] <= o["price"]:
                self._fill_order(o["id"], o["price"])
            # 限价卖单: 最高价 >= 委托价 即成交
            elif o["direction"] == "sell" and o["price"] and p["high"] >= o["price"]:
                self._fill_order(o["id"], o["price"])

    # ── 查询 ──────────────────────────────────────
    def get_positions(self):
        df = query("SELECT * FROM sim_positions")
        if df.empty:
            return df
        rt = query("SELECT code, price FROM realtime")
        if not rt.empty:
            rt_map = dict(zip(rt["code"], rt["price"]))
            for i, row in df.iterrows():
                cp = rt_map.get(row["code"])
                if cp and row["avg_cost"]:
                    df.at[i, "current_price"] = cp
                    df.at[i, "market_value"] = cp * row["quantity"]
                    df.at[i, "pnl"] = (cp - row["avg_cost"]) * row["quantity"]
                    df.at[i, "pnl_pct"] = (cp / row["avg_cost"] - 1) * 100
        return df

    def get_orders(self, status=None, limit=50):
        sql = "SELECT * FROM sim_orders"
        if status:
            sql += f" WHERE status='{status}'"
        sql += " ORDER BY id DESC"
        if limit:
            sql += f" LIMIT {limit}"
        return query(sql)

    def get_trades(self, limit=50):
        return query(f"SELECT * FROM sim_trades ORDER BY id DESC LIMIT {limit}")

    def get_summary(self):
        acct = self.get_account()
        positions = self.get_positions()
        total_mv = positions["market_value"].sum() if not positions.empty and "market_value" in positions.columns else 0
        total_pnl = positions["pnl"].sum() if not positions.empty and "pnl" in positions.columns else 0
        total_value = acct["cash"] + total_mv

        return {
            "initial_cash": acct["initial_cash"],
            "cash": round(acct["cash"], 2),
            "market_value": round(total_mv, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return": round((total_value / acct["initial_cash"] - 1) * 100, 2),
            "positions": len(positions) if not positions.empty else 0,
        }
