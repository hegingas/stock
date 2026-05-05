import logging
import click
from database import init_db, save_dataframe, query, table_exists
from exporters import export
from fetchers import (
    RealtimeFetcher, HistoryFetcher, FinancialFetcher, FundFlowFetcher
)
from analytics import (
    run_backtest, optimize_backtest, portfolio_backtest, benchmark_compare, rolling_backtest,
    calc_factor, factor_ic, cross_section_ic, quantile_returns, screen, rank_screen,
    value_screen, momentum_screen, quality_screen,
    breakout_screen, oversold_screen, growth_screen, get_advice,
)
from analytics.backtest import PARAM_GRIDS
from trading import scan_signals, Portfolio, SimAccount

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """A股股票数据抓取工具"""
    init_db()


# ── realtime ──────────────────────────────────────────────

@cli.command()
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def realtime(save, export_csv):
    """抓取全市场实时行情"""
    fetcher = RealtimeFetcher()
    df = fetcher.fetch()
    if df is None:
        click.echo("获取实时行情失败")
        return

    click.echo(f"获取到 {len(df)} 条实时行情")
    click.echo(df.head(10).to_string())

    if save:
        save_dataframe(df, "realtime")
        click.echo(f"已保存到 realtime 表")
    if export_csv:
        export("realtime", fmt="csv")


# ── history ───────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码，如 000001")
@click.option("--period", default="daily",
              type=click.Choice(["daily", "weekly", "monthly"]),
              help="周期")
@click.option("--start", default="20200101", help="起始日期 YYYYMMDD")
@click.option("--end", default="20501231", help="结束日期 YYYYMMDD")
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def history(code, period, start, end, save, export_csv):
    """抓取个股历史K线"""
    fetcher = HistoryFetcher()
    df = fetcher._fetch(code=code, period=period,
                        start_date=start, end_date=end)
    if df is None or df.empty:
        click.echo("获取历史K线失败")
        return

    click.echo(f"获取到 {len(df)} 条K线数据")
    click.echo(df.head(10).to_string())

    if save:
        save_dataframe(df, "history")
        click.echo("已保存到 history 表")
    if export_csv:
        export("history", fmt="csv")


# ── financial ─────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码，如 600519")
@click.option("--type", "rpt_type", default="income",
              type=click.Choice(["income", "balance", "cashflow"]),
              help="报表类型")
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def financial(code, rpt_type, save, export_csv):
    """抓取财务报表（利润表/资产负债表/现金流量表）"""
    names = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
    fetcher = FinancialFetcher()
    df = fetcher._fetch(code=code, report_type=rpt_type)
    if df is None or df.empty:
        click.echo(f"获取 {names[rpt_type]} 失败")
        return

    click.echo(f"获取到 {names[rpt_type]} {len(df)} 条")
    # show key numeric columns only
    show_cols = ["report_date", "report_type", "revenue",
                 "net_profit", "net_profit_parent", "basic_eps",
                 "total_assets", "cf_operating"]
    available = [c for c in show_cols if c in df.columns]
    click.echo(df[available].head(10).to_string())

    if save:
        save_dataframe(df, "financial")
        click.echo("已保存到 financial 表")
    if export_csv:
        export("financial", fmt="csv")


# ── fund-flow ─────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def fund_flow(code, save, export_csv):
    """抓取个股资金流向"""
    fetcher = FundFlowFetcher()
    df = fetcher.fetch_individual(code)
    if df is None or df.empty:
        click.echo("获取资金流向失败")
        return

    click.echo(f"获取到 {len(df)} 条资金流向")
    click.echo(df.head(10).to_string())

    if save:
        save_dataframe(df, "fund_flow")
        click.echo("已保存到 fund_flow 表")
    if export_csv:
        export("fund_flow", fmt="csv")


@cli.command()
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
def industry(save):
    """抓取东方财富行业分类数据"""
    from fetchers.industry import fetch_industry
    click.echo("抓取行业分类数据（约 2~3 分钟）...")
    df = fetch_industry()
    if df is not None and not df.empty:
        industries = df["industry"].nunique()
        click.echo(f"✅ 获取 {len(df)} 只股票, {industries} 个行业")
    else:
        click.echo("抓取失败")


