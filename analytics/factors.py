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


# ── 截面因子分析 ────────────────────────────────────────

def _load_multi_stock_history(codes, max_bars=500):
    """批量加载多只股票的收盘价——返回 dict {code: Series}。"""
    result = {}
    for code in codes:
        df = query(
            "SELECT date, close FROM history WHERE code=? ORDER BY date LIMIT ?",
            [code, max_bars],
        )
        if df.empty or len(df) < 50:
            continue
        df["date"] = pd.to_datetime(df["date"])
        s = df.set_index("date")["close"]
        result[code] = s
    return result


def cross_section_factor(codes, factor_name, target_date=None, **params):
    """计算多只股票在某日的截面因子值。
    返回 DataFrame(code, factor_value)。
    """
    if target_date is None:
        import datetime
        target_date = datetime.date.today().strftime("%Y%m%d")

    rows = []
    for code in codes:
        val = None
        if factor_name == "momentum":
            df = query(
                "SELECT close FROM history WHERE code=? AND date<=? ORDER BY date DESC LIMIT ?",
                [code, target_date, params.get("period", 20) + 1],
            )
            if len(df) >= params.get("period", 20) + 1:
                val = df["close"].iloc[0] / df["close"].iloc[-1] - 1

        elif factor_name == "volatility":
            period = params.get("period", 20)
            df = query(
                "SELECT close FROM history WHERE code=? AND date<=? ORDER BY date DESC LIMIT ?",
                [code, target_date, period + 1],
            )
            if len(df) >= period + 1:
                rets = df["close"].pct_change().dropna()
                val = rets.std() * np.sqrt(252)

        elif factor_name == "turnover":
            period = params.get("period", 20)
            df = query(
                "SELECT turnover FROM history WHERE code=? AND date<=? ORDER BY date DESC LIMIT ?",
                [code, target_date, period],
            )
            if len(df) >= period:
                val = df["turnover"].mean()

        elif factor_name == "volume_ratio":
            period = params.get("period", 5)
            df = query(
                "SELECT volume FROM history WHERE code=? AND date<=? ORDER BY date DESC LIMIT ?",
                [code, target_date, period + 1],
            )
            if len(df) >= period + 1:
                today = df["volume"].iloc[0]
                avg = df["volume"].iloc[1:].mean()
                val = today / avg if avg > 0 else None

        rows.append({"code": code, "factor": val})

    return pd.DataFrame(rows).dropna(subset=["factor"])


def cross_section_ic(codes, factor_name, forward_days=5, periods=20, **params):
    """滚动计算截面 IC（多只股票每日 factor 与 forward return 的秩相关）。
    返回 DataFrame(date, ic, cumulative_ic)。
    """
    prices = _load_multi_stock_history(codes)
    if len(prices) < 5:
        return pd.DataFrame()

    # 取最早和最晚的公共日期范围
    all_dates = sorted(set().union(*[set(s.index) for s in prices.values()]))
    ic_rows = []

    for i in range(periods, len(all_dates) - forward_days):
        t = all_dates[i]
        t_fwd = all_dates[i + forward_days]

        rows = []
        for code, s in prices.items():
            if t in s.index and t_fwd in s.index:
                # 因子值
                if factor_name == "momentum":
                    idx = s.index.get_loc(t)
                    if idx >= params.get("period", 20):
                        factor_val = s.iloc[idx] / s.iloc[idx - params.get("period", 20)] - 1
                    else:
                        continue
                else:
                    continue  # 简化：截面 IC 目前只支持 momentum

                fwd_ret = s[t_fwd] / s[t] - 1
                rows.append({"code": code, "factor": factor_val, "forward_ret": fwd_ret})

        if len(rows) < 5:
            continue

        df = pd.DataFrame(rows)
        ic = df["factor"].corr(df["forward_ret"], method="spearman")
        ic_rows.append({"date": t, "ic": ic})

    if not ic_rows:
        return pd.DataFrame()

    result = pd.DataFrame(ic_rows)
    result["cumulative_ic"] = result["ic"].cumsum()
    return result


def quantile_returns(codes, factor_name, target_date=None, n_groups=5, forward_days=5, **params):
    """分层收益：按因子值分 N 组，计算每组未来收益。
    返回 dict: {group_returns, group_labels, top_bottom_spread}。
    """
    df = cross_section_factor(codes, factor_name, target_date, **params)
    if df.empty or len(df) < n_groups * 3:
        return {"error": "数据不足"}

    df["group"] = pd.qcut(df["factor"], n_groups, labels=False, duplicates="drop")
    groups = sorted(df["group"].unique())
    if len(groups) < 2:
        return {"error": "无法分层"}

    # 计算每组未来收益
    prices = _load_multi_stock_history(codes)
    results = []
    for g in groups:
        g_codes = df[df["group"] == g]["code"].tolist()
        fwd_rets = []
        for code in g_codes:
            if code in prices:
                s = prices[code]
                t = pd.Timestamp(target_date) if target_date else s.index[-1]
                if t in s.index:
                    idx = s.index.get_loc(t)
                    if idx + forward_days < len(s):
                        ret = s.iloc[idx + forward_days] / s.iloc[idx] - 1
                        fwd_rets.append(ret)
        if fwd_rets:
            results.append({
                "group": int(g + 1),
                "n_stocks": len(fwd_rets),
                "avg_return": round(np.mean(fwd_rets) * 100, 4),
                "median_return": round(np.median(fwd_rets) * 100, 4),
            })

    if len(results) < 2:
        return {"error": "分组收益计算失败"}

    spread = results[-1]["avg_return"] - results[0]["avg_return"]
    return {
        "factor": factor_name,
        "groups": results,
        "top_bottom_spread": round(spread, 4),
        "n_stocks_total": len(df),
    }
