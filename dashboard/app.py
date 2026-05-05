"""Streamlit 可视化看板 — 行情/个股/回测/因子/筛选。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from database import query, table_exists
from analytics import run_backtest, calc_factor, factor_ic, screen, get_advice
from analytics.metrics import sharpe_ratio, max_drawdown, annual_return

st.set_page_config(page_title="Stock 量化看板", layout="wide")
st.title("A股量化看板")

# ── 侧边栏：股票选择 ────────────────────────────────────────
st.sidebar.header("设置")
default_codes = []
if table_exists("realtime"):
    df_codes = query("SELECT code, name FROM realtime LIMIT 5000")
    if not df_codes.empty:
        default_codes = (df_codes["code"] + " " + df_codes["name"]).tolist()

selected = st.sidebar.selectbox("选择股票", default_codes, index=0) if default_codes else None
code = selected.split()[0] if selected else "000559"

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["行情总览", "个股详情", "回测", "因子分析", "股票筛选", "交易建议"]
)

# ── Tab 1: 行情总览 ─────────────────────────────────────────
with tab1:
    st.subheader("全市场行情概览")
    if table_exists("realtime"):
        df = query("""
            SELECT code, name, price, change_pct, volume, amount, turnover, pe, pb
            FROM realtime
        """)
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)
            up_count = (df["change_pct"] > 0).sum()
            down_count = (df["change_pct"] < 0).sum()
            col1.metric("股票总数", len(df))
            col2.metric("上涨", up_count)
            col3.metric("下跌", down_count)
            col4.metric("平盘", len(df) - up_count - down_count)

            # 涨跌幅分布
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=df["change_pct"].clip(-10, 10),
                nbinsx=50,
                name="涨跌幅分布",
            ))
            fig.update_layout(height=300, xaxis_title="涨跌幅(%)", yaxis_title="数量")
            st.plotly_chart(fig, use_container_width=True)

            # 成交额 Top 20
            st.subheader("成交额 Top 20")
            top_amount = df.nlargest(20, "amount")[
                ["code", "name", "price", "change_pct", "amount"]
            ]
            top_amount["amount"] = (top_amount["amount"] / 1e8).round(1)
            top_amount.columns = ["代码", "名称", "最新价", "涨跌幅%", "成交额(亿)"]
            st.dataframe(top_amount, use_container_width=True, hide_index=True)

            # 涨幅榜 / 跌幅榜
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("涨幅榜 Top 10")
                up = df.nlargest(10, "change_pct")[
                    ["code", "name", "price", "change_pct"]
                ]
                st.dataframe(up, use_container_width=True, hide_index=True)
            with col_b:
                st.subheader("跌幅榜 Top 10")
                down = df.nsmallest(10, "change_pct")[
                    ["code", "name", "price", "change_pct"]
                ]
                st.dataframe(down, use_container_width=True, hide_index=True)
        else:
            st.warning("realtime 表为空，请先抓取数据: python main.py realtime")
    else:
        st.warning("realtime 表不存在，请先抓取数据: python main.py realtime")

# ── Tab 2: 个股详情 ─────────────────────────────────────────
with tab2:
    st.subheader(f"{code} 个股详情")

    # K 线图
    df_hist = query(
        "SELECT date, open, high, low, close, volume FROM history "
        "WHERE code=? ORDER BY date DESC LIMIT 120",
        [code],
    )
    if not df_hist.empty:
        df_hist = df_hist.iloc[::-1]
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
        )
        fig.add_trace(
            go.Candlestick(
                x=df_hist["date"], open=df_hist["open"],
                high=df_hist["high"], low=df_hist["low"],
                close=df_hist["close"], name="K线",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(x=df_hist["date"], y=df_hist["volume"], name="成交量"),
            row=2, col=1,
        )
        fig.update_layout(height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"{code} 无历史K线数据")

    # 资金流向图
    df_flow = query(
        "SELECT date, main_net, super_large_net, large_net, medium_net, small_net "
        "FROM fund_flow WHERE code=? ORDER BY date DESC LIMIT 60",
        [code],
    )
    if not df_flow.empty:
        df_flow = df_flow.iloc[::-1]
        st.subheader("资金流向")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_flow["date"], y=df_flow["main_net"] / 1e4, name="主力净额(万)",
            marker_color=df_flow["main_net"].apply(
                lambda x: "red" if x > 0 else "green"
            ),
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    # 最新财务
    df_fin = query(
        "SELECT report_date, report_type, revenue, net_profit, basic_eps "
        "FROM financial WHERE code=? ORDER BY report_date DESC LIMIT 8",
        [code],
    )
    if not df_fin.empty:
        st.subheader("最新财务")
        df_fin["revenue"] = (df_fin["revenue"] / 1e8).round(2)
        df_fin["net_profit"] = (df_fin["net_profit"] / 1e8).round(2)
        name_map = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
        df_fin["report_type"] = df_fin["report_type"].map(name_map)
        st.dataframe(df_fin, use_container_width=True, hide_index=True)

# ── Tab 3: 回测 ─────────────────────────────────────────────
with tab3:
    st.subheader("策略回测")

    col1, col2, col3 = st.columns(3)
    with col1:
        strat = st.selectbox("策略", [
    "sma_cross", "rsi", "buy_hold", "macd", "bollinger",
    "ma_align", "turtle", "vol_breakout", "mean_revert",
    "kdj", "cci", "williams_r", "donchian", "three_bar",
], format_func=lambda x: {
    "sma_cross": "双均线交叉", "rsi": "RSI 超买超卖",
    "buy_hold": "买入持有(基准)", "macd": "MACD 金叉死叉",
    "bollinger": "布林带突破", "ma_align": "均线多头排列",
    "turtle": "海龟交易", "vol_breakout": "量价突破",
    "mean_revert": "均值回归", "kdj": "KDJ 金叉死叉",
    "cci": "CCI 反转", "williams_r": "威廉指标",
    "donchian": "唐奇安通道反弹", "three_bar": "三K线反转",
}.get(x, x))
    with col2:
        start_date = st.date_input("起始日期", value=pd.to_datetime("2024-01-01"))
    with col3:
        end_date = st.date_input("结束日期", value=pd.to_datetime("today"))
    cash = st.number_input("初始资金", value=100000, step=10000)

    if st.button("运行回测", type="primary"):
        with st.spinner("回测运行中..."):
            try:
                result = run_backtest(
                    code, strategy=strat,
                    start=start_date.strftime("%Y%m%d"),
                    end=end_date.strftime("%Y%m%d"),
                    initial_cash=int(cash),
                )
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("总收益率", f"{result['total_return_pct']}%")
                c2.metric("年化收益", f"{result['annual_return_pct']}%")
                c3.metric("最大回撤", f"{result['max_drawdown_pct']}%")
                c4.metric("夏普比率", f"{result['sharpe_ratio']}")

                c5, c6 = st.columns(2)
                c5.metric("交易次数", result["total_trades"])
                c6.metric("胜率", f"{result['win_rate_pct']}%")
            except ValueError as e:
                st.error(f"回测失败: {e}")

# ── Tab 4: 因子分析 ─────────────────────────────────────────
with tab4:
    st.subheader("因子分析")

    col1, col2 = st.columns(2)
    with col1:
        factor_name = st.selectbox(
            "因子", ["momentum", "volatility", "turnover", "volume_ratio"],
            format_func=lambda x: {
                "momentum": "动量", "volatility": "波动率",
                "turnover": "换手率", "volume_ratio": "量比",
            }.get(x, x),
        )
    with col2:
        period = st.slider("计算周期(天)", 5, 60, 20)

    if st.button("计算因子 & IC", type="primary"):
        with st.spinner("计算中..."):
            df = calc_factor(code, factor_name, period=period)
            if df is not None and not df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df["factor"], mode="lines", name="因子值",
                ))
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

                ic_result = factor_ic(code, factor_name, forward_period=5, period=period)
                if "error" not in ic_result:
                    st.metric("IC 均值", ic_result["ic_mean"])
                    st.metric("IC_IR", ic_result["ic_ir"])
                    st.metric("IC 胜率", f"{ic_result['ic_win_rate']*100:.0f}%")
            else:
                st.warning("数据不足")

# ── Tab 5: 股票筛选 ─────────────────────────────────────────
with tab5:
    st.subheader("股票筛选器")

    mode = st.radio("模式", ["条件筛选", "模板筛选", "多因子排名"], horizontal=True)

    if mode == "条件筛选":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            pe_max = st.number_input("PE 上限", value=0.0, step=5.0)
            pe_min = st.number_input("PE 下限", value=0.0, step=1.0)
        with col2:
            pb_max = st.number_input("PB 上限", value=0.0, step=0.5)
            turnover_min = st.number_input("换手率下限(%)", value=0.0, step=1.0)
        with col3:
            vol_ratio = st.number_input("量比下限(倍)", value=0.0, step=0.5)
            roe_min = st.number_input("ROE 下限(%)", value=0.0, step=5.0)
        with col4:
            ma_align = st.checkbox("均线多头排列")
            near_high = st.number_input("接近N日新高", value=0, step=5)

        if st.button("筛选", type="primary"):
            conditions = {}
            if pe_max > 0:
                conditions["pe_max"] = pe_max
            if pe_min > 0:
                conditions["pe_min"] = pe_min
            if pb_max > 0:
                conditions["pb_max"] = pb_max
            if turnover_min > 0:
                conditions["turnover_min"] = turnover_min
            if vol_ratio > 0:
                conditions["vol_ratio_min"] = vol_ratio
            if roe_min > 0:
                conditions["roe_min"] = roe_min
            if ma_align:
                conditions["ma_align"] = True
            if near_high > 0:
                conditions["near_high"] = near_high
            df = screen(conditions)
            if df is not None and not df.empty:
                st.success(f"共 {len(df)} 只符合条件")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available].head(50), use_container_width=True, hide_index=True)
            else:
                st.warning("无符合条件的股票")

    elif mode == "模板筛选":
        from analytics.screener import (
            value_screen, momentum_screen, quality_screen,
            breakout_screen, oversold_screen, growth_screen,
        )
        tpl = st.selectbox("模板", ["低估值", "动量", "高质量", "放量突破", "超跌反弹", "高增长"])
        top = st.slider("显示数量", 10, 100, 30)
        if st.button("执行模板", type="primary"):
            tpl_map = {
                "低估值": value_screen, "动量": momentum_screen,
                "高质量": quality_screen, "放量突破": breakout_screen,
                "超跌反弹": oversold_screen, "高增长": growth_screen,
            }
            fn = tpl_map[tpl]
            df = fn(top=top) if tpl in ("放量突破", "超跌反弹", "高增长") else fn()
            if df is not None and not df.empty:
                st.success(f"共 {len(df)} 只")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available].head(top), use_container_width=True, hide_index=True)
            else:
                st.warning("无符合条件的股票")

    else:
        from analytics.screener import rank_screen
        top = st.slider("排名数量", 10, 100, 30)
        if st.button("多因子排名", type="primary"):
            df = rank_screen(top=top)
            if df is not None and not df.empty:
                st.success(f"多因子排名 Top {len(df)}")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "_rank_score"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available], use_container_width=True, hide_index=True)
            else:
                st.warning("无结果")

# ── Tab 6: 交易建议 ─────────────────────────────────────────
with tab6:
    st.subheader("交易建议")

    if st.button("获取交易建议", type="primary"):
        with st.spinner("计算中..."):
            result = get_advice(code)
            if "error" in result:
                st.error(result["error"])
            else:
                conf_map = {"high": "🟢 高", "medium": "🟡 中", "low": "🔴 低"}

                col1, col2, col3 = st.columns(3)
                col1.metric("当前价格", f"{result['current_price']:.2f} 元")
                col2.metric("趋势判断", result["trend"])
                col3.metric("信心等级", conf_map.get(result["confidence"], result["confidence"]))

                st.markdown("---")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("🎯 建议买入", f"{result['buy_price']:.2f} 元",
                            f"{(result['buy_price']/result['current_price']-1)*100:+.1f}% vs 当前")
                col2.metric("🏁 止盈目标", f"{result['take_profit']:.2f} 元",
                            f"{(result['take_profit']/result['buy_price']-1)*100:+.1f}%")
                col3.metric("🛑 止损价位", f"{result['stop_loss']:.2f} 元",
                            f"{(result['stop_loss']/result['buy_price']-1)*100:+.1f}%")
                col4.metric("📊 盈亏比", f"{result['risk_reward']}:1")

                st.markdown("---")
                st.subheader("技术指标")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("MA20", f"{result['ma20']:.2f}")
                c2.metric("MA60", f"{result['ma60']:.2f}")
                c3.metric("布林上轨", f"{result['bb_upper']:.2f}")
                c4.metric("布林下轨", f"{result['bb_lower']:.2f}")

                st.markdown("---")
                st.subheader("分析理由")
                for r in result["reasons"]:
                    st.write(f"· {r}")
