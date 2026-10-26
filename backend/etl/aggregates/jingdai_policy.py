"""Identity-bearing daily facts: policy counts must be distinct over the query range."""
from __future__ import annotations

import pandas as pd

from etl.classify import _classify_jingdai_payment_period
from etl.columns import _pick_col
from etl.normalize import _period_year_month, _to_number, jingdai_policy_counts


def aggregate_jingdai_policy_daily(df: pd.DataFrame) -> list[dict]:
    time = _pick_col(df, ['时间', '年月日', '统计时间_年月日', '年月'])
    qj = _pick_col(df, ['期交保费'])
    gm = _pick_col(df, ['承保年化规保', '年化规保', '规模保费'])
    if not all([time, qj, gm]):
        return []
    work = _period_year_month(df, None, time, require_day=True)
    if work.empty:
        return []
    def text(column, fallback=''):
        return work[column].fillna('').astype(str).str.strip().replace('', fallback) if column in work else pd.Series(fallback, index=work.index)
    work['_org'] = text('经代机构', '未知')
    work['_product'] = text('产品名称', '未分类')
    work['_policy'] = text('投保单号')
    if '经代源格式' in work:
        work['_identity'] = text('经代源格式').eq('policy_detail').astype(int)
    else:
        work['_identity'] = int('投保单号' in work)
    work['_qj'] = _to_number(work[qj], required=True)
    work['_gm'] = _to_number(work[gm], required=True)
    legacy, missing = jingdai_policy_counts(work)
    work['_legacy'] = legacy.where(work['_identity'].eq(0), 0)
    work['_legacy_missing'] = missing.where(work['_identity'].eq(0), False).astype(int)
    pay = work.get('缴费年限', pd.Series(None, index=work.index, dtype=object))
    term = work.get('当前缴别大类', pd.Series('', index=work.index))
    work['_category'] = [_classify_jingdai_payment_period(p, t) or '未分类' for p, t in zip(pay, term)]
    keys = ['_year', '_month', '_day', '_org', '_product', '_category', '_policy', '_identity']
    grouped = work.groupby(keys, dropna=False).agg(
        qj=('_qj', 'sum'), gm=('_gm', 'sum'), source_rows=('_qj', 'size'),
        legacy_count=('_legacy', 'sum'), legacy_missing=('_legacy_missing', 'sum')).reset_index()
    return [{
        'year': int(r['_year']), 'month': int(r['_month']), 'day': int(r['_day']),
        'org': r['_org'], 'product_category': r['_product'], 'product_name': r['_product'],
        'category': r['_category'], 'policy_no': r['_policy'], 'identity_source': int(r['_identity']),
        'qj_premium': float(r['qj']) / 10000.0, 'gm_premium': float(r['gm']) / 10000.0,
        'source_rows': int(r['source_rows']), 'legacy_count': float(r['legacy_count']),
        'legacy_missing': int(r['legacy_missing']),
    } for r in grouped.to_dict('records')]
