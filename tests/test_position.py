"""测试 analytics/position.py — 纯函数。"""
import numpy as np
from analytics.position import (
    kelly_fraction, volatility_sizer, fixed_fraction,
    equal_weight, adaptive_sizer,
)


class TestKellyFraction:
    def test_win_rate_50(self):
        f = kelly_fraction(0.5, 2.0)
        assert 0.2 < f < 0.3  # 0.5 - 0.5/2 = 0.25

    def test_high_win_rate(self):
        f = kelly_fraction(0.8, 1.5)
        assert f > 0.4

    def test_below_minimum(self):
        f = kelly_fraction(0.05, 1.0)
        assert f == 0.02  # clamped to min

    def test_bad_params(self):
        assert kelly_fraction(0, 2) == 0.05
        assert kelly_fraction(0.5, -1) == 0.05


class TestVolatilitySizer:
    def test_normal_volatility(self):
        rets = np.random.normal(0.001, 0.02, 50)
        size = volatility_sizer(rets, max_risk=0.02)
        assert 0.05 < size < 0.95

    def test_high_volatility(self):
        rets = np.array([0.05, -0.06, 0.04, -0.05] * 10)
        size = volatility_sizer(rets, max_risk=0.02)
        assert size < 0.5  # high vol → small position


class TestFixedFraction:
    def test_standard(self):
        f = fixed_fraction(100000, risk_per_trade=0.02, stop_loss_pct=0.05)
        assert f == 0.4  # 0.02 / 0.05


class TestEqualWeight:
    def test_5_stocks(self):
        assert equal_weight(5) == 0.2

    def test_zero(self):
        assert equal_weight(0) == 0.0


class TestAdaptiveSizer:
    def test_normal(self):
        rets = np.random.normal(0.001, 0.02, 50)
        size = adaptive_sizer(rets, win_rate=0.6, profit_loss_ratio=2.0, max_risk=0.02)
        assert 0.05 < size < 0.95

    def test_conservative(self):
        rets = np.array([0.08, -0.07, 0.06, -0.09] * 10)
        size = adaptive_sizer(rets, win_rate=0.3, profit_loss_ratio=1.0, max_risk=0.01)
        assert size < 0.3
