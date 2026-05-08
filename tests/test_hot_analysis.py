"""测试 hot_analysis 模块：批量深度分析 + 信号判断。"""
import pandas as pd
import pytest
from unittest.mock import patch


class TestAnalyzeHotStocks:
    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_full_success(self, mock_advice, mock_bt):
        mock_advice.return_value = {
            "code": "000001", "name": "平安", "current_price": 10.5,
            "trend": "强势上涨", "confidence": "high", "buy_price": 10.3,
            "take_profit": 12.0, "stop_loss": 9.5, "risk_reward": 2.5,
            "ma20": 10.1, "ma60": 9.8, "reasons": ["强"],
        }
        mock_bt.return_value = {
            "code": "000001", "strategy": "macd",
            "total_return_pct": 15.0, "sharpe_ratio": 1.5,
            "max_drawdown_pct": 8.0, "win_rate_pct": 60.0,
            "total_trades": 5, "period": "2025-01-01 ~ 2026-01-01",
            "trading_days": 250, "initial_cash": 100000,
            "final_value": 115000, "annual_return_pct": 15.0,
        }

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["000001"], strategy="macd")
        assert len(df) == 1
        assert df.iloc[0]["code"] == "000001"
        assert df.iloc[0]["signal"] == "buy"
        assert df.iloc[0]["bt_return"] == 15.0
        assert df.iloc[0]["bt_sharpe"] == 1.5
        assert df.iloc[0]["error"] is None

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_sell_signal(self, mock_advice, mock_bt):
        mock_advice.return_value = {
            "code": "000002", "name": "万科", "current_price": 8.0,
            "trend": "弱势下跌", "confidence": "low", "buy_price": 7.5,
            "take_profit": 9.0, "stop_loss": 7.0, "risk_reward": 1.2,
            "ma20": 8.5, "ma60": 9.1, "reasons": ["弱"],
        }
        mock_bt.return_value = {
            "code": "000002", "strategy": "macd",
            "total_return_pct": -15.0, "sharpe_ratio": -1.0,
            "max_drawdown_pct": 20.0, "win_rate_pct": 30.0,
            "total_trades": 3, "period": "", "trading_days": 250,
            "initial_cash": 100000, "final_value": 85000,
            "annual_return_pct": -15.0,
        }

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["000002"])
        assert df.iloc[0]["signal"] == "sell"

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_missing_data_marked_as_error(self, mock_advice, mock_bt):
        mock_advice.return_value = {"error": "未找到实时行情"}

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["999999"])
        assert len(df) == 1
        assert df.iloc[0]["error"] == "未找到实时行情"

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_one_fails_others_succeed(self, mock_advice, mock_bt):
        def adv_side_effect(code):
            if code == "000001":
                return {
                    "code": "000001", "name": "平安", "current_price": 10.5,
                    "trend": "强势上涨", "confidence": "high", "buy_price": 10.3,
                    "take_profit": 12.0, "stop_loss": 9.5, "risk_reward": 2.5,
                    "ma20": 10.1, "ma60": 9.8, "reasons": ["强"],
                }
            return {"error": "无数据"}

        mock_advice.side_effect = adv_side_effect
        mock_bt.return_value = {
            "code": "000001", "strategy": "macd",
            "total_return_pct": 15.0, "sharpe_ratio": 1.5,
            "max_drawdown_pct": 8.0, "win_rate_pct": 60.0,
            "total_trades": 5, "period": "", "trading_days": 250,
            "initial_cash": 100000, "final_value": 115000,
            "annual_return_pct": 15.0,
        }

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["000001", "999999"])
        assert len(df) == 2
        success_row = df[df["code"] == "000001"].iloc[0]
        fail_row = df[df["code"] == "999999"].iloc[0]
        assert success_row["error"] is None
        assert success_row["signal"] == "buy"
        assert fail_row["error"] == "无数据"

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_sort_order_buy_first(self, mock_advice, mock_bt):
        def adv_side_effect(code):
            advs = {
                "000001": {"code": "000001", "name": "A", "current_price": 10.0,
                           "trend": "强势上涨", "confidence": "high", "buy_price": 9.8,
                           "take_profit": 12.0, "stop_loss": 9.0, "risk_reward": 3.0,
                           "ma20": 9.5, "ma60": 9.0, "reasons": []},
                "000002": {"code": "000002", "name": "B", "current_price": 8.0,
                           "trend": "弱势下跌", "confidence": "low", "buy_price": 0,
                           "take_profit": 0, "stop_loss": 0, "risk_reward": 0,
                           "ma20": 9.0, "ma60": 9.5, "reasons": []},
                "000003": {"code": "000003", "name": "C", "current_price": 15.0,
                           "trend": "震荡整理", "confidence": "medium", "buy_price": 14.5,
                           "take_profit": 16.0, "stop_loss": 13.5, "risk_reward": 1.8,
                           "ma20": 15.1, "ma60": 14.8, "reasons": []},
            }
            return advs[code]

        def bt_side_effect(code, **kwargs):
            bts = {
                "000001": {"code": code, "strategy": "macd", "total_return_pct": 20.0,
                           "sharpe_ratio": 2.0, "max_drawdown_pct": 5.0,
                           "win_rate_pct": 70.0, "total_trades": 10, "period": "",
                           "trading_days": 250, "initial_cash": 100000,
                           "final_value": 120000, "annual_return_pct": 20.0},
                "000002": {"code": code, "strategy": "macd", "total_return_pct": -20.0,
                           "sharpe_ratio": -2.0, "max_drawdown_pct": 25.0,
                           "win_rate_pct": 20.0, "total_trades": 5, "period": "",
                           "trading_days": 250, "initial_cash": 100000,
                           "final_value": 80000, "annual_return_pct": -20.0},
                "000003": {"code": code, "strategy": "macd", "total_return_pct": 5.0,
                           "sharpe_ratio": 0.5, "max_drawdown_pct": 10.0,
                           "win_rate_pct": 50.0, "total_trades": 3, "period": "",
                           "trading_days": 250, "initial_cash": 100000,
                           "final_value": 105000, "annual_return_pct": 5.0},
            }
            return bts[code]

        mock_advice.side_effect = adv_side_effect
        mock_bt.side_effect = bt_side_effect

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["000001", "000002", "000003"])
        assert len(df) == 3
        # buy should be first, sell last
        assert df.iloc[0]["signal"] == "buy"
        assert df.iloc[1]["signal"] == "hold"
        assert df.iloc[2]["signal"] == "sell"

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_empty_input(self, mock_advice, mock_bt):
        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks([])
        assert df.empty

    @patch("analytics.hot_analysis.run_backtest")
    @patch("analytics.hot_analysis.get_advice")
    def test_backtest_exception(self, mock_advice, mock_bt):
        mock_advice.return_value = {
            "code": "000001", "name": "平安", "current_price": 10.5,
            "trend": "强势上涨", "confidence": "high", "buy_price": 10.3,
            "take_profit": 12.0, "stop_loss": 9.5, "risk_reward": 2.5,
            "ma20": 10.1, "ma60": 9.8, "reasons": ["强"],
        }
        mock_bt.side_effect = ValueError("无数据")

        from analytics.hot_analysis import analyze_hot_stocks

        df = analyze_hot_stocks(["000001"])
        assert len(df) == 1
        assert "回测失败" in str(df.iloc[0]["error"])
        assert df.iloc[0]["name"] == "平安"  # advice data preserved
