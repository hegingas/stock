"""Pytest fixtures — 测试数据库 + 样本数据。"""
import os
import sys
import pytest
import sqlite3
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from database import init_db, get_conn, save_dataframe, query


@pytest.fixture(scope="function")
def test_db(tmp_path):
    """创建临时测试数据库。"""
    db_path = tmp_path / "test_stock.db"
    config.DB_PATH = str(db_path)
    config.DATA_DIR = str(tmp_path)
    config.OUTPUT_DIR = str(tmp_path / "output")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    init_db()
    yield db_path

    # cleanup
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_history(test_db):
    """插入样本日线数据。"""
    dates = pd.date_range("2024-01-01", "2024-06-30", freq="B")
    np.random.seed(42)
    price = 10.0
    rows = []
    for d in dates:
        chg = np.random.normal(0.0005, 0.02)
        close = price * (1 + chg)
        high = close * (1 + abs(np.random.normal(0, 0.01)))
        low = close * (1 - abs(np.random.normal(0, 0.01)))
        open_p = low + np.random.random() * (high - low)
        vol = np.random.randint(50000, 500000)
        rows.append({
            "code": "000559", "date": d.strftime("%Y%m%d"),
            "open": open_p, "high": high, "low": low, "close": close,
            "volume": vol, "amount": vol * close, "turnover": np.random.uniform(0.5, 3),
            "amplitude": (high - low) / low * 100,
            "change_pct": (close - price) / price * 100,
        })
        price = close

    df = pd.DataFrame(rows)
    save_dataframe(df, "history")
    return df


@pytest.fixture
def sample_realtime(test_db):
    """插入样本实时行情。"""
    df = pd.DataFrame([
        {"code": "000001", "name": "平安银行", "price": 10.50, "change_pct": 1.5,
         "volume": 500000, "amount": 5.25e6, "turnover": 1.2, "pe": 6.5, "pb": 0.8,
         "high": 10.80, "low": 10.20, "open": 10.30, "pre_close": 10.34},
        {"code": "000559", "name": "万向钱潮", "price": 16.09, "change_pct": -2.5,
         "volume": 600000, "amount": 9.65e6, "turnover": 3.5, "pe": 25.0, "pb": 2.1,
         "high": 16.80, "low": 15.90, "open": 16.50, "pre_close": 16.50},
        {"code": "600519", "name": "贵州茅台", "price": 1384.79, "change_pct": -1.17,
         "volume": 35000, "amount": 4.85e7, "turnover": 0.42, "pe": 15.9, "pb": 6.4,
         "high": 1400.00, "low": 1380.00, "open": 1398.00, "pre_close": 1401.17},
        {"code": "000002", "name": "ST金科", "price": 1.50, "change_pct": 4.9,
         "volume": 300000, "amount": 4.5e5, "turnover": 2.0, "pe": -5.0, "pb": 0.3,
         "high": 1.55, "low": 1.42, "open": 1.43, "pre_close": 1.43},
        {"code": "300750", "name": "*ST蓝光", "price": 0.50, "change_pct": -5.0,
         "volume": 10000, "amount": 5000, "turnover": 0.1, "pe": None, "pb": 0.1,
         "high": 0.55, "low": 0.48, "open": 0.52, "pre_close": 0.53},
    ])
    save_dataframe(df, "realtime")
    return df


@pytest.fixture
def sample_financial(test_db):
    """插入样本财报。"""
    df = pd.DataFrame([
        {"code": "000559", "name": "万向钱潮", "report_date": "20260331", "report_type": "income",
         "revenue": 2.8e9, "net_profit": 2.48e8, "net_profit_parent": 2.48e8, "basic_eps": 0.074,
         "total_assets": None, "total_liabilities": None, "shareholders_equity": None,
         "cf_operating": None, "cf_investing": None, "cf_financing": None},
        {"code": "000559", "name": "万向钱潮", "report_date": "20251231", "report_type": "income",
         "revenue": 1.34e10, "net_profit": 1.05e9, "net_profit_parent": 1.05e9, "basic_eps": 0.31,
         "total_assets": None, "total_liabilities": None, "shareholders_equity": None,
         "cf_operating": None, "cf_investing": None, "cf_financing": None},
        {"code": "000559", "name": "万向钱潮", "report_date": "20260331", "report_type": "balance",
         "revenue": None, "net_profit": None, "net_profit_parent": None, "basic_eps": None,
         "total_assets": 2.53e10, "total_liabilities": 1.64e10, "shareholders_equity": None,
         "cf_operating": None, "cf_investing": None, "cf_financing": None},
    ])
    save_dataframe(df, "financial")
    return df


@pytest.fixture
def sample_fund_flow(test_db):
    """插入样本资金流向。"""
    dates = pd.date_range("2025-01-01", "2025-01-20", freq="B")
    rows = []
    for d in dates:
        rows.append({
            "code": "000559", "date": d.strftime("%Y%m%d"),
            "main_net": np.random.randint(-5e7, 5e7),
            "super_large_net": np.random.randint(-3e7, 3e7),
            "large_net": np.random.randint(-2e7, 2e7),
            "medium_net": np.random.randint(-1e7, 1e7),
            "small_net": np.random.randint(-1e7, 1e7),
        })
    df = pd.DataFrame(rows)
    save_dataframe(df, "fund_flow")
    return df
