"""股票筛选器 — 技术面 + 基本面 + 多因子打分。"""
import numpy as np
import pandas as pd
from database import query, table_exists
from fetchers.industry import get_industry_list as _get_industries


# ═══════════════════════════════════════════════════════════
# 核心筛选
# ═══════════════════════════════════════════════════════════

def screen(conditions=None):
    conditions = conditions or {}
    df = _all_stocks()
    if df is None or df.empty:
        return pd.DataFrame()

    for key, val in conditions.items():
        if val is None or val is False:
            continue
        fn = _FILTERS.get(key)
        if fn:
            df = fn(df, val)
        if df.empty:
            break

    return df.reset_index(drop=True)


def rank_screen(top=30, weights=None):
    """多因子打分排名。
    默认权重: 低PE 20%, 低PB 20%, 高ROE 25%, 动量 20%, 量比 15%
    """
    weights = weights or {"pe": 0.20, "pb": 0.20, "roe": 0.25, "momentum": 0.20, "vol_ratio": 0.15}
    df = _all_stocks()
    if df is None or df.empty:
        return pd.DataFrame()

    # 只保留有效 PE/PB 的股票
    df = df[(df["pe"] > 0) & (df["pb"] > 0)].copy()
    if df.empty:
        return pd.DataFrame()

    # 计算各因子排名百分位（越高越好）
    scores = pd.DataFrame(index=df.index)
    scores["code"] = df["code"]
    scores["name"] = df["name"]

    if "pe" in weights and weights["pe"] > 0:
        scores["score_pe"] = 1 - df["pe"].rank(pct=True)  # PE 越低越好
    if "pb" in weights and weights["pb"] > 0:
        scores["score_pb"] = 1 - df["pb"].rank(pct=True)  # PB 越低越好
    if "roe" in weights and weights["roe"] > 0:
        df["_roe"] = _estimate_roe(df)
        df["_roe"] = df["_roe"].clip(0, 100)
        scores["score_roe"] = df["_roe"].rank(pct=True)
    if "momentum" in weights and weights["momentum"] > 0:
        scores["score_momentum"] = df["change_pct"].rank(pct=True)
    if "vol_ratio" in weights and weights["vol_ratio"] > 0:
        df["_vol_score"] = df["turnover"].fillna(0).rank(pct=True)
        scores["score_vol"] = df["_vol_score"]

    # 加权综合得分
    df["_rank_score"] = 0.0
    for key, w in weights.items():
        col = f"score_{key}"
        if col in scores.columns:
            df["_rank_score"] += scores[col] * w

    result = df.nlargest(top, "_rank_score")
    keep_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover", "_rank_score"]
    available = [c for c in keep_cols if c in result.columns]
    return result[available].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════
# 预置模板
# ═══════════════════════════════════════════════════════════

def breakout_screen(top=30):
    """放量突破：均线多头 + 量比>1.5 + 近5日新高。"""
    return screen({"ma_align": True, "vol_ratio_min": 1.5, "near_high": 5}) \
        .head(top).reset_index(drop=True)


def oversold_screen(top=30):
    """超跌反弹候选：跌幅>10% + PE>0（非亏损）+ 换手率低位。"""
    return screen({"change_max": -10, "pe_min": 0.01, "turnover_max": 3}) \
        .head(top).reset_index(drop=True)


def growth_screen(top=30):
    """高增长+合理估值：营收增速>20% + 利润增速>20% + PE<50。"""
    return screen({"revenue_growth": 20, "profit_growth": 20, "pe_max": 50}) \
        .head(top).reset_index(drop=True)


def value_screen(pe_max=20, pb_max=2, change_min=-5):
    return screen({"pe_max": pe_max, "pb_max": pb_max, "change_min": change_min})


def momentum_screen(change_min=3, change_max=9.9, vol_ratio_min=1.5):
    return screen({"change_min": change_min, "change_max": change_max, "vol_ratio_min": vol_ratio_min})


def quality_screen(pe_max=30, roe_min=15):
    return screen({"pe_max": pe_max, "roe_min": roe_min})


# ═══════════════════════════════════════════════════════════
# 估值面 Filter（realtime 表）
# ═══════════════════════════════════════════════════════════

