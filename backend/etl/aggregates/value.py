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

def aggregate_value(df: pd.DataFrame) -> List[Dict]:
    month_col = _pick_col(df, ['年月', '时间'])
    channel_col = _pick_col(df, ['业务模式名称', '业务模式', '渠道'])
    value_col = _pick_col(df, ['价值'])

    if not all([month_col, channel_col, value_col]):
        raise ValueError(f"无法识别价值必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_value'] = _to_number(work[value_col])

    grouped = work.groupby(['_year', '_month', '_channel'], dropna=False)
    rows = []
    for (year, month, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'value_premium': _amount_to_wan(group['_value'].sum()),
        })
    return rows



def aggregate_org_value(df: pd.DataFrame) -> List[Dict]:
    """按机构+业务模式聚合价值数据"""
    month_col = _pick_col(df, ['年月', '时间'])
    channel_col = _pick_col(df, ['业务模式名称', '业务模式', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    value_col = _pick_col(df, ['价值'])

    if not all([month_col, channel_col, value_col]):
        raise ValueError(f"无法识别机构价值必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, None, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work = work[work['_org'].isin(ORG_SCOPE)]
    work['_value'] = _to_number(work[value_col])

    grouped = work.groupby(['_year', '_month', '_org', '_channel'], dropna=False)
    rows = []
    for (year, month, org, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'org': str(org),
            'channel': str(channel),
            'value_premium': _amount_to_wan(group['_value'].sum()),
        })
    return rows



