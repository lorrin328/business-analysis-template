"""ETL aggregate — auto-split from aggregator.py."""
import io
from typing import Dict, List

import pandas as pd

from etl.normalize import (
    _normalize_channel, _to_number, _amount_to_wan,
    _period_year_month, _fee_weight,
)
from etl.columns import _pick_col
from config.business_lines import TRANSFORM_CHANNELS
from config.orgs import ORG_SCOPE
from metrics.business_rules import is_tenyear_product, normalize_product_code


def _is_yes_flag(value) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().upper()
    return text in {'Y', 'YES', 'TRUE', '1', '是'}

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
    pay_years_col = _pick_col(df, ['缴费年限'])
    product_code_col = _pick_col(df, ['产品代码'])
    annuity_col = _pick_col(df, ['是否商保年金产品', '是否商保年金', '商保年金标识'])
    protection_col = _pick_col(df, [
        '是否社会保障型产品',
        '是否社会保障类产品',
        '社会保障类产品标识',
        '是否保障类产品',
    ])

    time_col = date_col or month_col
    if not all([time_col, channel_col, org_col, qj_col]):
        raise ValueError(f"无法识别机构日常业绩必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col if not date_col else None, time_col if date_col else None)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知')
    work = work[work['_org'].isin(ORG_SCOPE)]
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_zs'] = _to_number(work[zs_col]) if zs_col else 0
    work['_product_code'] = ""
    if product_code_col:
        work['_product_code'] = work[product_code_col].map(normalize_product_code)
    work['_is_10year'] = False
    if pay_years_col:
        work['_pay_years_num'] = pd.to_numeric(work[pay_years_col], errors='coerce').fillna(0)
        work['_is_10year'] = work.apply(
            lambda r: is_tenyear_product(r['_pay_years_num'], r['_product_code'], r['_year']),
            axis=1,
        )
    elif product_code_col:
        work['_is_10year'] = work.apply(
            lambda r: is_tenyear_product(None, r['_product_code'], r['_year']),
            axis=1,
        )
    work['_is_annuity'] = work[annuity_col].map(_is_yes_flag) if annuity_col else False
    work['_is_protection'] = work[protection_col].map(_is_yes_flag) if protection_col else False
    work['_product_10year'] = work['_qj'].where(work['_is_10year'], 0)
    work['_product_annuity'] = work['_qj'].where(work['_is_annuity'], 0)
    work['_product_protection'] = work['_qj'].where(work['_is_protection'], 0)

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
            'product_10year': _amount_to_wan(group['_product_10year'].sum()),
            'product_annuity': _amount_to_wan(group['_product_annuity'].sum()),
            'product_protection': _amount_to_wan(group['_product_protection'].sum()),
        })
    return rows


def aggregate_org_performance(df: pd.DataFrame) -> List[Dict]:
    """按机构+业务模式聚合业绩数据，含产品分类明细。

    转型业务产品分类（商保年金 / 社会保障型产品）直接读取业绩基表标识列。
    10年期产品仍按缴费年限 >= 10 判断。
    """
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])
    pay_years_col = _pick_col(df, ['缴费年限'])
    product_code_col = _pick_col(df, ['产品代码'])
    annuity_col = _pick_col(df, ['是否商保年金产品', '是否商保年金', '商保年金标识'])
    protection_col = _pick_col(df, [
        '是否社会保障型产品',
        '是否社会保障类产品',
        '社会保障类产品标识',
        '是否保障类产品',
    ])

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
    work['_product_code'] = ""
    if product_code_col:
        work['_product_code'] = work[product_code_col].map(normalize_product_code)

    work['_is_10year'] = False
    if pay_years_col:
        work['_pay_years_num'] = pd.to_numeric(work[pay_years_col], errors='coerce').fillna(0)
        work['_is_10year'] = work.apply(
            lambda r: is_tenyear_product(r['_pay_years_num'], r['_product_code'], r['_year']),
            axis=1,
        )
    elif product_code_col:
        work['_is_10year'] = work.apply(
            lambda r: is_tenyear_product(None, r['_product_code'], r['_year']),
            axis=1,
        )

    work['_is_annuity'] = False
    work['_is_protection'] = False
    if annuity_col:
        work['_is_annuity'] = work[annuity_col].map(_is_yes_flag)
    if protection_col:
        work['_is_protection'] = work[protection_col].map(_is_yes_flag)

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



