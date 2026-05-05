"""Streamlit 可视化看板 — 行情/个股/回测/因子/筛选/建议。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from database import query, table_exists, save_dataframe, clear_code, get_conn
from analytics import (
    run_backtest, optimize_backtest, portfolio_backtest, benchmark_compare,
    calc_factor, factor_ic, screen, get_advice,
)
from fetchers import HistoryFetcher, FinancialFetcher, FundFlowFetcher, RealtimeFetcher

st.set_page_config(
    page_title="A股量化看板", page_icon="📊",
    layout="wide", initial_sidebar_state="expanded",
)

# ── 全局样式 ──────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px; padding: 20px; color: white;
        text-align: center; margin-bottom: 10px;
    }
    .metric-card.up { background: linear-gradient(135deg, #e74c3c, #c0392b); }
    .metric-card.down { background: linear-gradient(135deg, #27ae60, #1e8449); }
    .metric-card.neutral { background: linear-gradient(135deg, #7f8c8d, #5d6d7e); }
    .metric-card .label { font-size: 14px; opacity: 0.9; }
    .metric-card .value { font-size: 32px; font-weight: bold; margin: 5px 0; }
    .metric-card .delta { font-size: 13px; opacity: 0.8; }
    .main-header {
        font-size: 28px; font-weight: 700;
        background: linear-gradient(90deg, #667eea, #e74c3c);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    div.stButton > button {
        border-radius: 8px; font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0; padding: 10px 20px; font-weight: 500;
    }
    /* 搜索结果高亮 */
    .search-info {
        background: #f0f4ff; border-left: 3px solid #667eea;
        padding: 8px 12px; border-radius: 4px; margin: 8px 0;
        font-size: 13px; color: #444;
    }
    .stock-card {
        background: #f8f9fc; border: 1px solid #e0e4f0;
        border-radius: 12px; padding: 18px; text-align: center; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── 页头 ──────────────────────────────────────────────────
st.markdown('<p class="main-header">A股量化看板</p>', unsafe_allow_html=True)

# ── 侧边栏：股票搜索 ──────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 股票搜索")

    @st.cache_data(ttl=600)
    def load_stock_list():
        if table_exists("realtime"):
            df = query("SELECT code, name FROM realtime ORDER BY code")
            if not df.empty:
                # 过滤 ST / *ST / 退市 / N开头新股
                mask = ~df["name"].str.startswith(("ST", "*ST", "N", "PT"), na=False)
                mask &= ~df["name"].str.contains("退", na=False)
                df = df[mask]
            return df
        return pd.DataFrame(columns=["code", "name"])

    df_all = load_stock_list()

    # 初始化 session state
    if "selected_code" not in st.session_state:
        st.session_state.selected_code = "000559"

    search_query = st.text_input(
        "输入代码或名称", placeholder="如: 000559 或 万向钱潮",
        label_visibility="collapsed", key="stock_search",
    ).strip()

    # 根据搜索构造选项列表
    if search_query and not df_all.empty:
        mask = (
            df_all["code"].str.contains(search_query, case=False) |
            df_all["name"].str.contains(search_query, case=False)
        )
        matches = df_all[mask].head(80)
        if not matches.empty:
            st.markdown(f'<div class="search-info">🔍 "{search_query}" — {len(matches)} 只</div>', unsafe_allow_html=True)
            options = (matches["code"] + " | " + matches["name"]).tolist()
        else:
            st.warning(f"未找到 \"{search_query}\"")
            options = ["000559 | 未找到匹配"]
    elif not df_all.empty:
        options = (df_all["code"] + " | " + df_all["name"]).tolist()
    else:
        options = ["000559 | 无数据"]

    selected = st.selectbox(
        "选择股票", options,
        label_visibility="collapsed", key="stock_picker",
    )
    if selected:
        st.session_state.selected_code = selected.split(" | ")[0]

    code = st.session_state.selected_code

    if not df_all.empty and code in df_all["code"].values:
        name = df_all[df_all["code"] == code]["name"].values[0]

        # 实时行情
        p, chg, color, r = None, None, "#aaa", {}
        rt = query("SELECT * FROM realtime WHERE code=?", [code])
        if not rt.empty:
            r = rt.iloc[0].to_dict()
            p = r.get("price")
            chg = r.get("change_pct")
            if chg is not None:
                color = "#ff6b6b" if chg > 0 else ("#51cf66" if chg < 0 else "#aaa")

        price_str = f"{p:.2f}" if p else "--"
        chg_str = f"{chg:+.2f}%" if chg is not None else "--"
        mv = r.get("total_mv")
        mv_str = f"{mv/1e8:.0f}亿" if (mv and mv > 0) else "--"
        pe_val = r.get("pe")
        pe_str = f"{pe_val:.1f}" if (pe_val and pe_val > 0) else "--"
        pb_val = r.get("pb")
        pb_str = f"{pb_val:.2f}" if (pb_val and pb_val > 0) else "--"
        to_val = r.get("turnover")
        to_str = f"{to_val:.2f}%" if to_val else "--"

        st.markdown(f"""
        <div class="stock-card">
            <div style="font-size:22px; font-weight:bold; color:#222;">{code}</div>
            <div style="font-size:14px; color:#888; margin:2px 0 8px;">{name}</div>
            <div style="font-size:30px; font-weight:bold; color:{color};">{price_str}</div>
            <div style="font-size:15px; color:{color}; margin:2px 0 8px;">{chg_str}</div>
            <table style="width:100%; font-size:12px; color:#666;">
                <tr><td>总市值</td><td style="text-align:right; font-weight:600; color:#333;">{mv_str}</td></tr>
                <tr><td>PE(TTM)</td><td style="text-align:right; font-weight:600; color:#333;">{pe_str}</td></tr>
                <tr><td>PB</td><td style="text-align:right; font-weight:600; color:#333;">{pb_str}</td></tr>
                <tr><td>换手率</td><td style="text-align:right; font-weight:600; color:#333;">{to_str}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # ── 数据抓取 ──────────────────────────────────
    st.divider()
    st.caption("📥 数据抓取")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 历史K线", use_container_width=True, help=f"抓取 {code} 历史K线"):
            with st.spinner(f"抓取 {code} K线数据..."):
                try:
                    clear_code("history", code)
                    df = HistoryFetcher()._fetch(code=code)
                    if df is not None and not df.empty:
                        save_dataframe(df, "history")
                        st.success(f"✅ {len(df)} 条K线")
                    else:
                        st.warning("无数据")
                except Exception as e:
                    st.error(f"失败: {e}")
        if st.button("💰 资金流向", use_container_width=True, help=f"抓取 {code} 资金流向"):
            with st.spinner(f"抓取 {code} 资金流向..."):
                try:
                    clear_code("fund_flow", code)
                    df = FundFlowFetcher().fetch_individual(code)
                    if df is not None and not df.empty:
                        save_dataframe(df, "fund_flow")
                        st.success(f"✅ {len(df)} 条")
                    else:
                        st.warning("无数据")
                except Exception as e:
                    st.error(f"失败: {e}")
    with c2:
        if st.button("📋 利润表", use_container_width=True, help=f"抓取 {code} 利润表"):
            with st.spinner(f"抓取 {code} 利润表..."):
                try:
                    conn = get_conn()
                    conn.execute("DELETE FROM financial WHERE code=? AND report_type='income'", [code])
                    conn.commit()
                    conn.close()
                    df = FinancialFetcher()._fetch(code=code, report_type="income")
                    if df is not None and not df.empty:
                        save_dataframe(df, "financial")
                        st.success(f"✅ {len(df)} 条")
                    else:
                        st.warning("无数据")
                except Exception as e:
                    st.error(f"失败: {e}")
        if st.button("📋 资产负债表", use_container_width=True, help=f"抓取 {code} 资产负债表"):
            with st.spinner(f"抓取 {code} 资产负债表..."):
                try:
                    conn = get_conn()
                    conn.execute("DELETE FROM financial WHERE code=? AND report_type='balance'", [code])
                    conn.commit(); conn.close()
                    df = FinancialFetcher()._fetch(code=code, report_type="balance")
                    if df is not None and not df.empty:
                        save_dataframe(df, "financial")
                        st.success(f"✅ {len(df)} 条")
                    else:
                        st.warning("无数据")
                except Exception as e:
                    st.error(f"失败: {e}")

    if st.button("🌐 全市场实时行情", use_container_width=True, help="抓取全市场实时行情（约60-90秒）"):
        with st.spinner("抓取全市场实时行情，请耐心等待..."):
            try:
                conn = get_conn()
                conn.execute("DELETE FROM realtime")
                conn.commit()
                conn.close()
                df = RealtimeFetcher().fetch()
                if df is not None and not df.empty:
                    save_dataframe(df, "realtime")
                    load_stock_list.clear()
                    st.success(f"✅ {len(df)} 只股票")
                    st.rerun()
                else:
                    st.warning("无数据")
            except Exception as e:
                st.error(f"失败: {e}")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 行情总览", "📋 个股详情", "⚡ 策略回测",
    "🔬 因子分析", "🔍 股票筛选", "💡 交易建议",
])

