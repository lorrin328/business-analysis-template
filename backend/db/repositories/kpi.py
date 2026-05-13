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
            'value': [dict(r) for r in value_rows],
            'org_performance': [dict(r) for r in org_perf_rows],
            'daily_performance': [dict(r) for r in daily_rows],
            'org_daily_performance': [dict(r) for r in org_daily_rows],
            'latest_period': latest,
        }



def get_kpi_data(year: int):
    with get_db() as conn:
        c = conn.cursor()

        # 两表各自最大月，取较小者确保数据齐备
        c.execute('SELECT MAX(month) FROM agg_performance WHERE year = ?', (year,))
        perf_max = c.fetchone()[0] or 1
        c.execute('SELECT MAX(month) FROM agg_hr_data WHERE year = ?', (year,))
        hr_max = c.fetchone()[0] or 1
        query_month = min(perf_max, hr_max)

        # YTD 保费
        c.execute('''
            SELECT channel, SUM(qj_premium) AS total
            FROM agg_performance WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        perf = {r['channel']: r['total'] or 0 for r in c.fetchall()}

        c.execute('''
            SELECT SUM(qj_premium) AS total FROM agg_jingdai WHERE year = ? AND month <= ?
        ''', (year, query_month))
        jingdai_qj = c.fetchone()['total'] or 0

        # HR
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

        # 去年同期
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

        # 长险期交（YTD）
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

        # 价值（YTD）
        c.execute('''
            SELECT channel, SUM(value_premium) AS total
            FROM agg_value_data WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        value = {r['channel']: r['total'] or 0 for r in c.fetchall()}

        # 商保年金 / 10年期 — 转型部分
        c.execute('''
            SELECT channel, SUM(product_annuity) AS a, SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ? GROUP BY channel
        ''', (year, query_month))
        annuity_tf = sum((r['a'] or 0) for r in c.fetchall())
        # 10年期 转型部分 — 重新单独查询（上面游标已消费完）
        c.execute('''
            SELECT SUM(product_10year) AS t
            FROM agg_org_performance WHERE year = ? AND month <= ?
        ''', (year, query_month))
        row = c.fetchone()
        tenyear_tf = (row['t'] or 0) if row else 0.0

        # 经代年金/10年期 暂缺（经代基表无年金/缴费年限分列）
        annuity_jd = 0.0
        tenyear_jd = 0.0

        total_transform = perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0)
        return {
            'year': year,
            'qj_premium': {
                'jingdai': round(jingdai_qj, 2),
                'oto': round(perf.get('OTO', 0), 2),
                'zhengbao': round(perf.get('证保', 0), 2),
                'yiqiao': round(perf.get('蚁桥', 0), 2),
                'total_transform': round(total_transform, 2),
                'total': round(jingdai_qj + total_transform, 2),
            },
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


