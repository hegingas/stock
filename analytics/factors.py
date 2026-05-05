"""因子计算与 IC 分析。"""
import numpy as np
import pandas as pd
from database import query


def calc_factor(code, factor_name, **params):
    """计算单只股票的因子值，返回 DataFrame(date, factor_value)。"""
    fn = {
        "momentum": _momentum,
        "volatility": _volatility,
        "turnover": _turnover,
        "volume_ratio": _volume_ratio,
    }.get(factor_name)
    if fn is None:
        raise ValueError(f"未知因子: {factor_name}。支持: momentum, volatility, turnover, volume_ratio")
    return fn(code, **params)


def _momentum(code, period=20):
    """N 日动量（收益率）。"""
    df = query(
        "SELECT date, close FROM history WHERE code=? ORDER BY date",
        [code],
    )
    df["factor"] = df["close"].pct_change(period)
    return df[["date", "factor"]].dropna()


def _volatility(code, period=20):
    """N 日年化波动率。"""
    df = query(
        "SELECT date, close FROM history WHERE code=? ORDER BY date",
        [code],
    )
    df["ret"] = df["close"].pct_change()
    df["factor"] = df["ret"].rolling(period).std() * np.sqrt(252)
    return df[["date", "factor"]].dropna()


def _turnover(code, period=20):
    """N 日均换手率。"""
    df = query(
        "SELECT date, turnover FROM history WHERE code=? ORDER BY date",
        [code],
    )
    df["factor"] = df["turnover"].rolling(period).mean()
    return df[["date", "factor"]].dropna()


def _volume_ratio(code, period=5):
    """量比：当日成交量 / N 日均量。"""
    df = query(
        "SELECT date, volume FROM history WHERE code=? ORDER BY date",
        [code],
    )
    df["avg_vol"] = df["volume"].rolling(period).mean().shift(1)
    df["factor"] = df["volume"] / df["avg_vol"]
    return df[["date", "factor"]].dropna()


def factor_ic(code, factor_name, forward_period=5, **params):
    """计算单只股票的 IC 序列（因子值与未来收益的秩相关系数）。
    返回 dict: {ic_series, ic_mean, ic_ir, ic_win_rate}。
    """
    factor_df = calc_factor(code, factor_name, **params)
    price_df = query(
        "SELECT date, close FROM history WHERE code=? ORDER BY date",
        [code],
    )
    price_df["forward_ret"] = price_df["close"].shift(-forward_period) / price_df["close"] - 1

    merged = factor_df.merge(price_df[["date", "forward_ret"]], on="date")
    merged = merged.dropna()

    if len(merged) < 10:
        return {"error": "数据不足"}

    ic = merged["factor"].rolling(20).corr(merged["forward_ret"])
    ic = ic.dropna()

    return {
        "code": code,
        "factor": factor_name,
        "forward_days": forward_period,
        "data_points": len(merged),
        "ic_mean": round(float(ic.mean()), 4),
        "ic_std": round(float(ic.std()), 4),
        "ic_ir": round(float(ic.mean() / ic.std()), 4) if ic.std() > 0 else 0,
        "ic_win_rate": round(float((ic > 0).mean()), 2),
    }
