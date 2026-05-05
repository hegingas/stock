"""测试 database.py — 需要 test_db fixture。"""
import pandas as pd
from database import (
    init_db, get_conn, save_dataframe, query, table_exists, clear_code,
)


class TestInitDB:
    def test_all_tables_created(self, test_db):
        tables = ["realtime", "history", "financial", "fund_flow", "lhb", "north_flow"]
        for t in tables:
            assert table_exists(t), f"Table {t} should exist"


class TestSaveAndQuery:
    def test_save_and_query_realtime(self, test_db, sample_realtime):
        df = query("SELECT COUNT(*) as cnt FROM realtime")
        assert df.iloc[0, 0] == 5

    def test_query_with_params(self, test_db, sample_realtime):
        df = query("SELECT * FROM realtime WHERE code=?", ["000559"])
        assert len(df) == 1
        assert df.iloc[0]["name"] == "万向钱潮"

    def test_query_history(self, test_db, sample_history):
        df = query("SELECT COUNT(*) as cnt FROM history")
        assert df.iloc[0, 0] > 0


class TestClearCode:
    def test_clear_history(self, test_db, sample_history):
        df1 = query("SELECT COUNT(*) as cnt FROM history WHERE code='000559'")
        assert df1.iloc[0, 0] > 0

        clear_code("history", "000559")
        df2 = query("SELECT COUNT(*) as cnt FROM history WHERE code='000559'")
        assert df2.iloc[0, 0] == 0

    def test_clear_nonexistent(self, test_db):
        import sqlite3, config
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("INSERT INTO history (code, date) VALUES ('000001', '2024-01-01')")
        conn.commit()
        conn.close()
        clear_code("history", "999999")
        df = query("SELECT COUNT(*) as cnt FROM history")
        assert df.iloc[0, 0] == 1  # 原记录还在


class TestTableExists:
    def test_existing(self, test_db):
        assert table_exists("realtime")

    def test_nonexistent(self, test_db):
        assert not table_exists("nonexistent_table")
