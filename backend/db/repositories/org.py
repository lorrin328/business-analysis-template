"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db


def get_org_kpi_data(year: int):
    """获取机构维度KPI数据，年度同比使用日累计至统计日截止"""
    with get_db() as conn:
        c = conn.cursor()

        # 找到当前年度统计截止日（日表最新日期），用于截断同比基准
        c.execute('''
            SELECT month, MAX(day) as max_day
            FROM agg_org_daily_performance
            WHERE year = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
        ''', (year,))
        cutoff = c.fetchone()
        if cutoff and cutoff['month']:
            ytd_end_month = cutoff['month']
            ytd_end_day = cutoff['max_day'] or 31
            use_daily = True
        else:
            # 无日数据时回退：当月表最新月份截断
            c.execute('SELECT MAX(month) FROM agg_org_performance WHERE year = ?', (year,))
            row = c.fetchone()
            ytd_end_month = row[0] if row and row[0] else 12
            ytd_end_day = 31
            use_daily = False

        def _ytd_premiums(query_year: int):
            """从日表取截至统计日的期交保费累计，无数据则回退None"""
            if not use_daily:
                return {}
            c.execute('''
                SELECT org, channel, SUM(qj_premium) AS qj_total
                FROM agg_org_daily_performance
                WHERE year = ?
                  AND (month < ? OR (month = ? AND day <= ?))
                GROUP BY org, channel
            ''', (query_year, ytd_end_month, ytd_end_month, ytd_end_day))
            return {f"{r['org']}|{r['channel']}": round(r['qj_total'] or 0, 2)
                    for r in c.fetchall()}

        def collect_perf(query_year: int):
            result = {}
            # 月度明细 + 季度汇总（完整月数据，保留原逻辑）
            c.execute('''
                SELECT org, channel, month,
                       SUM(qj_premium) AS qj_total,
                       SUM(product_10year) AS p10_total,
                       SUM(product_annuity) AS annuity_total,
                       SUM(product_protection) AS protection_total
                FROM agg_org_performance
                WHERE year = ?
                GROUP BY org, channel, month
            ''', (query_year,))
            for r in c.fetchall():
                key = f"{r['org']}|{r['channel']}"
                month = int(r['month'])
                item = result.setdefault(key, {
                    'year': {'qj_premium': 0, 'product_10year': 0, 'product_annuity': 0, 'product_protection': 0},
                    'month': {},
                    'quarter': {},
                })
                month_data = {
                    'qj_premium': round(r['qj_total'] or 0, 2),
                    'product_10year': round(r['p10_total'] or 0, 2),
                    'product_annuity': round(r['annuity_total'] or 0, 2),
                    'product_protection': round(r['protection_total'] or 0, 2),
                }
                item['month'][str(month)] = month_data
                q_label = f"Q{((month - 1) // 3) + 1}"
                q_data = item['quarter'].setdefault(q_label, {
                    'qj_premium': 0, 'product_10year': 0, 'product_annuity': 0, 'product_protection': 0
                })
                for field, value in month_data.items():
                    q_data[field] = round(q_data[field] + value, 2)
                # 年度累计仅累加 ≤ 统计截止月的月份（产品分解）
                if month <= ytd_end_month:
                    item['year']['product_10year'] = round(item['year']['product_10year'] + month_data['product_10year'], 2)
                    item['year']['product_annuity'] = round(item['year']['product_annuity'] + month_data['product_annuity'], 2)
                    item['year']['product_protection'] = round(item['year']['product_protection'] + month_data['product_protection'], 2)
                    # 无日数据时用月表累加期交保费
                    if not use_daily:
                        item['year']['qj_premium'] = round(item['year']['qj_premium'] + month_data['qj_premium'], 2)

            # 有日数据时用日累计覆盖年度期交保费（更精确到天）
            ytd_map = _ytd_premiums(query_year)
            for key, item in result.items():
                if key in ytd_map:
                    item['year']['qj_premium'] = ytd_map[key]
                elif use_daily:
                    # 日表无该组合则置零
                    item['year']['qj_premium'] = 0
            return result

        def collect_value(query_year: int):
            c.execute('''
                SELECT org, channel, month, SUM(value_premium) AS value_total
                FROM agg_org_value
                WHERE year = ?
                GROUP BY org, channel, month
            ''', (query_year,))
            result = {}
            for r in c.fetchall():
                key = f"{r['org']}|{r['channel']}"
                month = int(r['month'])
                value = round(r['value_total'] or 0, 2)
                item = result.setdefault(key, {'year': 0, 'month': {}, 'quarter': {}})
                if month <= ytd_end_month:
                    item['year'] = round(item['year'] + value, 2)
                item['month'][str(month)] = value
                q_label = f"Q{((month - 1) // 3) + 1}"
                item['quarter'][q_label] = round(item['quarter'].get(q_label, 0) + value, 2)
            return result

        org_perf = collect_perf(year)
        org_value = collect_value(year)
        org_perf_prev = collect_perf(year - 1)
        org_value_prev = collect_value(year - 1)
        org_keys = set(org_perf.keys()) | set(org_value.keys())
        orgs = sorted({key.split('|', 1)[0] for key in org_keys})

        return {
            'year': year,
            'orgs': orgs,
            'perf': org_perf,
            'value': org_value,
            'perf_prev': org_perf_prev,
            'value_prev': org_value_prev,
        }


