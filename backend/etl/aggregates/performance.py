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

def aggregate_performance(df: pd.DataFrame) -> List[Dict]:
    year_col = _pick_col(df, ['年'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])

    if not all([year_col, month_col, channel_col, qj_col]):
        raise ValueError(f"无法识别业绩必要列。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_zs'] = _to_number(work[zs_col]) if zs_col else 0

    grouped = work.groupby(['_year', '_month', '_channel'], dropna=False)
    rows = []
    for (year, month, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'channel': str(channel),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
        })
    return rows



def aggregate_daily_performance(df: pd.DataFrame) -> List[Dict]:
    """按日聚合转型业务保费数据，用于月度视图的日累计趋势。"""
    year_col = _pick_col(df, ['年'])
    date_col = _pick_col(df, ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])

    # 优先使用日期列，如果没有则回退到年月列
    time_col = date_col or month_col
    if not all([time_col, channel_col, qj_col]):
        raise ValueError(f"无法识别日常业绩必要列（日期/年月、业务模式、期交保费）。当前列: {list(df.columns)}")

    work = _period_year_month(df, year_col, month_col if not date_col else None, time_col if date_col else None)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_qj'] = _to_number(work[qj_col])
    work['_gm'] = _to_number(work[gm_col]) if gm_col else 0
    work['_zs'] = _to_number(work[zs_col]) if zs_col else 0

    grouped = work.groupby(['_year', '_month', '_day', '_channel'], dropna=False)
    rows = []
    for (year, month, day, channel), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'day': int(day),
            'channel': str(channel),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
        })
    return rows