# ── 配色常量 ──────────────────────────────────────────────
UP_RED, DOWN_GREEN = "#e74c3c", "#27ae60"
CHART_BG = "rgba(0,0,0,0)"
PLOT_LAYOUT = dict(
    paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
    font=dict(color="#4a4a4a"),
    hovermode="x unified",
)
PLOT_AXIS = dict(showgrid=True, gridcolor="#eee")


# ── Tab 1: 行情总览 ──────────────────────────────────────
with tab1:
    if not table_exists("realtime"):
        st.warning("⚠️ realtime 表不存在，请先抓取: `python main.py realtime`")
    else:
        df = query("SELECT code, name, price, change_pct, volume, amount, turnover, pe, pb FROM realtime")
        # 过滤 ST / *ST / 退市 / N开头新股
        if not df.empty:
            mask = ~df["name"].str.startswith(("ST", "*ST", "N", "PT"), na=False)
            mask &= ~df["name"].str.contains("退", na=False)
            df = df[mask]
        if df.empty:
            st.warning("⚠️ realtime 表为空")
        else:
            up_count = (df["change_pct"] > 0).sum()
            down_count = (df["change_pct"] < 0).sum()
            flat_count = len(df) - up_count - down_count
            up_pct = up_count / len(df) * 100 if len(df) else 0

            # 市场概览卡片
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.markdown(f"""
                <div class="metric-card neutral">
                    <div class="label">股票总数</div>
                    <div class="value">{len(df):,}</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="metric-card up">
                    <div class="label">📈 上涨</div>
                    <div class="value">{up_count:,}</div>
                    <div class="delta">{up_pct:.1f}%</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="metric-card down">
                    <div class="label">📉 下跌</div>
                    <div class="value">{down_count:,}</div>
                    <div class="delta">{down_count/len(df)*100:.1f}%</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                avg_chg = df["change_pct"].mean()
                card = "up" if avg_chg > 0 else ("down" if avg_chg < 0 else "neutral")
                st.markdown(f"""
                <div class="metric-card {card}">
                    <div class="label">平均涨跌</div>
                    <div class="value">{avg_chg:+.2f}%</div>
                </div>""", unsafe_allow_html=True)
            with c5:
                total_amt = df["amount"].sum() / 1e8
                st.markdown(f"""
                <div class="metric-card neutral">
                    <div class="label">总成交额</div>
                    <div class="value">{total_amt:.0f}亿</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # 涨跌幅分布
            col_l, col_r = st.columns([3, 2])
            with col_l:
                st.subheader("涨跌幅分布")
                fig = go.Figure()
                clipped = df["change_pct"].clip(-10, 10)
                fig.add_trace(go.Histogram(
                    x=clipped, nbinsx=60,
                    marker=dict(
                        color=clipped.apply(lambda x: UP_RED if x >= 0 else DOWN_GREEN),
                        line=dict(width=0),
                    ),
                    hovertemplate="涨跌: %{x:.1f}%<br>数量: %{y}",
                ))
                fig.update_layout(**PLOT_LAYOUT, height=320,
                    xaxis=dict(title="涨跌幅(%)", **PLOT_AXIS),
                    yaxis=dict(title="数量", **PLOT_AXIS))
                st.plotly_chart(fig, width="stretch")

            with col_r:
                st.subheader("成交额 Top 10")
                top_amt = df.nlargest(10, "amount")[["code", "name", "price", "change_pct", "amount"]].copy()
                top_amt["amount"] = (top_amt["amount"] / 1e8).round(1)
                top_amt.columns = ["代码", "名称", "价", "涨跌%", "成交额(亿)"]
                st.dataframe(top_amt, width="stretch", hide_index=True,
                    column_config={"涨跌%": st.column_config.NumberColumn(format="%+.2f")})

            # 涨跌榜
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🔥 涨幅榜 Top 10")
                up = df.nlargest(10, "change_pct")[["code", "name", "price", "change_pct"]]
                st.dataframe(up, width="stretch", hide_index=True,
                    column_config={"change_pct": st.column_config.NumberColumn(format="%+.2f%%")})
            with c2:
                st.subheader("❄️ 跌幅榜 Top 10")
                dn = df.nsmallest(10, "change_pct")[["code", "name", "price", "change_pct"]]
                st.dataframe(dn, width="stretch", hide_index=True,
                    column_config={"change_pct": st.column_config.NumberColumn(format="%+.2f%%")})


# ── Tab 2: 个股详情 ──────────────────────────────────────
with tab2:
    # ── 周期选择 ──────────────────────────────────────
    tf_map = {
        "分时": ("minute", 240, None),
        "5分钟": ("minute", 2000, None),
        "日线": ("daily", 400, None),
        "周线": ("daily", 2000, "W"),
        "月线": ("daily", 5000, "M"),
        "半年线": ("daily", 5000, "6M"),
        "年线": ("daily", 5000, "Y"),
    }
    c_tf, c_ind1, c_ind2, c_dummy = st.columns([2, 2, 2, 6])
    with c_tf:
        timeframe = st.selectbox("周期", list(tf_map.keys()), index=0, key="kline_tf")
    with c_ind1:
        show_macd = st.checkbox("MACD", value=True, key="ind_macd")
    with c_ind2:
        show_kdj = st.checkbox("KDJ", key="ind_kdj")
    source_type, fetch_days, resample_rule = tf_map[timeframe]

    c_left, c_right = st.columns([7, 3])

    with c_left:
        df_hist = None
        # ── 分钟数据从 AKShare 实时获取 ──────────
        if source_type == "minute":
            import akshare as ak
            prefix = "sh" if code.startswith("6") else "sz"
            try:
                df_min = ak.stock_zh_a_minute(symbol=f"{prefix}{code}", period="5")
                if not df_min.empty:
                    df_min["day"] = pd.to_datetime(df_min["day"])
                    df_min = df_min.rename(columns={"day": "date"})
                    df_min.set_index("date", inplace=True)
                    # AKShare 分钟数据可能是字符串，全部转数值
                    for col in ["open", "high", "low", "close", "volume", "amount"]:
                        if col in df_min.columns:
                            df_min[col] = pd.to_numeric(df_min[col], errors="coerce")
                    if timeframe == "分时":
                        latest_day = df_min.index.max().date()
                        df_min = df_min[df_min.index.date == latest_day]
                    df_hist = df_min
            except Exception:
                df_hist = pd.DataFrame()

        if df_hist is None:
            df_hist = query(
                f"SELECT date, open, high, low, close, volume FROM history "
                f"WHERE code=? ORDER BY date DESC LIMIT {fetch_days}",
                [code],
            )
            if not df_hist.empty:
                df_hist = df_hist.iloc[::-1].copy()
                df_hist["date"] = pd.to_datetime(df_hist["date"])
                df_hist.set_index("date", inplace=True)

        if df_hist is not None and not df_hist.empty:
            # ── 重采样到目标周期 ─────────────────────
            if resample_rule and source_type == "daily":
                df_resampled = df_hist.resample(resample_rule).agg({
                    "open": "first", "high": "max", "low": "min",
                    "close": "last", "volume": "sum",
                }).dropna()
                df_resampled = df_resampled.reset_index()
            else:
                df_resampled = df_hist.reset_index()

            data = df_resampled
            close = data["close"]
            high = data["high"]
            low = data["low"]
            vol = data["volume"]
            is_intraday = timeframe in ("分时", "5分钟")

            # ── 连续索引 ─────────────────────────────
            n_bars = len(data)
            idx = list(range(n_bars))
            step = max(1, n_bars // 10)
            tick_vals = idx[::step]
            if is_intraday:
                tick_text = [d.strftime("%H:%M") for d in data["date"].iloc[::step]]
            elif resample_rule in ("M", "6M", "Y"):
                tick_text = [d.strftime("%Y-%m") for d in data["date"].iloc[::step]]
            else:
                tick_text = [d.strftime("%m/%d") for d in data["date"].iloc[::step]]

            # MA 均线
            ma5 = close.rolling(5, min_periods=1).mean()
            ma20 = close.rolling(20, min_periods=1).mean()
            ma60 = close.rolling(60, min_periods=1).mean()

            # ── 技术指标 ──────────────────────────────
            macd_line = macd_signal = macd_hist = k_val = d_val = j_val = None
            if not is_intraday:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd_line = ema12 - ema26
                macd_signal = macd_line.ewm(span=9, adjust=False).mean()
                macd_hist = macd_line - macd_signal

                low9 = low.rolling(9, min_periods=1).min()
                high9 = high.rolling(9, min_periods=1).max()
                rsv = (close - low9) / (high9 - low9).replace(0, np.nan) * 100
                k_val = rsv.ewm(alpha=1/3, adjust=False).mean()
                d_val = k_val.ewm(alpha=1/3, adjust=False).mean()
                j_val = 3 * k_val - 2 * d_val

            # ── 动态子图行数 ─────────────────────────
            n_extra = (1 if show_macd and not is_intraday else 0) + (1 if show_kdj and not is_intraday else 0)
            n_rows = 2 + n_extra
            row_heights = [0.7] + (([0.15] if show_macd and not is_intraday else [])) + (([0.15] if show_kdj and not is_intraday else [])) + [0.3]
            row_heights = [h / sum(row_heights) for h in row_heights]

            fig = make_subplots(
                rows=n_rows, cols=1, shared_xaxes=True,
                vertical_spacing=0.01,
                row_heights=row_heights,
            )

            # 行号分配
            row_k = 1
            row_macd = 2 if show_macd else None
            row_kdj = (2 if not show_macd else 3) if show_kdj else None
            row_vol = n_rows

            # 价格图
            if timeframe == "分时":
                # 昨收从日线表取
                yest_close = data["open"].iloc[0]
                today_str = data["date"].iloc[0].strftime("%Y%m%d")
                df_yc = query("SELECT close FROM history WHERE code=? AND date<? ORDER BY date DESC LIMIT 1", [code, today_str])
                if not df_yc.empty:
                    yest_close = float(df_yc.iloc[0]["close"])

                # 涨跌幅(%)
                chg_pct = (close - yest_close) / yest_close * 100

                fig.add_trace(go.Scatter(
                    x=idx, y=chg_pct, mode="lines",
                    line=dict(color="#667eea", width=1.5),
                    name="涨跌幅", showlegend=False,
                    fill="tozeroy", fillcolor="rgba(102,126,234,0.1)",
                    hovertemplate="%{text}<br>价格: %{customdata:.2f}<br>涨跌: %{y:+.2f}%",
                    text=[d.strftime("%H:%M") for d in data["date"]],
                    customdata=close,
                ), row=row_k, col=1)
                # 零轴
                fig.add_hline(y=0, line_dash="dash", line_color="#999",
                              row=row_k, col=1)
                # 均价线（涨跌幅）
                avg_price = (vol * close).cumsum() / vol.cumsum()
                avg_chg = (avg_price - yest_close) / yest_close * 100
                fig.add_trace(go.Scatter(
                    x=idx, y=avg_chg, mode="lines",
                    line=dict(color="#f39c12", width=1, dash="dot"),
                    name="均价", showlegend=False,
                ), row=row_k, col=1)

                # y 轴标签（在下面统一设置处会覆盖，需在此处理）
            else:
                fig.add_trace(go.Candlestick(
                    x=idx, open=data["open"], high=high, low=low, close=close,
                    name="K线", showlegend=False,
                    increasing=dict(line=dict(color=UP_RED), fillcolor=UP_RED),
                    decreasing=dict(line=dict(color=DOWN_GREEN), fillcolor=DOWN_GREEN),
                    hovertext=data["date"].dt.strftime("%Y-%m-%d %H:%M" if is_intraday else "%Y-%m-%d"),
                ), row=row_k, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=ma5, line=dict(color="#f39c12", width=1), name="MA5",
                ), row=row_k, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=ma20, line=dict(color="#3498db", width=1.2), name="MA20",
                ), row=row_k, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=ma60, line=dict(color="#9b59b6", width=1.2), name="MA60",
                ), row=row_k, col=1)

            # MACD（非分时模式）
            if show_macd and not is_intraday:
                fig.add_trace(go.Bar(
                    x=idx, y=macd_hist, name="MACD柱",
                    marker=dict(color=[UP_RED if v>=0 else DOWN_GREEN for v in macd_hist], opacity=0.7),
                    showlegend=False,
                ), row=row_macd, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=macd_line, line=dict(color="#e74c3c", width=1), name="DIF",
                ), row=row_macd, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=macd_signal, line=dict(color="#3498db", width=1), name="DEA",
                ), row=row_macd, col=1)
                fig.add_hline(y=0, line_dash="dash", line_color="#bbb", row=row_macd, col=1)

            # KDJ（非分时模式）
            if show_kdj and not is_intraday:
                fig.add_trace(go.Scatter(
                    x=idx, y=k_val, line=dict(color="#e74c3c", width=1), name="K",
                ), row=row_kdj, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=d_val, line=dict(color="#3498db", width=1), name="D",
                ), row=row_kdj, col=1)
                fig.add_trace(go.Scatter(
                    x=idx, y=j_val, line=dict(color="#9b59b6", width=1, dash="dot"), name="J",
                ), row=row_kdj, col=1)
                fig.add_hline(y=80, line_dash="dash", line_color="#bbb", row=row_kdj, col=1)
                fig.add_hline(y=20, line_dash="dash", line_color="#bbb", row=row_kdj, col=1)

            # 成交量
            vol_colors = [UP_RED if close.iloc[i] >= data["open"].iloc[i] else DOWN_GREEN
                          for i in range(n_bars)]
            fig.add_trace(go.Bar(
                x=idx, y=vol, name="成交量",
                marker=dict(color=vol_colors, opacity=0.5),
                showlegend=False,
                hovertext=data["date"].dt.strftime("%Y-%m-%d"),
            ), row=row_vol, col=1)

            # 动态布局
            if timeframe == "分时":
                yaxis_dict = {"yaxis": dict(title="涨跌幅(%)", side="right", autorange=True, fixedrange=False, ticksuffix="%", **PLOT_AXIS)}
            else:
                yaxis_dict = {"yaxis": dict(title="价格", side="right", autorange=True, fixedrange=False, **PLOT_AXIS)}
            yaxis_dict[f"yaxis{row_vol}"] = dict(title="成交量", side="right", autorange=True, fixedrange=False, **PLOT_AXIS)
            if show_macd:
                yaxis_dict[f"yaxis{row_macd}"] = dict(title="MACD", side="right", autorange=True, fixedrange=False, **PLOT_AXIS)
            if show_kdj:
                yaxis_dict[f"yaxis{row_kdj}"] = dict(title="KDJ", side="right", autorange=True, fixedrange=False, **PLOT_AXIS)

            xaxis_dict = {"xaxis": dict(tickvals=tick_vals, ticktext=tick_text, **PLOT_AXIS)}
            xaxis_dict[f"xaxis{row_vol}"] = dict(tickvals=tick_vals, ticktext=tick_text, **PLOT_AXIS)

            fig.update_layout(
                **PLOT_LAYOUT, height=180 + n_rows * 120,
                xaxis_rangeslider_visible=False,
                **xaxis_dict, **yaxis_dict,
            )

            st.plotly_chart(fig, width="stretch", config={
                "scrollZoom": True,
                "displayModeBar": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            })
        else:
            st.warning(f"⚠️ {code} 无历史K线，请先抓取数据")

    with c_right:
        st.subheader("技术指标")
        df_hist2 = query(
            "SELECT close, high, low FROM history WHERE code=? ORDER BY date DESC LIMIT 60",
            [code],
        )
        if not df_hist2.empty:
            c = df_hist2["close"].values
            latest = c[0]
            ma5_v = c[:5].mean(); ma10_v = c[:10].mean(); ma20_v = c[:20].mean()
            ma60_v = c[:60].mean() if len(c) >= 60 else c.mean()
            chg_5d = (c[0] / c[4] - 1) * 100 if len(c) >= 5 else 0
            chg_20d = (c[0] / c[19] - 1) * 100 if len(c) >= 20 else 0
            high_20 = df_hist2["high"].values[:20].max()
            low_20 = df_hist2["low"].values[:20].min()

            rows = [
                ("最新价", f"{latest:.2f}", ""),
                ("5日涨跌", f"{chg_5d:+.2f}%", "up" if chg_5d > 0 else "down"),
                ("20日涨跌", f"{chg_20d:+.2f}%", "up" if chg_20d > 0 else "down"),
                ("MA5", f"{ma5_v:.2f}", "up" if latest > ma5_v else "down"),
                ("MA10", f"{ma10_v:.2f}", "up" if latest > ma10_v else "down"),
                ("MA20", f"{ma20_v:.2f}", "up" if latest > ma20_v else "down"),
                ("MA60", f"{ma60_v:.2f}", "up" if latest > ma60_v else "down"),
                ("20日高", f"{high_20:.2f}", ""),
                ("20日低", f"{low_20:.2f}", ""),
            ]
            html = '<table style="width:100%; font-size:14px;">'
            for label, val, cls in rows:
                vc = UP_RED if cls == "up" else (DOWN_GREEN if cls == "down" else "#333")
                html += f'<tr><td style="color:#888; padding:4px 0;">{label}</td><td style="text-align:right; color:{vc}; font-weight:600;">{val}</td></tr>'
            html += '</table>'
            st.markdown(html, unsafe_allow_html=True)

    # 资金流向 + 财务
    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        df_flow = query(
            "SELECT date, main_net FROM fund_flow WHERE code=? ORDER BY date DESC LIMIT 60",
            [code],
        )
        if not df_flow.empty:
            df_flow = df_flow.iloc[::-1].copy()
            df_flow["date"] = pd.to_datetime(df_flow["date"])
            st.subheader("💰 资金流向（主力净额/万）")
            fig = go.Figure()
            flow_vals = df_flow["main_net"] / 1e4
            fig.add_trace(go.Bar(
                x=df_flow["date"], y=flow_vals,
                marker=dict(color=[UP_RED if v > 0 else DOWN_GREEN for v in flow_vals]),
                hovertemplate="日期: %{x|%Y-%m-%d}<br>主力净额: %{y:,.0f}万",
            ))
            fig.update_layout(**PLOT_LAYOUT, height=280)
            fig.update_yaxes(title="万元")
            st.plotly_chart(fig, width="stretch")

    with c2:
        df_fin = query(
            "SELECT report_date, report_type, revenue, net_profit, basic_eps "
            "FROM financial WHERE code=? ORDER BY report_date DESC LIMIT 6",
            [code],
        )
        if not df_fin.empty:
            st.subheader("📊 最新财报")
            df_fin["revenue"] = pd.to_numeric(df_fin["revenue"], errors="coerce").div(1e8).round(2)
            df_fin["net_profit"] = pd.to_numeric(df_fin["net_profit"], errors="coerce").div(1e8).round(2)
            type_map = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
            df_fin["report_type"] = df_fin["report_type"].map(type_map)
            df_fin.columns = ["报告期", "类型", "营收(亿)", "净利(亿)", "EPS"]
            st.dataframe(df_fin, width="stretch", hide_index=True)


