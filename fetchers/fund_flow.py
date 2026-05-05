import pandas as pd
import akshare as ak
from .base import BaseFetcher


class FundFlowFetcher(BaseFetcher):
    table_name = "fund_flow"

    def fetch_individual(self, code: str) -> pd.DataFrame:
        df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
        df = df.rename(columns={
            "日期": "date",
            "股票代码": "code",
            "主力净流入-净额": "main_net",
            "超大单净流入-净额": "super_large_net",
            "大单净流入-净额": "large_net",
            "中单净流入-净额": "medium_net",
            "小单净流入-净额": "small_net",
        })
        df["date"] = df["date"].astype(str)
        if "code" not in df.columns:
            df["code"] = code
        keep_cols = ["code", "date", "main_net", "super_large_net",
                     "large_net", "medium_net", "small_net"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]

    def fetch_north_flow(self) -> pd.DataFrame:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        df = df.rename(columns={
            "日期": "date",
            "当日成交净买额": "net_buy",
            "买入成交额": "buy_amount",
            "卖出成交额": "sell_amount",
        })
        if "date" in df.columns:
            df["date"] = df["date"].astype(str)
        return df

    def fetch_lhb(self, date: str = None) -> pd.DataFrame:
        if date is None:
            import datetime
            date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        df = ak.stock_lhb_detail_daily(date=date)
        df = df.rename(columns={
            "代码": "code",
            "名称": "name",
            "上榜日": "date",
            "解读": "reason",
            "买入金额": "buy_amount",
            "卖出金额": "sell_amount",
            "成交金额": "net_amount",
        })
        if "date" in df.columns:
            df["date"] = df["date"].astype(str)
        keep_cols = ["code", "name", "date", "reason",
                     "buy_amount", "sell_amount", "net_amount"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]

    def _fetch(self) -> pd.DataFrame:
        raise NotImplementedError("use fetch_individual / fetch_north_flow / fetch_lhb")
