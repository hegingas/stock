"""测试 analytics/screener.py — 需要 sample_realtime + sample_history。"""
import pytest
from analytics.screener import (
    screen, rank_screen, _all_stocks,
    value_screen, momentum_screen, quality_screen,
    breakout_screen, oversold_screen, growth_screen,
)


class TestAllStocks:
    def test_excludes_st(self, test_db, sample_realtime):
        df = _all_stocks()
        names = df["name"].tolist()
        assert "平安银行" in names
        assert "万向钱潮" in names
        assert "ST金科" not in names
        assert "*ST蓝光" not in names

    def test_excludes_exclude_st_false(self, test_db, sample_realtime):
        df = _all_stocks(exclude_st=False)
        names = df["name"].tolist()
        assert "ST金科" in names


class TestScreen:
    def test_pe_max(self, test_db, sample_realtime):
        df = screen({"pe_max": 20})
        codes = df["code"].tolist()
        assert "000001" in codes   # PE=6.5
        assert "600519" in codes   # PE=15.9
        assert "000559" not in codes  # PE=25

    def test_pb_max(self, test_db, sample_realtime):
        df = screen({"pb_max": 1.0})
        assert len(df) == 1  # only 000001 (pb=0.8)

    def test_change_min(self, test_db, sample_realtime):
        df = screen({"change_min": 0})
        assert len(df) == 1  # only 000001 (change=1.5)

    def test_empty_conditions(self, test_db, sample_realtime):
        df = screen()
        assert len(df) == 3  # 5 stocks - 2 ST

    def test_nonexistent_table(self, test_db):
        """没有 realtime 表时应返回空 DataFrame。"""
        import sqlite3
        import config
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("DROP TABLE IF EXISTS realtime")
        conn.commit()
        conn.close()
        df = screen()
        assert df.empty


class TestRankScreen:
    def test_ranks(self, test_db, sample_realtime):
        df = rank_screen(top=5)
        assert len(df) <= 5
        assert "_rank_score" in df.columns

    def test_no_st_stocks(self, test_db, sample_realtime):
        df = rank_screen(top=10)
        names = df["name"].tolist()
        assert "ST金科" not in names


class TestTemplates:
    def test_value(self, test_db, sample_realtime, sample_history):
        df = value_screen()
        assert "000001" in df["code"].tolist()

    def test_quality(self, test_db, sample_realtime, sample_history):
        df = quality_screen()
        assert df is not None

    def test_breakout(self, test_db, sample_realtime, sample_history):
        df = breakout_screen(top=5)
        assert df is not None

    def test_oversold(self, test_db, sample_realtime):
        df = oversold_screen(top=5)
        assert df is not None