@cli.command()
@click.option("--date", default=None, help="日期 YYYYMMDD，默认昨天")
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def lhb(date, save, export_csv):
    """抓取龙虎榜明细"""
    fetcher = FundFlowFetcher()
    df = fetcher.fetch_lhb(date=date)
    if df is None or df.empty:
        click.echo("获取龙虎榜失败")
        return

    click.echo(f"获取到 {len(df)} 条龙虎榜记录")
    click.echo(df.head(10).to_string())

    if save:
        save_dataframe(df, "lhb")
        click.echo("已保存到 lhb 表")
    if export_csv:
        export("lhb", fmt="csv")


@cli.command()
@click.option("--save/--no-save", default=True, help="是否保存到数据库")
@click.option("--export-csv", is_flag=True, help="同时导出为 CSV")
def north_flow(save, export_csv):
    """抓取北向资金流向"""
    fetcher = FundFlowFetcher()
    df = fetcher.fetch_north_flow()
    if df is None or df.empty:
        click.echo("获取北向资金失败")
        return

    click.echo(f"获取到 {len(df)} 条北向资金记录")
    click.echo(df.tail(10).to_string())

    if save:
        save_dataframe(df, "north_flow")
        click.echo("已保存到 north_flow 表")
    if export_csv:
        export("north_flow", fmt="csv")


# ── export ────────────────────────────────────────────────

@cli.command()
@click.option("--table", required=True, help="表名")
@click.option("--format", "fmt", default="csv",
              type=click.Choice(["csv", "excel"]),
              help="导出格式")
@click.option("--output", default=None, help="输出路径")
@click.option("--code", default=None, help="按股票代码筛选")
@click.option("--date", default=None, help="按日期筛选")
def export_cmd(table, fmt, output, code, date):
    """导出数据为 CSV/Excel"""
    filters = {}
    if code:
        filters["code"] = code
    if date:
        filters["date"] = date
    try:
        export(table, fmt=fmt, output_path=output, **filters)
    except ValueError as e:
        click.echo(f"错误: {e}")


# ── backtest ─────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--strategy", "strat", default="sma_cross",
              type=click.Choice(["sma_cross", "rsi", "buy_hold", "macd", "bollinger", "ma_align", "turtle", "vol_breakout", "mean_revert", "kdj", "cci", "williams_r", "donchian", "three_bar"]),
              help="策略名称")
@click.option("--start", default=None, help="起始日期 YYYYMMDD（默认一年前）")
@click.option("--end", default=None, help="结束日期 YYYYMMDD（默认今天）")
@click.option("--cash", default=100000, help="初始资金")
def backtest(code, strat, start, end, cash):
    """运行策略回测"""
    try:
        result = run_backtest(code, strategy=strat, start=start, end=end,
                              initial_cash=int(cash))
    except ValueError as e:
        click.echo(f"错误: {e}")
        return

    click.echo(f"\n{'='*50}")
    click.echo(f"  回测结果: {result['code']}  {result['strategy']}")
    click.echo(f"{'='*50}")
    click.echo(f"  回测区间: {result['period']}")
    click.echo(f"  交易日数: {result['trading_days']}")
    click.echo(f"  初始资金: {result['initial_cash']:,.0f}")
    click.echo(f"  最终资金: {result['final_value']:,.0f}")
    click.echo(f"  总收益率: {result['total_return_pct']}%")
    click.echo(f"  年化收益: {result['annual_return_pct']}%")
    click.echo(f"  最大回撤: {result['max_drawdown_pct']}%")
    click.echo(f"  夏普比率: {result['sharpe_ratio']}")
    click.echo(f"  交易次数: {result['total_trades']}")
    click.echo(f"  胜率:     {result['win_rate_pct']}%")


