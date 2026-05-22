"""ETL aggregate — auto-split from aggregator.py."""
import io
from typing import Dict, List

import pandas as pd

from etl.normalize import (
    _normalize_channel, _to_number, _amount_to_wan,
    _period_year_month, _fee_weight,
)
from etl.columns import _pick_col
from db import get_db


def _load_jingdai_product_config() -> dict:
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT product_code, is_annuity, is_protection
                FROM product_config
                WHERE business_type = '经代'
            ''').fetchall()
            return {
                str(r['product_code']).strip(): {
                    'is_annuity': str(r['is_annuity']).upper() == 'Y',
                    'is_protection': str(r['is_protection']).upper() == 'Y',
                }
                for r in rows
            }
    except Exception:
        return {}


def aggregate_jingdai(df: pd.DataFrame) -> List[Dict]:
    time_col = _pick_col(df, ['时间', '年月'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])
    product_name_col = _pick_col(df, ['产品名称'])

    if not all([time_col, qj_col, gm_col]):
        raise ValueError(f"无法识别经代必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, time_col)
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col])
    if pay_col:
        weights = work[pay_col].map(_fee_weight)
        work['_zs'] = work['_qj'] * weights
    else:
        work['_zs'] = 0
    work['_is_annuity'] = False
    work['_is_protection'] = False
    if product_name_col:
        config_map = _load_jingdai_product_config()
        work['_product_key'] = work[product_name_col].astype(str).str.strip()
        work['_is_annuity'] = work['_product_key'].map(
            lambda x: config_map.get(x, {}).get('is_annuity', False)
        ).fillna(False)
        work['_is_protection'] = work['_product_key'].map(
            lambda x: config_map.get(x, {}).get('is_protection', False)
        ).fillna(False)
    work['_product_annuity'] = work['_qj'].where(work['_is_annuity'], 0)
    work['_product_protection'] = work['_qj'].where(work['_is_protection'], 0)

    grouped = work.groupby(['_year', '_month'], dropna=False)
    rows = []
    for (year, month), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
            'product_annuity': _amount_to_wan(group['_product_annuity'].sum()),
            'product_protection': _amount_to_wan(group['_product_protection'].sum()),
        })
    return rows


def aggregate_jingdai_daily(df: pd.DataFrame) -> List[Dict]:
    """按经代基表的时间字段聚合到日，用于经代月度/季度日累计趋势。"""
    time_col = _pick_col(df, ['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])

    if not all([time_col, qj_col, gm_col]):
        raise ValueError(f"无法识别经代日聚合必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, None, time_col)
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col])
    if pay_col:
        weights = work[pay_col].map(_fee_weight)
        work['_zs'] = work['_qj'] * weights
    else:
        work['_zs'] = 0

    grouped = work.groupby(['_year', '_month', '_day'], dropna=False)
    rows = []
    for (year, month, day), group in grouped:
        y = int(year)
        m = int(month)
        d = int(day)
        rows.append({
            'year': y,
            'month': m,
            'day': d,
            'ymd': f"{y:04d}-{m:02d}-{d:02d}",
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
        })
    return rows



