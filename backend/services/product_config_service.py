"""产品配置服务 — 从 DataFrame 提取产品列表到 product_config 表。"""
import logging

import pandas as pd

from db import get_db
from etl.columns import _pick_col
from etl.normalize import _period_year_month, _normalize_channel

logger = logging.getLogger("business-analysis")


def extract_products_to_config(df):
    """从 performance DataFrame 中提取年份≥2026的产品列表到 product_config 表（INSERT OR IGNORE）。"""
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    code_col = _pick_col(df, ['产品代码'])
    name_col = _pick_col(df, ['产品名称'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])

    if not code_col:
        return

    work = _period_year_month(df, year_col, month_col)
    work['_product_code'] = work[code_col].astype(str).str.strip()
    work = work[work['_product_code'].replace('', pd.NA).notna()]
    work = work[work['_year'] >= 2026]
    if work.empty:
        return

    if name_col:
        work['_product_name'] = work[name_col].astype(str).str.strip()
    else:
        work['_product_name'] = ''
    if channel_col:
        work['_business_type'] = work[channel_col].map(_normalize_channel)
    else:
        work['_business_type'] = ''

    products = work[['_product_code', '_product_name', '_business_type']].drop_duplicates(
        subset=['_product_code']
    )

    with get_db() as conn:
        for _, row in products.iterrows():
            conn.execute('''
                INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
                VALUES (?, ?, ?)
            ''', (row['_product_code'], row['_product_name'], row['_business_type']))
        conn.commit()
    logger.info("extracted %s products to product_config (year>=2026)", len(products))


def extract_jingdai_products_to_config(df):
    """从经代 DataFrame 中提取年份>=2026的产品名称到 product_config 表。"""
    time_col = _pick_col(df, ['时间', '年月'])
    name_col = _pick_col(df, ['产品名称'])
    if not (time_col and name_col):
        return

    work = _period_year_month(df, None, time_col)
    work['_product_name'] = work[name_col].astype(str).str.strip()
    work = work[work['_product_name'].replace('', pd.NA).notna()]
    work = work[work['_year'] >= 2026]
    if work.empty:
        return

    products = work[['_product_name']].drop_duplicates()
    with get_db() as conn:
        for _, row in products.iterrows():
            name = row['_product_name']
            conn.execute('''
                INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
                VALUES (?, ?, '经代')
            ''', (name, name))
        conn.commit()
    logger.info("extracted %s jingdai products to product_config (year>=2026)", len(products))
