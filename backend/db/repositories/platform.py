"""Platform aggregate repository queries."""
import sqlite3
import calendar

from db.connection import get_db
from services.cutoff_policy import build_as_of_context, build_period_context, date_filter_sql, date_range_filter_sql, parse_as_of
from services.raw_table_reader import pick_existing_column


def _jingdai_discount_expr(conn, table: str, *, aggregate: bool = False) -> str:
    """Old schemas have no missing marker; new schemas must never sum a partial amount."""
    missing = 'zs_missing' if pick_existing_column(conn, table, ['zs_missing']) else '0'
    if aggregate:
        return f'CASE WHEN SUM({missing})=0 THEN SUM(zs_premium) END AS zs_premium'
    return f'CASE WHEN {missing}=0 THEN zs_premium END AS zs_premium'


def _get_ranged_platform_data(conn, year: int, period: dict) -> dict:
    """Read an explicit inclusive range without substituting a whole partial month."""
    start, end = period['startCutoff'], period['endCutoff']
    range_sql, range_params = date_range_filter_sql(start, end)
    warnings = []
    precision = {}
    unavailable = {}
    monthly_fallbacks = {}

    def read_premium(monthly_table, daily_table, dimensions, name, jingdai=False):
        columns = ', '.join(['month', *dimensions])
        discount = _jingdai_discount_expr(conn, monthly_table) if jingdai else 'zs_premium'
        monthly = [dict(r) for r in conn.execute(
            f'SELECT {columns}, qj_premium, gm_premium, {discount} FROM {monthly_table} '
            'WHERE year=? AND month BETWEEN ? AND ?', (year, start['month'], end['month']))]
        discount = _jingdai_discount_expr(conn, daily_table) if jingdai else 'zs_premium'
        daily = [dict(r) for r in conn.execute(
            f'SELECT {columns}, day, qj_premium, gm_premium, {discount} FROM {daily_table} '
            f'WHERE year=? AND {range_sql} ORDER BY month, day', [year, *range_params])]
        # Availability is checked before filtering days: a genuine zero-day selection
        # must not revive that month's full monthly aggregate.
        daily_months = {r[0] for r in conn.execute(
            f'SELECT DISTINCT month FROM {daily_table} WHERE year=?', (year,))}
        grouped = {}
        for row in daily:
            key = tuple(row[d] for d in ['month', *dimensions])
            target = grouped.setdefault(key, {d: row[d] for d in ['month', *dimensions]})
            for metric in ('qj_premium', 'gm_premium', 'zs_premium'):
                value = row.get(metric)
                target[metric] = None if value is None or target.get(metric, 0) is None else target.get(metric, 0) + value
        fallback_months = set()
        unknown_months = set()
        for row in monthly:
            month = row['month']
            if month in daily_months:
                continue
            first_day = start['day'] if month == start['month'] else 1
            final_day = end['day'] if month == end['month'] else calendar.monthrange(year, month)[1]
            full_month = first_day == 1 and final_day == calendar.monthrange(year, month)[1]
            if full_month:
                fallback_months.add(month)
            else:
                unknown_months.add(month)
                row.update(qj_premium=None, gm_premium=None, zs_premium=None)
            grouped[tuple(row[d] for d in ['month', *dimensions])] = row
        precision[name] = 'unavailable' if unknown_months else 'mixed' if fallback_months and daily else 'month' if fallback_months else 'day'
        unavailable[name] = sorted(unknown_months)
        monthly_fallbacks[name] = sorted(fallback_months)
        if unknown_months:
            warnings.append(f'{name}：{",".join(map(str, sorted(unknown_months)))}月缺少日级数据，所选非完整月范围不可计算')
        elif fallback_months:
            warnings.append(f'{name}：完整月份使用月级数据，不能生成该月日趋势')
        return sorted(grouped.values(), key=lambda row: (row['month'], *[str(row[d]) for d in dimensions])), daily

    performance, daily = read_premium('agg_performance', 'agg_daily_performance', ['channel'], 'performance')
    jingdai, jingdai_daily = read_premium('agg_jingdai', 'agg_jingdai_daily', [], 'jingdai', True)
    org_performance, org_daily = read_premium('agg_org_performance', 'agg_org_daily_performance', ['org', 'channel'], 'org_performance')

    def month_rows(table, columns):
        try:
            return [dict(r) for r in conn.execute(
                f'SELECT {columns} FROM {table} WHERE year=? AND month BETWEEN ? AND ? ORDER BY month',
                (year, start['month'], end['month']))]
        except sqlite3.OperationalError:
            return []

    period['precision']['premium'] = precision['performance'] if precision['performance'] == precision['jingdai'] else 'mixed'
    latest = conn.execute('''SELECT MAX(year * 100 + month) FROM (
        SELECT year, month FROM agg_performance UNION ALL SELECT year, month FROM agg_jingdai
        UNION ALL SELECT year, month FROM agg_hr_data UNION ALL SELECT year, month FROM agg_value_data)''').fetchone()[0]
    return {
        'performance': performance, 'jingdai': jingdai, 'jingdai_daily': jingdai_daily,
        'daily_performance': daily, 'org_performance': org_performance, 'org_daily_performance': org_daily,
        'hr': month_rows('agg_hr_data', 'month, channel, start_headcount, end_headcount, active_headcount'),
        'org_hr': month_rows('agg_org_hr_data', 'month, org, channel, start_headcount, end_headcount, active_headcount'),
        'value': month_rows('agg_value_data', 'month, channel, value_premium'),
        'latest_period': latest, 'as_of': period['asOf'], 'period': period, 'rangeApplied': True,
        'sourcePrecision': precision, 'unavailableMonths': unavailable, 'rangeWarnings': warnings,
        'monthlyFallbackMonths': monthly_fallbacks,
    }


