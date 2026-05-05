import pandas as pd
import akshare as ak
from .base import BaseFetcher


class HistoryFetcher(BaseFetcher):
    table_name = "history"

    def _fetch(self, code: str = "", period: str = "daily",
               start_date: str = "20200101", end_date: str = "20501231",
               adjust: str = "qfq") -> pd.DataFrame:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        df = df.rename(columns={
            "日期": "date",
            "股票代码": "code",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover",
            "振幅": "amplitude",
            "涨跌幅": "change_pct",
        })
        df["date"] = df["date"].astype(str)
        if "code" not in df.columns:
            df["code"] = code
        keep_cols = ["code", "date", "open", "close", "high", "low",
                     "volume", "amount", "turnover", "amplitude", "change_pct"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]