# ── Tab 3: 回测 ──────────────────────────────────────────
with tab3:
    st.subheader("⚡ 策略回测")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        strat = st.selectbox("策略", [
            "sma_cross", "rsi", "buy_hold", "macd", "bollinger",
            "ma_align", "turtle", "vol_breakout", "mean_revert",
            "kdj", "cci", "williams_r", "donchian", "three_bar",
        ], format_func=lambda x: {
            "sma_cross": "双均线交叉", "macd": "MACD", "bollinger": "布林突破",
            "ma_align": "均线多头排列", "turtle": "海龟交易", "vol_breakout": "量价突破",
            "mean_revert": "均值回归", "rsi": "RSI", "kdj": "KDJ",
            "cci": "CCI反转", "williams_r": "威廉指标", "donchian": "唐奇安反弹",
            "three_bar": "三K线反转", "buy_hold": "买入持有(基准)",
        }.get(x, x))
    with c2:
        start_date = st.date_input("起始", value=pd.to_datetime("2024-01-01"))
    with c3:
        end_date = st.date_input("结束", value=pd.to_datetime("today"))
    with c4:
        cash = st.number_input("初始资金(万)", value=10, step=1) * 10000

    if st.button("🚀 运行回测", type="primary", width="stretch"):
        with st.spinner("回测运行中..."):
            try:
                result = run_backtest(
                    code, strategy=strat,
                    start=start_date.strftime("%Y%m%d"),
                    end=end_date.strftime("%Y%m%d"),
                    initial_cash=int(cash), return_equity=True,
                )
                # 净值曲线
                if result.get("equity") and result.get("equity_dates"):
                    eq = result["equity"]
                    dates = pd.to_datetime(result["equity_dates"])
                    # 买入持有基准
                    bench = run_backtest(code, "buy_hold",
                        start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"),
                        int(cash), return_equity=True,
                    )
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        x=dates, y=eq, mode="lines",
                        line=dict(color="#667eea", width=2), name=strat,
                    ))
                    if bench.get("equity") and len(bench["equity"]) == len(eq):
                        fig_eq.add_trace(go.Scatter(
                            x=dates, y=bench["equity"],
                            line=dict(color="#bbb", width=1.5, dash="dash"),
                            name="买入持有",
                        ))
                    fig_eq.update_layout(**PLOT_LAYOUT, height=300,
                        yaxis=dict(title="净值", side="right", autorange=True, **PLOT_AXIS))
                    st.plotly_chart(fig_eq, width="stretch")

                # 绩效卡片
                c1, c2, c3, c4, c5 = st.columns(5)
                total_ret = result["total_return_pct"]
                card_c = "up" if total_ret > 0 else "down"
                c1.markdown(f'<div class="metric-card {card_c}"><div class="label">总收益率</div><div class="value">{total_ret:+.2f}%</div></div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="metric-card neutral"><div class="label">年化收益</div><div class="value">{result["annual_return_pct"]:.2f}%</div></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="metric-card neutral"><div class="label">最大回撤</div><div class="value">{result["max_drawdown_pct"]:.2f}%</div></div>', unsafe_allow_html=True)
                c4.markdown(f'<div class="metric-card neutral"><div class="label">夏普比率</div><div class="value">{result["sharpe_ratio"]:.2f}</div></div>', unsafe_allow_html=True)
                c5.markdown(f'<div class="metric-card neutral"><div class="label">盈亏比</div><div class="value">{result.get("risk_reward", "-")}</div></div>', unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3)
                c1.metric("交易次数", result["total_trades"])
                c2.metric("胜率", f'{result["win_rate_pct"]}%')
                c3.metric("回测区间", result["period"])

            except ValueError as e:
                st.error(f"回测失败: {e}")

    # ── 基准对比 / 参数优化 / 组合回测 ──────────────
    st.markdown("---")
    mode_bt = st.radio("扩展功能", ["基准对比", "参数优化", "组合回测"], horizontal=True)

    if mode_bt == "基准对比":
        if st.button("📊 对比买入持有基准", type="primary"):
            with st.spinner("计算中..."):
                try:
                    bm = benchmark_compare(code, strat, start_date.strftime("%Y%m%d"),
                                           end_date.strftime("%Y%m%d"), int(cash))
                    c1, c2 = st.columns(2)
                    excess = bm["excess_return"]
                    tag = "✅ 跑赢基准" if excess > 0 else ("❌ 跑输基准" if excess < 0 else "➖ 持平")
                    with c1:
                        st.markdown(f"""
                        <div class="metric-card {'up' if excess>0 else 'down'}">
                            <div class="label">{tag}</div>
                            <div class="value">{excess:+.2f}%</div>
                            <div class="delta">超额收益</div>
                        </div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                        <div class="metric-card neutral">
                            <div class="label">策略 vs 基准</div>
                            <div class="value">{bm['strategy_return']:.1f}% vs {bm['buy_hold_return']:.1f}%</div>
                            <div class="delta">夏普 {bm['strategy_sharpe']:.2f} vs {bm['buy_hold_sharpe']:.2f}</div>
                        </div>""", unsafe_allow_html=True)
                except ValueError as e:
                    st.error(f"失败: {e}")

    elif mode_bt == "参数优化":
        from analytics.backtest import PARAM_GRIDS
        metric_opt = st.selectbox("优化目标", ["sharpe_ratio", "total_return_pct", "annual_return_pct"],
                                  format_func=lambda x: {"sharpe_ratio": "夏普比率", "total_return_pct": "总收益率", "annual_return_pct": "年化收益"}.get(x, x))
        opt_strats = [s for s in PARAM_GRIDS if PARAM_GRIDS[s]]
        opt_strat = st.selectbox("策略", opt_strats, key="opt_strat")

        grid = PARAM_GRIDS.get(opt_strat, {})
        n_combos = 1
        for v in grid.values():
            n_combos *= len(v)
        st.caption(f"搜索空间: {n_combos} 种组合")

        if st.button("🔍 开始优化", type="primary"):
            with st.spinner(f"参数优化中，测试 {n_combos} 组..."):
                try:
                    best_params, best_result, _ = optimize_backtest(
                        code, opt_strat, start_date.strftime("%Y%m%d"),
                        end_date.strftime("%Y%m%d"), int(cash), metric_opt,
                    )
                    if best_params:
                        st.success(f"最优参数: {best_params}")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("总收益", f"{best_result['total_return_pct']}%")
                        c2.metric("夏普", f"{best_result['sharpe_ratio']:.2f}")
                        c3.metric("最大回撤", f"{best_result['max_drawdown_pct']}%")
                    else:
                        st.warning("无结果")
                except Exception as e:
                    st.error(f"优化失败: {e}")

    elif mode_bt == "组合回测":
        extra_codes = st.text_input("额外股票代码（逗号分隔）", placeholder="如: 000001,600519,300750")
        if st.button("📊 组合回测", type="primary"):
            codes = [code] + [c.strip() for c in extra_codes.split(",") if c.strip()]
            codes = list(dict.fromkeys(codes))  # 去重
            with st.spinner(f"回测 {len(codes)} 只股票组合..."):
                try:
                    pf = portfolio_backtest(codes, strat, start_date.strftime("%Y%m%d"),
                                            end_date.strftime("%Y%m%d"), int(cash))
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("股票数", pf["n_stocks"])
                    c2.metric("总收益率", f"{pf['total_return_pct']}%")
                    c3.metric("最大回撤", f"{pf['max_drawdown_pct']}%")
                    c4.metric("夏普", f"{pf['sharpe_ratio']}")
                    st.caption(f"股票池: {', '.join(pf['codes'])}")
                except ValueError as e:
                    st.error(f"失败: {e}")


