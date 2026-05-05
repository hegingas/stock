import os
import pandas as pd
from database import query, table_exists
from config import OUTPUT_DIR


def export(table_name, fmt="csv", output_path=None, **filters):
    if not table_exists(table_name):
        raise ValueError(f"表 {table_name} 不存在")

    sql = f"SELECT * FROM {table_name}"
    params = None
    if filters:
        conditions = " AND ".join(f"{k}=?" for k in filters)
        sql = f"SELECT * FROM {table_name} WHERE {conditions}"
        params = list(filters.values())

    df = query(sql, params)

    if df.empty:
        print(f"表 {table_name} 为空，跳过导出")
        return None

    if output_path is None:
        ext = "xlsx" if fmt == "excel" else "csv"
        output_path = os.path.join(OUTPUT_DIR, f"{table_name}.{ext}")

    os.makedirs(os.path.dirname(output_path) or OUTPUT_DIR, exist_ok=True)

    if fmt == "csv":
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
    elif fmt == "excel":
        df.to_excel(output_path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"不支持的格式: {fmt}")

    print(f"已导出 {len(df)} 条记录到 {output_path}")
    return output_path
