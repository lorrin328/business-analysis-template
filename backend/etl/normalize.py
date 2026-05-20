"""Data normalization utilities."""
from typing import List, Optional

import pandas as pd


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').fillna(0)


from config.business_lines import CHANNEL_MAP


def _normalize_channel(value) -> str:
    return CHANNEL_MAP.get(str(value).strip(), str(value).strip())


def _year_month_day_from_series(series: pd.Series):
    text = series.astype(str).str.strip()
    digit_text = text.where(text.str.fullmatch(r'\d+'), '')
    dt = pd.to_datetime(series.mask(digit_text != ''), errors='coerce')

    # pandas treats bare numbers like 5 or 202605 as nanoseconds after epoch.
    # In these Excel files they mean month or YYYYMM, so parse them explicitly.
    short_number = digit_text.str.fullmatch(r'\d{1,2}', na=False)
    dt = dt.mask(short_number)

    yyyymm = digit_text.str.fullmatch(r'\d{6}', na=False)
    if yyyymm.any():
        dt = dt.mask(yyyymm, pd.to_datetime(text.where(yyyymm), format='%Y%m', errors='coerce'))

    yyyymmdd = digit_text.str.fullmatch(r'\d{8}', na=False)
    if yyyymmdd.any():
        dt = dt.mask(yyyymmdd, pd.to_datetime(text.where(yyyymmdd), format='%Y%m%d', errors='coerce'))
    return dt.dt.year, dt.dt.month, dt.dt.day


def _period_year_month(df: pd.DataFrame, year_col: Optional[str], month_col: Optional[str], date_col: Optional[str] = None):
    work = df.copy()
    if date_col and date_col in work.columns:
        y, m, d = _year_month_day_from_series(work[date_col])
        work['_year'] = y
        work['_month'] = m
        work['_day'] = d
    elif month_col and month_col in work.columns:
        y, m, d = _year_month_day_from_series(work[month_col])
        work['_year'] = y
        work['_month'] = m
        work['_day'] = d.fillna(1)
    else:
        work['_year'] = pd.NA
        work['_month'] = pd.NA
        work['_day'] = 1
    if year_col and year_col in work.columns:
        work['_year'] = work['_year'].fillna(pd.to_numeric(work[year_col], errors='coerce'))
    if month_col and month_col in work.columns:
        work['_month'] = work['_month'].fillna(pd.to_numeric(work[month_col], errors='coerce'))
    work = work[work['_year'].notna() & work['_month'].notna()]
    work['_month'] = work['_month'].astype(int)
    work = work[(work['_month'] >= 1) & (work['_month'] <= 12)]
    work['_year'] = work['_year'].astype(int)
    work['_day'] = work['_day'].fillna(1).astype(int)
    return work


def _amount_to_wan(value) -> float:
    return round(float(value) / 10000.0, 4)


def _fee_weight(pay_years) -> float:
    try:
        years = float(pay_years)
    except (TypeError, ValueError):
        return 0.1
    if years < 3:  return 0.1
    if years < 5:  return 0.3
    if years < 10: return 0.5
    return 1.0