# ── optimize ───────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--strategy", "strat", default="sma_cross",
              type=click.Choice([s for s in PARAM_GRIDS.keys() if PARAM_GRIDS[s]]),
              help="策略名称（仅显示有可调参数的策略）")
@click.option("--start", default=None, help="起始日期")
@click.option("--end", default=None, help="结束日期")
@click.option("--cash", default=100000, help="初始资金")
@click.option("--metric", default="sharpe_ratio",
              type=click.Choice(["sharpe_ratio", "total_return_pct", "annual_return_pct"]),
              help="优化目标")
def optimize(code, strat, start, end, cash, metric):
    """网格搜索优化策略参数"""
    click.echo(f"\n🔍 优化 {strat} 策略参数（目标: {metric}）...")
    grid = PARAM_GRIDS.get(strat, {})
    n_combos = 1
    for v in grid.values():
        n_combos *= len(v)
    click.echo(f"   搜索空间: {len(grid)} 个参数, {n_combos} 种组合")

    best_params, best_result, all_results = optimize_backtest(
        code, strategy=strat, start=start, end=end,
        initial_cash=int(cash), metric=metric,
    )

    if not best_result:
        click.echo("优化失败")
        return

    click.echo(f"\n✅ 最优参数: {best_params}")
    click.echo(f"   总收益率: {best_result['total_return_pct']}%")
    click.echo(f"   年化收益: {best_result['annual_return_pct']}%")
    click.echo(f"   最大回撤: {best_result['max_drawdown_pct']}%")
    click.echo(f"   夏普比率: {best_result['sharpe_ratio']}")
    click.echo(f"   交易次数: {best_result['total_trades']}")
    click.echo(f"   胜率:     {best_result['win_rate_pct']}%")
    click.echo(f"   共测试 {best_result.get('_total_tested', 0)} 组参数")

    # 对比默认参数
    click.echo(f"\n📊 vs 默认参数:")
    bench = benchmark_compare(code, strat, start, end, int(cash))
    click.echo(f"   优化前收益: {bench['strategy_return']}%  →  优化后: {best_result['total_return_pct']}%")
    click.echo(f"   vs 买入持有: {bench['buy_hold_return']}%  (超额: {bench['excess_return']}%)")


# ── portfolio ─────────────────────────────────────────────

@cli.command()
@click.option("--codes", required=True, help="股票代码，逗号分隔，如 000001,600519,300750")
@click.option("--strategy", "strat", default="sma_cross",
              type=click.Choice(["sma_cross", "rsi", "buy_hold", "macd", "bollinger",
                                 "ma_align", "turtle", "vol_breakout", "mean_revert",
                                 "kdj", "cci", "williams_r", "donchian", "three_bar"]),
              help="策略名称")
