"""Repository queries — auto-split from database.py."""
import json
import logging
import sqlite3
from db.connection import get_db
from db.schema import init_db
from services.cutoff_policy import build_period_context
from services.raw_table_reader import (
    append_date_range_filter,
    append_period_filter,
    pick_existing_column,
    quote_identifier,
)

logger = logging.getLogger("business-analysis")


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item and item.strip()]


def _existing_numeric_expr(
    conn: sqlite3.Connection,
    table: str,
    candidates: list[str],
    *,
    default: str = '0',
) -> str:
    col = pick_existing_column(conn, table, candidates)
    if not col:
        logger.warning("%s missing expected numeric columns: %s", table, candidates)
        return default
    return f'COALESCE({quote_identifier(col)}, {default})'


def _max_daily_cutoff(conn: sqlite3.Connection, table: str, year: int, months: list[int] | None, channels: list[str] | None = None):
    params: list = [year]
    where = 'year = ?'
    if months:
        placeholders = ','.join(['?'] * len(months))
        where += f' AND month IN ({placeholders})'
        params.extend(months)
    if channels:
        placeholders = ','.join(['?'] * len(channels))
        where += f' AND channel IN ({placeholders})'
        params.extend(channels)
    try:
        row = conn.execute(f'''
            SELECT month, day
            FROM {table}
            WHERE {where}
            ORDER BY month DESC, day DESC
            LIMIT 1
        ''', params).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return (int(row['month']), int(row['day']))


