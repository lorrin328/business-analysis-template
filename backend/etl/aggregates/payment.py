"""ETL aggregate — auto-split from aggregator.py."""
import io
from typing import Dict, List

import pandas as pd

from etl.normalize import (
    _normalize_channel, _to_number, _amount_to_wan,
    _period_year_month, _fee_weight,
)
from etl.columns import _pick_col
from etl.classify import _classify_payment_period, _classify_jingdai_payment_period
from config.business_lines import TRANSFORM_CHANNELS

def _aggregate_payment_period(df: pd.DataFrame, *, daily: bool) -> List[Dict]:
    """转型业务交期结构聚合，可按月或按日输出。"""
    year_col = _pick_col(df, ['年'])
    date_col = _pick_col(df, ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    count_col = _pick_col(df, ['承保件数'])
    term_col = _pick_col(df, ['长短险'])
    pay_col = _pick_col(df, ['缴费年限'])

    if not all([channel_col, qj_col, pay_col]):
        raise ValueError(f"无法识别交期结构必要列。当前列: {list(df.columns)}")

    time_col = date_col or month_col
    work = _period_year_month(df, year_col, month_col if not date_col else None, time_col if date_col else None)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_count'] = _to_number(work[count_col]) if count_col else 0
    work['_category'] = work.apply(
        lambda r: _classify_payment_period(r[pay_col], r[term_col] if term_col else ''), axis=1
    )
    work = work[work['_category'].notna() & (work['_category'] != '')]

    group_cols = ['_year', '_month'] + (['_day'] if daily else []) + ['_channel', '_org', '_category']
    grouped = work.groupby(group_cols, dropna=False)
    rows = []
    for keys, group in grouped:
        if daily:
            year, month, day, channel, org, category = keys
        else:
            year, month, channel, org, category = keys
            day = None
        row = {
            'year': int(year),
            'month': int(month),
            'business_type': '转型',
            'channel': str(channel),
            'org': str(org),
            'category': str(category),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'count': int(group['_count'].sum()),
        }
        if daily:
            row['day'] = int(day)
        rows.append(row)
    return rows


def aggregate_payment_period(df: pd.DataFrame) -> List[Dict]:
    return _aggregate_payment_period(df, daily=False)


def aggregate_payment_period_daily(df: pd.DataFrame) -> List[Dict]:
    return _aggregate_payment_period(df, daily=True)


def _aggregate_jingdai_payment_period(df: pd.DataFrame, *, daily: bool) -> List[Dict]:
    """经代业务交期结构聚合，可按月或按日输出。"""
    time_col = _pick_col(df, ['时间', '年月'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])
    org_col = _pick_col(df, ['经代机构'])
    term_cat_col = _pick_col(df, ['当前缴别大类'])

    if not all([time_col, qj_col, pay_col]):
        raise ValueError(f"无法识别经代交期结构必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, time_col)
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_count'] = 0  # 经代Excel无件数列
    work['_category'] = work.apply(
        lambda r: _classify_jingdai_payment_period(r[pay_col], r[term_cat_col] if term_cat_col else ''), axis=1
    )
    work = work[work['_category'].notna() & (work['_category'] != '')]

    group_cols = ['_year', '_month'] + (['_day'] if daily else []) + ['_org', '_category']
    grouped = work.groupby(group_cols, dropna=False)
    rows = []
    for keys, group in grouped:
        if daily:
            year, month, day, org, category = keys
        else:
            year, month, org, category = keys
            day = None
        row = {
            'year': int(year),
            'month': int(month),
            'business_type': '经代',
            'channel': '',
            'org': str(org),
            'category': str(category),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'count': 0,
        }
        if daily:
            row['day'] = int(day)
        rows.append(row)
    return rows


def aggregate_jingdai_payment_period(df: pd.DataFrame) -> List[Dict]:
    return _aggregate_jingdai_payment_period(df, daily=False)


def aggregate_jingdai_payment_period_daily(df: pd.DataFrame) -> List[Dict]:
    return _aggregate_jingdai_payment_period(df, daily=True)

