"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db
from services.cutoff_policy import build_as_of_context


def get_payment_period_structure(
    year: int,
    month: int | None = None,
    months: list[int] | None = None,
    business_types: list[str] | None = None,
    channels: list[str] | None = None,
    orgs: list[str] | None = None,
    jingdai_orgs: list[str] | None = None,
    metric: str = 'qj',
    as_of: str | None = None,
):
    """获取交期结构数据，按交期分类聚合保费/件数"""
    init_db()
    premium_field = 'gm_premium' if metric == 'gm' else 'qj_premium'
    with get_db() as conn:
        c = conn.cursor()
        as_of_context = build_as_of_context(conn, year, as_of)
        selected_cutoff = as_of_context.get("selectedCutoff") or {}
        cutoff_month = int(selected_cutoff["month"]) if selected_cutoff else 12

        conditions = ['year = ?']
        params = [year]

        month_list = [int(m) for m in (months or []) if 1 <= int(m) <= 12]
        if month_list:
            month_list = [m for m in month_list if m <= cutoff_month]
            placeholders = ','.join(['?'] * len(month_list))
            if month_list:
                conditions.append(f'month IN ({placeholders})')
                params.extend(month_list)
            else:
                conditions.append('1 = 0')
        elif month is not None:
            if int(month) <= cutoff_month:
                conditions.append('month = ?')
                params.append(month)
            else:
                conditions.append('1 = 0')
        else:
            conditions.append('month <= ?')
            params.append(cutoff_month)

        if business_types:
            placeholders = ','.join(['?'] * len(business_types))
            conditions.append(f'business_type IN ({placeholders})')
            params.extend(business_types)

        if channels:
            placeholders = ','.join(['?'] * len(channels))
            conditions.append(f'channel IN ({placeholders})')
            params.extend(channels)

        if orgs and 'all' not in orgs:
            placeholders = ','.join(['?'] * len(orgs))
            conditions.append(f'org IN ({placeholders})')
            params.extend(orgs)

        if jingdai_orgs and 'all' not in jingdai_orgs:
            placeholders = ','.join(['?'] * len(jingdai_orgs))
            conditions.append(f'(business_type != \'经代\' OR org IN ({placeholders}))')
            params.extend(jingdai_orgs)

        where = ' AND '.join(conditions) if conditions else '1=1'

        c.execute(f'''
            SELECT category,
                   SUM({premium_field}) AS premium_total,
                   SUM(count) AS count_total
            FROM agg_payment_period
            WHERE {where}
            GROUP BY category
            ORDER BY premium_total DESC
        ''', params)

        premium_rows = []
        count_rows = []
        for r in c.fetchall():
            premium_rows.append({'name': r['category'], 'value': round(r['premium_total'] or 0, 2)})
            count_rows.append({'name': r['category'], 'value': int(r['count_total'] or 0)})

        # 获取经代机构列表
        jd_orgs = []
        if business_types is None or '经代' in business_types:
            c2 = conn.cursor()
            c2.execute('''
                SELECT DISTINCT org FROM agg_payment_period
                WHERE year = ? AND business_type = '经代' AND org != '' AND org != '未知'
                ORDER BY org
            ''', (year,))
            jd_orgs = [r['org'] for r in c2.fetchall()]

        return {
            'year': year,
            'as_of': as_of_context,
            'premium': premium_rows,
            'count': count_rows,
            'jingdai_orgs': jd_orgs,
        }


