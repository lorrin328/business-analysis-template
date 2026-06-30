"""Platform aggregate repository queries."""
import sqlite3

from db.connection import get_db
from services.cutoff_policy import build_as_of_context, date_filter_sql


def get_platform_data(year: int, as_of: str | None = None):
    with get_db() as conn:
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

        c.execute('''
            SELECT month, qj_premium, gm_premium, zs_premium
            FROM agg_jingdai WHERE year = ? AND month <= ? ORDER BY month
        ''', (year, cutoff_month))
        jingdai_rows = c.fetchall()
        if selected_cutoff:
            date_sql, date_params = date_filter_sql(selected_cutoff)
            c.execute('''
                SELECT month, SUM(qj_premium) AS qj_premium,
                       SUM(gm_premium) AS gm_premium, SUM(zs_premium) AS zs_premium
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
            c.execute('''
                SELECT year, month, day, ymd, qj_premium, gm_premium, zs_premium
                FROM agg_jingdai_daily WHERE year = ? AND ''' + date_sql + ''' ORDER BY month, day
            ''', [year, *date_params])
        else:
            c.execute('''
                SELECT year, month, day, ymd, qj_premium, gm_premium, zs_premium
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
