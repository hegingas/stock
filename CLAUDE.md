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
python main.py industry                    # 东方财富行业分类（约2-3分钟）

# 策略回测
python main.py backtest --code 000559 --strategy macd      # 单股回测（14种策略）
python main.py optimize --code 000559 --strategy sma_cross # 参数网格搜索优化
python main.py portfolio --codes "000001,600519"           # 多股组合回测
python main.py benchmark --code 000559 --strategy cci      # 策略 vs 买入持有基准对比
python main.py rolling --code 000559 --strategy sma_cross  # 滚动窗口样本外验证

# 因子/筛选/建议
python main.py factor --code 000559 --name momentum --ic   # 单股因子计算+IC分析
python main.py screen --pe-max 20 --ma-align --top 20      # 多条件筛选（自动过滤ST）
python main.py screen --industry 白酒 --pe-max 30           # 行业+条件筛选
python main.py screen --template breakout                  # 模板筛选
python main.py screen --rank --top 30                      # 多因子排名
python main.py advice --code 000559                        # 交易建议（买入/止盈/止损）

# 交易
python main.py scan --codes "000559,600519"                 # 扫描信号（买入/卖出/观望）
python main.py position                                     # 查看持仓+盈亏
python main.py trade --code 000559 --action buy --price 16.50 --quantity 100  # 记录交易
python main.py sim start --cash 500000                      # 初始化模拟账户
python main.py sim order --code 000559 --direction buy --quantity 1000  # 模拟下单
python main.py sim order --code 000559 --direction buy --quantity 100 --order-type limit --price 15.00  # 限价单
python main.py sim orders --type pending                    # 查看待成交订单
python main.py sim cancel --id 3                            # 撤单
python main.py sim status                                   # 模拟账户状态

# 看板与工具
python main.py dashboard                   # 启动 Streamlit 看板
python main.py export --table realtime --format csv         # 导出 CSV/Excel
python main.py status                      # 数据库状态

# 测试
python -m pytest tests/ -v                 # 67 tests
```

## Architecture

**Seven layers:** CLI (`main.py`, 20+ commands) → Dashboard (`dashboard/app.py`, 7 tabs) → Trading (`trading/`, 3 modules) → Analytics (`analytics/`, 6 modules) → Fetchers (`fetchers/`, 5 fetchers) → Persistence (`database.py`, SQLite WAL) → Export (`exporters.py`, CSV/Excel).

### Analytics modules

| Module | Key exports | Purpose |
|--------|------------|---------|
| `backtest.py` | `run_backtest`, `optimize_backtest`, `portfolio_backtest`, `benchmark_compare`, `rolling_backtest`, `STRATEGIES`, `PARAM_GRIDS` | 14 strategies + grid-search + portfolio + benchmark + rolling window out-of-sample validation. `run_backtest(return_equity=True)` returns daily equity curve for plotting |
| `factors.py` | `calc_factor`, `factor_ic`, `cross_section_ic`, `quantile_returns` | Single-stock factor calc + IC + cross-sectional IC + quantile group returns |
| `screener.py` | `screen`, `rank_screen`, 6 templates, 16 filters | 16 filters (tech/fundamental/valuation/industry) + multi-factor ranking. Auto-excludes ST/\*ST/N/PT/退 |
| `position.py` | `kelly_fraction`, `volatility_sizer`, `fixed_fraction`, `equal_weight`, `adaptive_sizer` | 5 position sizing methods |
| `metrics.py` | `sharpe_ratio`, `max_drawdown`, `annual_return`, `win_rate`, `profit_loss_ratio`, `calmar_ratio` | Pure functions |
| `signal.py` | `get_advice` | Buy/stop-loss/take-profit via Bollinger+ATR+MA |

### Trading modules

| Module | Key exports | Purpose |
|--------|------------|---------|
| `portfolio.py` | `Portfolio` | Manual trade recording: positions, trade history, P&L summary. Tables: `positions`(code/buy_price/qty/sl/tp), `trades`(buy/sell/pnl/hold_days) |
| `signal_engine.py` | `scan_signals` | Batch scan stocks → buy/sell/hold signals based on advice + backtest results |
| `sim_account.py` | `SimAccount` | Simulated trading: cash/positions/orders with auto-fill. Market orders fill immediately at realtime price; limit orders fill via `process_eod()` when price crosses. Tables: `sim_account`, `sim_orders`, `sim_positions`, `sim_trades` |

### Fetchers

| Module | Source | Table(s) |
|--------|--------|----------|
| `realtime.py` | 东方财富 | `realtime` |
| `history.py` | 东方财富 | `history` |
| `financial.py` | 新浪财经 | `financial` |
| `fund_flow.py` | 东方财富 | `fund_flow`, `lhb`, `north_flow` |
| `industry.py` | 东方财富 | `industry` (code, name, industry) |

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
| `kdj` | swing | period=9, period_d=3 |
| `cci` | swing | period=20 |
| `williams_r` | swing | period=14 |
| `donchian` | swing | period=20 |
| `mean_revert` | swing | period=20, devfactor=2.0 |
| `three_bar` | swing | (no params) |
| `buy_hold` | baseline | (no params) |

### Dashboard (6 tabs + sidebar)

- **Tab 1** — market overview: stats cards, volume histogram, amount Top 10, gainer/loser Top 10 (ST filtered)
- **Tab 2** — stock detail: 7 timeframes (分时/5分钟/日线/周线/月线/半年线/年线), MACD/KDJ checkbox overlays, fund flow, financials, tech indicator panel. 分时 mode: price %change line + VWAP + yesterday close baseline. 5-minute mode: candlestick from AKShare minute API
- **Tab 3** — backtest: single-stock + equity curve chart (strategy vs buy&hold) + benchmark + optimize + portfolio modes
- **Tab 4** — factor: line chart + IC metrics
- **Tab 5** — screener: condition/template/ranking modes, industry filter
- **Tab 6** — advice: buy/take-profit/stop-loss + confidence
- **Tab 7** — trading: simulated account (order/position/P&L) + manual trade recording + signal scanning
- **Sidebar** — fuzzy search (code/name) + one-click data fetch + stock card (price/change/market-cap/PE/PB/turnover)

### Key design decisions

- `config.py` auto-fixes Windows terminal encoding; `DB_PATH` accessed via `config.DB_PATH`
- `database.py` uses `import config as _config` so fixture overrides work in tests; `init_db()` auto-migrates realtime columns via `ALTER TABLE ADD COLUMN`
- `realtime` table v2 includes: `total_mv`, `circ_mv`, `volume_ratio`, `change_60d`, `change_ytd`, `change_amt` (fetched from 东方财富 spot API)
- K-line: integer x-axis (no gaps), dynamic rows (2-4), 分时 mode uses AKShare minute API with %change y-axis + VWAP
- `FundFlowFetcher._fetch()` raises `NotImplementedError` — use `fetch_individual`/`fetch_north_flow`/`fetch_lhb` directly
- All monetary values stored as-is in DB; divided by 1e8 (亿) or 1e4 (万) only at display time
- `pd.to_numeric(..., errors="coerce")` used before arithmetic on DB values
- `_ST_PATTERNS = ["ST", "*ST", "N", "PT", "退"]` filters at data-load level in screener and dashboard

### Stock code convention
Shanghai: `6xxxxx` (600519 茅台). Shenzhen: `0xxxxx` (000001 平安银行), `3xxxxx` (300750 宁德时代).
