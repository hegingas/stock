"""行业分类数据 — 东方财富行业板块。"""
import pandas as pd
import akshare as ak
from database import save_dataframe, query, table_exists, get_conn


def fetch_industry():
    """获取东方财富行业板块成分股，写入 industry 表。"""
    try:
        df = ak.stock_board_industry_name_em()
    except Exception:
        return pd.DataFrame()

    rows = []
    for _, r in df.iterrows():
        board_code = r["板块代码"]
        board_name = r["板块名称"]
        try:
            members = ak.stock_board_industry_cons_em(symbol=board_name)
            for _, m in members.iterrows():
                rows.append({
                    "code": m["代码"],
                    "name": m["名称"],
                    "industry": board_name,
                })
        except Exception:
            continue

    result = pd.DataFrame(rows)
    if not result.empty:
        # 重建行业表
        conn = get_conn()
        conn.execute("DROP TABLE IF EXISTS industry")
        conn.execute("""
            CREATE TABLE industry (
                code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT
            )
        """)
        conn.commit()
        conn.close()
        save_dataframe(result, "industry")
    return result


def get_industry(code=None):
    """查询行业分类。code=None 返回全部。"""
    if not table_exists("industry"):
        return pd.DataFrame()
    if code:
        return query("SELECT * FROM industry WHERE code=?", [code])
    return query("SELECT * FROM industry")


def get_industry_list():
    """返回所有行业名称列表。"""
    if not table_exists("industry"):
        return []
    df = query("SELECT DISTINCT industry FROM industry ORDER BY industry")
    return df["industry"].tolist()