@click.option("--start", default="20200101", help="起始日期")
@click.option("--end", default=None, help="结束日期")
@click.option("--cash", default=100000, help="初始资金")
def portfolio(codes, strat, start, end, cash):
    """多股组合回测"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    click.echo(f"\n📊 组合回测: {len(code_list)} 只股票, 策略={strat}")

    try:
        result = portfolio_backtest(code_list, strategy=strat, start=start, end=end,
                                    initial_cash=int(cash))
    except ValueError as e:
        click.echo(f"错误: {e}")
        return

    click.echo(f"\n{'='*50}")
    click.echo(f"  组合回测结果")
    click.echo(f"{'='*50}")
    click.echo(f"  股票池:   {', '.join(result['codes'])} ({result['n_stocks']} 只)")
    click.echo(f"  总收益率: {result['total_return_pct']}%")
    click.echo(f"  年化收益: {result['annual_return_pct']}%")
    click.echo(f"  最大回撤: {result['max_drawdown_pct']}%")
    click.echo(f"  夏普比率: {result['sharpe_ratio']}")
    click.echo(f"  交易次数: {result['total_trades']}")
    click.echo(f"  胜率:     {result['win_rate_pct']}%")


# ── rolling ───────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--strategy", "strat", default="sma_cross",
              type=click.Choice(["sma_cross", "rsi", "macd", "bollinger", "ma_align",
                                 "turtle", "vol_breakout", "mean_revert", "kdj", "cci"]),
              help="策略名称")
@click.option("--start", default="20200101", help="起始日期")
@click.option("--end", default=None, help="结束日期")
@click.option("--train-years", default=2, help="训练窗口年数")
@click.option("--test-months", default=3, help="测试窗口月数")
@click.option("--cash", default=100000, help="初始资金")
def rolling(code, strat, start, end, train_years, test_months, cash):
    """滚动窗口回测 — 样本外验证防过拟合"""
    click.echo(f"\n🔁 滚动回测: {code} {strat} (训练{train_years}年/测试{test_months}月)")

    try:
        windows = rolling_backtest(code, strategy=strat, start=start, end=end,
                                   train_years=int(train_years),
                                   test_months=int(test_months),
                                   initial_cash=int(cash))
    except ValueError as e:
        click.echo(f"错误: {e}")
        return

    click.echo(f"\n{'='*75}")
    click.echo(f"窗口  {'训练区间':<22} {'测试区间':<22} {'策略收益':>8} {'基准':>8} {'超额':>8} {'夏普':>6}")
    click.echo(f"{'='*75}")
    wins = []
    for i, w in enumerate(windows):
        wins.append(w["excess_return"])
        click.echo(f"{i+1:>4}  {w['train_period']:<22} {w['test_period']:<22} "
                   f"{w['strategy_return']:>8.2f} {w['buy_hold_return']:>8.2f} "
                   f"{w['excess_return']:>8.2f} {w['strategy_sharpe']:>6.2f}")
    click.echo(f"{'='*75}")

    win_count = sum(1 for w in wins if w > 0)
    avg_excess = sum(wins) / len(wins) if wins else 0
    click.echo(f"\n📊 共 {len(windows)} 个窗口 | 跑赢 {win_count}/{len(windows)} | 平均超额: {avg_excess:+.2f}%")


# ── benchmark ─────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--strategy", "strat", default="macd",
              type=click.Choice(["sma_cross", "rsi", "buy_hold", "macd", "bollinger",
                                 "ma_align", "turtle", "vol_breakout", "mean_revert",
                                 "kdj", "cci", "williams_r", "donchian", "three_bar"]),
              help="策略名称")
@click.option("--start", default="20200101", help="起始日期")
@click.option("--end", default=None, help="结束日期")
@click.option("--cash", default=100000, help="初始资金")
def benchmark(code, strat, start, end, cash):
    """策略 vs 买入持有 基准对比"""
    result = benchmark_compare(code, strat, start, end, int(cash))
    excess = result["excess_return"]
    tag = "✅ 跑赢" if excess > 0 else ("❌ 跑输" if excess < 0 else "➖ 持平")

    click.echo(f"""