# ── Tab 4: 因子分析 ──────────────────────────────────────
with tab4:
    st.subheader("🔬 因子分析")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        factor_name = st.selectbox("因子", ["momentum", "volatility", "turnover", "volume_ratio"],
            format_func=lambda x: {"momentum": "动量", "volatility": "波动率", "turnover": "换手率", "volume_ratio": "量比"}.get(x, x))
    with c2:
        period = st.slider("周期(天)", 5, 60, 20)

    if st.button("🔬 计算因子 & IC", type="primary"):
        with st.spinner("计算中..."):
            df_f = calc_factor(code, factor_name, period=period)
            if df_f is not None and not df_f.empty:
                df_f["date"] = pd.to_datetime(df_f["date"])
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_f["date"], y=df_f["factor"], mode="lines",
                    line=dict(color="#667eea", width=2),
                    fill="tozeroy", fillcolor="rgba(102,126,234,0.1)",
                    name="因子值",
                ))
                fig.update_layout(**PLOT_LAYOUT, height=320,
                    yaxis_title="因子值")
                st.plotly_chart(fig, width="stretch")

                ic_result = factor_ic(code, factor_name, forward_period=5, period=period)
                if "error" not in ic_result:
                    c1, c2, c3, c4 = st.columns(4)
                    ic_val = ic_result["ic_mean"]
                    card = "up" if ic_val > 0 else "down"
                    c1.markdown(f'<div class="metric-card {card}"><div class="label">IC 均值</div><div class="value">{ic_val:.4f}</div></div>', unsafe_allow_html=True)
                    c2.markdown(f'<div class="metric-card neutral"><div class="label">IC 标准差</div><div class="value">{ic_result["ic_std"]:.4f}</div></div>', unsafe_allow_html=True)
                    c3.markdown(f'<div class="metric-card neutral"><div class="label">IC_IR</div><div class="value">{ic_result["ic_ir"]:.4f}</div></div>', unsafe_allow_html=True)
                    c4.markdown(f'<div class="metric-card neutral"><div class="label">IC 胜率</div><div class="value">{ic_result["ic_win_rate"]*100:.0f}%</div></div>', unsafe_allow_html=True)
            else:
                st.warning("数据不足")


