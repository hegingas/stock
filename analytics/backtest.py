"""回测引擎 — 基于 Backtrader，从 SQLite history 表取数。"""
import datetime
import numpy as np
import pandas as pd
import backtrader as bt
from database import query
from .metrics import sharpe_ratio, max_drawdown, annual_return, win_rate, profit_loss_ratio


# ── 内置策略 ──────────────────────────────────────────────

class SmaCrossStrategy(bt.Strategy):
    """双均线交叉策略。"""
    params = dict(fast=5, slow=20)

    def __init__(self):
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        if not self.position and self.crossover > 0:
            self.buy()
        elif self.position and self.crossover < 0:
            self.sell()


class RSIStrategy(bt.Strategy):
    """RSI 超买超卖策略。"""
    params = dict(period=14, oversold=30, overbought=70)

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.period)

    def next(self):
        if not self.position and self.rsi < self.p.oversold:
            self.buy()
        elif self.position and self.rsi > self.p.overbought:
            self.sell()


class BuyAndHoldStrategy(bt.Strategy):
    """买入持有基准策略。"""
    def next(self):
        if not self.position:
            self.buy()


class MacdStrategy(bt.Strategy):
    """MACD 金叉死叉策略。"""
    params = dict(fast=12, slow=26, signal=9)

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast,
            period_me2=self.p.slow,
            period_signal=self.p.signal,
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if not self.position and self.crossover > 0:
            self.buy()
        elif self.position and self.crossover < 0:
            self.sell()


class BollingerStrategy(bt.Strategy):
    """布林带突破策略：价格突破上轨做多，跌破下轨平仓。"""
    params = dict(period=20, devfactor=2.0)

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data.close, period=self.p.period, devfactor=self.p.devfactor
        )
        self.cross_up = bt.indicators.CrossOver(self.data.close, self.bb.lines.top)
        self.cross_down = bt.indicators.CrossDown(self.data.close, self.bb.lines.mid)

    def next(self):
        if not self.position and self.cross_up > 0:
            self.buy()
        elif self.position and self.cross_down > 0:
            self.sell()


class MaAlignmentStrategy(bt.Strategy):
    """均线多头排列：MA5>MA10>MA20 同时满足时买入，跌破 MA20 卖出。"""
    params = dict(ma_short=5, ma_mid=10, ma_long=20)

    def __init__(self):
        self.ma_s = bt.indicators.SMA(self.data.close, period=self.p.ma_short)
        self.ma_m = bt.indicators.SMA(self.data.close, period=self.p.ma_mid)
        self.ma_l = bt.indicators.SMA(self.data.close, period=self.p.ma_long)

    def next(self):
        aligned = self.ma_s[0] > self.ma_m[0] > self.ma_l[0]
        if not self.position and aligned:
            self.buy()
        elif self.position and self.data.close[0] < self.ma_l[0]:
            self.sell()


class TurtleStrategy(bt.Strategy):
    """海龟交易：突破 N 日高点买入，跌破 M 日低点卖出（简化版）。"""
    params = dict(entry_period=20, exit_period=10, atr_period=20)

    def __init__(self):
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.entry_period)
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.p.exit_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

    def next(self):
        if not self.position:
            if self.data.close[0] > self.highest[-1]:
                self.buy()
        elif self.data.close[0] < self.lowest[-1]:
            self.sell()


class VolumeBreakoutStrategy(bt.Strategy):
    """量价突破：放量突破 N 日最高价买入，缩量跌破 M 日均线卖出。"""
    params = dict(price_period=20, vol_period=20, vol_factor=1.5, exit_ma=10)

    def __init__(self):
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.price_period)
        self.avg_vol = bt.indicators.SMA(self.data.volume, period=self.p.vol_period)
        self.exit_ma = bt.indicators.SMA(self.data.close, period=self.p.exit_ma)

    def next(self):
        vol_surge = self.data.volume[0] > self.avg_vol[0] * self.p.vol_factor
        break_high = self.data.close[0] > self.highest[-1]
        if not self.position and vol_surge and break_high:
            self.buy()
        elif self.position and self.data.close[0] < self.exit_ma[0]:
            self.sell()