╔══════════════════════════════════════════╗
║  {result['code']}  {result['strategy']} vs 买入持有(基准)
╠══════════════════════════════════════════╣
║          策略        买入持有      超额
║  收益    {result['strategy_return']:>8.2f}%  {result['buy_hold_return']:>8.2f}%  {excess:>8.2f}%  {tag}
║  夏普    {result['strategy_sharpe']:>8.2f}   {result['buy_hold_sharpe']:>8.2f}
║  回撤    {result['strategy_mdd']:>8.2f}%  {result['buy_hold_mdd']:>8.2f}%
║  区间: {result['period']}
╚══════════════════════════════════════════╝
""")



@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--name", "factor_name", default="momentum",
              type=click.Choice(["momentum", "volatility", "turnover", "volume_ratio"]),
              help="因子名称")
@click.option("--period", default=20, help="计算周期")
@click.option("--ic", is_flag=True, help="同时计算 IC 分析")
def factor(code, factor_name, period, ic):
    """计算因子值"""
    fname_map = {
        "momentum": "动量", "volatility": "波动率",
        "turnover": "换手率", "volume_ratio": "量比"
    }
    df = calc_factor(code, factor_name, period=period)
    if df is None or df.empty:
        click.echo("因子计算失败，数据不足")
        return

    name_cn = fname_map.get(factor_name, factor_name)
    click.echo(f"\n{code} {name_cn}因子（最近10个交易日）")
    click.echo(df.tail(10).to_string(index=False))

    if ic:
        result = factor_ic(code, factor_name, forward_period=5, period=period)
        if "error" not in result:
            click.echo(f"\nIC 分析（前向5日收益）:")
            click.echo(f"  IC 均值:   {result['ic_mean']}")
            click.echo(f"  IC 标准差: {result['ic_std']}")
            click.echo(f"  IC_IR:     {result['ic_ir']}")
            click.echo(f"  IC 胜率:   {result['ic_win_rate']}")
            click.echo(f"  数据点:    {result['data_points']}")


# ── screen ────────────────────────────────────────────────

@cli.command()
@click.option("--pe-max", default=None, type=float, help="PE 上限")
@click.option("--pe-min", default=None, type=float, help="PE 下限（排除亏损）")
@click.option("--pb-max", default=None, type=float, help="PB 上限")
@click.option("--change-min", default=None, type=float, help="涨跌幅下限(%)")
@click.option("--change-max", default=None, type=float, help="涨跌幅上限(%)")
@click.option("--turnover-min", default=None, type=float, help="换手率下限(%)")
@click.option("--turnover-max", default=None, type=float, help="换手率上限(%)")
@click.option("--ma-align/--no-ma-align", default=None, help="均线多头排列(MA5>MA10>MA20)")
@click.option("--near-high", default=None, type=int, help="接近 N 日内最高价")
@click.option("--vol-ratio-min", default=None, type=float, help="量比下限（倍）")
@click.option("--up-days", default=None, type=str, help="近N日至少M日上涨，格式: N,M")
@click.option("--roe-min", default=None, type=float, help="ROE 下限(%，从财报计算)")
@click.option("--revenue-growth", default=None, type=float, help="营收增速下限(%)")
@click.option("--profit-growth", default=None, type=float, help="利润增速下限(%)")
@click.option("--industry", default=None, type=str, help="行业名称，如 白酒、半导体")
@click.option("--template", "tpl", default=None,
              type=click.Choice(["value", "momentum", "quality", "breakout", "oversold", "growth"]),
              help="预置筛选模板")
@click.option("--rank", "do_rank", is_flag=True, help="多因子打分排名模式")
@click.option("--top", default=20, help="显示前 N 条")
def screen_cmd(pe_max, pe_min, pb_max, change_min, change_max, turnover_min, turnover_max,
               ma_align, near_high, vol_ratio_min, up_days, roe_min, revenue_growth,
               profit_growth, industry, tpl, do_rank, top):
    """多条件股票筛选 — 技术面 + 基本面 + 多因子打分"""

    if do_rank:
        df = rank_screen(top=top)
        if df is not None and not df.empty:
            click.echo(f"\n多因子打分排名 Top {len(df)}:")
            click.echo(df.to_string(index=False))
        else:
            click.echo("无结果")
        return

    if tpl:
        tpl_map = {
            "value": value_screen,
            "momentum": momentum_screen,
            "quality": quality_screen,
            "breakout": breakout_screen,
            "oversold": oversold_screen,
            "growth": growth_screen,
        }
        fn = tpl_map[tpl]
        df = fn(top=top) if tpl in ("breakout", "oversold", "growth") else fn()
    else:
        conditions = {}
        if pe_max is not None:
            conditions["pe_max"] = pe_max
        if pe_min is not None:
            conditions["pe_min"] = pe_min
        if pb_max is not None:
            conditions["pb_max"] = pb_max
        if change_min is not None:
            conditions["change_min"] = change_min
        if change_max is not None:
            conditions["change_max"] = change_max
        if turnover_min is not None:
            conditions["turnover_min"] = turnover_min
        if turnover_max is not None:
            conditions["turnover_max"] = turnover_max
        if ma_align:
            conditions["ma_align"] = True
        if near_high:
            conditions["near_high"] = near_high
        if vol_ratio_min:
            conditions["vol_ratio_min"] = vol_ratio_min
        if up_days:
            conditions["up_days"] = up_days
        if roe_min:
            conditions["roe_min"] = roe_min
        if revenue_growth:
            conditions["revenue_growth"] = revenue_growth
        if profit_growth:
            conditions["profit_growth"] = profit_growth
        if industry:
            conditions["industry"] = industry
        df = screen(conditions if conditions else None)

    if df is None or df.empty:
        click.echo("无符合条件的股票")
        return

    click.echo(f"\n筛选结果: {len(df)} 只（显示前 {min(top, len(df))} 只）")
    show_cols = ["code", "name", "price", "change_pct", "pe", "pb", "turnover"]
    available = [c for c in show_cols if c in df.columns]
    click.echo(df[available].head(top).to_string(index=False))


# ── dashboard ─────────────────────────────────────────────

@cli.command()
def dashboard():
    """启动 Streamlit 可视化看板"""
    import subprocess
    import sys
    import os
    app_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])


# ── advice ────────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
def advice(code):
    """获取交易建议（买入价/止盈价/止损价）"""
    result = get_advice(code)
    if "error" in result:
        click.echo(f"错误: {result['error']}")
        return

    confidence_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    conf = result["confidence"]

    click.echo(f"""
