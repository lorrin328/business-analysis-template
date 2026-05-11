"""ETL aggregate — auto-split from aggregator.py."""
import io
from typing import Dict, List

import pandas as pd

from etl.normalize import (
    _normalize_channel, _to_number, _amount_to_wan,
    _period_year_month, _fee_weight,
)
from etl.columns import _pick_col

CHANNEL_MAP = {'证券': '证保', '网服': '蚁桥'}
TRANSFORM_CHANNELS = {'OTO', '证保', '蚁桥'}
ORG_SCOPE = {'上海', '湖北', '四川', '辽宁', '山东', '广东', '福建', '浙江', '河南', '北京'}

def aggregate_org_daily_performance(df: pd.DataFrame) -> List[Dict]:
    """按日、机构、业务模式聚合保费，用于机构筛选后的同口径日累计趋势。"""
    year_col = _pick_col(df, ['年'])
    date_col = _pick_col(df, ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])

    time_col = date_col or month_col
    if not all([time_col, channel_col, org_col, qj_col]):
        return []

    work = _period_year_month(df, year_col, month_col if not date_col else None, time_col if date_col else None)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知')
    work = work[work['_org'].isin(ORG_SCOPE)]
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_zs'] = _to_number(work[zs_col]) if zs_col else 0

    grouped = work.groupby(['_year', '_month', '_day', '_org', '_channel'], dropna=False)
    rows = []
    for (year, month, day, org, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'day': int(day),
            'org': str(org),
            'channel': str(channel),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
        })
    return rows


def aggregate_product_structure(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    qj_col = _pick_col(df, ['期交保费'])
    count_col = _pick_col(df, ['承保件数'])
    dims = {
        'design_cat': _pick_col(df, ['产品设计分类']),
        'pay_years': _pick_col(df, ['缴费年限']),
        'cov_years': _pick_col(df, ['保障年限']),
        'annuity': _pick_col(df, ['是否商保年金产品']),
    }

    if not all([year_col, month_col, qj_col]):
        raise ValueError(f"无法识别产品结构必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col)
    work['_qj'] = _to_number(work[qj_col])
    work['_count'] = _to_number(work[count_col]) if count_col else 1

    rows = []
    for dim, col in dims.items():
        if not col:
            continue
        part = work.copy()
        part['_label'] = part[col].fillna('未分类').astype(str).str.strip().replace('', '未分类')
        grouped = part.groupby(['_year', dim and '_label'], dropna=False)
        for (year, label), group in grouped:
            rows.append({
                'year': int(year),
                'dimension': dim,
                'label': str(label),
                'premium': _amount_to_wan(group['_qj'].sum()),
                'count': int(group['_count'].sum()),
            })
    return rows


def aggregate_org_performance(df: pd.DataFrame) -> List[Dict]:
    """按机构+业务模式聚合业绩数据，含产品分类明细"""
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])
    pay_years_col = _pick_col(df, ['缴费年限'])
    is_annuity_col = _pick_col(df, ['是否商保年金产品'])
    term_type_col = _pick_col(df, ['长短险'])

    if not all([year_col, month_col, channel_col, qj_col]):
        raise ValueError(f"无法识别机构业绩必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work = work[work['_org'].isin(ORG_SCOPE)]
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_zs'] = _to_number(work[zs_col]) if zs_col else 0

    # 产品分类：10年期 / 商保年金 / 保障类
    work['_is_10year'] = False
    if pay_years_col:
        work['_pay_years_str'] = work[pay_years_col].fillna('').astype(str).str.strip()
        work['_is_10year'] = work['_pay_years_str'].str.contains('10年', na=False) & ~work['_pay_years_str'].str.contains('趸交', na=False)

    work['_is_annuity'] = False
    if is_annuity_col:
        work['_is_annuity'] = work[is_annuity_col].fillna('').astype(str).str.strip().str.upper().isin(['Y', 'YES', '是', 'TRUE', '1'])

    work['_is_protection'] = False
    if term_type_col:
        work['_term_str'] = work[term_type_col].fillna('').astype(str).str.strip()
        # 长期险中非年金视为保障类
        work['_is_protection'] = work['_term_str'].str.contains('长期', na=False) & ~work['_is_annuity']

    work['_product_10year'] = work['_qj'].where(work['_is_10year'], 0)
    work['_product_annuity'] = work['_qj'].where(work['_is_annuity'], 0)
    work['_product_protection'] = work['_qj'].where(work['_is_protection'], 0)

    grouped = work.groupby(['_year', '_month', '_org', '_channel'], dropna=False)
    rows = []
    for (year, month, org, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'org': str(org),
            'channel': str(channel),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
            'product_10year': _amount_to_wan(group['_product_10year'].sum()),
            'product_annuity': _amount_to_wan(group['_product_annuity'].sum()),
            'product_protection': _amount_to_wan(group['_product_protection'].sum()),
        })
    return rows



