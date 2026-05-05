"""测试 analytics/metrics.py — 纯函数，不依赖数据库。"""
import numpy as np
from analytics.metrics import (
    sharpe_ratio, max_drawdown, annual_return, win_rate,
    profit_loss_ratio, calmar_ratio,
)


class TestSharpeRatio:
    def test_zero_returns(self):
        assert sharpe_ratio(np.array([0.0, 0.0, 0.0])) == 0.0

    def test_positive_sharpe(self):
        rets = np.array([0.001, 0.002, 0.001, 0.003, 0.001])
        sr = sharpe_ratio(rets)
        assert sr > 0

    def test_negative_returns(self):
        rets = np.array([-0.01, -0.02, -0.01])
        sr = sharpe_ratio(rets)
        assert sr < 0

    def test_single_value(self):
        assert sharpe_ratio(np.array([0.01])) == 0.0


class TestMaxDrawdown:
    def test_no_drawdown(self):
        eq = np.array([1.0, 1.1, 1.2, 1.3])
        assert max_drawdown(eq) == 0.0

    def test_with_drawdown(self):
        eq = np.array([1.0, 1.2, 0.8, 1.1])
        mdd = max_drawdown(eq)
        assert 0.3 < mdd < 0.4  # (1.2-0.8)/1.2 = 0.333

    def test_deep_drawdown(self):
        eq = np.array([1.0, 0.5, 0.3, 0.6])
        mdd = max_drawdown(eq)
        assert mdd == 0.7  # (1.0-0.3)/1.0


class TestAnnualReturn:
    def test_flat(self):
        eq = np.array([1.0, 1.0])
        assert annual_return(eq, 252) == 0.0

    def test_positive(self):
        eq = np.array([1.0, 1.26])  # 26% over 252 days
        ann = annual_return(eq, 252)
        assert 0.25 < ann < 0.27


class TestWinRate:
    def test_all_wins(self):
        assert win_rate([100, 200, 50]) == 1.0

    def test_mixed(self):
        assert win_rate([100, -50, 200, -100]) == 0.5

    def test_empty(self):
        assert win_rate([]) == 0.0


class TestProfitLossRatio:
    def test_balanced(self):
        assert profit_loss_ratio([200, -100, 300, -150]) == 2.0  # avg(250) / avg(125)

    def test_no_wins(self):
        assert profit_loss_ratio([-100, -200]) == 0.0

    def test_no_losses(self):
        assert profit_loss_ratio([100, 200]) == 0.0


class TestCalmarRatio:
    def test_positive(self):
        rets = np.array([0.005] * 30 + [-0.03] * 5 + [0.008] * 40)
        eq = np.cumprod(1 + rets)
        cr = calmar_ratio(rets, eq)
        assert cr > 0

    def test_zero_drawdown(self):
        rets = np.array([0.001] * 50)
        eq = np.cumprod(1 + rets)
        cr = calmar_ratio(rets, eq)
        assert cr == 0.0