╔══════════════════════════════════════════╗
║  {result['code']} {result['name']}  交易建议
╠══════════════════════════════════════════╣
║  当前价格:    {result['current_price']:>10.2f} 元
║  趋势判断:    {result['trend']:>10}
║  信心等级:    {confidence_color.get(conf, '⚪')} {conf}
╠══════════════════════════════════════════╣
║  🎯 建议买入:  {result['buy_price']:>10.2f} 元
║  🏁 止盈目标:  {result['take_profit']:>10.2f} 元
║  🛑 止损价位:  {result['stop_loss']:>10.2f} 元
║  📊 盈亏比:    {result['risk_reward']:>10.1f} : 1
╠══════════════════════════════════════════╣
║  技术指标:
║    MA20:  {result['ma20']:>8.2f}   布林上轨: {result['bb_upper']:>8.2f}
║    MA60:  {result['ma60']:>8.2f}   布林下轨: {result['bb_lower']:>8.2f}
║    ATR14: {result['atr']:>8.2f}   20日高:  {result['swing_high_20']:>8.2f}
║    20日低: {result['swing_low_20']:>8.2f}
╠══════════════════════════════════════════╣""")
    for reason in result["reasons"]:
        click.echo(f"║  · {reason}")
    click.echo("╚══════════════════════════════════════════╝")


# ── scan ──────────────────────────────────────────────────

@cli.command()
@click.option("--codes", default=None, help="股票代码逗号分隔，默认取持仓+关注列表")
@click.option("--strategy", "strat", default="macd", help="参考策略")
@click.option("--top", default=10, help="显示前 N 条信号")
def scan(codes, strat, top):
    """扫描信号 — 对关注列表生成买卖建议"""
    if codes:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
    else:
        # 默认取实时行情前 20 只 + 当前持仓
        from database import query, table_exists
        code_list = []
        if table_exists("realtime"):
            df = query("SELECT code FROM realtime LIMIT 20")
            code_list = df["code"].tolist() if not df.empty else []
        if table_exists("positions"):
            df = query("SELECT code FROM positions")
            for c in df["code"].tolist():
                if c not in code_list:
                    code_list.append(c)

    click.echo(f"\n🔍 扫描 {len(code_list)} 只股票（策略={strat}）...")
    df = scan_signals(code_list, strategy=strat, top=top)

    if df.empty:
        click.echo("无信号")
        return

    for _, r in df.iterrows():
        icon = {"buy": "🟢 买入", "sell": "🔴 卖出", "hold": "🟡 观望"}.get(r["signal"], "?")
        click.echo(f"\n{icon} {r['code']} {r['name']}  {r['price']:.2f}")
        click.echo(f"   趋势: {r['trend']} | 信心: {r['confidence']} | 盈亏比: {r['risk_reward']}:1")
        click.echo(f"   建议买 {r['buy_price']:.2f} / 止盈 {r['take_profit']:.2f} / 止损 {r['stop_loss']:.2f}")
        click.echo(f"   理由: {r['reason']}")


# ── position ──────────────────────────────────────────────

@cli.command()
def position():
    """查看当前持仓"""
    pf = Portfolio()
    summary = pf.get_summary()
    positions = pf.get_positions()

    click.echo(f"\n📊 交易概览")
    click.echo(f"   累计交易: {summary['total_trades']} 笔")
    click.echo(f"   胜率:     {summary['win_rate']}%")
    click.echo(f"   已实现盈亏: {summary['total_pnl']:+,.2f}")
    click.echo(f"   未实现盈亏: {summary['unrealized_pnl']:+,.2f}")
    click.echo(f"   当前持仓: {summary['open_positions']} 只")

    if not positions.empty:
        click.echo(f"\n{'代码':<8} {'名称':<10} {'买入价':>8} {'现价':>8} {'数量':>6} {'盈亏':>10} {'盈亏%':>8}")
        click.echo("-" * 64)
        for _, p in positions.iterrows():
            pnl = p.get("pnl", 0) or 0
            pnl_pct = p.get("pnl_pct", 0) or 0
            cp = p.get("current_price", 0) or 0
            click.echo(f"{p['code']:<8} {p['name']:<10} {p['buy_price']:>8.2f} {cp:>8.2f} "
                       f"{int(p['quantity']):>6} {pnl:>+10.2f} {pnl_pct:>+8.2f}%")


# ── trade ─────────────────────────────────────────────────

@cli.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--action", type=click.Choice(["buy", "sell"]), required=True, help="买卖方向")
@click.option("--price", type=float, required=True, help="成交价")
@click.option("--quantity", type=int, default=100, help="数量(股)")
@click.option("--stop-loss", type=float, default=None, help="止损价(买入时)")
@click.option("--take-profit", type=float, default=None, help="止盈价(买入时)")
def trade_cmd(code, action, price, quantity, stop_loss, take_profit):
    """记录交易（买入/卖出）"""
    pf = Portfolio()

    if action == "buy":
        from database import query
        name = code
        rt = query("SELECT name FROM realtime WHERE code=?", [code])
        if not rt.empty:
            name = rt.iloc[0]["name"]
        pf.open_position(code, name, price, quantity, stop_loss, take_profit)
        click.echo(f"✅ 买入 {code} {name} {price:.2f}×{quantity}股")
        if stop_loss:
            click.echo(f"   止损: {stop_loss:.2f}  止盈: {take_profit or '--'}")
    else:
        result = pf.close_position(code, price)
        if result:
            click.echo(f"✅ 卖出 {code} 盈亏: {result['pnl']:+,.2f} ({result['pnl_pct']:+.2f}%) "
                       f"持有 {result['hold_days']} 天")
        else:
            click.echo(f"⚠️ {code} 不在持仓中")


# ── sim ───────────────────────────────────────────────────

@cli.group()
def sim():
    """模拟交易账户管理"""
    pass


@sim.command()
@click.option("--cash", default=100000, help="初始资金")
def start(cash):
    """初始化模拟账户"""
    acc = SimAccount()
    acc.reset(cash)
    click.echo(f"✅ 模拟账户已初始化，初始资金: {cash:,.0f}")


@sim.command()
def status():
    """模拟账户状态"""
    acc = SimAccount()
    s = acc.get_summary()
    click.echo(f"""
