"""交易信号引擎 — 批量扫描关注列表，生成买卖信号。"""
import pandas as pd
from database import query
from analytics import run_backtest, get_advice


def scan_signals(codes, strategy="macd", top=10):
    """扫描关注列表，返回信号 DataFrame。
    每只股票跑交易建议 + 策略回测，综合判断产生信号。
    """
    signals = []
    for code in codes:
        try:
            adv = get_advice(code)
            if "error" in adv:
                continue

            bt_result = run_backtest(code, strategy=strategy)
            if "error" in bt_result:
                continue

            # 信号逻辑
            signal = _judge_signal(adv, bt_result)
            if signal:
                signals.append({
                    "code": code,
                    "name": adv.get("name", ""),
                    "price": adv["current_price"],
                    "trend": adv["trend"],
                    "signal": signal["type"],
                    "confidence": adv["confidence"],
                    "buy_price": adv["buy_price"],
                    "take_profit": adv["take_profit"],
                    "stop_loss": adv["stop_loss"],
                    "risk_reward": adv["risk_reward"],
                    "strategy_return": bt_result["total_return_pct"],
                    "strategy_sharpe": bt_result["sharpe_ratio"],
                    "reason": signal["reason"],
                })

        except Exception:
            continue

    if not signals:
        return pd.DataFrame()

    df = pd.DataFrame(signals)
    # 排序: 买入优先, 按信心+盈亏比
    priority = {"buy": 0, "hold": 1, "sell": 2}
    df["_pri"] = df["signal"].map(priority)
    df = df.sort_values(["_pri", "confidence", "risk_reward"],
                        ascending=[True, False, False])
    df = df.drop(columns=["_pri"]).head(top)
    return df.reset_index(drop=True)


def _judge_signal(advice, bt_result):
    """综合技术建议 + 回测结果判断信号。"""
    trend = advice["trend"]
    conf = advice["confidence"]
    rr = advice["risk_reward"]
    bt_ret = bt_result["total_return_pct"]

    # 强势 + 高信心 + 策略历史正收益 → 买入
    if trend in ("强势上涨", "震荡偏多") and conf == "high" and bt_ret > 0:
        return {"type": "buy", "reason": f"趋势{trend} + 高信心 + 策略历史收益{bt_ret:.1f}%"}
    if trend == "强势上涨" and conf == "medium" and rr >= 2 and bt_ret > 10:
        return {"type": "buy", "reason": f"强势+中等信心+盈亏比{rr}:1+策略收益{bt_ret:.1f}%"}

    # 弱势 + 低信心 → 卖出
    if trend == "弱势下跌" and conf == "low":
        return {"type": "sell", "reason": f"趋势弱+低信心"}
    if trend == "弱势下跌" and bt_ret < -10:
        return {"type": "sell", "reason": f"弱势+策略历史亏损{bt_ret:.1f}%"}

    # 高信心但趋势震荡 → 观望
    if trend == "震荡整理" and conf in ("high", "medium") and rr >= 1.5:
        return {"type": "hold", "reason": f"震荡整理+可关注,盈亏比{rr}:1"}

    return None  # 不产生信号
