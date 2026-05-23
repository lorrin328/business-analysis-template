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
    人力、价值等无日维度的指标仍按月级精度计算。
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
        # 转型与经代必须按同一截止日计算。若两张日表截止日不同，统一取较早日期；
        # 若任一日表缺失，则回退到共同月份的月级聚合，避免混用不同精度。
        def _latest_daily_cutoff(table: str):
            c.execute(f'''
                SELECT month, MAX(day) as max_day
                FROM {table}
                WHERE year = ?
                GROUP BY month
                ORDER BY month DESC
                LIMIT 1
            ''', (year,))
            row = c.fetchone()
            if not row or not row['month']:
                return None
            return {'month': int(row['month']), 'day': int(row['max_day'] or 31)}

        transform_daily_cutoff = _latest_daily_cutoff('agg_daily_performance')
        jingdai_daily_cutoff = _latest_daily_cutoff('agg_jingdai_daily')
        if transform_daily_cutoff and jingdai_daily_cutoff:
            common_daily_cutoff = min(transform_daily_cutoff, jingdai_daily_cutoff, key=lambda x: (x['month'], x['day']))
            ytd_end_month = common_daily_cutoff['month']
            ytd_end_day = common_daily_cutoff['day']
            use_daily = True
        else:
            common_daily_cutoff = None
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

        # 长险期交（YTD）。有日级共同截止日时，与期交保费使用同一统计日。
        longterm_where = 'year = ? AND month <= ?'
        longterm_params = [year, ytd_end_month]
        if use_daily:
            longterm_where = 'year = ? AND (month < ? OR (month = ? AND day <= ?))'
            longterm_params = [year, ytd_end_month, ytd_end_month, ytd_end_day]
        c.execute(f'''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE {longterm_where} GROUP BY business_type, channel
        ''', longterm_params)
        lt_qj = {}; lt_tf = 0.0; lt_jd = 0.0
        for r in c.fetchall():
            v = round(r['total'] or 0, 2)
            key = f"{r['business_type']}|{r['channel']}" if r['channel'] else r['business_type']
            lt_qj[key] = v
            if r['business_type'] == '转型': lt_tf += v
            else: lt_jd += v
        lt_total = lt_tf + lt_jd

        prev_longterm_where = 'year = ? AND month <= ?'
        prev_longterm_params = [year - 1, ytd_end_month]
        if use_daily:
            prev_longterm_where = 'year = ? AND (month < ? OR (month = ? AND day <= ?))'
            prev_longterm_params = [year - 1, ytd_end_month, ytd_end_month, ytd_end_day]
        c.execute(f'''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE {prev_longterm_where} GROUP BY business_type, channel
        ''', prev_longterm_params)
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

        # 商保年金 / 保障类 / 10年期（月级精度）
        c.execute('''
            SELECT channel, SUM(product_annuity) AS a, SUM(product_protection) AS p, SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        org_product_rows = c.fetchall()
        annuity_tf = sum((r['a'] or 0) for r in org_product_rows)
        protection_tf = sum((r['p'] or 0) for r in org_product_rows)
        c.execute('''
            SELECT SUM(product_annuity) AS a, SUM(product_protection) AS p
            FROM agg_jingdai WHERE year = ? AND month <= ?
        ''', (year, query_month))
        jd_product_row = c.fetchone()
        annuity_jd = (jd_product_row['a'] or 0) if jd_product_row else 0.0
        protection_jd = (jd_product_row['p'] or 0) if jd_product_row else 0.0
        c.execute('''
            SELECT SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ?
        ''', (year, query_month))
        row = c.fetchone()
        tenyear_tf = (row['t'] or 0) if row else 0.0
        c.execute('''
            SELECT SUM(qj_premium) AS t
            FROM agg_payment_period
            WHERE year = ? AND month <= ?
              AND business_type = '经代'
              AND category = '10年及以上'
        ''', (year, query_month))
        row = c.fetchone()
        tenyear_jd = (row['t'] or 0) if row else 0.0

        total_transform = perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0)

        # 去年同期期交保费（日级口径）
        prev_perf = _ytd_premiums_daily(year - 1) if use_daily else {}
        prev_jingdai_qj = _ytd_jingdai_daily(year - 1) if use_daily else 0.0

        return {
            'year': year,
            'month': query_month,
            'data_cutoff': data_cutoff,
            'daily_cutoff': {
                'month': ytd_end_month,
                'day': ytd_end_day,
                'use_daily': use_daily,
                'common': common_daily_cutoff,
                'transform': transform_daily_cutoff,
                'jingdai': jingdai_daily_cutoff,
            },
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
            'annuity_total': round(annuity_tf + annuity_jd, 2),
            'annuity_tf': round(annuity_tf, 2),
            'annuity_jd': round(annuity_jd, 2),
            'protection_total': round(protection_tf + protection_jd, 2),
            'protection_tf': round(protection_tf, 2),
            'protection_jd': round(protection_jd, 2),
            'tenyear_total': round(tenyear_tf + tenyear_jd, 2),
            'tenyear_tf': round(tenyear_tf, 2),
            'tenyear_jd': round(tenyear_jd, 2),
            'hr': hr,
            'hr_prev': hr_prev,
            'value': value,
        }


