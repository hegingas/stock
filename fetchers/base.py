import logging
import pandas as pd
from database import save_dataframe, query

logger = logging.getLogger(__name__)


class BaseFetcher:
    table_name: str = ""

    def fetch(self):
        df = self._fetch()
        if df is None or df.empty:
            logger.warning("%s: 未获取到数据", self.__class__.__name__)
            return None
        logger.info("%s: 获取到 %d 条数据", self.__class__.__name__, len(df))
        return df

    def fetch_and_save(self):
        df = self.fetch()
        if df is not None:
            save_dataframe(df, self.table_name)
            logger.info("%s: 已保存 %d 条到 %s", self.__class__.__name__, len(df), self.table_name)
        return df

    def _fetch(self) -> pd.DataFrame:
        raise NotImplementedError

    def query(self, sql=None, **kwargs):
        if sql is None:
            sql = f"SELECT * FROM {self.table_name}"
        if kwargs:
            conditions = " AND ".join(f"{k}=?" for k in kwargs)
            sql = f"SELECT * FROM {self.table_name} WHERE {conditions}"
            return query(sql, list(kwargs.values()))
        return query(sql)
