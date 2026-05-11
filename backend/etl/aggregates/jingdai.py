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

def aggregate_jingdai(df: pd.DataFrame) -> List[Dict]:
    time_col = _pick_col(df, ['时间', '年月'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    pay_col = _pick_col(df, ['缴费年限'])

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

    grouped = work.groupby(['_year', '_month'], dropna=False)
    rows = []
    for (year, month), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
            'gm_premium': _amount_to_wan(group['_gm'].sum()),
            'zs_premium': _amount_to_wan(group['_zs'].sum()),
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