def _common_mixed_cutoff(
    conn: sqlite3.Connection,
    year: int,
    months: list[int] | None,
    transform_lines: list[str],
    include_transform: bool,
    include_jingdai: bool,
):
    if not (include_transform and include_jingdai and transform_lines):
        return None
    transform_cutoff = _max_daily_cutoff(conn, 'agg_daily_performance', year, months, transform_lines)
    jingdai_cutoff = _max_daily_cutoff(conn, 'agg_jingdai_daily', year, months)
    if transform_cutoff and jingdai_cutoff:
        return min(transform_cutoff, jingdai_cutoff)
    return None


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
    start_cutoff: tuple[int, int] | None = None,
    end_cutoff: tuple[int, int] | None = None,
) -> list[dict]:
    """从原始明细表查询产品结构。依赖原始表列名和数据格式，查询失败时返回空列表并记录原因。"""
    rows: list[dict] = []
    c = conn.cursor()

    perf_premium_col = _existing_numeric_expr(
        conn,
        'performance',
        ['年化规保', '规模保费'] if metric_type == 'gm' else ['期交保费'],
    )
    perf_count_col = _existing_numeric_expr(conn, 'performance', ['承保件数'], default='1')
    jd_premium_col = _existing_numeric_expr(
        conn,
        'jingdai',
        ['承保年化规保', '年化规保', '规模保费'] if metric_type == 'gm' else ['期交保费'],
    )

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
            transform_time_col = pick_existing_column(
                conn,
                'performance',
                ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期', '年月'],
            ) or '年月'
            common_cutoff = _common_mixed_cutoff(
                conn, year, months, sorted(normalized_transform_lines), include_transform, include_jingdai
            )
            cutoff = min(common_cutoff, end_cutoff) if common_cutoff and end_cutoff else common_cutoff or end_cutoff
            extra_where = append_period_filter(transform_time_col, year, months, t_params)
            extra_where += append_date_range_filter(transform_time_col, start_cutoff, cutoff, t_params)
            if orgs:
                o_placeholders = ','.join(['?'] * len(orgs))
                extra_where += f' AND "销售机构名称" IN ({o_placeholders})'
                t_params.extend(orgs)
            placeholders = ','.join(['?'] * len(raw_transform_line_list))
            c.execute(f'''
                SELECT COALESCE(NULLIF(TRIM("产品类型"), ''), '未分类') AS label,
                       SUM({perf_premium_col}) / 10000.0 AS premium,
                       SUM({perf_count_col}) AS count
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
            jingdai_time_col = pick_existing_column(
                conn,
                'jingdai',
                ['年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期', '时间', '年月'],
            ) or '时间'
            common_cutoff = _common_mixed_cutoff(
                conn, year, months, sorted(normalized_transform_lines), include_transform, include_jingdai
            )
            cutoff = min(common_cutoff, end_cutoff) if common_cutoff and end_cutoff else common_cutoff or end_cutoff
            jd_extra_where = append_period_filter(jingdai_time_col, year, months, jd_params)
            jd_extra_where += append_date_range_filter(jingdai_time_col, start_cutoff, cutoff, jd_params)
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


def _text_coalesce_expr(conn: sqlite3.Connection, table: str, candidates: list[str], fallback: str = '未分类') -> str:
    parts = []
    for col in candidates:
        if pick_existing_column(conn, table, [col]):
            parts.append(f"NULLIF(TRIM({quote_identifier(col)}), '')")
    if not parts:
        return f"'{fallback}'"
    return f"COALESCE({', '.join(parts)}, '{fallback}')"


def _query_top_products_by_business_line(
    conn: sqlite3.Connection,
    year: int,
    transform_lines: list[str],
    jingdai_orgs: list[str],
    include_transform: bool,
    include_jingdai: bool,
    orgs: list[str] | None = None,
    months: list[int] | None = None,
    start_cutoff: tuple[int, int] | None = None,
    end_cutoff: tuple[int, int] | None = None,
) -> list[dict]:
    """按业务模式返回期交保费占比前三名产品，用于前端表格展示。"""
    rows: list[dict] = []
    normalized_transform_lines = set(transform_lines or [])
    raw_transform_lines = set(normalized_transform_lines)
    if '证保' in normalized_transform_lines:
        raw_transform_lines.add('证券')
    if '蚁桥' in normalized_transform_lines:
        raw_transform_lines.add('网服')

    common_cutoff = _common_mixed_cutoff(
        conn, year, months, sorted(normalized_transform_lines), include_transform, include_jingdai
    )
    cutoff = min(common_cutoff, end_cutoff) if common_cutoff and end_cutoff else common_cutoff or end_cutoff

    if include_transform and raw_transform_lines:
        try:
            t_params: list = []
            transform_time_col = pick_existing_column(
                conn,
                'performance',
                ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期', '年月'],
            ) or '年月'
            extra_where = append_period_filter(transform_time_col, year, months, t_params)
            extra_where += append_date_range_filter(transform_time_col, start_cutoff, cutoff, t_params)
            if orgs:
                o_placeholders = ','.join(['?'] * len(orgs))
                extra_where += f' AND "销售机构名称" IN ({o_placeholders})'
                t_params.extend(orgs)
            raw_line_list = sorted(raw_transform_lines)
            placeholders = ','.join(['?'] * len(raw_line_list))
            premium_expr = _existing_numeric_expr(conn, 'performance', ['期交保费'])
            product_expr = _text_coalesce_expr(conn, 'performance', ['产品名称', '产品类型', '产品代码'])
            line_expr = '''
                CASE TRIM("业务模式")
                  WHEN '证券' THEN '证保'
                  WHEN '网服' THEN '蚁桥'
                  ELSE TRIM("业务模式")
                END
            '''
            query = f'''
                SELECT {line_expr} AS business_line,
                       {product_expr} AS product_name,
                       SUM({premium_expr}) / 10000.0 AS premium
                FROM performance
                WHERE 1=1
                  {extra_where}
                  AND "业务模式" IN ({placeholders})
                GROUP BY {line_expr}, {product_expr}
            '''
            rows.extend(dict(row) for row in conn.execute(query, [*t_params, *raw_line_list]).fetchall())
        except sqlite3.OperationalError as e:
            logger.warning("转型业务最高占比产品查询失败: %s", e)

    if include_jingdai:
        try:
            jd_params: list = []
            jingdai_time_col = pick_existing_column(
                conn,
                'jingdai',
                ['年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期', '时间', '年月'],
            ) or '时间'
            jd_extra_where = append_period_filter(jingdai_time_col, year, months, jd_params)
            jd_extra_where += append_date_range_filter(jingdai_time_col, start_cutoff, cutoff, jd_params)
            org_clause = ''
            if jingdai_orgs:
                placeholders = ','.join(['?'] * len(jingdai_orgs))
                org_clause = f' AND "经代机构" IN ({placeholders})'
                jd_params.extend(jingdai_orgs)
            premium_expr = _existing_numeric_expr(conn, 'jingdai', ['期交保费'])
            product_expr = _text_coalesce_expr(conn, 'jingdai', ['产品名称'])
            query = f'''
                SELECT '经代' AS business_line,
                       {product_expr} AS product_name,
                       SUM({premium_expr}) / 10000.0 AS premium
                FROM jingdai
                WHERE 1=1
                  {jd_extra_where}
                  {org_clause}
                GROUP BY {product_expr}
            '''
            rows.extend(dict(row) for row in conn.execute(query, jd_params).fetchall())
        except sqlite3.OperationalError as e:
            logger.warning("经代业务最高占比产品查询失败: %s", e)

    by_line: dict[str, dict] = {}
    for row in rows:
        line = row.get('business_line') or '未分类'
        premium = float(row.get('premium') or 0)
        if premium == 0:
            continue
        line_bucket = by_line.setdefault(line, {'total_premium': 0.0, 'products': []})
        line_bucket['total_premium'] += premium
        line_bucket['products'].append({
            'business_line': line,
            'product_name': row.get('product_name') or '未分类',
            'premium': premium,
        })

    ordered_lines = ['OTO', '证保', '蚁桥', '经代']
    result = []
    for line in ordered_lines:
        bucket = by_line.get(line)
        if not bucket or not bucket.get('products') or bucket['total_premium'] == 0:
            continue
        top_products = sorted(bucket['products'], key=lambda item: abs(item['premium']), reverse=True)[:3]
        for rank, product in enumerate(top_products, start=1):
            share = product['premium'] / bucket['total_premium'] * 100
            result.append({
                'businessLine': line,
                'rank': rank,
                'productName': product['product_name'],
                'premium': round(product['premium'], 2),
                'totalPremium': round(bucket['total_premium'], 2),
                'share': round(share, 1),
            })
    return result


def get_jingdai_orgs(year: int | None = None) -> list[str]:
    with get_db() as conn:
        params: list = []
        where = ''
        if year:
            where = 'WHERE 1=1' + append_period_filter('时间', year, None, params)
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
    as_of: str | None = None,
    range_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    with get_db() as conn:
        period_context = build_period_context(
            conn,
            year,
            range_type=range_type,
            start_date=start_date,
            end_date=end_date,
            as_of=as_of,
        )
        as_of_context = period_context["asOf"]
        selected_start = period_context.get("startCutoff") or {}
        selected_cutoff = period_context.get("endCutoff") or {}
        start_cutoff = (int(selected_start["month"]), int(selected_start["day"])) if selected_start else None
        end_cutoff = (int(selected_cutoff["month"]), int(selected_cutoff["day"])) if selected_cutoff else None
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
                start_cutoff=start_cutoff, end_cutoff=end_cutoff,
            )
            return {
                'year': year,
                'as_of': as_of_context,
                'period': period_context,
                'dimension': dimension,
                'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows if round(r['premium'], 2) != 0],
                'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows if int(r['count']) != 0],
                'topProducts': _query_top_products_by_business_line(
                    conn, year, transform_list, jingdai_org_list,
                    include_transform, include_jingdai,
                    orgs=org_list, months=month_list,
                    start_cutoff=start_cutoff, end_cutoff=end_cutoff,
                ),
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
            'as_of': as_of_context,
            'period': period_context,
            'dimension': dimension,
            'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows],
            'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows],
            'jingdaiOrgs': get_jingdai_orgs(year),
        }