_ST_PATTERNS = ["ST", "*ST", "N", "退", "PT"]  # ST/退市/新股首日过滤


def _all_stocks(exclude_st=True):
    if not table_exists("realtime"):
        return pd.DataFrame()
    df = query("SELECT * FROM realtime")
    if exclude_st and not df.empty:
        mask = ~df["name"].str.startswith(tuple(_ST_PATTERNS), na=False)
        mask &= ~df["name"].str.contains("退", na=False)
        df = df[mask]
    return df


def _filter_pe_max(df, val):
    return df[df["pe"].between(0.01, val)]


def _filter_pe_min(df, val):
    return df[df["pe"] >= val]


def _filter_pb_max(df, val):
    return df[df["pb"].between(0.01, val)]


def _filter_change_min(df, val):
    return df[df["change_pct"] >= val]


def _filter_change_max(df, val):
    return df[df["change_pct"] <= val]


def _filter_turnover_min(df, val):
    return df[df["turnover"] >= val]


def _filter_turnover_max(df, val):
    return df[df["turnover"] <= val]


# ═══════════════════════════════════════════════════════════
# 技术面 Filter（history 表 — 批量查询）
# ═══════════════════════════════════════════════════════════

def _filter_ma_align(df, val):
    """筛选 MA5 > MA10 > MA20 多头排列的股票。"""
    codes = df["code"].unique()
    passed = set()
    for code in codes:
        hist = query(
            "SELECT close FROM history WHERE code=? ORDER BY date DESC LIMIT 22",
            [code],
        )
        if len(hist) < 22:
            continue
        c = hist["close"].values
        ma5 = c[:5].mean()
        ma10 = c[:10].mean()
        ma20 = c[:20].mean()
        latest = c[0]
        if ma5 > ma10 > ma20 and latest > ma5:
            passed.add(code)
    return df[df["code"].isin(passed)]


def _filter_near_high(df, val):
    """收盘价接近 N 日内最高点（5% 以内）。"""
    codes = df["code"].unique()
    n = int(val)
    passed = set()
    for code in codes:
        hist = query(
            "SELECT close, high FROM history WHERE code=? ORDER BY date DESC LIMIT ?",
            [code, n],
        )
        if len(hist) < n:
            continue
        latest = hist.iloc[0]["close"]
        period_high = hist["high"].max()
        if period_high > 0 and latest >= period_high * 0.95:
            passed.add(code)
    return df[df["code"].isin(passed)]


def _filter_vol_ratio_min(df, val):
    """当日成交量 > N 倍 20 日均量。"""
    codes = df["code"].unique()
    ratio = float(val)
    passed = set()
    for code in codes:
        hist = query(
            "SELECT volume FROM history WHERE code=? ORDER BY date DESC LIMIT 21",
            [code],
        )
        if len(hist) < 21:
            continue
        v = hist["volume"].values
        today_vol = v[0]
        avg_vol_20 = v[1:].mean()
        if avg_vol_20 > 0 and today_vol > avg_vol_20 * ratio:
            passed.add(code)
    return df[df["code"].isin(passed)]


def _filter_up_days(df, val):
    """最近 N 天中至少 M 天上涨。val 为 "N,M" 格式。"""
    parts = str(val).split(",")
    n = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else n
    codes = df["code"].unique()
    passed = set()
    for code in codes:
        hist = query(
            "SELECT close, open FROM history WHERE code=? ORDER BY date DESC LIMIT ?",
            [code, n + 1],
        )
        if len(hist) < n:
            continue
        up = (hist["close"].values[:n] > hist["open"].values[:n]).sum()
        if up >= m:
            passed.add(code)
    return df[df["code"].isin(passed)]


# ═══════════════════════════════════════════════════════════
# 基本面 Filter（financial 表）
# ═══════════════════════════════════════════════════════════

