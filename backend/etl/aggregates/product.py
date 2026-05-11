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



