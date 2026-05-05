import numpy as np


def sharpe_ratio(returns, rf=0.03):
    """年化夏普比率。returns 为日收益率序列。"""
    if len(returns) < 2:
        return 0.0
    excess = np.mean(returns) - rf / 252
    std = np.std(returns, ddof=1)
    return float(excess / std * np.sqrt(252)) if std > 0 else 0.0


def max_drawdown(equity):
    """最大回撤。equity 为净值序列。"""
    peak = np.maximum.accumulate(equity)
    drawdown = (peak - equity) / peak
    return float(np.max(drawdown))


def annual_return(equity, days):
    """年化收益率。"""
    if days <= 0:
        return 0.0
    total = equity[-1] / equity[0]
    return float(total ** (252 / days) - 1)


def win_rate(trades):
    """胜率。trades 为每笔交易的盈亏列表（正为盈）。"""
    if not trades:
        return 0.0
    return sum(1 for t in trades if t > 0) / len(trades)


def profit_loss_ratio(trades):
    """盈亏比（平均盈利 / 平均亏损）。"""
    wins = [t for t in trades if t > 0]
    losses = [abs(t) for t in trades if t < 0]
    if not losses or not wins:
        return 0.0
    return np.mean(wins) / np.mean(losses)


def calmar_ratio(returns, equity):
    """Calmar 比率 = 年化收益 / 最大回撤。"""
    ann = annual_return(equity, len(returns))
    mdd = max_drawdown(equity)
    return float(ann / mdd) if mdd > 0 else 0.0