def _get_latest_financial_metrics(codes):
    """批量获取每只股票最新的财务指标。返回 DataFrame(code, roe, rev_growth, profit_growth)。"""
    if not table_exists("financial"):
        return pd.DataFrame()

    rows = []
    for code in codes:
        # 取最新两期利润表
        inc = query(
            "SELECT report_date, revenue, net_profit FROM financial "
            "WHERE code=? AND report_type='income' ORDER BY report_date DESC LIMIT 2",
            [code],
        )
        # 取最新一期资产负债表
        bal = query(
            "SELECT report_date, shareholders_equity, total_assets, total_liabilities FROM financial "
            "WHERE code=? AND report_type='balance' ORDER BY report_date DESC LIMIT 1",
            [code],
        )

        roe = None
        if not bal.empty:
            br = bal.iloc[0]
            eq = br.get("shareholders_equity")
            if eq is None or eq == 0:
                ta = br.get("total_assets")
                tl = br.get("total_liabilities")
                if ta and tl:
                    eq = ta - tl
            if eq and eq > 0 and not inc.empty:
                np_ = inc.iloc[0]["net_profit"]
                if np_ is not None:
                    roe = np_ / eq * 100

        rev_growth = None
        profit_growth = None
        if len(inc) >= 2:
            r0, r1 = inc.iloc[0]["revenue"], inc.iloc[1]["revenue"]
            p0, p1 = inc.iloc[0]["net_profit"], inc.iloc[1]["net_profit"]
            if r0 and r1 and r1 != 0:
                rev_growth = (r0 - r1) / abs(r1) * 100
            if p0 and p1 and p1 != 0:
                profit_growth = (p0 - p1) / abs(p1) * 100

        rows.append({
            "code": code,
            "_roe": round(roe, 2) if roe else None,
            "_rev_growth": round(rev_growth, 2) if rev_growth is not None else None,
            "_profit_growth": round(profit_growth, 2) if profit_growth is not None else None,
        })

    return pd.DataFrame(rows)


def _filter_roe_min(df, val):
    """真实 ROE >= val（从 financial 表计算）。"""
    codes = df["code"].unique()
    fin = _get_latest_financial_metrics(codes)
    if fin.empty:
        return df.iloc[:0]
    passed = set(fin[fin["_roe"].notna() & (fin["_roe"] >= val)]["code"])
    return df[df["code"].isin(passed)]


def _filter_revenue_growth(df, val):
    codes = df["code"].unique()
    fin = _get_latest_financial_metrics(codes)
    if fin.empty:
        return df.iloc[:0]
    passed = set(fin[fin["_rev_growth"].notna() & (fin["_rev_growth"] >= val)]["code"])
    return df[df["code"].isin(passed)]


def _filter_profit_growth(df, val):
    codes = df["code"].unique()
    fin = _get_latest_financial_metrics(codes)
    if fin.empty:
        return df.iloc[:0]
    passed = set(fin[fin["_profit_growth"].notna() & (fin["_profit_growth"] >= val)]["code"])
    return df[df["code"].isin(passed)]


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _estimate_roe(df):
    """PE/PB 反推 ROE（粗略估计，用于打分时填补空缺）。"""
    mask = df["pe"].between(0.01, 200) & df["pb"].between(0.01, 50)
    roe = pd.Series(np.nan, index=df.index)
    roe[mask] = df.loc[mask, "pb"] / df.loc[mask, "pe"] * 100
    return roe


def _filter_industry(df, val):
    """行业过滤。需要先抓取行业数据: python main.py industry"""
    from fetchers.industry import get_industry
    ind_df = get_industry()
    if ind_df.empty:
        return df
    codes_in_industry = set(ind_df[ind_df["industry"] == val]["code"])
    return df[df["code"].isin(codes_in_industry)]


_FILTERS = {
    "pe_max": _filter_pe_max,
    "pe_min": _filter_pe_min,
    "pb_max": _filter_pb_max,
    "change_min": _filter_change_min,
    "change_max": _filter_change_max,
    "turnover_min": _filter_turnover_min,
    "turnover_max": _filter_turnover_max,
    "ma_align": _filter_ma_align,
    "near_high": _filter_near_high,
    "vol_ratio_min": _filter_vol_ratio_min,
    "up_days": _filter_up_days,
    "roe_min": _filter_roe_min,
    "revenue_growth": _filter_revenue_growth,
    "profit_growth": _filter_profit_growth,
    "industry": _filter_industry,
}
