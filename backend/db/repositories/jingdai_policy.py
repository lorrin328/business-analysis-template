"""Range-distinct counts with explicit source semantics; never sum daily counts."""
from __future__ import annotations


IDENTITY_NOTE = '经代按所选范围内非空投保单号去重；跨日、跨产品和跨平台不重复计入合计，含冲正记录，不等同于净承保件数。各分项保单可能重叠，分项件数不能直接相加。'
MIXED_NOTE = '所选范围混有投保单号去重和旧源件数净额，合并件数及件均不可计算。'


def query_policy_counts(conn, where, params, group_columns=(), *, channel=''):
    """Return None when facts are unavailable; {} means no selected JD facts."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agg_jingdai_policy_daily'").fetchone():
        return None
    allowed = {'org', 'category', 'product_category', 'product_name'}
    if not set(group_columns) <= allowed:
        raise ValueError('Unsupported policy count grouping')
    columns = ', '.join(group_columns)
    prefix = columns + ', ' if columns else ''
    group = ' GROUP BY ' + columns if columns else ''
    # Both projections use the caller's exact filters, including dates, months,
    # source selection and platform. Parameters remain bound, never interpolated.
    channel_sql = "'经代'" if channel == '经代' else "''"
    rows = conn.execute(f'''
        SELECT {prefix} COUNT(*) AS fact_rows,
               MIN(identity_source) AS min_basis, MAX(identity_source) AS max_basis,
               MIN(year) AS first_year, MAX(year) AS last_year,
               SUM(CASE WHEN identity_source=1 AND TRIM(policy_no)='' THEN source_rows ELSE 0 END) AS missing_identity,
               COUNT(DISTINCT NULLIF(TRIM(policy_no), '')) AS identity_count,
               SUM(legacy_count) AS legacy_count, SUM(legacy_missing) AS legacy_missing
        FROM (SELECT *, '经代' AS business_type, {channel_sql} AS channel FROM agg_jingdai_policy_daily)
        WHERE {where}{group}
    ''', params).fetchall()
    result = {}
    for row in rows:
        if not row['fact_rows']:
            continue
        if row['max_basis'] == 0 and 2020 <= row['first_year'] <= row['last_year'] <= 2024:
            # Retained historical aggregates are authoritative. Partial old raw
            # facts cannot replace complete historical counts in the API.
            continue
        if row['min_basis'] != row['max_basis']:
            count, basis = None, 'mixed'
        elif row['max_basis'] == 1:
            count = None if row['missing_identity'] else int(row['identity_count'])
            basis = 'policy_identity' if count is not None else 'unavailable'
        else:
            count = None if row['legacy_missing'] else int(row['legacy_count'] or 0)
            basis = 'source_net' if count is not None else 'unavailable'
        result[tuple(row[column] for column in group_columns)] = {'count': count, 'basis': basis, 'identity': bool(row['max_basis'])}
    return result
