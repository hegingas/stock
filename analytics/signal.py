"""交易建议模块 — 基于技术指标给出买入价/止盈价/止损价。"""
import numpy as np
import pandas as pd
from database import query, table_exists


def get_advice(code):
    """返回 dict: code, name, current_price, trend, buy_price, take_profit, stop_loss, confidence, reasons"""
    advice = {
        "code": code,
        "name": "",
        "current_price": None,
        "trend": "unknown",
        "buy_price": None,
        "take_profit": None,
        "stop_loss": None,
        "confidence": "low",
        "reasons": [],
    }

    # 当前价格（从 realtime 表）
    if table_exists("realtime"):
        df_rt = query("SELECT name, price FROM realtime WHERE code=?", [code])
        if not df_rt.empty:
            advice["name"] = str(df_rt.iloc[0]["name"])
            advice["current_price"] = float(df_rt.iloc[0]["price"])
    if advice["current_price"] is None:
        return {"error": f"未找到 {code} 的实时行情，请先 python main.py realtime"}

    # 历史K线数据
    df = query(
        "SELECT date, open, high, low, close, volume FROM history "
        "WHERE code=? ORDER BY date",
        [code],
    )
    if df.empty:
        return {"error": f"未找到 {code} 的历史K线，请先 python main.py history --code {code}"}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    current = advice["current_price"]

    # ── 技术指标 ──────────────────────────────────────────
    ma20 = pd.Series(close).rolling(20).mean().iloc[-1]
    ma60 = pd.Series(close).rolling(60).mean().iloc[-1]
    bb_mid = pd.Series(close).rolling(20).mean().iloc[-1]
    bb_std = pd.Series(close).rolling(20).std().iloc[-1]
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    # ATR(14)
    tr = np.maximum(
        high[-14:] - low[-14:],
        np.maximum(
            abs(high[-14:] - np.roll(close[-14:], 1)),
            abs(low[-14:] - np.roll(close[-14:], 1)),
        ),
    )
    tr[0] = high[-14] - low[-14]
    atr = np.mean(tr)

    # 近期支撑阻力位
    swing_high_20 = np.max(high[-20:])
    swing_low_20 = np.min(low[-20:])
    swing_high_60 = np.max(high[-60:]) if len(high) >= 60 else swing_high_20
    swing_low_60 = np.min(low[-60:]) if len(low) >= 60 else swing_low_20

    # ── 趋势判断 ──────────────────────────────────────────
    if ma20 > ma60 and current > ma20:
        trend = "强势上涨"
        advice["reasons"].append(f"价格({current:.2f})在 MA20({ma20:.2f})上方，均线多头排列")
    elif current > ma20:
        trend = "震荡偏多"
        advice["reasons"].append(f"价格在 MA20({ma20:.2f})上方，但均线未完全多头")
    elif current > ma60:
        trend = "震荡整理"
        advice["reasons"].append(f"价格在 MA20({ma20:.2f})下方、MA60({ma60:.2f})上方，处于震荡区")
    else:
        trend = "弱势下跌"
        advice["reasons"].append(f"价格({current:.2f})在 MA60({ma60:.2f})下方，均线空头排列")
    advice["trend"] = trend

    # ── 建议买入价 ────────────────────────────────────────
    if trend in ("强势上涨", "震荡偏多"):
        # 上涨趋势：激进可在当前价介入，稳健等回调到 MA20
        if current <= ma20 * 1.03:
            buy = round(current, 2)
            advice["reasons"].append(f"当前价接近 MA20({ma20:.2f})，可直接介入")
        else:
            buy = round(ma20, 2)
            advice["reasons"].append(f"建议等回调至 MA20({ma20:.2f})附近买入")
    elif trend == "震荡整理":
        buy = round((bb_lower + ma60) / 2, 2)
        advice["reasons"].append(f"震荡市建议在布林下轨({bb_lower:.2f})与 MA60({ma60:.2f})之间分批建仓")
    else:
        buy = round(min(bb_lower, swing_low_60), 2)
        advice["reasons"].append(f"弱势建议等跌至布林下轨({bb_lower:.2f})或前期低点({swing_low_60:.2f})再考虑")
    advice["buy_price"] = buy

    # ── 止盈价 ────────────────────────────────────────────
    # 基于 ATR + 阻力位
    atr_tp = buy + 2.5 * atr
    if trend in ("强势上涨", "震荡偏多"):
        tp = round(max(atr_tp, bb_upper, swing_high_20), 2)
        advice["reasons"].append(f"止盈参考：布林上轨({bb_upper:.2f})或 20日高点({swing_high_20:.2f})")
    elif trend == "震荡整理":
        tp = round(max(atr_tp, bb_upper), 2)
        advice["reasons"].append(f"止盈参考：布林上轨({bb_upper:.2f})")
    else:
        tp = round(max(atr_tp, ma20), 2)
        advice["reasons"].append(f"止盈参考：MA20({ma20:.2f}) (弱势反弹目标)")
    advice["take_profit"] = tp

    # ── 止损价 ────────────────────────────────────────────
    atr_sl = buy - 1.5 * atr
    if trend in ("强势上涨", "震荡偏多"):
        # 涨势中止损宽一些，避免被震出
        sl = round(min(atr_sl, ma60, swing_low_20), 2)
        advice["reasons"].append(f"止损参考：MA60({ma60:.2f})或 20日低点({swing_low_20:.2f})")
    elif trend == "震荡整理":
        sl = round(max(atr_sl, bb_lower * 0.97), 2)
        advice["reasons"].append(f"止损参考：布林下轨下方({bb_lower*.97:.2f})")
    else:
        # 弱势中用更宽的止损，防止被洗出
        sl = round(min(atr_sl, swing_low_60 * 0.95), 2)
        advice["reasons"].append(f"止损参考：60日低点下方({swing_low_60*.95:.2f})或2倍ATR({atr_sl:.2f})")
    advice["stop_loss"] = sl

    # ── 盈亏比与信心 ──────────────────────────────────────
    reward = abs(tp - buy)
    risk = abs(buy - sl)
    rr_ratio = reward / risk if risk > 0 else 0

    if rr_ratio >= 2.5 and trend in ("强势上涨", "震荡偏多"):
        confidence = "high"
    elif rr_ratio >= 1.5:
        confidence = "medium"
    else:
        confidence = "low"
    advice["confidence"] = confidence
    advice["risk_reward"] = round(rr_ratio, 2)

    if rr_ratio >= 2:
        advice["reasons"].append(f"盈亏比 {rr_ratio:.1f}:1，风险收益比较好")
    else:
        advice["reasons"].append(f"盈亏比仅 {rr_ratio:.1f}:1，风险收益比不够理想")

    # ── 额外指标 ──────────────────────────────────────────
    advice["ma20"] = round(ma20, 2)
    advice["ma60"] = round(ma60, 2)
    advice["bb_upper"] = round(bb_upper, 2)
    advice["bb_lower"] = round(bb_lower, 2)
    advice["atr"] = round(atr, 2)
    advice["swing_high_20"] = round(swing_high_20, 2)
    advice["swing_low_20"] = round(swing_low_20, 2)

    return advice