class MeanReversionStrategy(bt.Strategy):
    """布林带均值回归：触及下轨超卖买入，回到中轨卖出。"""
    params = dict(period=20, devfactor=2.0)

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data.close, period=self.p.period, devfactor=self.p.devfactor
        )

    def next(self):
        if not self.position and self.data.close[0] <= self.bb.lines.bot[0]:
            self.buy()
        elif self.position and self.data.close[0] >= self.bb.lines.mid[0]:
            self.sell()


# ── 波段策略 ──────────────────────────────────────────────

class KdjStrategy(bt.Strategy):
    """KDJ 金叉死叉：K上穿D且超卖区买入，K下穿D且超买区卖出。"""
    params = dict(period=9, period_d=3, oversold=20, overbought=80)

    def __init__(self):
        self.stoch = bt.indicators.Stochastic(
            self.data, period=self.p.period, period_dfast=self.p.period_d
        )
        self.cross_up = bt.indicators.CrossUp(self.stoch.lines.percK, self.stoch.lines.percD)
        self.cross_down = bt.indicators.CrossDown(self.stoch.lines.percK, self.stoch.lines.percD)

    def next(self):
        # J = 3K - 2D
        j = 3 * self.stoch.lines.percK[0] - 2 * self.stoch.lines.percD[0]
        if not self.position:
            if self.cross_up > 0 and j < self.p.oversold:
                self.buy()
        elif self.cross_down > 0 and j > self.p.overbought:
            self.sell()


class CciStrategy(bt.Strategy):
    """CCI 反转：CCI低于-100超卖后回升买入，高于+100超买后回落卖出。"""
    params = dict(period=20, oversold=-100, overbought=100)

    def __init__(self):
        self.cci = bt.indicators.CCI(self.data, period=self.p.period)

    def next(self):
        if not self.position:
            if self.cci[-1] < self.p.oversold and self.cci[0] > self.p.oversold:
                self.buy()
        elif self.cci[-1] > self.p.overbought and self.cci[0] < self.p.overbought:
            self.sell()


class WilliamsRStrategy(bt.Strategy):
    """威廉指标：WR低于-80超卖买入，回升到-20上方卖出。"""
    params = dict(period=14, oversold=-80, exit=-20)

    def __init__(self):
        self.wr = bt.indicators.WilliamsR(self.data, period=self.p.period)

    def next(self):
        if not self.position and self.wr[0] < self.p.oversold:
            self.buy()
        elif self.position and self.wr[0] > self.p.exit:
            self.sell()


class DonchianBounceStrategy(bt.Strategy):
    """唐奇安通道反弹：价格触及下轨后回升买入，触及中轨或上轨卖出。"""
    params = dict(period=20)

    def __init__(self):
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.period)
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.p.period)

    def next(self):
        mid = (self.highest[0] + self.lowest[0]) / 2
        # 前一日触及下轨，当日回升
        touched_low = self.data.low[-1] <= self.lowest[-1] * 1.005
        if not self.position and touched_low and self.data.close[0] > self.data.open[0]:
            self.buy()
        elif self.position and self.data.close[0] >= mid:
            self.sell()


class ThreeBarReversalStrategy(bt.Strategy):
    """三K线反转：连续3阴后收阳买入，连续3阳后收阴卖出。"""
    def __init__(self):
        pass

    def next(self):
        if len(self.data) < 4:
            return
        # 三连阴后收阳
        bearish = (self.data.close[-3] < self.data.open[-3] and
                   self.data.close[-2] < self.data.open[-2] and
                   self.data.close[-1] < self.data.open[-1])
        reversal_up = self.data.close[0] > self.data.open[0]
        if not self.position and bearish and reversal_up:
            self.buy()
        # 三连阳后收阴
        bullish = (self.data.close[-3] > self.data.open[-3] and
                   self.data.close[-2] > self.data.open[-2] and
                   self.data.close[-1] > self.data.open[-1])
        reversal_down = self.data.close[0] < self.data.open[0]
        if self.position and bullish and reversal_down:
            self.sell()


STRATEGIES = {
    "sma_cross": SmaCrossStrategy,
    "rsi": RSIStrategy,
    "buy_hold": BuyAndHoldStrategy,
    "macd": MacdStrategy,
    "bollinger": BollingerStrategy,
    "ma_align": MaAlignmentStrategy,
    "turtle": TurtleStrategy,
    "vol_breakout": VolumeBreakoutStrategy,
    "mean_revert": MeanReversionStrategy,
    "kdj": KdjStrategy,
    "cci": CciStrategy,
    "williams_r": WilliamsRStrategy,
    "donchian": DonchianBounceStrategy,
    "three_bar": ThreeBarReversalStrategy,
}


