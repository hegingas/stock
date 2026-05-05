# Stock — A股数据抓取工具

基于 [AKShare](https://github.com/akfamily/akshare) 的 A 股股票数据抓取工具，支持实时行情、历史K线、财务报表、资金流向等数据的采集，数据存入 SQLite 并支持导出 CSV/Excel。

> 数据来源于东方财富、新浪财经等公开接口，仅供学习参考，不构成投资建议。投资有风险，入市需谨慎。

## 安装

### Windows

```powershell
# 1. 安装 Python 3.10+（推荐从 Microsoft Store 或 python.org 下载）

# 2. 克隆项目
git clone git@github.com:hegingas/stock.git
cd stock

# 3. 创建虚拟环境（可选但推荐）
python -m venv venv
venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 终端编码（如遇中文乱码）
# 在 PowerShell / CMD 中执行：
chcp 65001
# 或者直接运行——项目已在 config.py 自动修复 UTF-8 编码
```

### macOS

```bash
# 1. 安装 Python 3.10+（推荐 Homebrew）
brew install python@3.12

# 2. 克隆项目
git clone git@github.com:hegingas/stock.git
cd stock

# 3. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

### Linux

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

git clone git@github.com:hegingas/stock.git
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### CentOS / RHEL / Fedora

```bash
# CentOS 7/8 需先启用 EPEL
sudo yum install epel-release -y       # CentOS 7
sudo dnf install epel-release -y       # CentOS 8+ / Fedora

sudo dnf install python3 python3-pip git -y

git clone git@github.com:hegingas/stock.git
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Arch Linux / Manjaro

```bash
sudo pacman -S python python-pip git

git clone git@github.com:hegingas/stock.git
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### openSUSE

```bash
sudo zypper install python3 python3-pip git

git clone git@github.com:hegingas/stock.git
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Alpine Linux

```bash
sudo apk add python3 py3-pip git

git clone git@github.com:hegingas/stock.git
cd stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 验证安装

```bash
python main.py status
# 输出:
#   realtime          0 条
#   history           0 条
#   ...
```

## 快速开始

### 数据抓取

```bash
# 查看数据库状态
python main.py status

# 抓取全市场实时行情（约 60~90 秒）
python main.py realtime

# 抓取个股历史K线
python main.py history --code 000001 --start 20250101 --end 20250505

# 抓取财务报表（利润表 / 资产负债表 / 现金流量表）
python main.py financial --code 600519 --type income

# 抓取资金流向 / 龙虎榜 / 北向资金
python main.py fund-flow --code 000559
python main.py lhb
python main.py north-flow

# 导出 CSV / Excel
python main.py export --table history --format csv
```

所有抓取命令均支持 `--save/--no-save`（默认入库）和 `--export-csv`（同时导出）。

### 量化分析

```bash
# 策略回测（14 种策略可选）
python main.py backtest --code 000559 --strategy macd

# 参数优化 + 滚动窗口验证 + 组合回测 + 基准对比
python main.py optimize --code 000559 --strategy sma_cross
python main.py rolling --code 000559 --strategy sma_cross
python main.py portfolio --codes "000001,600519,300750" --strategy macd
python main.py benchmark --code 000559 --strategy cci

# 因子计算 + IC 分析
python main.py factor --code 000559 --name momentum --ic

# 股票筛选（自动过滤 ST/退市）
python main.py screen --pe-max 20 --pb-max 2 --ma-align --top 20
python main.py screen --template breakout
python main.py screen --rank --top 30

# 交易建议（买入价 / 止盈价 / 止损价）
python main.py advice --code 000559

# 启动可视化看板
python main.py dashboard
```

## 数据类型

| 命令 | 数据内容 | 来源 |
|------|----------|------|
| `realtime` | 全市场实时行情（最新价/涨跌幅/PE/PB/市值/换手率/量比/60日涨跌等） | 东方财富 |
| `history` | 个股历史K线（日/周/月，前复权） | 东方财富 |
| `financial` | 利润表、资产负债表、现金流量表 | 新浪财经 |
| `fund-flow` | 个股每日资金流向（主力/超大单/大单/中单/小单） | 东方财富 |
| `lhb` | 龙虎榜明细 | 东方财富 |
| `north-flow` | 北向资金成交净买入 | 东方财富 |

## 项目结构

```
stock/
├── main.py              # CLI 入口（17 个命令）
├── config.py            # 路径配置 + Windows 编码修复
├── database.py          # SQLite 读写
├── exporters.py         # CSV/Excel 导出
├── fetchers/            # 数据抓取层
│   ├── base.py          # BaseFetcher 基类
│   ├── realtime.py      # 实时行情
│   ├── history.py       # 历史K线
│   ├── financial.py     # 财务报表
│   └── fund_flow.py     # 资金流向 / 龙虎榜 / 北向资金
├── analytics/           # 量化分析层
│   ├── backtest.py      # 回测引擎（14策略+参数优化+组合+基准+滚动窗口）
│   ├── factors.py       # 因子计算+IC+截面因子+分层收益
│   ├── screener.py      # 多条件筛选+多因子排名（行业/技术/基本面，自动过滤ST）
│   ├── position.py      # 仓位管理（Kelly/波动率/固定比例）
│   ├── metrics.py       # 绩效指标（夏普/回撤/胜率）
│   └── signal.py        # 交易建议（买/止盈/止损）
├── fetchers/
│   └── industry.py      # 东方财富行业分类
├── dashboard/
│   └── app.py           # Streamlit 看板（6 个 Tab）
├── data/                # SQLite 数据库
├── output/              # CSV/Excel 导出目录
└── requirements.txt
```

## 参数参考

### 通用约定

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--code` | `string` | 股票代码，沪市 6 开头，深市 0/3 开头 | `000001` `600519` `300750` |
| `--start` / `--end` | `string` | 日期，格式 `YYYYMMDD` | `20250101` |
| `--save` / `--no-save` | `bool` | 是否存入数据库，默认 `--save` | |
| `--export-csv` | `flag` | 同时导出为 CSV 到 `output/` 目录 | |

### `history` — 历史K线

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--code` | `string` | — | 必填 | 股票代码 |
| `--period` | `enum` | `daily` `weekly` `monthly` | `daily` | K线周期 |
| `--start` | `string` | `YYYYMMDD` | `20200101` | 起始日期 |
| `--end` | `string` | `YYYYMMDD` | `20501231` | 结束日期 |

> 数据为前复权（`qfq`），自动处理分红送转对价格的影响。

### `financial` — 财务报表

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--code` | `string` | — | 必填 | 股票代码 |
| `--type` | `enum` | `income` `balance` `cashflow` | `income` | 报表类型 |

| `--type` 值 | 含义 | 核心字段 |
|-------------|------|----------|
| `income` | 利润表 | 营业收入、净利润、EPS |
| `balance` | 资产负债表 | 总资产、总负债、净资产 |
| `cashflow` | 现金流量表 | 经营/投资/筹资现金流 |

### `export` — 数据导出

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--table` | `string` | `realtime` `history` `financial` `fund_flow` `lhb` `north_flow` | 必填 | 表名 |
| `--format` | `enum` | `csv` `excel` | `csv` | 导出格式 |
| `--output` | `string` | 文件路径 | `output/<表名>.csv` | 输出路径 |
| `--code` | `string` | — | 无 | 按股票代码筛选导出 |
| `--date` | `string` | `YYYYMMDD` | 无 | 按日期筛选导出 |

### `backtest` — 策略回测

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--code` | `string` | — | 必填 | 股票代码 |
| `--strategy` | `enum` | 见下方策略表 | `sma_cross` | 策略名称 |
| `--start` | `string` | `YYYYMMDD` | 一年前 | 起始日期 |
| `--end` | `string` | `YYYYMMDD` | 今天 | 结束日期 |
| `--cash` | `int` | — | `100000` | 初始资金（元） |

**策略列表（14 种）：**

| 策略名 | 类型 | 逻辑 |
|--------|------|------|
| `sma_cross` | 趋势 | 双均线金叉买入、死叉卖出（快线 5 / 慢线 20） |
| `macd` | 趋势 | MACD 金叉买入、死叉卖出（12/26/9） |
| `ma_align` | 趋势 | MA5>MA10>MA20 多头排列买入，跌破 MA20 卖出 |
| `turtle` | 趋势 | 突破 20 日高点买入，跌破 10 日低点卖出 |
| `bollinger` | 趋势 | 价格突破布林上轨买入，跌破中轨卖出 |
| `vol_breakout` | 趋势 | 放量突破 N 日最高价买入，跌破均线卖出 |
| `rsi` | 波段 | RSI < 30 超卖买入，> 70 超买卖出 |
| `kdj` | 波段 | KDJ 金叉 + 超卖区买入，死叉 + 超买区卖出 |
| `cci` | 波段 | CCI 从超卖区回升买入，从超买区回落卖出 |
| `williams_r` | 波段 | WR 低于 -80 超卖买入，回升到 -20 卖出 |
| `donchian` | 波段 | 触及唐奇安通道下轨反弹买入，到中轨卖出 |
| `mean_revert` | 波段 | 触及布林下轨买入，回到中轨卖出 |
| `three_bar` | 波段 | 三连阴后收阳买入，三连阳后收阴卖出 |
| `buy_hold` | 基准 | 首日买入持有到期末 |

### `factor` — 因子分析

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--code` | `string` | — | 必填 | 股票代码 |
| `--name` | `enum` | 见下方 | `momentum` | 因子名称 |
| `--period` | `int` | 5~120 | `20` | 计算周期（天） |
| `--ic` | `flag` | — | 关闭 | 同时输出 IC 分析 |

| `--name` 值 | 含义 | 计算方式 |
|-------------|------|----------|
| `momentum` | 动量因子 | N 日收益率 |
| `volatility` | 波动率因子 | N 日年化波动率 |
| `turnover` | 换手率因子 | N 日均换手率 |
| `volume_ratio` | 量比因子 | 当日量 / N 日均量 |

**IC 分析输出：** IC 均值、IC 标准差、IC_IR、IC 胜率、数据点数。

### `screen` — 股票筛选

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--pe-max` | `float` | — | 无 | PE 上限（排除负值） |
| `--pe-min` | `float` | — | 无 | PE 下限 |
| `--pb-max` | `float` | — | 无 | PB 上限 |
| `--change-min` | `float` | — | 无 | 涨跌幅下限（%） |
| `--change-max` | `float` | — | 无 | 涨跌幅上限（%） |
| `--turnover-min` | `float` | — | 无 | 换手率下限（%） |
| `--turnover-max` | `float` | — | 无 | 换手率上限（%） |
| `--ma-align` | `flag` | — | 关闭 | 要求 MA5>MA10>MA20 多头排列 |
| `--near-high` | `int` | 正整数 | 无 | 收盘价在 N 日最高价 5% 以内 |
| `--vol-ratio-min` | `float` | — | 无 | 量比下限（当日量 / 20 日均量） |
| `--up-days` | `string` | `N,M` 格式 | 无 | 近 N 日至少 M 日上涨 |
| `--roe-min` | `float` | — | 无 | ROE 下限（%，从财报计算） |
| `--revenue-growth` | `float` | — | 无 | 营收同比增速下限（%） |
| `--profit-growth` | `float` | — | 无 | 净利同比增速下限（%） |
| `--template` | `enum` | 见下方 | 无 | 预置模板 |
| `--rank` | `flag` | — | 关闭 | 多因子打分排名模式 |
| `--top` | `int` | — | `20` | 显示前 N 条 |

**筛选模板：**

| 模板 | 逻辑 |
|------|------|
| `value` | PE ≤ 20, PB ≤ 2, 涨跌 ≥ -5% |
| `momentum` | 涨跌 3%~9.9%, 量比 > 1.5 |
| `quality` | PE ≤ 30, ROE ≥ 15% |
| `breakout` | 均线多头 + 量比 > 1.5 + 近 5 日新高 |
| `oversold` | 跌超 10% + PE 为正 + 换手 < 3% |
| `growth` | 营收增速 > 20% + 利润增速 > 20% + PE < 50 |

### `advice` — 交易建议

| 参数 | 类型 | 说明 |
|------|------|------|
| `--code` | `string` | 股票代码 |

输出：当前价、趋势判断、建议买入价、止盈价、止损价、盈亏比、技术指标（MA20/MA60/布林带/ATR）。

### `optimize` — 参数优化

| 参数 | 类型 | 可选值 | 默认值 | 说明 |
|------|------|--------|--------|------|
| `--code` | `string` | — | 必填 | 股票代码 |
| `--strategy` | `enum` | 12 种可调参数策略 | `sma_cross` | 策略名称 |
| `--start` | `string` | `YYYYMMDD` | 一年前 | 起始日期 |
| `--end` | `string` | `YYYYMMDD` | 今天 | 结束日期 |
| `--cash` | `int` | — | `100000` | 初始资金 |
| `--metric` | `enum` | `sharpe_ratio` `total_return_pct` `annual_return_pct` | `sharpe_ratio` | 优化目标 |

各策略搜索空间：双均线 16 组、MACD 27 组、RSI 27 组、KDJ 81 组……最大 81 组组合。

### `portfolio` — 组合回测

| 参数 | 类型 | 说明 |
|------|------|------|
| `--codes` | `string` | 股票代码，逗号分隔（如 `000001,600519`） |
| `--strategy` | `enum` | 策略名称，全部 14 种可选 |
| `--start` | `string` | 起始日期 |
| `--end` | `string` | 结束日期 |
| `--cash` | `int` | 初始资金，默认 100000 |

多股等权仓位，自动剔除无数据的股票。返回组合的总收益/年化/回撤/夏普/交易详情。

### `benchmark` — 基准对比

| 参数 | 类型 | 说明 |
|------|------|------|
| `--code` | `string` | 股票代码 |
| `--strategy` | `enum` | 策略名称 |
| `--start` | `string` | 起始日期 |
| `--end` | `string` | 结束日期 |
| `--cash` | `int` | 初始资金 |

输出：策略 vs 买入持有的收益/夏普/回撤三列对比 + 超额收益。

### 仓位管理（`analytics/position.py`）

| 函数 | 逻辑 |
|------|------|
| `kelly_fraction(win_rate, pl_ratio)` | 凯利公式：f = p - (1-p)/r |
| `volatility_sizer(returns, max_risk)` | 波动率调整：目标最大单日亏损 |
| `fixed_fraction(capital, risk, stop_loss)` | 固定风险比例：每笔亏 ≤ X% 本金 |
| `equal_weight(n_stocks)` | 等权分配：1 / N |
| `adaptive_sizer(returns, wr, plr, risk)` | 自适应：Kelly + 波动率取保守值 |

## 详细使用说明

### 场景一：首次使用 — 建立数据库

```bash
# 1. 抓取全市场实时行情（基础数据，后续筛选依赖此表）
python main.py realtime
# → 获取约 5000+ 只股票的实时价格/PE/PB

# 2. 抓取关注个股的完整数据
python main.py history --code 000001        # 平安银行历史K线
python main.py financial --code 000001 --type income --save    # 利润表
python main.py financial --code 000001 --type balance --save   # 资产负债表
python main.py fund-flow --code 000001      # 资金流向

# 3. 确认数据入库
python main.py status
# realtime        5849 条
# history         1522 条
# financial        331 条
# fund_flow        120 条
```

### 场景二：分析一只股票 — 从数据到决策

```bash
# 1. 查看交易建议
python main.py advice --code 000559
# → 当前价 / 趋势判断 / 建议买入价 / 止盈价 / 止损价 / 盈亏比

# 2. 计算因子，判断是否处于有利位置
python main.py factor --code 000559 --name momentum --ic
# → 动量因子最近走势 + IC 分析（因子有效性）

# 3. 回测验证策略是否在该股上有效
python main.py backtest --code 000559 --strategy cci
# → 如果 CCI 策略历史上在该股表现好，当前信号更可信

# 4. 多策略对比
for s in macd cci kdj mean_revert; do
    python main.py backtest --code 000559 --strategy $s --start 20200101
done
```

### 场景三：全市场选股

```bash
# 方式 1：条件筛选 — 找到符合交易逻辑的股票池
# 放量突破（均线多头 + 放量 + 接近新高）
python main.py screen --ma-align --vol-ratio-min 1.5 --near-high 20 --top 30

# 低估值 + 高 ROE
python main.py screen --pe-max 15 --pb-max 1.5 --roe-min 10 --top 30

# 方式 2：模板筛选 — 快速使用预设逻辑
python main.py screen --template breakout --top 30     # 放量突破
python main.py screen --template oversold --top 30     # 超跌反弹

# 方式 3：多因子排名 — 综合打分
python main.py screen --rank --top 30
# → 按低PE/低PB/高ROE/动量/量比加权打分排序

# 对筛选结果中的股票，逐一拉取数据 + 分析
python main.py history --code <代码> --save
python main.py financial --code <代码> --type income --save
python main.py advice --code <代码>
```

### 场景四：批量抓取关注列表

```bash
# 创建关注列表文件 watchlist.txt，每行一个代码
echo "000001" > watchlist.txt
echo "000559" >> watchlist.txt
echo "600519" >> watchlist.txt
echo "300750" >> watchlist.txt

# 批量抓取（Linux/macOS）
while read code; do
    echo "抓取 $code ..."
    python main.py history --code $code --save
    python main.py financial --code $code --type income --save
    python main.py fund-flow --code $code --save
done < watchlist.txt

# 批量抓取（Windows PowerShell）
Get-Content watchlist.txt | ForEach-Object {
    python main.py history --code $_ --save
    python main.py financial --code $_ --type income --save
    python main.py fund-flow --code $_ --save
}
```

### 场景五：定期更新数据

```bash
# 每日收盘后更新（可配合 cron / 任务计划程序）

# 更新全市场行情（覆盖旧数据）
python main.py realtime

# 更新关注个股的最新K线（追加新交易日）
python main.py history --code 000559 --start 20250501 --save
python main.py fund-flow --code 000559 --save

# 导出最新数据
python main.py export --table realtime --format excel
python main.py export --table history --code 000559 --format csv
```

### 场景六：可视化分析

```bash
# 启动看板
python main.py dashboard
# → 浏览器打开 http://localhost:8501

# 看板功能：
#   Tab 1 行情总览 — 涨跌分布/成交额排排/涨跌幅榜（自动过滤 ST）
#   Tab 2 个股详情 — K线(分时/5分钟/日/周/月/半年/年+MACD/KDJ)/资金流向/财报/技术指标
#   Tab 3 策略回测 — 单股回测/基准对比/参数优化/组合回测
#   Tab 4 因子分析 — 因子值曲线 + IC 分析
#   Tab 5 股票筛选 — 条件/模板/多因子排名（自动过滤 ST）
#   Tab 6 交易建议 — 买入/止盈/止损 + 盈亏比
#   侧边栏     — 代码+名称搜索 + 股票卡片(价/市值/PE/PB/换手) + 一键数据抓取
```

### 场景七：策略研究

```bash
# 1. 在同一只股票上对比所有策略
python main.py backtest --code 000559 --strategy buy_hold --start 20200101
python main.py backtest --code 000559 --strategy cci --start 20200101
python main.py backtest --code 000559 --strategy kdj --start 20200101
python main.py backtest --code 000559 --strategy macd --start 20200101

# 2. 用不同股票验证策略普适性
for code in 000001 000559 600519 300750; do
    echo "=== $code ==="
    python main.py backtest --code $code --strategy cci --start 20200101
done

# 3. 因子 IC 分析 — 判断因子是否有效
python main.py factor --code 000559 --name momentum --ic
# IC > 0.02 且 IC_IR > 0.3 → 因子有一定预测能力
# IC < 0     → 因子无效或反向
```

### 场景八：参数优化 — 找到最优策略配置

```bash
# 1. 对双均线策略做网格搜索
python main.py optimize --code 000559 --strategy sma_cross --start 20200101
# → 测试 fast×slow = 16 组组合
# → 最优参数: fast=3, slow=10
# → 优化后收益 121% vs 默认参数 19%

# 2. 多策略参数对比
for s in sma_cross macd rsi kdj cci; do
    echo "=== $s ==="
    python main.py optimize --code 000559 --strategy $s --start 20200101
done

# 3. 验证优化效果 — 对比优化前后 + 基准
python main.py benchmark --code 000559 --strategy sma_cross --start 20200101
# → 策略 26.2% vs 买入持有 255.6% → ❌ 跑输
```

### 场景九：组合回测 — 验证策略普适性

```bash
# 1. 三只股票等权组合
python main.py portfolio --codes "000001,000559,600519" --strategy macd --start 20200101
# → 组合总收益/年化/回撤/夏普

# 2. 对比单股 vs 组合
python main.py backtest --code 000001 --strategy macd --start 20200101
python main.py backtest --code 000559 --strategy macd --start 20200101
python main.py backtest --code 600519 --strategy macd --start 20200101
# → 组合收益通常比单股波动小、回撤低

# 3. 不同策略跑组合
for s in macd cci kdj mean_revert; do
    echo "=== $s ==="
    python main.py portfolio --codes "000001,000559,600519" --strategy $s --start 20200101
done
```

### 数据关系

```
realtime (全市场快照)         history (K线序列)
├── code                      ├── code + date (联合主键)
├── name                      ├── open/high/low/close
├── price (最新价)            ├── volume/amount
├── pe / pb                   ├── turnover/change_pct
└── change_pct / turnover     └── 依赖 history 命令抓取
    依赖 realtime 命令抓取
                              financial (财报)
fund_flow (资金流)            ├── code + report_date + report_type
├── code + date               ├── revenue / net_profit / EPS
├── main_net (主力净额)       ├── total_assets / total_liabilities
├── super_large_net           └── 依赖 financial 命令抓取
└── large/medium/small_net
    依赖 fund-flow 命令抓取

筛选器 screener 读这三张表 → 输出符合条件的股票列表（自动过滤 ST/退市）
回测 backtest 从 history 取 OHLCV → 单股/组合/优化/基准
交易建议 advice 从 history + realtime 取数据 → 计算价位
仓位管理 position 根据回测结果 → 计算最优仓位比例
```

## 常见问题

### Windows 终端中文乱码

项目已内置 `config.py` 自动修复，无需额外配置。如仍有问题：

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

### Streamlit 看板无法启动

```bash
# 确认 streamlit 已安装
pip install streamlit

# 手动启动
streamlit run dashboard/app.py
```

### 财务筛选无结果

财务报表筛选（ROE/营收增速等）需要先抓取对应股票的财报数据：

```bash
python main.py financial --code 600519 --type income --save
python main.py financial --code 600519 --type balance --save
```

## 注意事项

- 实时行情数据量较大（5000+ 条），抓取耗时约 60~90 秒
- 财务报表接口（新浪）按报告期返回，历史数据可追溯多年
- 股票代码：沪市主板以 6 开头（如 600519 茅台），深市以 0/3 开头（如 000001 平安银行、300750 宁德时代）
- 数据写入采用 `INSERT OR REPLACE` 策略，重复抓取不会产生重复记录
- 筛选器和看板自动过滤 ST、*ST、N（新股首日）、PT、退市股票
- 虚拟环境（`venv/`）和数据库（`data/`）已加入 `.gitignore`，不会提交到 Git
