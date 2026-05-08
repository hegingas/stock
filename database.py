import sqlite3
import pandas as pd
import config as _config


def get_conn():
    conn = sqlite3.connect(_config.DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS realtime (
            code       TEXT PRIMARY KEY,
            name       TEXT,
            price      REAL,
            change_pct REAL,
            change_amt REAL,
            volume     REAL,
            amount     REAL,
            turnover   REAL,
            pe         REAL,
            pb         REAL,
            high       REAL,
            low        REAL,
            open       REAL,
            pre_close  REAL,
            total_mv   REAL,
            circ_mv    REAL,
            volume_ratio REAL,
            change_60d REAL,
            change_ytd REAL,
            update_time TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS history (
            code       TEXT NOT NULL,
            date       TEXT NOT NULL,
            open       REAL,
            close      REAL,
            high       REAL,
            low        REAL,
            volume     REAL,
            amount     REAL,
            turnover   REAL,
            amplitude  REAL,
            change_pct REAL,
            PRIMARY KEY (code, date)
        );

        CREATE TABLE IF NOT EXISTS fund_flow (
            code       TEXT NOT NULL,
            date       TEXT NOT NULL,
            main_net   REAL,
            super_large_net REAL,
            large_net  REAL,
            medium_net REAL,
            small_net  REAL,
            PRIMARY KEY (code, date)
        );

        CREATE TABLE IF NOT EXISTS lhb (
            code       TEXT NOT NULL,
            name       TEXT,
            date       TEXT NOT NULL,
            reason     TEXT,
            buy_amount REAL,
            sell_amount REAL,
            net_amount REAL,
            PRIMARY KEY (code, date)
        );

        CREATE TABLE IF NOT EXISTS north_flow (
            date         TEXT PRIMARY KEY,
            net_buy      REAL,
            buy_amount   REAL,
            sell_amount  REAL
        );

        CREATE TABLE IF NOT EXISTS financial (
            code       TEXT NOT NULL,
            name       TEXT,
            report_date TEXT NOT NULL,
            report_type TEXT,
            -- 利润表
            revenue            REAL,
            net_profit         REAL,
            net_profit_parent  REAL,
            basic_eps          REAL,
            -- 资产负债表
            total_assets       REAL,
            total_liabilities  REAL,
            shareholders_equity REAL,
            -- 现金流量表
            cf_operating       REAL,
            cf_investing       REAL,
            cf_financing       REAL,
            PRIMARY KEY (code, report_date, report_type)
        );

        CREATE TABLE IF NOT EXISTS hot_rank (
            code       TEXT NOT NULL,
            name       TEXT,
            rank       INTEGER,
            price      REAL,
            change_amt REAL,
            change_pct REAL,
            fetch_date TEXT DEFAULT (date('now','localtime')),
            PRIMARY KEY (code, fetch_date)
        );

        CREATE TABLE IF NOT EXISTS hot_up (
            code        TEXT NOT NULL,
            name        TEXT,
            rank        INTEGER,
            rank_change INTEGER,
            price       REAL,
            change_amt  REAL,
            change_pct  REAL,
            fetch_date  TEXT DEFAULT (date('now','localtime')),
            PRIMARY KEY (code, fetch_date)
        );

        CREATE TABLE IF NOT EXISTS stock_news (
            code     TEXT NOT NULL,
            title    TEXT,
            content  TEXT,
            pub_time TEXT,
            source   TEXT,
            url      TEXT,
            PRIMARY KEY (code, url)
        );
    """)
    # 迁移：确保新字段存在
    cur = conn.execute("PRAGMA table_info(realtime)")
    existing = [r[1] for r in cur.fetchall()]
    new_cols = [
        ("change_amt", "REAL"),
        ("total_mv", "REAL"),
        ("circ_mv", "REAL"),
        ("volume_ratio", "REAL"),
        ("change_60d", "REAL"),
        ("change_ytd", "REAL"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE realtime ADD COLUMN {col_name} {col_type}")
    conn.commit()
    conn.close()


# 各表主键列，用于写入前先删冲突行，避免 UNIQUE 约束导致整批回滚
_PK_COLS = {
    "realtime": ["code"],
    "history": ["code", "date"],
    "fund_flow": ["code", "date"],
    "lhb": ["code", "date"],
    "north_flow": ["date"],
    "financial": ["code", "report_date", "report_type"],
    "hot_rank": ["code", "fetch_date"],
    "hot_up": ["code", "fetch_date"],
    "stock_news": ["code", "url"],
}


def save_dataframe(df, table_name, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        keys = _PK_COLS.get(table_name)
        if keys:
            existing_keys = df[keys].drop_duplicates()
            placeholders = ", ".join(["?"] * len(keys))
            # 分批删除，避免超出 SQLite 999 参数上限
            batch_size = 500 // len(keys)
            for i in range(0, len(existing_keys), batch_size):
                batch = existing_keys.iloc[i : i + batch_size]
                values = [row[col] for _, row in batch.iterrows() for col in keys]
                row_phs = ", ".join(["(" + placeholders + ")"] * len(batch))
                conn.execute(
                    f"DELETE FROM {table_name} WHERE ({', '.join(keys)}) IN ({row_phs})",
                    values,
                )
        df.to_sql(table_name, conn, if_exists="append", index=False)
    finally:
        if own_conn:
            conn.commit()
            conn.close()


def query(sql, params=None):
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def clear_code(table_name, code):
    """删除指定表中某只股票的所有记录。"""
    conn = get_conn()
    try:
        conn.execute(f"DELETE FROM {table_name} WHERE code=?", [code])
        conn.commit()
    finally:
        conn.close()


def table_exists(table_name):
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()
