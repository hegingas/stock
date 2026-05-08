"""测试 notify 模块：HTML 构建 + send_email 各种路径。"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


class TestBuildSignalHtml:
    def test_empty_df(self):
        from notify import build_signal_html

        df = pd.DataFrame(columns=[
            "code", "name", "price", "trend", "signal",
            "confidence", "buy_price", "take_profit",
            "stop_loss", "risk_reward", "reason",
        ])
        html = build_signal_html(df)
        assert "<html" in html
        assert "<table" in html
        assert "买入 0" in html
        assert "卖出 0" in html
        assert "观望 0" in html

    def test_mixed_signals(self):
        from notify import build_signal_html

        df = pd.DataFrame([
            {"code": "000001", "name": "平安", "price": 10.5, "trend": "强势上涨",
             "signal": "buy", "confidence": "high", "buy_price": 10.3,
             "take_profit": 12.0, "stop_loss": 9.5, "risk_reward": 2.5,
             "reason": "趋势强"},
            {"code": "000002", "name": "万科", "price": 8.0, "trend": "弱势下跌",
             "signal": "sell", "confidence": "low", "buy_price": 0,
             "take_profit": 0, "stop_loss": 0, "risk_reward": 0,
             "reason": "弱势"},
            {"code": "000003", "name": "招行", "price": 35.0, "trend": "震荡整理",
             "signal": "hold", "confidence": "medium", "buy_price": 34.0,
             "take_profit": 38.0, "stop_loss": 32.0, "risk_reward": 1.5,
             "reason": "震荡"},
        ])
        html = build_signal_html(df)
        assert "#27ae60" in html
        assert "#e74c3c" in html
        assert "#f39c12" in html
        assert "买入 1" in html
        assert "卖出 1" in html
        assert "观望 1" in html


class TestBuildDailyReportHtml:
    def test_with_positions(self):
        from notify import build_daily_report_html

        positions = pd.DataFrame([
            {"code": "000001", "name": "平安", "buy_price": 10.0, "current_price": 10.5,
             "quantity": 1000, "pnl": 500.0, "pnl_pct": 5.0},
        ])
        summary = {
            "total_trades": 10, "win_rate": 60.0,
            "total_pnl": 1500.0, "unrealized_pnl": 500.0,
            "open_positions": 1,
        }
        html = build_daily_report_html(positions, summary)
        assert "持仓日报" in html
        assert "000001" in html
        assert "+500.00" in html
        assert "+5.00%" in html
        assert "#27ae60" in html

    def test_empty_positions(self):
        from notify import build_daily_report_html

        positions = pd.DataFrame()
        summary = {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "unrealized_pnl": 0, "open_positions": 0,
        }
        html = build_daily_report_html(positions, summary)
        assert "当前无持仓" in html

    def test_none_positions(self):
        from notify import build_daily_report_html

        summary = {
            "total_trades": 0, "win_rate": 0, "total_pnl": 0,
            "unrealized_pnl": 0, "open_positions": 0,
        }
        html = build_daily_report_html(None, summary)
        assert "当前无持仓" in html


class TestSendEmail:
    def test_missing_credentials(self, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "")
        monkeypatch.setattr("config.SMTP_PASS", "")
        from notify import send_email

        assert send_email("test", "<p>hi</p>") is False

    def test_missing_recipients(self, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "u@x.com")
        monkeypatch.setattr("config.SMTP_PASS", "pwd")
        monkeypatch.setattr("config.SMTP_TO", "")
        from notify import send_email

        assert send_email("test", "<p>hi</p>") is False

    @patch("smtplib.SMTP")
    def test_tls_success(self, mock_smtp, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "u@x.com")
        monkeypatch.setattr("config.SMTP_PASS", "pwd")
        monkeypatch.setattr("config.SMTP_TO", "to@x.com")
        monkeypatch.setattr("config.SMTP_USE_TLS", True)

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        from notify import send_email

        assert send_email("test", "<p>hi</p>") is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("u@x.com", "pwd")
        mock_server.send_message.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_ssl_mode(self, mock_smtp_ssl, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "u@x.com")
        monkeypatch.setattr("config.SMTP_PASS", "pwd")
        monkeypatch.setattr("config.SMTP_TO", "to@x.com")
        monkeypatch.setattr("config.SMTP_USE_TLS", False)

        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server

        from notify import send_email

        assert send_email("test", "<p>hi</p>") is True
        mock_server.login.assert_called_once_with("u@x.com", "pwd")

    @patch("smtplib.SMTP")
    def test_to_addrs_override(self, mock_smtp, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "u@x.com")
        monkeypatch.setattr("config.SMTP_PASS", "pwd")
        monkeypatch.setattr("config.SMTP_TO", "default@x.com")

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        from notify import send_email

        assert send_email("test", "<p>hi</p>", to_addrs=["override@x.com"]) is True
        call_args = mock_server.send_message.call_args[0][0]
        assert "override@x.com" in call_args["To"]

    @patch("smtplib.SMTP")
    def test_smtp_error(self, mock_smtp, monkeypatch):
        monkeypatch.setattr("config.SMTP_USER", "u@x.com")
        monkeypatch.setattr("config.SMTP_PASS", "pwd")
        monkeypatch.setattr("config.SMTP_TO", "to@x.com")

        mock_smtp.side_effect = Exception("Connection refused")

        from notify import send_email

        assert send_email("test", "<p>hi</p>") is False


class TestStripHtml:
    def test_strips_tags(self):
        from notify import _strip_html

        html = "<html><body><h2>标题</h2><p>内容</p></body></html>"
        text = _strip_html(html)
        assert "标题" in text
        assert "内容" in text
        assert "<" not in text

    def test_truncates(self):
        from notify import _strip_html

        long_text = "x" * 1000
        html = f"<p>{long_text}</p>"
        result = _strip_html(html, max_len=500)
        assert len(result) <= 510  # 500 + " ..."
        assert "..." in result
