import pandas as pd
import akshare as ak
from .base import BaseFetcher


class RealtimeFetcher(BaseFetcher):
    table_name = "realtime"

    def _fetch(self) -> pd.DataFrame:
        df = ak.stock_zh_a_spot_em()
        df = df.rename(columns={
            "代码": "code",
            "名称": "name",
            "最新价": "price",
            "涨跌幅": "change_pct",
            "涨跌额": "change_amt",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover",
            "市盈率-动态": "pe",
            "市净率": "pb",
            "最高": "high",
            "最低": "low",
            "今开": "open",
            "昨收": "pre_close",
            "总市值": "total_mv",
            "流通市值": "circ_mv",
            "量比": "volume_ratio",
            "60日涨跌幅": "change_60d",
            "年初至今涨跌幅": "change_ytd",
        })
        keep_cols = ["code", "name", "price", "change_pct", "change_amt",
                     "volume", "amount", "turnover", "pe", "pb",
                     "high", "low", "open", "pre_close",
                     "total_mv", "circ_mv", "volume_ratio",
                     "change_60d", "change_ytd"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]