# ── Tab 5: 股票筛选 ──────────────────────────────────────
with tab5:
    st.subheader("🔍 股票筛选器")

    mode = st.radio("模式", ["📋 条件筛选", "🎯 模板筛选", "🏆 多因子排名"], horizontal=True)

    if mode == "📋 条件筛选":
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pe_max = st.number_input("PE ≤", value=0.0, step=5.0, key="s_pe_max")
            pe_min = st.number_input("PE ≥", value=0.0, step=1.0, key="s_pe_min")
        with c2:
            pb_max = st.number_input("PB ≤", value=0.0, step=0.5, key="s_pb_max")
            turnover_min = st.number_input("换手率 ≥ (%)", value=0.0, step=1.0, key="s_ts")
        with c3:
            vol_ratio = st.number_input("量比 ≥ (倍)", value=0.0, step=0.5, key="s_vr")
            roe_min = st.number_input("ROE ≥ (%)", value=0.0, step=5.0, key="s_roe")
        with c4:
            ma_align = st.checkbox("均线多头排列", key="s_ma")
            near_high = st.number_input("接近N日新高", value=0, step=5, key="s_nh")

        if st.button("🔍 开始筛选", type="primary", width="stretch"):
            conditions = {}
            if pe_max > 0: conditions["pe_max"] = pe_max
            if pe_min > 0: conditions["pe_min"] = pe_min
            if pb_max > 0: conditions["pb_max"] = pb_max
            if turnover_min > 0: conditions["turnover_min"] = turnover_min
            if vol_ratio > 0: conditions["vol_ratio_min"] = vol_ratio
            if roe_min > 0: conditions["roe_min"] = roe_min
            if ma_align: conditions["ma_align"] = True
            if near_high > 0: conditions["near_high"] = near_high
            df = screen(conditions)
            if df is not None and not df.empty:
                st.success(f"✅ 共 {len(df)} 只符合条件")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available].head(50), width="stretch", hide_index=True)
            else:
                st.warning("无符合条件的股票")

    elif mode == "🎯 模板筛选":
        from analytics.screener import (
            value_screen, momentum_screen, quality_screen,
            breakout_screen, oversold_screen, growth_screen,
        )
        tpl = st.selectbox("选择模板", ["低估值", "动量", "高质量", "放量突破", "超跌反弹", "高增长"])
        top = st.slider("显示数量", 10, 100, 30)
        if st.button("🎯 执行模板", type="primary"):
            tpl_map = {
                "低估值": value_screen, "动量": momentum_screen,
                "高质量": quality_screen, "放量突破": breakout_screen,
                "超跌反弹": oversold_screen, "高增长": growth_screen,
            }
            fn = tpl_map[tpl]
            df = fn(top=top) if tpl in ("放量突破", "超跌反弹", "高增长") else fn()
            if df is not None and not df.empty:
                st.success(f"✅ 共 {len(df)} 只")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available].head(top), width="stretch", hide_index=True)
            else:
                st.warning("无符合条件的股票")

    else:
        from analytics.screener import rank_screen
        top = st.slider("排名数量", 10, 100, 30, key="rank_top")
        if st.button("🏆 多因子排名", type="primary"):
            df = rank_screen(top=top)
            if df is not None and not df.empty:
                st.success(f"🏆 多因子排名 Top {len(df)}")
                show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "_rank_score"]
                available = [c for c in show_cols if c in df.columns]
                st.dataframe(df[available], width="stretch", hide_index=True,
                    column_config={"_rank_score": st.column_config.NumberColumn("综合得分", format="%.4f")})
            else:
                st.warning("无结果")


