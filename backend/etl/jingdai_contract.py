"""Canonical Jingdai source fields with explicit, non-interchangeable count bases."""
from __future__ import annotations

import numpy as np
import pandas as pd

from etl.classify import _classify_jingdai_payment_period
from etl.normalize import NumericSourceError, _to_number, _year_month_day_from_series


POLICY_DETAIL = 'policy_detail'
LEGACY_AGGREGATE = 'legacy_aggregate'
IDENTITY_DAILY = 'policy_identity_daily'
SOURCE_NET = 'source_net'
SOURCE_FIELDS = (
    '统计时间_年月日', '销售平台', '投保单号', '产品代码', '产品名称', '产品销售名称',
    '长短险', '缴别', '缴费年限', '是否社会保障类产品', '是否商保年金产品',
    '是否个人养老金', '期交保费', '年化规保',
)


def _present(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype('string').str.strip().ne('').fillna(False)


def _coalesce(frame: pd.DataFrame, left: str, right: str) -> None:
    """Fill aliases only where absent; keep the original source representation."""
    if left not in frame:
        frame[left] = frame[right] if right in frame else None
    elif right in frame:
        frame[left] = frame[left].where(_present(frame[left]), frame[right])
    if right not in frame:
        frame[right] = frame[left]
    else:
        frame[right] = frame[right].where(_present(frame[right]), frame[left])


def _legacy_counts(frame: pd.DataFrame) -> pd.Series:
    values = pd.Series(None, index=frame.index, dtype=object)
    for name in ('承保件数', '承保保单件数', '承保产品件数'):
        if name not in frame:
            continue
        source = frame[name]
        left, right = _present(values), _present(source)
        conflict = left & right & _to_number(values).ne(_to_number(source))
        if conflict.any():
            raise NumericSourceError('经代件数字段两列不一致；请确认后重新导入。')
        values = values.where(left, source.where(right))
    return values


def normalize_jingdai_source(frame: pd.DataFrame, *, source_format: str | None = None) -> pd.DataFrame:
    """Normalize reader and persisted frames without inventing historical identity.

    A policy source's 承保件数 is a contribution at the daily fact grain only.
    Query-range counts must continue to use COUNT DISTINCT over policy facts.
    Old exports retain their supplied signed counts and a different source basis.
    Missing markers default to legacy, even if a database schema has added an
    empty 投保单号 column; column existence is not identity-source evidence.
    """
    result = frame.copy()
    if source_format is not None:
        if source_format not in {POLICY_DETAIL, LEGACY_AGGREGATE}:
            raise ValueError('不支持的经代来源格式。')
        result['经代源格式'] = source_format
    elif '经代源格式' not in result:
        result['经代源格式'] = LEGACY_AGGREGATE
    else:
        result['经代源格式'] = result['经代源格式'].where(_present(result['经代源格式']), LEGACY_AGGREGATE)
    identity = result['经代源格式'].eq(POLICY_DETAIL)

    # Read the old signed count before adding canonical columns. Policy-source
    # derived daily contributions are recomputed below, never reused as net counts.
    old = _legacy_counts(result.loc[~identity])
    for left, right in (('时间', '统计时间_年月日'), ('经代机构', '销售平台'),
                        ('承保年化规保', '年化规保')):
        _coalesce(result, left, right)
    for name in SOURCE_FIELDS:
        if name not in result:
            result[name] = None
    if '缴别' in result and '当前缴别小类' in result:
        result['缴别'] = result['缴别'].where(_present(result['缴别']), result['当前缴别小类'])
    result['投保单号'] = result['投保单号'].map(lambda value: str(value).strip() if pd.notna(value) else None)

    years = result['缴费年限']
    present = _present(years)
    numeric = pd.to_numeric(years.where(present), errors='coerce')
    legal = numeric.notna() & np.isfinite(numeric.fillna(0)) & numeric.ge(0) & numeric.mod(1).eq(0)
    invalid = identity & present & ~legal
    if invalid.any():
        raise NumericSourceError(f'缴费年限存在{int(invalid.sum())}个非法数值；请提供非负整数年限，缺失保持空值。')
    # Old source values remain unchanged; this migration cannot manufacture a
    # new historical payment-period definition from source frequency or years.
    result['缴费年限'] = years.where(~(identity & legal), numeric)
    result.loc[~present, '缴费年限'] = None

    if '当前缴别大类' not in result:
        result['当前缴别大类'] = None
    frequency = result['缴别'].astype('string').str.strip()
    recurring = frequency.isin(['月交', '年交', '季交', '半年交', '双月交', '周交', '日交',
                               '月缴', '年缴', '季缴', '半年缴'])
    derived_term = pd.Series(None, index=result.index, dtype=object)
    derived_term.loc[legal & numeric.gt(0)] = '期交'
    derived_term.loc[recurring] = '期交'
    derived_term.loc[frequency.isin(['趸交', '趸缴']) | (legal & numeric.eq(0))] = '趸交'
    needs_term = identity & ~_present(result['当前缴别大类'])
    result['当前缴别大类'] = result['当前缴别大类'].where(~needs_term, derived_term)

    counts = pd.Series(None, index=result.index, dtype=object)
    counts.loc[~identity] = old
    if identity.any():
        current = result.loc[identity]
        y, m, d = _year_month_day_from_series(current['时间'])
        keys = pd.DataFrame({
            'year': y, 'month': m, 'day': d,
            'platform': current['经代机构'].fillna('').astype(str).str.strip(),
            'product': current['产品名称'].fillna('').astype(str).str.strip(),
            'category': [_classify_jingdai_payment_period(pay, term) or '未分类'
                         for pay, term in zip(current['缴费年限'], current['当前缴别大类'])],
            'policy': current['投保单号'].fillna('').astype(str).str.strip(),
        }, index=current.index)
        known = _present(current['投保单号']) & y.notna() & m.notna() & d.notna()
        contributions = (~keys.duplicated(keep='first')).astype(int)
        counts.loc[current.index] = contributions.where(known)
    result['承保件数'] = counts
    result['件数来源'] = pd.Series(np.where(identity, IDENTITY_DAILY, SOURCE_NET), index=result.index)
    return result
