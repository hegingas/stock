"""测试 analytics/signal.py — 需要 sample_realtime + sample_history。"""
from analytics.signal import get_advice


class TestGetAdvice:
    def test_basic(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        assert "error" not in result
        assert "current_price" in result
        assert result["current_price"] == 16.09
        assert "trend" in result
        assert result["trend"] in ("强势上涨", "震荡偏多", "震荡整理", "弱势下跌")
        assert result["buy_price"] is not None
        assert result["take_profit"] is not None
        assert result["stop_loss"] is not None
        assert result["risk_reward"] > 0

    def test_buy_lt_take_profit(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        assert result["buy_price"] < result["take_profit"]

    def test_stop_loss_lt_buy(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        assert result["stop_loss"] < result["buy_price"]

    def test_reasons_not_empty(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        assert len(result["reasons"]) >= 2

    def test_indicators_present(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        for key in ("ma20", "ma60", "bb_upper", "bb_lower", "atr"):
            assert key in result, f"Missing {key}"

    def test_no_realtime(self, test_db, sample_history):
        result = get_advice("999999")
        assert "error" in result

    def test_confidence_level(self, test_db, sample_realtime, sample_history):
        result = get_advice("000559")
        assert result["confidence"] in ("high", "medium", "low")