# ── Tab 6: 交易建议 ──────────────────────────────────────
with tab6:
    st.subheader("💡 交易建议")

    if st.button("💡 获取交易建议", type="primary", width="stretch"):
        with st.spinner("计算中..."):
            result = get_advice(code)
            if "error" in result:
                st.error(result["error"])
            else:
                conf_map = {"high": "🟢 强烈推荐", "medium": "🟡 可关注", "low": "🔴 暂不建议"}
                conf_class = {"high": "up", "medium": "neutral", "low": "down"}

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f'<div class="metric-card {conf_class[result["confidence"]]}"><div class="label">当前价格</div><div class="value">{result["current_price"]:.2f}</div><div class="delta">{result["trend"]}</div></div>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<div class="metric-card neutral"><div class="label">信心等级</div><div class="value">{conf_map[result["confidence"]]}</div><div class="delta">盈亏比 {result["risk_reward"]}:1</div></div>', unsafe_allow_html=True)

                st.markdown("---")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    buy_delta = (result["buy_price"] / result["current_price"] - 1) * 100
                    st.markdown(f'<div class="metric-card up"><div class="label">🎯 建议买入</div><div class="value">{result["buy_price"]:.2f}</div><div class="delta">{buy_delta:+.1f}% vs 当前</div></div>', unsafe_allow_html=True)
                with c2:
                    tp_delta = (result["take_profit"] / result["buy_price"] - 1) * 100
                    st.markdown(f'<div class="metric-card up"><div class="label">🏁 止盈目标</div><div class="value">{result["take_profit"]:.2f}</div><div class="delta">+{tp_delta:.1f}%</div></div>', unsafe_allow_html=True)
                with c3:
                    sl_delta = (result["stop_loss"] / result["buy_price"] - 1) * 100
                    st.markdown(f'<div class="metric-card down"><div class="label">🛑 止损价位</div><div class="value">{result["stop_loss"]:.2f}</div><div class="delta">{sl_delta:.1f}%</div></div>', unsafe_allow_html=True)
                with c4:
                    st.markdown(f'<div class="metric-card neutral"><div class="label">📊 盈亏比</div><div class="value">{result["risk_reward"]}:1</div></div>', unsafe_allow_html=True)

                st.markdown("---")

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("MA20", f'{result["ma20"]:.2f}')
                c2.metric("MA60", f'{result["ma60"]:.2f}')
                c3.metric("布林上轨", f'{result["bb_upper"]:.2f}')
                c4.metric("布林下轨", f'{result["bb_lower"]:.2f}')
                c5.metric("ATR(14)", f'{result["atr"]:.2f}')

                st.markdown("---")
                st.caption("📝 分析理由")
                for r in result["reasons"]:
                    st.write(f"· {r}")