# ── 数据适配器 ────────────────────────────────────────────

def _load_data(code, start, end):
    df = query(
        "SELECT date, open, high, low, close, volume FROM history "
        "WHERE code=? AND date>=? AND date<=? ORDER BY date",
        [code, start, end],
    )
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


# ── 回测运行 ──────────────────────────────────────────────

def run_backtest(code, strategy="sma_cross", start=None, end=None,
                 initial_cash=100000, commission=0.0003, **strat_params):
    if start is None:
        start = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y%m%d")
    if end is None:
        end = datetime.date.today().strftime("%Y%m%d")

    df = _load_data(code, start, end)
    if df.empty:
        raise ValueError(f"{code} 在 {start}~{end} 无数据")

    data = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
    strat_cls = STRATEGIES.get(strategy, SmaCrossStrategy)
    cerebro.addstrategy(strat_cls, **strat_params)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)

    results = cerebro.run()
    strat_instance = results[0]

    # 从 TimeReturn analyzer 获取每日收益率
    time_return = strat_instance.analyzers.timereturn.get_analysis()
    if time_return:
        daily_rets = np.array(list(time_return.values()))
    else:
        daily_rets = np.array([0.0])

    # 从 trade analyzer 提取
    ta = strat_instance.analyzers.trades.get_analysis()
    total_trades = ta.get("total", {}).get("total", 0)
    won = ta.get("won", {}).get("total", 0)

    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash * 100

    # 用日收益率计算指标
    ann_ret = (np.prod(1 + daily_rets) ** (252 / len(daily_rets)) - 1) * 100 if len(daily_rets) > 0 else 0.0
    mdd = max_drawdown(np.cumprod(1 + daily_rets)) * 100
    sharpe = sharpe_ratio(daily_rets)

    return {
        "code": code,
        "strategy": strategy,
        "period": f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}",
        "trading_days": len(df),
        "initial_cash": initial_cash,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "annual_return_pct": round(ann_ret, 2),
        "max_drawdown_pct": round(mdd, 2),
        "sharpe_ratio": round(sharpe, 2) if sharpe else 0.0,
        "total_trades": total_trades,
        "win_rate_pct": round(won / total_trades * 100, 1) if total_trades else 0.0,
    }


# ── 参数网格定义 ──────────────────────────────────────────

PARAM_GRIDS = {
    "sma_cross": {"fast": [3, 5, 10, 15], "slow": [10, 20, 30, 60]},
    "macd": {"fast": [8, 12, 16], "slow": [20, 26, 34], "signal": [6, 9, 12]},
    "rsi": {"period": [7, 14, 21], "oversold": [20, 25, 30], "overbought": [65, 70, 80]},
    "bollinger": {"period": [10, 20, 30], "devfactor": [1.5, 2.0, 2.5]},
    "ma_align": {"ma_short": [3, 5, 8], "ma_mid": [8, 10, 15], "ma_long": [15, 20, 30]},
    "turtle": {"entry_period": [10, 20, 30], "exit_period": [5, 10, 15]},
    "vol_breakout": {"price_period": [10, 20, 30], "vol_factor": [1.2, 1.5, 2.0]},
    "mean_revert": {"period": [10, 20, 30], "devfactor": [1.5, 2.0, 2.5]},
    "kdj": {"period": [5, 9, 14], "period_d": [2, 3, 5], "oversold": [15, 20, 25], "overbought": [75, 80, 85]},
    "cci": {"period": [10, 14, 20, 30], "oversold": [-150, -100, -80], "overbought": [80, 100, 150]},
    "williams_r": {"period": [7, 14, 21], "oversold": [-90, -80, -70], "exit": [-30, -20, -10]},
    "donchian": {"period": [10, 20, 30]},
    "three_bar": {},
    "buy_hold": {},
}


# ── 参数优化 ──────────────────────────────────────────────

