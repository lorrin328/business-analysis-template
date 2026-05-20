"""长险期交保费聚合 — 转型 + 经代。"""
from typing import Dict, List

import pandas as pd

from etl.normalize import _normalize_channel, _to_number, _amount_to_wan, _period_year_month
from etl.columns import _pick_col
from config.business_lines import TRANSFORM_CHANNELS
from config.orgs import ORG_SCOPE


def aggregate_transform_longterm(df: pd.DataFrame) -> List[Dict]:
    """转型业务长险期交：长短险=长期 或 产品代码=4281。"""
    year_col = _pick_col(df, ['年'])
    date_col = _pick_col(df, ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    qj_col = _pick_col(df, ['期交保费'])
    term_col = _pick_col(df, ['长短险'])
    code_col = _pick_col(df, ['产品代码'])

    if not all([channel_col, qj_col]):
        return []

    time_col = date_col or month_col
    work = _period_year_month(df, year_col, month_col if not date_col else None, time_col if date_col else None)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work = work[work['_org'].isin(ORG_SCOPE)]
    work['_qj'] = _to_number(work[qj_col])
    # 长险条件
    is_longterm = False
    if term_col:
        is_longterm = work[term_col].fillna('').astype(str).str.strip() == '长期'
    if code_col:
        is_code4281 = work[code_col].fillna('').astype(str).str.strip() == '4281'
        is_longterm = is_longterm | is_code4281 if term_col else is_code4281
    if term_col or code_col:
        work = work[is_longterm]

    grouped = work.groupby(['_year', '_month', '_channel', '_org'], dropna=False)
    rows = []
    for (year, month, channel, org), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'business_type': '转型',
            'channel': str(channel),
            'org': str(org),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
        })
    return rows


def aggregate_jingdai_longterm(df: pd.DataFrame) -> List[Dict]:
    """经代业务长险期交：排除 当前缴别大类=期交 且 缴费年限=1。"""
    time_col = _pick_col(df, ['时间', '年月'])
    qj_col = _pick_col(df, ['期交保费'])
    pay_col = _pick_col(df, ['缴费年限'])
    org_col = _pick_col(df, ['经代机构'])
    term_cat_col = _pick_col(df, ['当前缴别大类'])

    if not all([time_col, qj_col, pay_col]):
        return []

    work = _period_year_month(df, None, time_col)
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
    work['_qj'] = _to_number(work[qj_col])
    # 长险：排除 (期交 且 缴费年限=1)
    if term_cat_col:
        is_term = work[term_cat_col].fillna('').astype(str).str.strip() == '期交'
        pay_num = pd.to_numeric(work[pay_col], errors='coerce').fillna(0)
        is_short = is_term & (pay_num == 1)
        work = work[~is_short]

    grouped = work.groupby(['_year', '_month', '_org'], dropna=False)
    rows = []
    for (year, month, org), group in grouped:
        rows.append({
            'year': int(year),
            'month': int(month),
            'business_type': '经代',
            'channel': '',
            'org': str(org),
            'qj_premium': _amount_to_wan(group['_qj'].sum()),
        })
    return rows
