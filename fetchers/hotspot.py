"""热点数据抓取 — 人气榜 / 热门上涨 / 个股新闻。"""
import pandas as pd
import akshare as ak
from datetime import date
from .base import BaseFetcher


class HotspotFetcher(BaseFetcher):
    table_name = "hot_rank"

    def fetch_hot_rank(self) -> pd.DataFrame:
        """全市场人气榜 Top 100（东方财富）。"""
        df = ak.stock_hot_rank_em()
        df = df.rename(columns={
            "当前排名": "rank",
            "代码": "code",
            "股票名称": "name",
            "最新价": "price",
            "涨跌额": "change_amt",
            "涨跌幅": "change_pct",
        })
        df["fetch_date"] = date.today().isoformat()
        keep_cols = ["code", "name", "rank", "price", "change_amt", "change_pct", "fetch_date"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]

    def fetch_hot_up(self) -> pd.DataFrame:
        """热门上涨榜（东方财富）。"""
        df = ak.stock_hot_up_em()
        df = df.rename(columns={
            "排名较昨日变动": "rank_change",
            "当前排名": "rank",
            "代码": "code",
            "股票名称": "name",
            "最新价": "price",
            "涨跌额": "change_amt",
            "涨跌幅": "change_pct",
        })
        df["fetch_date"] = date.today().isoformat()
        keep_cols = ["code", "name", "rank", "rank_change", "price", "change_amt", "change_pct", "fetch_date"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]

    def fetch_news(self, code: str) -> pd.DataFrame:
        """个股新闻（东方财富）。"""
        df = ak.stock_news_em(symbol=code)
        df = df.rename(columns={
            "关键词": "keyword",
            "新闻标题": "title",
            "新闻内容": "content",
            "发布时间": "pub_time",
            "文章来源": "source",
            "新闻链接": "url",
        })
        df["code"] = code
        keep_cols = ["code", "title", "content", "pub_time", "source", "url"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]

    def _fetch(self) -> pd.DataFrame:
        raise NotImplementedError("use fetch_hot_rank / fetch_hot_up / fetch_news")
