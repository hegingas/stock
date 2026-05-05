import logging
import click
from database import init_db, save_dataframe, query, table_exists
from exporters import export
from fetchers import (
    RealtimeFetcher, HistoryFetcher, FinancialFetcher, FundFlowFetcher
)

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
