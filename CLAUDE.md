# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 数据抓取
python main.py realtime                    # 全市场实时行情（约60-90秒）
python main.py history --code 000001       # 个股历史K线（日/周/月，前复权）
python main.py financial --code 600519 --type income  # 利润表/balance/cashflow
python main.py fund-flow --code 000001     # 个股资金流向
python main.py lhb                         # 龙虎榜（默认昨天）
python main.py north-flow                  # 北向资金

# 策略回测
python main.py backtest --code 000559 --strategy macd      # 单股回测（14种策略）
python main.py optimize --code 000559 --strategy sma_cross # 参数网格搜索优化
python main.py portfolio --codes "000001,600519"           # 多股组合回测
python main.py benchmark --code 000559 --strategy cci      # 策略 vs 买入持有基准对比

# 因子/筛选/建议
python main.py factor --code 000559 --name momentum --ic   # 因子计算+IC分析
python main.py screen --pe-max 20 --ma-align --top 20      # 多条件筛选（自动过滤ST）
python main.py screen --template breakout                  # 模板筛选
python main.py screen --rank --top 30                      # 多因子排名
python main.py advice --code 000559                        # 交易建议（买入/止盈/止损）

# 看板与工具
python main.py dashboard                   # 启动 Streamlit 看板
python main.py export --table realtime --format csv         # 导出 CSV/Excel
python main.py status                      # 数据库状态
```

## Architecture

**Six layers:** CLI (`main.py`, 16 commands) → Dashboard (`dashboard/app.py`, 6 tabs) → Analytics (`analytics/`, 6 modules) → Fetchers (`fetchers/`, 4 fetchers) → Persistence (`database.py`, SQLite WAL) → Export (`exporters.py`, CSV/Excel).

### Analytics modules

| Module | Key exports | Purpose |
|--------|------------|---------|
| `backtest.py` | `run_backtest`, `optimize_backtest`, `portfolio_backtest`, `benchmark_compare`, `STRATEGIES`, `PARAM_GRIDS` | 14 strategies + grid-search optimization + multi-stock portfolio + benchmark vs buy&hold |
| `factors.py` | `calc_factor`, `factor_ic` | momentum/volatility/turnover/volume_ratio + rolling IC |
| `screener.py` | `screen`, `rank_screen`, 6 templates | 15 filters across tech/fundamental/valuation + multi-factor ranking. Auto-excludes ST/\*ST/N/PT/退 stocks via `_ST_PATTERNS` in `_all_stocks()` |
| `position.py` | `kelly_fraction`, `volatility_sizer`, `fixed_fraction`, `equal_weight`, `adaptive_sizer` | Kelly criterion, volatility-adjusted, fixed risk, equal weight, adaptive sizing |
| `metrics.py` | `sharpe_ratio`, `max_drawdown`, `annual_return`, `win_rate`, `profit_loss_ratio`, `calmar_ratio` | Pure functions, no external deps |
| `signal.py` | `get_advice` | Buy/stop-loss/take-profit recommendations via Bollinger+ATR+MA |

### Backtest strategies (14)

| Name | Type | Key params |
|------|------|-----------|
| `sma_cross` | trend | fast=5, slow=20 |
| `macd` | trend | fast=12, slow=26, signal=9 |
| `ma_align` | trend | ma_short=5, ma_mid=10, ma_long=20 |
| `turtle` | trend | entry_period=20, exit_period=10 |
| `bollinger` | trend | period=20, devfactor=2.0 |
| `vol_breakout` | trend | price_period=20, vol_factor=1.5 |
| `rsi` | swing | period=14, oversold=30, overbought=70 |
| `kdj` | swing | period=9, period_d=3, oversold=20, overbought=80 |
| `cci` | swing | period=20, oversold=-100, overbought=100 |
| `williams_r` | swing | period=14, oversold=-80, exit=-20 |
| `donchian` | swing | period=20 |
| `mean_revert` | swing | period=20, devfactor=2.0 |
| `three_bar` | swing | (no params — 3-bar reversal pattern) |
| `buy_hold` | baseline | (no params) |

`PARAM_GRIDS` defines optimization search space for each strategy. Strategies without params (`three_bar`, `buy_hold`) are skipped in `optimize`.

### Backtest data flow
1. `_load_data(code, start, end)` — fetches OHLCV from SQLite `history` table
2. `bt.feeds.PandasData` — wraps DataFrame for Backtrader
3. `cerebro.addsizer(bt.sizers.PercentSizer, percents=95)` — 95% position per trade (single stock)
4. `cerebro.addanalyzer(bt.analyzers.TimeReturn)` — daily returns for Sharpe/MDD calculation
5. Portfolio mode: one data feed per stock, `weight_per_stock = 95/N` equal-weight allocation

### Dashboard (6 tabs + sidebar)

- **Tab 1 行情总览** — market stats, volume distribution, top gainers/losers (ST filtered)
- **Tab 2 个股详情** — multi-timeframe K-line (日/5日/10日/周/月/半年/年), 主力吸筹 indicator, fund flow, financials, tech indicators panel. K-line uses integer index (no holiday gaps), MA5/MA20/MA60 overlays
- **Tab 3 策略回测** — single-stock backtest + benchmark compare + parameter optimization + portfolio
- **Tab 4 因子分析** — factor line chart + IC metrics
- **Tab 5 股票筛选** — condition/template/ranking modes (ST filtered)
- **Tab 6 交易建议** — buy/take-profit/stop-loss + confidence level
- **Sidebar** — stock search (code/name fuzzy match) + one-click data fetch (history/financial/fund-flow/realtime)

### Key design decisions

- `config.py` auto-fixes Windows terminal encoding via `sys.stdout.reconfigure(encoding="utf-8")`
- `database.py` `clear_code()` deletes existing records per stock before re-fetch to avoid UNIQUE constraint errors
- `FundFlowFetcher` has three methods (`fetch_individual`/`fetch_north_flow`/`fetch_lhb`) mapping to three tables; its `_fetch()` raises `NotImplementedError`
- Sina financial API returns Chinese column names without `code`/`name` columns — `FinancialFetcher` adds them manually
- All monetary values stored as-is in DB; divided by 1e8 (亿) or 1e4 (万) only at display time
- `pd.to_numeric(..., errors="coerce")` used before arithmetic on DB values to handle type mismatches
- ST/\*ST/N/PT/退 stocks filtered by `_ST_PATTERNS` at data-load level in screener and dashboard

### Stock code convention
Shanghai: `6xxxxx` (e.g., 600519 茅台). Shenzhen: `0xxxxx` (主板, e.g., 000001), `3xxxxx` (创业板, e.g., 300750). `FundFlowFetcher` uses prefix to set `market="sh"/"sz"`.
