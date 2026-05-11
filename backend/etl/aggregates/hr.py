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

def aggregate_hr(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ['统计年', '年'])
    month_col = _pick_col(df, ['统计日期', '年月', '统计月', '月'])
    channel_col = _pick_col(df, ['业务模式名称', '业务模式', '渠道'])
    start_col = _pick_col(df, ['月初在职人力'])
    end_col = _pick_col(df, ['月末在职人力'])

    if not all([year_col, month_col, channel_col, start_col, end_col]):
        raise ValueError(f"无法识别人力必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_start'] = _to_number(work[start_col])
    work['_end'] = _to_number(work[end_col])

    grouped = work.groupby(['_year', '_month', '_channel'], dropna=False)
    rows = []
    for (year, month, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'start_headcount': int(group['_start'].sum()),
            'end_headcount': int(group['_end'].sum()),
            'active_headcount': 0,
        })
    return rows


def aggregate_active_headcount(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    staff_col = _pick_col(df, ['人员工号', '人员代码'])
    amount_col = _pick_col(df, ['折算保费', '期交保费'])

    if not all([year_col, month_col, channel_col, staff_col, amount_col]):
        return []

    work = _period_year_month(df, year_col, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_staff'] = work[staff_col].fillna('').astype(str).str.strip()
    work['_amount'] = _to_number(work[amount_col])
    work = work[(work['_staff'] != '') & (work['_amount'] > 0)]

    grouped = work.groupby(['_year', '_month', '_channel'], dropna=False)
    rows = []
    for (year, month, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'active_headcount': int(group['_staff'].nunique()),
        })
    return rows