def optimize_backtest(code, strategy="sma_cross", start=None, end=None,
                      initial_cash=100000, metric="sharpe_ratio"):
    """网格搜索最优参数。返回 (best_params, best_result, all_results)。"""
    grid = PARAM_GRIDS.get(strategy, {})
    if not grid:
        # 无参数可调，直接跑一次
        r = run_backtest(code, strategy, start, end, initial_cash)
        return {}, r, [r]

    import itertools

    keys = list(grid.keys())
    combinations = list(itertools.product(*grid.values()))
    best_result = None
    best_params = None
    all_results = []

    for combo in combinations:
        params = dict(zip(keys, combo))
        try:
            r = run_backtest(code, strategy, start, end, initial_cash, **params)
            r["_params"] = params
            all_results.append(r)
            val = r.get(metric, 0)
            if best_result is None or val > best_result.get(metric, 0):
                best_result = r
                best_params = params
        except Exception:
            continue

    if best_result is None:
        return {}, {}, []
    best_result["_best_params"] = best_params
    best_result["_total_tested"] = len(all_results)
    return best_params, best_result, all_results


# ── 组合回测 ──────────────────────────────────────────────

def portfolio_backtest(codes, strategy="sma_cross", start=None, end=None,
                       initial_cash=100000, **strat_params):
    """多股等权组合回测，返回组合绩效。"""
    if start is None:
        start = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y%m%d")
    if end is None:
        end = datetime.date.today().strftime("%Y%m%d")

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.0003)

    valid_codes = []
    for code in codes:
        df = _load_data(code, start, end)
        if not df.empty:
            data = bt.feeds.PandasData(dataname=df)
            cerebro.adddata(data, name=code)
            valid_codes.append(code)

    if not valid_codes:
        raise ValueError(f"所有股票在 {start}~{end} 均无数据")

    strat_cls = STRATEGIES.get(strategy, SmaCrossStrategy)
    cerebro.addstrategy(strat_cls, **strat_params)

    # 等权仓位
    weight_per_stock = 95.0 / len(valid_codes) if valid_codes else 95
    cerebro.addsizer(bt.sizers.PercentSizer, percents=weight_per_stock)

    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

    results = cerebro.run()
    strat_instance = results[0]

    time_return = strat_instance.analyzers.timereturn.get_analysis()
    if time_return:
        daily_rets = np.array(list(time_return.values()))
    else:
        daily_rets = np.array([0.0])

    ta = strat_instance.analyzers.trades.get_analysis()
    total_trades = ta.get("total", {}).get("total", 0)
    won = ta.get("won", {}).get("total", 0)

    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash * 100
    ann_ret = (np.prod(1 + daily_rets) ** (252 / len(daily_rets)) - 1) * 100 if len(daily_rets) > 0 else 0.0
    mdd = max_drawdown(np.cumprod(1 + daily_rets)) * 100
    sharpe = sharpe_ratio(daily_rets)

    return {
        "codes": valid_codes,
        "n_stocks": len(valid_codes),
        "strategy": strategy,
        "period": f"{start} ~ {end}",
        "days": len(daily_rets),
        "initial_cash": initial_cash,
        "final_value": round(final_value, 2),
        "total_return_pct": round(total_return, 2),
        "annual_return_pct": round(ann_ret, 2),
        "max_drawdown_pct": round(mdd, 2),
        "sharpe_ratio": round(sharpe, 2) if sharpe else 0.0,
        "total_trades": total_trades,
        "win_rate_pct": round(won / total_trades * 100, 1) if total_trades else 0.0,
    }


# ── 基准对比 ──────────────────────────────────────────────

def benchmark_compare(code, strategy="sma_cross", start=None, end=None,
                      initial_cash=100000, **strat_params):
    """对比策略 vs 买入持有基准。"""
    strat_result = run_backtest(code, strategy, start, end, initial_cash, **strat_params)
    bench_result = run_backtest(code, "buy_hold", start, end, initial_cash)

    return {
        "code": code,
        "strategy": strategy,
        "strategy_return": strat_result["total_return_pct"],
        "buy_hold_return": bench_result["total_return_pct"],
        "excess_return": round(strat_result["total_return_pct"] - bench_result["total_return_pct"], 2),
        "strategy_sharpe": strat_result["sharpe_ratio"],
        "buy_hold_sharpe": bench_result["sharpe_ratio"],
        "strategy_mdd": strat_result["max_drawdown_pct"],
        "buy_hold_mdd": bench_result["max_drawdown_pct"],
        "period": strat_result["period"],
    }
