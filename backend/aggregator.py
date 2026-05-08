import io
from typing import Dict, List

import pandas as pd


CHANNEL_MAP = {'证券': '证保', '网服': '蚁桥'}
TRANSFORM_CHANNELS = {'OTO', '证保', '蚁桥'}


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith('Unnamed:')]]
    return df


def _find_header_row(file_bytes: bytes, required_cols: set[str], max_rows: int = 40) -> int:
    preview = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=max_rows)
    for idx, row in preview.iterrows():
        values = {str(v).strip() for v in row.tolist() if pd.notna(v)}
        if required_cols.issubset(values):
            return int(idx)
    return 0


def _read_excel(file_bytes: bytes, required_cols: set[str]) -> pd.DataFrame:
    header = _find_header_row(file_bytes, required_cols)
    df = pd.read_excel(io.BytesIO(file_bytes), header=header)
    return _clean_columns(df)


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').fillna(0)


def _normalize_channel(value) -> str:
    if pd.isna(value):
        return ''
    text = str(value).strip()
    return CHANNEL_MAP.get(text, text)


def _pick_col(df: pd.DataFrame, candidates: List[str], contains: List[str] | None = None) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    if contains:
        for col in df.columns:
            if any(token in col for token in contains):
                return col
    return None


def _year_month_day_from_series(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    dt = pd.to_datetime(series, errors='coerce')
    years = dt.dt.year
    months = dt.dt.month
    days = dt.dt.day
    return years, months, days


def _period_year_month(df: pd.DataFrame, year_col: str | None, month_col: str | None, date_col: str | None = None) -> pd.DataFrame:
    out = df.copy()
    if date_col and date_col in out.columns:
        years, months, days = _year_month_day_from_series(out[date_col])
        out['_year'] = years
        out['_month'] = months
        out['_day'] = days
    elif month_col and month_col in out.columns:
        years, months, days = _year_month_day_from_series(out[month_col])
        out['_year'] = years
        out['_month'] = months
        out['_day'] = days.fillna(1)
    else:
        out['_year'] = pd.NA
        out['_month'] = pd.NA
        out['_day'] = 1

    if year_col and year_col in out.columns:
        out['_year'] = out['_year'].fillna(pd.to_numeric(out[year_col], errors='coerce'))

    if out['_month'].isna().any():
        month_num = pd.to_numeric(out[month_col], errors='coerce') if month_col else pd.Series(pd.NA, index=out.index)
        out['_month'] = out['_month'].fillna(month_num)

    out = out.dropna(subset=['_year', '_month'])
    out['_year'] = out['_year'].astype(int)
    out['_month'] = out['_month'].astype(int)
    out['_day'] = out['_day'].fillna(1).astype(int)
    out = out[(out['_month'] >= 1) & (out['_month'] <= 12)]
    return out


def _amount_to_wan(value) -> float:
    return round(float(value or 0) / 10000.0, 4)


def _fee_weight(pay_years) -> float:
    try:
        years = float(pay_years)
    except (TypeError, ValueError):
        return 0.1
    if years < 3:
        return 0.1
    if years < 5:
        return 0.3
    if years < 10:
        return 0.5
    return 1.0


def parse_performance_excel(file_bytes: bytes) -> pd.DataFrame:
    df = _read_excel(file_bytes, {'年', '年月', '业务模式', '期交保费'})
    df['业务模式'] = df['业务模式'].map(_normalize_channel)
    return df[df['业务模式'].isin(TRANSFORM_CHANNELS)]


def parse_jingdai_excel(file_bytes: bytes) -> pd.DataFrame:
    return _read_excel(file_bytes, {'时间', '承保年化规保', '期交保费'})


def parse_hr_excel(file_bytes: bytes) -> pd.DataFrame:
    df = _read_excel(file_bytes, {'统计年', '统计月', '业务模式名称', '月初在职人力', '月末在职人力'})
    df['业务模式名称'] = df['业务模式名称'].map(_normalize_channel)
    return df[df['业务模式名称'].isin(TRANSFORM_CHANNELS)]


def parse_value_excel(file_bytes: bytes) -> pd.DataFrame:
    df = _read_excel(file_bytes, {'年月', '业务模式名称', '价值'})
    df['业务模式名称'] = df['业务模式名称'].map(_normalize_channel)
    return df[df['业务模式名称'].isin(TRANSFORM_CHANNELS)]


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


def aggregate_daily_performance(df: pd.DataFrame) -> List[Dict]:
    """按日聚合转型业务保费数据，用于月度视图的日累计趋势。"""
    year_col = _pick_col(df, ['年'])
    date_col = _pick_col(df, ['日期', '出单日期', '投保日期', '承保日期'])
    month_col = _pick_col(df, ['年月', '月', '月份'])
    channel_col = _pick_col(df, ['业务模式', '业务模式名称', '渠道'])
    qj_col = _pick_col(df, ['期交保费'])
    gm_col = _pick_col(df, ['年化规保', '规模保费', '规保'], ['规模', '规保'])
    zs_col = _pick_col(df, ['折算保费'], ['折算', '标准'])

    # 优先使用日期列，如果没有则回退到年月列
    time_col = date_col or month_col
    if not all([time_col, channel_col, qj_col]):
        return []

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


def aggregate_org_value(df: pd.DataFrame) -> List[Dict]:
    """按机构+业务模式聚合价值数据"""
    month_col = _pick_col(df, ['年月', '时间'])
    channel_col = _pick_col(df, ['业务模式名称', '业务模式', '渠道'])
    org_col = _pick_col(df, ['销售机构名称', '机构', '分公司', 'org'])
    value_col = _pick_col(df, ['价值'])

    if not all([month_col, channel_col, value_col]):
        return []

    work = _period_year_month(df, None, month_col)
    work['_channel'] = work[channel_col].map(_normalize_channel)
    work = work[work['_channel'].isin(TRANSFORM_CHANNELS)]
    work['_org'] = work[org_col].fillna('未知').astype(str).str.strip().replace('', '未知') if org_col else '未知'
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