╔══════════════════════════════════╗
║  📊 模拟账户状态
╠══════════════════════════════════╣
║  初始资金: {s['initial_cash']:>16,.0f}
║  可用现金: {s['cash']:>16,.2f}
║  持仓市值: {s['market_value']:>16,.2f}
║  总资产:   {s['total_value']:>16,.2f}
║  浮动盈亏: {s['total_pnl']:>+16,.2f}
║  总收益率: {s['total_return']:>+15.2f}%
║  持仓数:   {s['positions']:>16}
╚══════════════════════════════════╝
""")

    positions = acc.get_positions()
    if not positions.empty:
        click.echo("持仓明细:")
        click.echo(f"{'代码':<8} {'名称':<10} {'成本':>8} {'现价':>8} {'数量':>6} {'盈亏':>10}")
        for _, p in positions.iterrows():
            click.echo(f"{p['code']:<8} {p['name']:<10} {p['avg_cost']:>8.2f} "
                       f"{p.get('current_price',0) or 0:>8.2f} {int(p['quantity']):>6} "
                       f"{(p.get('pnl',0) or 0):>+10.2f}")


@sim.command()
@click.option("--code", required=True, help="股票代码")
@click.option("--direction", type=click.Choice(["buy", "sell"]), required=True)
@click.option("--quantity", type=int, required=True)
@click.option("--order-type", type=click.Choice(["market", "limit"]), default="market")
@click.option("--price", type=float, default=None, help="限价（limit类型必填）")
def order(code, direction, quantity, order_type, price):
    """提交模拟订单"""
    if order_type == "limit" and not price:
        click.echo("❌ 限价单需要指定 --price")
        return
    acc = SimAccount()
    result = acc.submit_order(code, direction, quantity, order_type, price)
    if "error" in result:
        click.echo(f"❌ {result['error']}")
    else:
        click.echo(f"✅ 订单已提交: {direction} {code} {quantity}股 "
                   f"({'市价' if order_type=='market' else f'限价{price}'}) "
                   f"状态: {result.get('status','')}")


@sim.command()
@click.option("--type", "status_filter", default=None,
              type=click.Choice(["pending", "filled", "cancelled"]),
              help="按状态筛选")
def orders(status_filter):
    """查看订单列表"""
    acc = SimAccount()
    df = acc.get_orders(status_filter)
    if df.empty:
        click.echo("无订单")
        return
    pending_n = len(df[df["status"] == "pending"]) if not df.empty else 0
    if pending_n:
        click.echo(f"\n⏳ {pending_n} 笔待成交 — 用 sim cancel --id <ID> 撤单")
    click.echo(f"\n{'ID':<5} {'代码':<8} {'方向':<6} {'数量':>6} {'价格':>8} {'状态':<10} {'成交价':>8}")
    click.echo("-" * 60)
    for _, o in df.iterrows():
        fp = o.get("fill_price") or 0
        st = o["status"]
        icon = {"pending": "⏳", "filled": "✅", "cancelled": "✕"}.get(st, "?")
        hint = " ← sim cancel --id " + str(int(o['id'])) if st == "pending" else ""
        click.echo(f"{int(o['id']):<5} {o['code']:<8} {o['direction']:<6} {int(o['quantity']):>6} "
                   f"{o.get('price') or 0:>8.2f} {icon}{st:<9} {fp:>8.2f}{hint}")


@sim.command()
@click.option("--id", "order_id", type=int, required=True, help="订单ID")
def cancel(order_id):
    """撤单 — 取消 pending 状态的订单"""
    acc = SimAccount()
    acc.cancel_order(order_id)
    click.echo(f"✅ 订单 {order_id} 已取消")


@sim.command()
def eod():
    """日终处理 — 撮合所有pending限价单"""
    acc = SimAccount()
    acc.process_eod()
    click.echo("✅ 日终撮合完成")


# ── status ────────────────────────────────────────────────

@cli.command()
def status():
    """查看数据库状态"""
    tables = ["realtime", "history", "financial", "fund_flow", "lhb", "north_flow"]
    for t in tables:
        exists = table_exists(t)
        if exists:
            df = query(f"SELECT COUNT(*) as cnt FROM {t}")
            cnt = df.iloc[0, 0]
            click.echo(f"  {t:15s}  {cnt:>8d} 条")
        else:
            click.echo(f"  {t:15s}  (无数据)")


if __name__ == "__main__":
    cli()
