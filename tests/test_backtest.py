"""测试 analytics/backtest.py — 需要 sample_history fixture。"""
import pytest
from analytics.backtest import (
    run_backtest, benchmark_compare, portfolio_backtest,
    optimize_backtest, STRATEGIES, PARAM_GRIDS,
)


class TestRunBacktest:
    def test_basic_run(self, test_db, sample_history):
        result = run_backtest("000559", strategy="buy_hold",
                              start="20240101", end="20240630")
        assert result["code"] == "000559"
        assert result["strategy"] == "buy_hold"
        assert result["trading_days"] > 0
        assert "total_return_pct" in result
        assert "sharpe_ratio" in result

    def test_sma_cross(self, test_db, sample_history):
        result = run_backtest("000559", strategy="sma_cross",
                              start="20240101", end="20240630")
        assert result["strategy"] == "sma_cross"

    def test_macd(self, test_db, sample_history):
        result = run_backtest("000559", strategy="macd",
                              start="20240101", end="20240630")
        assert "total_return_pct" in result

    def test_no_data_raises(self, test_db):
        with pytest.raises(ValueError):
            run_backtest("999999", strategy="buy_hold",
                         start="20240101", end="20240630")

    def test_all_strategies_run(self, test_db, sample_history):
        failed = []
        for name in STRATEGIES:
            try:
                r = run_backtest("000559", strategy=name,
                                 start="20240101", end="20240630")
                assert "total_return_pct" in r
            except Exception as e:
                failed.append(f"{name}: {e}")
        assert not failed, f"Failed strategies: {failed}"


class TestBenchmarkCompare:
    def test_compare(self, test_db, sample_history):
        bm = benchmark_compare("000559", strategy="sma_cross",
                               start="20240101", end="20240630")
        assert "strategy_return" in bm
        assert "buy_hold_return" in bm
        assert "excess_return" in bm


class TestPortfolioBacktest:
    def test_single_stock(self, test_db, sample_history):
        pf = portfolio_backtest(["000559"], strategy="buy_hold",
                                start="20240101", end="20240630")
        assert pf["n_stocks"] == 1

    def test_nonexistent_filtered(self, test_db, sample_history):
        pf = portfolio_backtest(["000559", "999999"], strategy="buy_hold",
                                start="20240101", end="20240630")
        assert pf["n_stocks"] == 1  # 999999 excluded


class TestOptimizeBacktest:
    def test_sma_optimize(self, test_db, sample_history):
        best_params, best_result, all_results = optimize_backtest(
            "000559", strategy="sma_cross", start="20240101", end="20240630",
            metric="total_return_pct",
        )
        assert len(best_params) == 2  # fast, slow
        assert "fast" in best_params
        assert best_result["_total_tested"] > 0

    def test_no_param_strategy(self, test_db, sample_history):
        best_params, best_result, all_results = optimize_backtest(
            "000559", strategy="buy_hold", start="20240101", end="20240630",
        )
        assert best_params == {}


class TestParamGrids:
    def test_valid_grids(self):
        for name, grid in PARAM_GRIDS.items():
            for k, v in grid.items():
                assert len(v) > 0, f"{name}.{k} empty"
                assert all(isinstance(x, (int, float)) for x in v)