def get_platform_data(year: int, as_of: str | None = None, *, range_type: str | None = None,
                      start_date: str | None = None, end_date: str | None = None):
    with get_db() as conn:
        if range_type is not None or start_date is not None or end_date is not None:
            period = build_period_context(conn, year, range_type=range_type, start_date=start_date,
                                          end_date=end_date, as_of=as_of)
            result = _get_ranged_platform_data(conn, year, period)
            requested_end = parse_as_of(end_date or as_of)
            if requested_end and (requested_end.month, requested_end.day) > (period['endCutoff']['month'], period['endCutoff']['day']):
                result['rangeWarnings'].append(
                    f'{year}年请求截至{requested_end.month}月{requested_end.day}日，受数据覆盖限制，实际统计范围为{period["startDate"]}至{period["endDate"]}')
            return result
        c = conn.cursor()
        as_of_context = build_as_of_context(conn, year, as_of)
        selected_cutoff = as_of_context.get("selectedCutoff")
        cutoff_month = int(selected_cutoff["month"]) if selected_cutoff else 12

        c.execute('''
            SELECT month, channel, qj_premium, gm_premium, zs_premium
            FROM agg_performance WHERE year = ? AND month <= ? ORDER BY month, channel
        ''', (year, cutoff_month))
        perf_rows = c.fetchall()
        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute('''
                SELECT month, channel, SUM(qj_premium) AS qj_premium,
                       SUM(gm_premium) AS gm_premium, SUM(zs_premium) AS zs_premium
                FROM agg_daily_performance
                WHERE year = ? AND ''' + date_sql + '''
                GROUP BY month, channel
                ORDER BY month, channel
            ''', [year, *date_params])
            daily_perf_rows = c.fetchall()
            if daily_perf_rows:
                perf_rows = daily_perf_rows

        c.execute(f'''
            SELECT month, qj_premium, gm_premium, {_jingdai_discount_expr(conn, 'agg_jingdai')}
            FROM agg_jingdai WHERE year = ? AND month <= ? ORDER BY month
        ''', (year, cutoff_month))
        jingdai_rows = c.fetchall()
        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute(f'''
                SELECT month, SUM(qj_premium) AS qj_premium,
                       SUM(gm_premium) AS gm_premium, {_jingdai_discount_expr(conn, 'agg_jingdai_daily', aggregate=True)}
                FROM agg_jingdai_daily
                WHERE year = ? AND ''' + date_sql + '''
                GROUP BY month
                ORDER BY month
            ''', [year, *date_params])
            daily_jingdai_rows = c.fetchall()
            if daily_jingdai_rows:
                jingdai_rows = daily_jingdai_rows

        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute(f'''
                SELECT year, month, day, ymd, qj_premium, gm_premium, {_jingdai_discount_expr(conn, 'agg_jingdai_daily')}
                FROM agg_jingdai_daily WHERE year = ? AND ''' + date_sql + ''' ORDER BY month, day
            ''', [year, *date_params])
        else:
            c.execute(f'''
                SELECT year, month, day, ymd, qj_premium, gm_premium, {_jingdai_discount_expr(conn, 'agg_jingdai_daily')}
                FROM agg_jingdai_daily WHERE year = ? ORDER BY month, day
            ''', (year,))
        jingdai_daily_rows = c.fetchall()

        c.execute('''
            SELECT month, channel, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? AND month <= ? ORDER BY month, channel
        ''', (year, cutoff_month))
        hr_rows = c.fetchall()

        try:
            c.execute('''
                SELECT month, org, channel, start_headcount, end_headcount, active_headcount
                FROM agg_org_hr_data WHERE year = ? AND month <= ? ORDER BY month, org, channel
            ''', (year, cutoff_month))
            org_hr_rows = c.fetchall()
        except sqlite3.OperationalError:
            org_hr_rows = []

        c.execute('''
            SELECT month, channel, value_premium
            FROM agg_value_data WHERE year = ? AND month <= ? ORDER BY month, channel
        ''', (year, cutoff_month))
        value_rows = c.fetchall()

        c.execute('''
            SELECT month, org, channel, qj_premium, gm_premium, zs_premium
            FROM agg_org_performance WHERE year = ? AND month <= ? ORDER BY month, org, channel
        ''', (year, cutoff_month))
        org_perf_rows = c.fetchall()
        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute('''
                SELECT month, org, channel, SUM(qj_premium) AS qj_premium,
                       SUM(gm_premium) AS gm_premium, SUM(zs_premium) AS zs_premium
                FROM agg_org_daily_performance
                WHERE year = ? AND ''' + date_sql + '''
                GROUP BY month, org, channel
                ORDER BY month, org, channel
            ''', [year, *date_params])
            org_daily_perf_rows = c.fetchall()
            if org_daily_perf_rows:
                org_perf_rows = org_daily_perf_rows

        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute('''
                SELECT month, day, channel, qj_premium, gm_premium, zs_premium
                FROM agg_daily_performance WHERE year = ? AND ''' + date_sql + ''' ORDER BY month, day, channel
            ''', [year, *date_params])
        else:
            c.execute('''
                SELECT month, day, channel, qj_premium, gm_premium, zs_premium
                FROM agg_daily_performance WHERE year = ? ORDER BY month, day, channel
            ''', (year,))
        daily_rows = c.fetchall()

        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute('''
                SELECT month, day, org, channel, qj_premium, gm_premium, zs_premium
                FROM agg_org_daily_performance WHERE year = ? AND ''' + date_sql + ''' ORDER BY month, day, org, channel
            ''', [year, *date_params])
        else:
            c.execute('''
                SELECT month, day, org, channel, qj_premium, gm_premium, zs_premium
                FROM agg_org_daily_performance WHERE year = ? ORDER BY month, day, org, channel
            ''', (year,))
        org_daily_rows = c.fetchall()

        c.execute('''
            SELECT MAX(year * 100 + month) AS latest_period
            FROM (
              SELECT year, month FROM agg_performance
              UNION ALL SELECT year, month FROM agg_jingdai
              UNION ALL SELECT year, month FROM agg_hr_data
              UNION ALL SELECT year, month FROM agg_value_data
            )
        ''')
        latest = c.fetchone()['latest_period']

        return {
            'performance': [dict(r) for r in perf_rows],
            'jingdai': [dict(r) for r in jingdai_rows],
            'jingdai_daily': [dict(r) for r in jingdai_daily_rows],
            'hr': [dict(r) for r in hr_rows],
            'org_hr': [dict(r) for r in org_hr_rows],
            'value': [dict(r) for r in value_rows],
            'org_performance': [dict(r) for r in org_perf_rows],
            'daily_performance': [dict(r) for r in daily_rows],
            'org_daily_performance': [dict(r) for r in org_daily_rows],
            'latest_period': latest,
            'as_of': as_of_context,
        }
