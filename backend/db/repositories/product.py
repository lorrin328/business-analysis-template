"""Repository queries — auto-split from database.py."""
import json
import logging
import sqlite3
from db.connection import get_db
from db.schema import init_db

logger = logging.getLogger("business-analysis")


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item and item.strip()]


def _compact_period_expr(column: str) -> str:
    quoted = '"' + column.replace('"', '""') + '"'
    expr = f'CAST({quoted} AS TEXT)'
    for token in ['-', '/', '.', '年', '月', '日', ' ']:
        expr = f"replace({expr}, '{token}', '')"
    return expr


def _append_period_filter(column: str, year: int, months: list[int] | None, params: list) -> str:
    expr = _compact_period_expr(column)
    clause = f' AND CAST(substr({expr}, 1, 4) AS INTEGER) = ?'
    params.append(year)
    if months:
        m_placeholders = ','.join(['?'] * len(months))
        clause += f' AND CAST(substr({expr}, 5, 2) AS INTEGER) IN ({m_placeholders})'
        params.extend(months)
    return clause


def _query_product_structure_raw(
    conn: sqlite3.Connection,
    year: int,
    transform_lines: list[str],
    jingdai_orgs: list[str],
    include_transform: bool,
    include_jingdai: bool,
    orgs: list[str] | None = None,
    months: list[int] | None = None,
    metric_type: str = 'qj',
) -> list[dict]:
    """从原始明细表查询产品结构。依赖原始表列名和数据格式，查询失败时返回空列表并记录原因。"""
    rows: list[dict] = []
    c = conn.cursor()

    perf_premium_col = 'COALESCE("年化规保", COALESCE("规模保费", 0))' if metric_type == 'gm' else 'COALESCE("期交保费", 0)'
    jd_premium_col = 'COALESCE("承保年化规保", 0)' if metric_type == 'gm' else 'COALESCE("期交保费", 0)'

    normalized_transform_lines = set(transform_lines or [])
    raw_transform_lines = set(normalized_transform_lines)
    if '证保' in normalized_transform_lines:
        raw_transform_lines.add('证券')
    if '蚁桥' in normalized_transform_lines:
        raw_transform_lines.add('网服')

    raw_transform_line_list = sorted(raw_transform_lines)
    if include_transform and raw_transform_line_list:
        try:
            t_params: list = []
            extra_where = _append_period_filter('年月', year, months, t_params)
            if orgs:
                o_placeholders = ','.join(['?'] * len(orgs))
                extra_where += f' AND "销售机构名称" IN ({o_placeholders})'
                t_params.extend(orgs)
            placeholders = ','.join(['?'] * len(raw_transform_line_list))
            c.execute(f'''
                SELECT COALESCE(NULLIF(TRIM("产品类型"), ''), '未分类') AS label,
                       SUM({perf_premium_col}) / 10000.0 AS premium,
                       SUM(COALESCE("承保件数", 1)) AS count
                FROM performance
                WHERE 1=1
                  {extra_where}
                  AND "业务模式" IN ({placeholders})
                GROUP BY COALESCE(NULLIF(TRIM("产品类型"), ''), '未分类')
            ''', [*t_params, *raw_transform_line_list])
            for row in c.fetchall():
                item = dict(row)
                item['source'] = '转型'
                rows.append(item)
        except sqlite3.OperationalError as e:
            logger.warning("转型业务产品结构查询失败 (表不存在或列不匹配): %s", e)

    if include_jingdai:
        try:
            jd_params: list = []
            jd_extra_where = _append_period_filter('时间', year, months, jd_params)
            org_clause = ''
            if jingdai_orgs:
                placeholders = ','.join(['?'] * len(jingdai_orgs))
                org_clause = f' AND "经代机构" IN ({placeholders})'
                jd_params.extend(jingdai_orgs)
            c.execute(f'''
                SELECT COALESCE(NULLIF(TRIM("产品名称"), ''), '未分类') AS label,
                       SUM({jd_premium_col}) / 10000.0 AS premium,
                       COUNT(*) AS count
                FROM jingdai
                WHERE 1=1
                  {jd_extra_where}
                  {org_clause}
                GROUP BY COALESCE(NULLIF(TRIM("产品名称"), ''), '未分类')
            ''', jd_params)
            for row in c.fetchall():
                item = dict(row)
                item['source'] = '经代'
                rows.append(item)
        except sqlite3.OperationalError as e:
            logger.warning("经代业务产品结构查询失败 (表不存在或列不匹配): %s", e)

    merged: dict[str, dict] = {}
    mixed_sources = include_transform and include_jingdai
    for row in rows:
        label = row.get('label') or '未分类'
        if mixed_sources:
            label = f"{row.get('source')}-{label}"
        item = merged.setdefault(label, {'label': label, 'premium': 0.0, 'count': 0})
        item['premium'] += float(row.get('premium') or 0)
        item['count'] += int(row.get('count') or 0)
    return sorted(merged.values(), key=lambda r: abs(r['premium']), reverse=True)[:20]


def get_jingdai_orgs(year: int | None = None) -> list[str]:
    with get_db() as conn:
        params: list = []
        where = ''
        if year:
            where = 'WHERE 1=1' + _append_period_filter('时间', year, None, params)
        rows = conn.execute(f'''
            SELECT DISTINCT TRIM("经代机构") AS org
            FROM jingdai
            {where}
            ORDER BY org
        ''', params).fetchall()
        return [r['org'] for r in rows if r['org']]


def get_product_structure(
    year: int,
    dimension: str = 'design_cat',
    transform_lines: str | list[str] | None = None,
    jingdai_orgs: str | list[str] | None = None,
    include_transform: bool = True,
    include_jingdai: bool = True,
    orgs: str | list[str] | None = None,
    months: str | list[int] | None = None,
    metric_type: str = 'qj',
):
    with get_db() as conn:
        transform_list = transform_lines if isinstance(transform_lines, list) else _split_csv(transform_lines)
        jingdai_org_list = jingdai_orgs if isinstance(jingdai_orgs, list) else _split_csv(jingdai_orgs)
        org_list = orgs if isinstance(orgs, list) else _split_csv(orgs) if isinstance(orgs, str) else None
        month_list = months if isinstance(months, list) else [int(m.strip()) for m in months.split(',') if m.strip().isdigit()] if isinstance(months, str) else None
        if not transform_list:
            transform_list = ['OTO', '证保', '蚁桥']

        if dimension == 'product_mix':
            rows = _query_product_structure_raw(
                conn, year, transform_list, jingdai_org_list,
                include_transform, include_jingdai,
                orgs=org_list, months=month_list, metric_type=metric_type,
            )
            return {
                'year': year,
                'dimension': dimension,
                'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows if round(r['premium'], 2) != 0],
                'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows if int(r['count']) != 0],
                'jingdaiOrgs': get_jingdai_orgs(year),
            }

        c = conn.cursor()
        c.execute('''
            SELECT label, premium, count
            FROM agg_product_structure
            WHERE year = ? AND dimension = ?
            ORDER BY premium DESC
            LIMIT 12
        ''', (year, dimension))
        rows = [dict(r) for r in c.fetchall()]
        return {
            'year': year,
            'dimension': dimension,
            'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows],
            'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows],
            'jingdaiOrgs': get_jingdai_orgs(year),
        }


