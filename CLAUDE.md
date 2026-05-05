# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python main.py realtime                  # 抓取全市场实时行情
python main.py history --code 000001     # 抓取个股历史K线
python main.py financial --code 600519 --type income   # 利润表 (balance/cashflow)
python main.py fund-flow --code 000001   # 个股资金流向
python main.py lhb                       # 龙虎榜（默认昨天）
python main.py north-flow                # 北向资金
python main.py export --table realtime --format csv   # 导出 CSV/Excel
python main.py status                    # 查看各表数据量
```

所有 fetch 命令支持 `--save/--no-save`（默认存档）和 `--export-csv`（同时导出）。

## Architecture

**Layered architecture** with four tiers:

1. **CLI layer** (`main.py`) — click command group, wires commands to fetchers
2. **Fetcher layer** (`fetchers/`) — AKShare API wrappers, one class per data type
3. **Persistence layer** (`database.py`) — SQLite via pandas `.to_sql()`, with `save_dataframe()` / `query()` helpers
4. **Export layer** (`exporters.py`) — reads from DB, writes CSV (utf-8-sig) or Excel via openpyxl

**Key design decisions:**

- `BaseFetcher` (`fetchers/base.py`) defines the template: `_fetch()` returns a DataFrame, `fetch()` adds logging, `fetch_and_save()` auto-saves. Most CLI commands bypass `fetch_and_save()` and call `_fetch()` + `save_dataframe()` directly for finer control.
- `FundFlowFetcher` breaks the pattern — it has three separate entry points (`fetch_individual`, `fetch_north_flow`, `fetch_lhb`) and its `_fetch()` raises `NotImplementedError`. This is because it maps to three different SQLite tables (`fund_flow`, `north_flow`, `lhb`).
- Column name mapping: AKShare returns Chinese column names; each fetcher renames them to English with a fixed `keep_cols` whitelist filtered to `available` columns (some API versions differ).
- The Sina financial API (`stock_financial_report_sina`) doesn't return `code`/`name` columns — `FinancialFetcher` sets `code` from the input and fetches `name` via a separate `stock_individual_info_em` call.
- SQLite uses `PRAGMA journal_mode=WAL` for concurrent read/write safety. Tables use composite primary keys with `IF NOT EXISTS` creation (called on every CLI invocation via `init_db()` in the click group).
- `config.py` creates `data/` and `output/` directories on import — no manual setup needed.

**Stock code convention:** Shanghai codes start with `6` (e.g., 600519 茅台), Shenzhen codes start with `0`/`3` (e.g., 000001 平安银行, 300750 宁德时代). The `FundFlowFetcher` uses this prefix to determine the `market` parameter.
