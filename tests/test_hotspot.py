"""测试 HotspotFetcher — 列名转换 + 保存逻辑。"""
import pandas as pd
import pytest
from unittest.mock import patch


class TestFetchHotRank:
    @patch("akshare.stock_hot_rank_em")
    def test_renames_columns(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "当前排名": [1, 2],
            "代码": ["000001", "000002"],
            "股票名称": ["平安", "万科"],
            "最新价": [10.5, 8.0],
            "涨跌额": [0.5, -0.3],
            "涨跌幅": [5.0, -3.6],
        })
        from fetchers.hotspot import HotspotFetcher

        df = HotspotFetcher().fetch_hot_rank()
        assert list(df.columns) == ["code", "name", "rank", "price", "change_amt", "change_pct", "fetch_date"]
        assert len(df) == 2
        assert df.iloc[0]["code"] == "000001"
        assert df.iloc[0]["rank"] == 1

    @patch("akshare.stock_hot_rank_em")
    def test_save_to_db(self, mock_api, test_db):
        mock_api.return_value = pd.DataFrame({
            "当前排名": [1],
            "代码": ["000559"],
            "股票名称": ["万向钱潮"],
            "最新价": [17.68],
            "涨跌额": [0.48],
            "涨跌幅": [2.79],
        })
        from fetchers.hotspot import HotspotFetcher
        from database import save_dataframe, query, table_exists

        df = HotspotFetcher().fetch_hot_rank()
        save_dataframe(df, "hot_rank")
        assert table_exists("hot_rank")

        rows = query("SELECT * FROM hot_rank WHERE code='000559'")
        assert len(rows) == 1
        assert rows.iloc[0]["name"] == "万向钱潮"


class TestFetchHotUp:
    @patch("akshare.stock_hot_up_em")
    def test_renames_columns(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "排名较昨日变动": [5070, 4879],
            "当前排名": [342, 270],
            "代码": ["920270", "605086"],
            "股票名称": ["天铭科技", "龙高股份"],
            "最新价": [20.64, 35.57],
            "涨跌额": [6.18, 3.55],
            "涨跌幅": [29.97, 9.99],
        })
        from fetchers.hotspot import HotspotFetcher

        df = HotspotFetcher().fetch_hot_up()
        assert list(df.columns) == ["code", "name", "rank", "rank_change", "price", "change_amt", "change_pct", "fetch_date"]
        assert df.iloc[0]["rank_change"] == 5070
        assert df.iloc[0]["code"] == "920270"


class TestFetchNews:
    @patch("akshare.stock_news_em")
    def test_renames_columns(self, mock_api):
        mock_api.return_value = pd.DataFrame({
            "关键词": ["000559"],
            "新闻标题": ["一季报净利润下降"],
            "新闻内容": ["公司发布一季报..."],
            "发布时间": ["2026-04-27 17:37:57"],
            "文章来源": ["界面新闻"],
            "新闻链接": ["http://example.com/1"],
        })
        from fetchers.hotspot import HotspotFetcher

        df = HotspotFetcher().fetch_news("000559")
        assert list(df.columns) == ["code", "title", "content", "pub_time", "source", "url"]
        assert len(df) == 1
        assert df.iloc[0]["code"] == "000559"
        assert df.iloc[0]["title"] == "一季报净利润下降"

    @patch("akshare.stock_news_em")
    def test_save_to_db(self, mock_api, test_db):
        mock_api.return_value = pd.DataFrame({
            "关键词": ["000559"],
            "新闻标题": ["Q1报告"],
            "新闻内容": ["内容..."],
            "发布时间": ["2026-04-27 17:37:57"],
            "文章来源": ["界面新闻"],
            "新闻链接": ["http://example.com/news1"],
        })
        from fetchers.hotspot import HotspotFetcher
        from database import save_dataframe, query, table_exists

        df = HotspotFetcher().fetch_news("000559")
        save_dataframe(df, "stock_news")
        assert table_exists("stock_news")

        rows = query("SELECT * FROM stock_news WHERE code='000559'")
        assert len(rows) == 1
        assert rows.iloc[0]["title"] == "Q1报告"


class TestFetchNotImplemented:
    def test_fetch_raises(self):
        from fetchers.hotspot import HotspotFetcher
        import pytest
        with pytest.raises(NotImplementedError):
            HotspotFetcher().fetch()
