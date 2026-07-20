"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db
from services.cutoff_policy import build_period_context, date_range_filter_sql


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
    range_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """获取交期结构数据，按交期分类聚合保费/件数"""
    init_db()
    premium_field = 'gm_premium' if metric == 'gm' else 'qj_premium'
    with get_db() as conn:
        c = conn.cursor()
        period_context = build_period_context(
            conn,
            year,
            range_type=range_type,
            start_date=start_date,
            end_date=end_date,
            as_of=as_of,
        )
        as_of_context = period_context["asOf"]
        selected_start = period_context["startCutoff"]
        selected_cutoff = period_context["endCutoff"]
        cutoff_month = int(selected_cutoff["month"]) if selected_cutoff else 12
        start_month = int(selected_start["month"]) if selected_start else 1
        daily_table_exists = bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agg_payment_period_daily'"
        ).fetchone())
        daily_available = daily_table_exists and bool(c.execute(
            "SELECT 1 FROM agg_payment_period_daily WHERE year = ? LIMIT 1", (year,)
        ).fetchone())
        table = "agg_payment_period_daily" if daily_available else "agg_payment_period"

        conditions = ['year = ?']
        params = [year]

        if daily_available:
            range_sql, range_params = date_range_filter_sql(selected_start, selected_cutoff)
            conditions.append(range_sql)
            params.extend(range_params)

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
            if not daily_available:
                conditions.append('month BETWEEN ? AND ?')
                params.extend([start_month, cutoff_month])

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
            FROM {table}
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

        period_context['precision']['paymentPeriod'] = 'day' if daily_available else 'month'
        return {
            'year': year,
            'as_of': as_of_context,
            'period': period_context,
            'precision': 'day' if daily_available else 'month',
            'premium': premium_rows,
            'count': count_rows,
            'jingdai_orgs': jd_orgs,
        }


