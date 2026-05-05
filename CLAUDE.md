# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 数据抓取
python main.py realtime                    # 全市场实时行情
python main.py history --code 000001       # 个股历史K线
python main.py financial --code 600519 --type income  # 利润表/balance/cashflow
python main.py fund-flow --code 000001     # 个股资金流向
python main.py lhb                         # 龙虎榜
python main.py north-flow                  # 北向资金

# 量化分析
python main.py backtest --code 000559 --strategy macd        # 策略回测（9种策略可选）
python main.py factor --code 000559 --name momentum --ic     # 因子计算+IC
python main.py screen --pe-max 20 --pb-max 2 --top 10        # 条件筛选
python main.py screen --template value                      # 模板筛选(value/momentum/quality)

# 看板与工具
python main.py dashboard                   # 启动 Streamlit 看板
python main.py export --table realtime --format csv         # 导出 CSV/Excel
python main.py status                      # 数据库状态
```

所有 fetch/backtest/factor/screen 命令支持 `--save/--no-save` 和 `--export-csv`。

## Architecture

**Six-layer architecture:**

1. **CLI layer** (`main.py`) — click command group, ~16 commands across fetch/analyze/export
2. **Dashboard layer** (`dashboard/app.py`) — Streamlit app with 5 tabs (行情总览/个股详情/回测/因子/筛选)
3. **Analytics layer** (`analytics/`) — backtest engine, factor computation, stock screener, performance metrics
4. **Fetcher layer** (`fetchers/`) — AKShare API wrappers, one class per data type
5. **Persistence layer** (`database.py`) — SQLite via pandas `.to_sql()`
6. **Export layer** (`exporters.py`) — CSV (utf-8-sig) / Excel via openpyxl

**Analytics module design:**

- `analytics/metrics.py` — pure functions (no external deps): sharpe_ratio, max_drawdown, annual_return, win_rate, profit_loss_ratio, calmar_ratio
- `analytics/backtest.py` — wraps Backtrader. `run_backtest(code, strategy, start, end, initial_cash)` loads data from SQLite history table, runs cerebro, returns dict with total_return/annual_return/max_drawdown/sharpe/win_rate. Built-in strategies: SmaCrossStrategy, RSIStrategy, BuyAndHoldStrategy in STRATEGIES dict.
- `analytics/factors.py` — `calc_factor(code, name, **params)` supports momentum/volatility/turnover/volume_ratio. `factor_ic()` computes rolling rank correlation with forward returns.
- `analytics/screener.py` — `screen(conditions: dict)` filters realtime table. PE/PB filters clamp to positive values only. ROE is estimated as PB/PE*100. Templates: value_screen, momentum_screen, quality_screen.

**Key design decisions:** (`fetchers/base.py`) defines the template: `_fetch()` returns a DataFrame, `fetch()` adds logging, `fetch_and_save()` auto-saves. Most CLI commands bypass `fetch_and_save()` and call `_fetch()` + `save_dataframe()` directly for finer control.
- `FundFlowFetcher` breaks the pattern — it has three separate entry points (`fetch_individual`, `fetch_north_flow`, `fetch_lhb`) and its `_fetch()` raises `NotImplementedError`. This is because it maps to three different SQLite tables (`fund_flow`, `north_flow`, `lhb`).
- Column name mapping: AKShare returns Chinese column names; each fetcher renames them to English with a fixed `keep_cols` whitelist filtered to `available` columns (some API versions differ).
- The Sina financial API (`stock_financial_report_sina`) doesn't return `code`/`name` columns — `FinancialFetcher` sets `code` from the input and fetches `name` via a separate `stock_individual_info_em` call.
- SQLite uses `PRAGMA journal_mode=WAL` for concurrent read/write safety. Tables use composite primary keys with `IF NOT EXISTS` creation (called on every CLI invocation via `init_db()` in the click group).
- `config.py` creates `data/` and `output/` directories on import — no manual setup needed.

**Stock code convention:** Shanghai codes start with `6` (e.g., 600519 茅台), Shenzhen codes start with `0`/`3` (e.g., 000001 平安银行, 300750 宁德时代). The `FundFlowFetcher` uses this prefix to determine the `market` parameter.
