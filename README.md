# Stock — A股数据抓取工具

基于 [AKShare](https://github.com/akfamily/akshare) 的 A 股股票数据抓取工具，支持实时行情、历史K线、财务报表、资金流向等数据的采集，数据存入 SQLite 并支持导出 CSV/Excel。

> 数据来源于东方财富、新浪财经等公开接口，仅供学习参考，不构成投资建议。投资有风险，入市需谨慎。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
# 查看数据库状态
python main.py status

# 抓取全市场实时行情
python main.py realtime

# 抓取个股历史K线
python main.py history --code 000001 --start 20250101 --end 20250505

# 抓取财务报表
python main.py financial --code 600519 --type income   # 利润表
python main.py financial --code 600519 --type balance  # 资产负债表
python main.py financial --code 600519 --type cashflow # 现金流量表

# 抓取资金流向
python main.py fund-flow --code 000559

# 抓取龙虎榜 / 北向资金
python main.py lhb
python main.py north-flow

# 导出数据
python main.py export --table history --format csv
python main.py export --table realtime --format excel
```

所有抓取命令均支持 `--save/--no-save`（默认入库）和 `--export-csv`（同时导出）。

## 数据类型

| 命令 | 数据内容 | 来源 |
|------|----------|------|
| `realtime` | 全市场实时行情（最新价、涨跌幅、成交量、PE/PB 等） | 东方财富 |
| `history` | 个股历史K线（日/周/月，前复权） | 东方财富 |
| `financial` | 利润表、资产负债表、现金流量表 | 新浪财经 |
| `fund-flow` | 个股每日资金流向（主力/超大单/大单/中单/小单） | 东方财富 |
| `lhb` | 龙虎榜明细 | 东方财富 |
| `north-flow` | 北向资金成交净买入 | 东方财富 |

## 项目结构

```
stock/
├── main.py              # CLI 入口
├── config.py            # 路径配置
├── database.py          # SQLite 读写
├── exporters.py         # CSV/Excel 导出
├── fetchers/
│   ├── base.py          # BaseFetcher 基类
│   ├── realtime.py      # 实时行情
│   ├── history.py       # 历史K线
│   ├── financial.py     # 财务报表
│   └── fund_flow.py     # 资金流向 / 龙虎榜 / 北向资金
├── data/                # SQLite 数据库目录
├── output/              # 导出文件目录
└── requirements.txt
```

## 注意事项

- 实时行情数据量较大（5000+ 条），抓取耗时约 60~90 秒
- 财务报表接口（新浪）按报告期返回，历史数据可追溯多年
- 股票代码：沪市主板以 6 开头（如 600519 茅台），深市以 0/3 开头（如 000001 平安银行、300750 宁德时代）
- 数据写入采用 `INSERT OR REPLACE` 策略，重复抓取不会产生重复记录
