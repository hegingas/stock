import sqlite3
import pandas as pd
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
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
            volume     REAL,
            amount     REAL,
            turnover   REAL,
            pe         REAL,
            pb         REAL,
            high       REAL,
            low        REAL,
            open       REAL,
            pre_close  REAL,
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
    """)
    conn.commit()
    conn.close()


def save_dataframe(df, table_name, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
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
