import pandas as pd
import akshare as ak
from .base import BaseFetcher


class FinancialFetcher(BaseFetcher):
    table_name = "financial"

    REPORT_TYPES = {
        "income": "利润表",
        "balance": "资产负债表",
        "cashflow": "现金流量表",
    }

    def _fetch(self, code: str = "", report_type: str = "income") -> pd.DataFrame:
        indicator = {
            "income": "利润表",
            "balance": "资产负债表",
            "cashflow": "现金流量表",
        }.get(report_type, report_type)

        df = ak.stock_financial_report_sina(stock=code, symbol=indicator)

        col_map = {
            "报告日": "report_date",
            "营业总收入": "revenue",
            "净利润": "net_profit",
            "归属于母公司股东的净利润": "net_profit_parent",
            "基本每股收益": "basic_eps",
            "资产总计": "total_assets",
            "负债合计": "total_liabilities",
            "股东权益合计": "shareholders_equity",
            "经营活动产生的现金流量净额": "cf_operating",
            "投资活动产生的现金流量净额": "cf_investing",
            "筹资活动产生的现金流量净额": "cf_financing",
        }
        df = df.rename(columns=col_map)
        df["code"] = code
        df["report_type"] = report_type
        if "report_date" in df.columns:
            df["report_date"] = df["report_date"].astype(str)

        # Get company name
        try:
            info = ak.stock_individual_info_em(symbol=code)
            name_row = info[info["item"] == "股票简称"]
            if not name_row.empty:
                df["name"] = name_row["value"].values[0]
        except Exception:
            pass

        keep_cols = ["code", "name", "report_date", "report_type",
                     "revenue", "net_profit", "net_profit_parent", "basic_eps",
                     "total_assets", "total_liabilities", "shareholders_equity",
                     "cf_operating", "cf_investing", "cf_financing"]
        available = [c for c in keep_cols if c in df.columns]
        return df[available]
