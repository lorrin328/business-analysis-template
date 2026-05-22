"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db


def get_platform_data(year: int):
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            SELECT month, channel, qj_premium, gm_premium, zs_premium
            FROM agg_performance WHERE year = ? ORDER BY month, channel
        ''', (year,))
        perf_rows = c.fetchall()

        c.execute('''
            SELECT month, qj_premium, gm_premium, zs_premium
            FROM agg_jingdai WHERE year = ? ORDER BY month
        ''', (year,))
        jingdai_rows = c.fetchall()

        c.execute('''
            SELECT year, month, day, ymd, qj_premium, gm_premium, zs_premium
            FROM agg_jingdai_daily WHERE year = ? ORDER BY month, day
        ''', (year,))
        jingdai_daily_rows = c.fetchall()

        c.execute('''
            SELECT month, channel, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        hr_rows = c.fetchall()

        try:
            c.execute('''
                SELECT month, org, channel, start_headcount, end_headcount, active_headcount
                FROM agg_org_hr_data WHERE year = ? ORDER BY month, org, channel
            ''', (year,))
            org_hr_rows = c.fetchall()
        except sqlite3.OperationalError:
            org_hr_rows = []

        c.execute('''
            SELECT month, channel, value_premium
            FROM agg_value_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        value_rows = c.fetchall()

        c.execute('''
            SELECT month, org, channel, qj_premium, gm_premium, zs_premium
            FROM agg_org_performance WHERE year = ? ORDER BY month, org, channel
        ''', (year,))
        org_perf_rows = c.fetchall()

        c.execute('''
            SELECT month, day, channel, qj_premium, gm_premium, zs_premium
            FROM agg_daily_performance WHERE year = ? ORDER BY month, day, channel
        ''', (year,))
        daily_rows = c.fetchall()

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
        }



def get_kpi_data(year: int):
    """获取 KPI 概览数据。

    期交保费 YTD 优先使用日累计表（agg_daily_performance / agg_jingdai_daily），
    按「统计日」口径截取去年同期，即截至上一年的同一日。
    人力、价值、长险期交等无日维度的指标仍按月级精度计算。
    """
    with get_db() as conn:
        c = conn.cursor()

        # Use the smallest available source cutoff to avoid mixing data through different months.
        def _max_month(table: str):
            c.execute(f'SELECT MAX(month) FROM {table} WHERE year = ?', (year,))
            value = c.fetchone()[0]
            return int(value) if value else None

        data_cutoff = {
            'performance': _max_month('agg_performance'),
            'hr': _max_month('agg_hr_data'),
            'jingdai': _max_month('agg_jingdai'),
            'value': _max_month('agg_value_data'),
        }
        available_cutoffs = [month for month in data_cutoff.values() if month]
        query_month = min(available_cutoffs) if available_cutoffs else 1

        # ── 日级统计截止日（用于期交保费同比同口径截取） ──
        c.execute('''
            SELECT month, MAX(day) as max_day
            FROM agg_daily_performance
            WHERE year = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
        ''', (year,))
        daily_cutoff = c.fetchone()
        if daily_cutoff and daily_cutoff['month']:
            ytd_end_month = daily_cutoff['month']
            ytd_end_day = daily_cutoff['max_day'] or 31
            use_daily = True
        else:
            ytd_end_month = query_month
            ytd_end_day = 31
            use_daily = False

        def _ytd_premiums_daily(query_year: int) -> dict:
            """从日累计表取截至统计日的期交保费，按 channel 汇总。"""
            result = {}
            if not use_daily:
                return result
            c.execute('''
                SELECT channel, SUM(qj_premium) AS total
                FROM agg_daily_performance
                WHERE year = ?
                  AND (month < ? OR (month = ? AND day <= ?))
                GROUP BY channel
            ''', (query_year, ytd_end_month, ytd_end_month, ytd_end_day))
            for r in c.fetchall():
                result[r['channel']] = round(r['total'] or 0, 2)
            return result

        def _ytd_jingdai_daily(query_year: int) -> float:
            """从经代日累计表取截至统计日的期交保费。"""
            if not use_daily:
                return 0.0
            c.execute('''
                SELECT SUM(qj_premium) AS total
                FROM agg_jingdai_daily
                WHERE year = ?
                  AND (month < ? OR (month = ? AND day <= ?))
            ''', (query_year, ytd_end_month, ytd_end_month, ytd_end_day))
            row = c.fetchone()
            return round(row['total'] or 0, 2) if row else 0.0

        # ── YTD 保费（有日数据时用日累计，否则回退月表） ──
        daily_perf = _ytd_premiums_daily(year)
        daily_jd = _ytd_jingdai_daily(year)

        if use_daily:
            perf = daily_perf
            jingdai_qj = daily_jd
        else:
            c.execute('''
                SELECT channel, SUM(qj_premium) AS total
                FROM agg_performance WHERE year = ? AND month <= ? GROUP BY channel
            ''', (year, query_month))
            perf = {r['channel']: r['total'] or 0 for r in c.fetchall()}
            c.execute('''
                SELECT SUM(qj_premium) AS total FROM agg_jingdai WHERE year = ? AND month <= ?
            ''', (year, query_month))
            jingdai_qj = c.fetchone()['total'] or 0

        # HR（月级精度）
        c.execute('''
            SELECT channel, month, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? AND month <= ?
            ORDER BY channel, month
        ''', (year, query_month))
        hr = {}
        hr_latest = {}
        for r in c.fetchall():
            ch = r['channel']
            avg_hc = ((r['start_headcount'] or 0) + (r['end_headcount'] or 0)) / 2.0
            info = hr.setdefault(ch, {'avg_sum': 0.0, 'months': 0, 'month': query_month})
            info['avg_sum'] += avg_hc
            info['months'] += 1
            if r['month'] == query_month:
                hr_latest[ch] = {
                    'start': r['start_headcount'] or 0,
                    'end': r['end_headcount'] or 0,
                    'active': r['active_headcount'] or 0,
                    'avg': avg_hc,
                }
        for ch, info in hr.items():
            info.update(hr_latest.get(ch, {}))
            if not info.get('avg'):
                info['avg'] = 0
            if info['months'] > 1:
                info['avg_sum'] = round(info['avg_sum'], 2)

        # 去年同期 HR（月级精度，人力基表无日维度）
        c.execute('''
            SELECT channel, month, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? AND month <= ?
            ORDER BY channel, month
        ''', (year - 1, query_month))
        hr_prev = {}; hr_prev_latest = {}
        for r in c.fetchall():
            ch = r['channel']
            avg_hc = ((r['start_headcount'] or 0) + (r['end_headcount'] or 0)) / 2.0
            info = hr_prev.setdefault(ch, {'avg_sum': 0.0, 'months': 0, 'month': query_month})
            info['avg_sum'] += avg_hc
            info['months'] += 1
            if r['month'] == query_month:
                hr_prev_latest[ch] = {
                    'start': r['start_headcount'] or 0, 'end': r['end_headcount'] or 0,
                    'active': r['active_headcount'] or 0, 'avg': avg_hc,
                }
        for ch, info in hr_prev.items():
            info.update(hr_prev_latest.get(ch, {}))
            if not info.get('avg'): info['avg'] = 0

        # 长险期交（YTD，月级精度，无日维度表）
        c.execute('''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE year = ? AND month <= ? GROUP BY business_type, channel
        ''', (year, query_month))
        lt_qj = {}; lt_tf = 0.0; lt_jd = 0.0
        for r in c.fetchall():
            v = round(r['total'] or 0, 2)
            key = f"{r['business_type']}|{r['channel']}" if r['channel'] else r['business_type']
            lt_qj[key] = v
            if r['business_type'] == '转型': lt_tf += v
            else: lt_jd += v
        lt_total = lt_tf + lt_jd

        c.execute('''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE year = ? AND month <= ? GROUP BY business_type, channel
        ''', (year - 1, query_month))
        lt_qj_prev = {}; lt_tf_prev = 0.0; lt_jd_prev = 0.0
        for r in c.fetchall():
            v = round(r['total'] or 0, 2)
            lt_qj_prev[f"{r['business_type']}|{r['channel']}" if r['channel'] else r['business_type']] = v
            if r['business_type'] == '转型': lt_tf_prev += v
            else: lt_jd_prev += v
        lt_total_prev = lt_tf_prev + lt_jd_prev

        # 价值（YTD，月级精度）
        c.execute('''
            SELECT channel, SUM(value_premium) AS total
            FROM agg_value_data WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        value = {r['channel']: r['total'] or 0 for r in c.fetchall()}

        # 商保年金 / 10年期 — 转型部分（月级精度）
        c.execute('''
            SELECT channel, SUM(product_annuity) AS a, SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        annuity_tf = sum((r['a'] or 0) for r in c.fetchall())
        c.execute('''
            SELECT SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ?
        ''', (year, query_month))
        row = c.fetchone()
        tenyear_tf = (row['t'] or 0) if row else 0.0

        total_transform = perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0)

        # 去年同期期交保费（日级口径）
        prev_perf = _ytd_premiums_daily(year - 1) if use_daily else {}
        prev_jingdai_qj = _ytd_jingdai_daily(year - 1) if use_daily else 0.0

        return {
            'year': year,
            'month': query_month,
            'data_cutoff': data_cutoff,
            'daily_cutoff': {'month': ytd_end_month, 'day': ytd_end_day, 'use_daily': use_daily},
            'qj_premium': {
                'jingdai': round(jingdai_qj, 2),
                'oto': round(perf.get('OTO', 0), 2),
                'zhengbao': round(perf.get('证保', 0), 2),
                'yiqiao': round(perf.get('蚁桥', 0), 2),
                'total_transform': round(total_transform, 2),
                'total': round(jingdai_qj + total_transform, 2),
            },
            'qj_premium_prev': {
                'jingdai': round(prev_jingdai_qj, 2),
                'oto': round(prev_perf.get('OTO', 0), 2),
                'zhengbao': round(prev_perf.get('证保', 0), 2),
                'yiqiao': round(prev_perf.get('蚁桥', 0), 2),
                'total_transform': round(
                    prev_perf.get('OTO', 0) + prev_perf.get('证保', 0) + prev_perf.get('蚁桥', 0), 2
                ),
                'total': round(prev_jingdai_qj + prev_perf.get('OTO', 0) + prev_perf.get('证保', 0) + prev_perf.get('蚁桥', 0), 2),
            } if use_daily else None,
            'longterm_qj': lt_total,
            'longterm_qj_tf': lt_tf,
            'longterm_qj_jd': lt_jd,
            'longterm_qj_prev': lt_total_prev,
            'longterm_qj_tf_prev': lt_tf_prev,
            'longterm_qj_jd_prev': lt_jd_prev,
            'annuity_total': round(annuity_tf, 2),
            'tenyear_total': round(tenyear_tf, 2),
            'hr': hr,
            'hr_prev': hr_prev,
            'value': value,
        }


