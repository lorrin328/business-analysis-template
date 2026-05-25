"""产品配置服务 — 从 DataFrame 提取产品列表到 product_config 表。"""
import logging

import pandas as pd

from db import get_db
from etl.columns import _pick_col
from etl.normalize import _period_year_month, _normalize_channel
from config.business_lines import DEFAULT_YEAR
from metrics.business_rules import normalize_product_code

logger = logging.getLogger("business-analysis")


def normalize_product_name(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def normalize_product_config_table(conn) -> int:
    """Normalize product_config.product_code and merge duplicates such as 4281/4281.0.

    When duplicate rows exist under the same business_type, a Y flag wins over N so
    user-defined product classification is not lost during cleanup.
    """
    rows = conn.execute('''
        SELECT product_code, product_name, business_type, is_annuity, is_protection, created_at, updated_at
        FROM product_config
    ''').fetchall()
    merged = {}
    changed = False
    for row in rows:
        raw_code = str(row['product_code'] or '').strip()
        code = normalize_product_code(raw_code)
        business_type = str(row['business_type'] or '').strip()
        if not code:
            changed = True
            continue
        key = (business_type, code)
        item = merged.setdefault(key, {
            'product_code': code,
            'product_name': '',
            'business_type': business_type,
            'is_annuity': 'N',
            'is_protection': 'N',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        })
        name = normalize_product_name(row['product_name'])
        if name and (not item['product_name'] or raw_code == code):
            item['product_name'] = name
        if str(row['is_annuity']).upper() == 'Y':
            item['is_annuity'] = 'Y'
        if str(row['is_protection']).upper() == 'Y':
            item['is_protection'] = 'Y'
        if raw_code != code:
            changed = True
        if item['created_at'] is None:
            item['created_at'] = row['created_at']
        item['updated_at'] = row['updated_at'] or item['updated_at']

    if len(merged) != len(rows):
        changed = True
    if not changed:
        return 0

    conn.execute('DELETE FROM product_config')
    conn.executemany(
        '''
        INSERT INTO product_config (
            product_code, product_name, business_type, is_annuity, is_protection, created_at, updated_at
        ) VALUES (
            :product_code, :product_name, :business_type, :is_annuity, :is_protection,
            COALESCE(:created_at, CURRENT_TIMESTAMP), COALESCE(:updated_at, CURRENT_TIMESTAMP)
        )
        ''',
        list(merged.values()),
    )
    return len(rows) - len(merged)


def extract_products_to_config(df):
    """从 performance DataFrame 中提取当前数据年及以后产品列表到 product_config 表。"""
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    code_col = _pick_col(df, ['产品代码'])
    name_col = _pick_col(df, ['产品名称'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])

    if not code_col:
        return

    work = _period_year_month(df, year_col, month_col)
    work['_product_code'] = work[code_col].map(normalize_product_code)
    work = work[work['_product_code'].replace('', pd.NA).notna()]
    work = work[work['_year'] >= DEFAULT_YEAR]
    if work.empty:
        return

    if name_col:
        work['_product_name'] = work[name_col].map(normalize_product_name)
    else:
        work['_product_name'] = ''
    if channel_col:
        work['_business_type'] = work[channel_col].map(_normalize_channel)
    else:
        work['_business_type'] = ''

    products = work[['_product_code', '_product_name', '_business_type']].drop_duplicates(
        subset=['_business_type', '_product_code']
    )

    with get_db() as conn:
        for _, row in products.iterrows():
            conn.execute('''
                INSERT OR IGNORE INTO product_config (product_code, product_name, business_type)
                VALUES (?, ?, ?)
            ''', (row['_product_code'], row['_product_name'], row['_business_type']))
        normalize_product_config_table(conn)
        conn.commit()
    logger.info("extracted %s products to product_config (year>=%s)", len(products), DEFAULT_YEAR)


def extract_jingdai_products_to_config(df):
    """从经代 DataFrame 中提取年份>=2026的产品名称到 product_config 表。"""
    time_col = _pick_col(df, ['时间', '年月'])
    name_col = _pick_col(df, ['产品名称'])
    if not (time_col and name_col):
        return

    work = _period_year_month(df, None, time_col)
    work['_product_name'] = work[name_col].map(normalize_product_name)
    work = work[work['_product_name'].replace('', pd.NA).notna()]
    work = work[work['_year'] >= DEFAULT_YEAR]
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
        normalize_product_config_table(conn)
        conn.commit()
    logger.info("extracted %s jingdai products to product_config (year>=%s)", len(products), DEFAULT_YEAR)
