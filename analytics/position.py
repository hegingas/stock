"""仓位管理 — Kelly, 波动率调整, 固定比例。"""
import numpy as np


def kelly_fraction(win_rate, profit_loss_ratio):
    """凯利公式：最优仓位比例。f = p - (1-p)/r"""
    if win_rate <= 0 or profit_loss_ratio <= 0:
        return 0.05
    f = win_rate - (1 - win_rate) / profit_loss_ratio
    return round(max(0.02, min(f, 0.5)), 2)


def volatility_sizer(returns, max_risk=0.02):
    """波动率调整仓位：目标单日最大亏损比例。size = max_risk / volatility"""
    vol = np.std(returns[-20:]) if len(returns) >= 20 else np.std(returns)
    if vol <= 0:
        return 0.5
    size = max_risk / vol
    return round(max(0.05, min(size, 0.95)), 2)


def fixed_fraction(capital, risk_per_trade=0.02, stop_loss_pct=0.05):
    """固定风险比例：每笔最多亏 X% 本金。"""
    if stop_loss_pct <= 0:
        return 0.5
    size = risk_per_trade / stop_loss_pct
    return round(max(0.02, min(size, 0.95)), 2)


def equal_weight(n_stocks):
    """等权分配。"""
    if n_stocks <= 0:
        return 0.0
    return round(1.0 / n_stocks, 4)


def adaptive_sizer(returns, win_rate=0.5, profit_loss_ratio=1.5, max_risk=0.02):
    """自适应仓位：结合 Kelly + 波动率，取两者保守值。"""
    kelly = kelly_fraction(win_rate, profit_loss_ratio)
    vol_size = volatility_sizer(returns, max_risk)
    return round(min(kelly, vol_size), 2)
