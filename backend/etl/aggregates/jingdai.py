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


def _set_discount_amounts(work: pd.DataFrame, pay_col: str | None) -> None:
    """Keep unknown payment terms separate from a real zero discount amount."""
    years = (pd.to_numeric(work[pay_col], errors='coerce') if pay_col
             else pd.Series(float('nan'), index=work.index))
    known = years.notna() & years.ge(0) & years.lt(float('inf'))
    work['_zs_missing'] = (~known).astype(int)
    work['_zs'] = (work['_qj'] * years.map(_fee_weight)).where(known, 0.0)


def _load_jingdai_product_config(conn=None) -> dict:
    if conn is not None:
        rows = conn.execute("SELECT product_code, is_annuity, is_protection FROM product_config WHERE business_type = '经代'").fetchall()
        return {str(r[0]).strip(): {'is_annuity': str(r[1]).upper() == 'Y',
                                  'is_protection': str(r[2]).upper() == 'Y'} for r in rows}
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


def _set_product_amounts(work: pd.DataFrame, product_name_col: str | None, config_map) -> None:
    """An explicit source annuity flag takes precedence over legacy manual settings."""
    work['_is_annuity'] = False
    work['_is_protection'] = False
    if product_name_col:
        if config_map is None:
            config_map = _load_jingdai_product_config()
        keys = work[product_name_col].astype(str).str.strip()
        work['_is_annuity'] = keys.map(lambda key: config_map.get(key, {}).get('is_annuity', False)).fillna(False)
        work['_is_protection'] = keys.map(lambda key: config_map.get(key, {}).get('is_protection', False)).fillna(False)
    if '是否商保年金产品' in work.columns:
        flags = work['是否商保年金产品'].astype('string').str.strip().str.upper()
        explicit = flags.isin(['Y', 'N'])
        work['_is_annuity'] = work['_is_annuity'].where(~explicit, flags.eq('Y').fillna(False))
    work['_product_annuity'] = work['_qj'].where(work['_is_annuity'], 0)
    work['_product_protection'] = work['_qj'].where(work['_is_protection'], 0)


def aggregate_jingdai(df: pd.DataFrame, *, config_map=None) -> List[Dict]:
    time_col = _pick_col(df, ['时间', '年月'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])
    product_name_col = _pick_col(df, ['产品名称'])

    if not all([time_col, qj_col, gm_col]):
        raise ValueError(f"无法识别经代必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, time_col)
    work['_qj'] = _to_number(work[qj_col], required=True)
    work['_gm'] = _to_number(work[gm_col])
    _set_discount_amounts(work, pay_col)
    _set_product_amounts(work, product_name_col, config_map)

    grouped = work.groupby(['_year', '_month'], dropna=False)
    rows = []
    for (year, month), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
            'zs_missing': int(group['_zs_missing'].sum()),
            'product_annuity': _amount_to_wan(group['_product_annuity'].sum()),
            'product_protection': _amount_to_wan(group['_product_protection'].sum()),
        })
    return rows


def aggregate_jingdai_daily(df: pd.DataFrame, *, config_map=None) -> List[Dict]:
    """按经代基表的时间字段聚合到日，用于经代月度/季度日累计趋势。"""
    time_col = _pick_col(df, ['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])
    product_name_col = _pick_col(df, ['产品名称'])

    if not all([time_col, qj_col, gm_col]):
        raise ValueError(f"无法识别经代日聚合必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, None, time_col, require_day=True)
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col])
    _set_discount_amounts(work, pay_col)
    _set_product_amounts(work, product_name_col, config_map)

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
            'zs_missing': int(group['_zs_missing'].sum()),
            'product_annuity': _amount_to_wan(group['_product_annuity'].sum()),
            'product_protection': _amount_to_wan(group['_product_protection'].sum()),
        })
    return rows



