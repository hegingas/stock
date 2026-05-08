"""人气榜深度分析 — 对股票列表逐一运行技术分析 + 回测，生成综合报告。"""
import pandas as pd
from analytics.signal import get_advice
from analytics.backtest import run_backtest


def analyze_hot_stocks(codes, strategy="macd"):
    """批量深度分析，返回综合报告 DataFrame。

    每只股票执行 get_advice + run_backtest，失败用 error 列标记。
    信号判断复用 _judge_signal 逻辑，但无信号时也保留数据（标记为 hold/观望）。
    """
    rows = []
    for code in codes:
        try:
            adv = get_advice(code)
            if "error" in adv:
                rows.append({"code": code, "error": adv["error"]})
                continue

            try:
                bt = run_backtest(code, strategy=strategy)
            except Exception as e:
                rows.append({
                    "code": code,
                    "name": adv.get("name", ""),
                    "price": adv["current_price"],
                    "trend": adv["trend"],
                    "error": f"回测失败: {e}",
                })
                continue

            signal = _judge(adv, bt)
            rows.append({
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
                "bt_return": bt["total_return_pct"],
                "bt_sharpe": bt["sharpe_ratio"],
                "bt_drawdown": bt["max_drawdown_pct"],
                "bt_wins": bt["win_rate_pct"],
                "bt_trades": bt["total_trades"],
                "ma20": adv.get("ma20"),
                "ma60": adv.get("ma60"),
                "reason": signal["reason"],
                "error": None,
            })

        except Exception as e:
            rows.append({"code": code, "error": f"分析异常: {e}"})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 排序: 买入优先, 再按信心, 再按盈亏比
    priority = {"buy": 0, "hold": 1, "sell": 2}
    if "signal" in df.columns:
        df["_pri"] = df["signal"].map(priority).fillna(3)
        df = df.sort_values(["_pri", "confidence", "risk_reward"],
                            ascending=[True, False, False])
        df = df.drop(columns=["_pri"])
    return df.reset_index(drop=True)


def _judge(advice, bt_result):
    """综合技术建议 + 回测结果判断信号（同上 signal_engine._judge_signal）。"""
    trend = advice["trend"]
    conf = advice["confidence"]
    rr = advice["risk_reward"]
    bt_ret = bt_result["total_return_pct"]

    if trend in ("强势上涨", "震荡偏多") and conf == "high" and bt_ret > 0:
        return {"type": "buy", "reason": f"趋势{trend}+高信心+策略收益{bt_ret:.1f}%"}
    if trend == "强势上涨" and conf == "medium" and rr >= 2 and bt_ret > 10:
        return {"type": "buy", "reason": f"强势+中等信心+盈亏比{rr}:1+策略收益{bt_ret:.1f}%"}

    if trend == "弱势下跌" and conf == "low":
        return {"type": "sell", "reason": "趋势弱+低信心"}
    if trend == "弱势下跌" and bt_ret < -10:
        return {"type": "sell", "reason": f"弱势+策略亏损{bt_ret:.1f}%"}

    if trend == "震荡整理" and conf in ("high", "medium") and rr >= 1.5:
        return {"type": "hold", "reason": f"震荡整理+可关注,盈亏比{rr}:1"}

    return {"type": "hold", "reason": f"无明确信号,{trend},盈亏比{rr}:1"}
