"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db
from services.cutoff_policy import build_as_of_context, cutoff_min, latest_daily_cutoff


def get_org_kpi_data(year: int, as_of: str | None = None):
    """获取机构维度KPI数据。

    年度同比使用日累计至统计日截止：
    - 从 agg_org_daily_performance 取当前年度最新月份和日期作为 cutoff
    - 去年同期数据按同一月/日截取（非整月累计）
    - 无日数据时回退到月表最新月份截断
    """
    with get_db() as conn:
        c = conn.cursor()
        as_of_context = build_as_of_context(conn, year, as_of)
        selected_cutoff = as_of_context.get("selectedCutoff")

        # 找到当前年度统计截止日（日表最新日期），用于截断同比基准
        org_source_cutoff = latest_daily_cutoff(conn, 'agg_org_daily_performance', year)
        org_daily_cutoff = cutoff_min(org_source_cutoff, selected_cutoff) if org_source_cutoff else None
        if org_daily_cutoff:
            ytd_end_month = int(org_daily_cutoff['month'])
            ytd_end_day = int(org_daily_cutoff['day'] or 31)
            use_daily = True
        else:
            # 无日数据时回退：当月表最新月份截断
            c.execute('SELECT MAX(month) FROM agg_org_performance WHERE year = ?', (year,))
            row = c.fetchone()
            ytd_end_month = row[0] if row and row[0] else 12
            if selected_cutoff:
                ytd_end_month = min(int(ytd_end_month), int(selected_cutoff['month']))
            ytd_end_day = 31
            use_daily = False

        channel_cutoffs = {}
        if use_daily:
            c.execute('''
                SELECT d.channel, d.month, MAX(d.day) AS max_day
                FROM agg_org_daily_performance d
                JOIN (
                    SELECT channel, MAX(month) AS month
                    FROM agg_org_daily_performance
                    WHERE year = ?
                    GROUP BY channel
                ) latest
                  ON latest.channel = d.channel
                 AND latest.month = d.month
                WHERE d.year = ?
                GROUP BY d.channel, d.month
            ''', (year, year))
            for r in c.fetchall():
                capped = cutoff_min(
                    {'month': int(r['month']), 'day': int(r['max_day'] or 31)},
                    selected_cutoff,
                )
                if capped:
                    channel_cutoffs[r['channel']] = (int(capped['month']), int(capped['day']))

        def _ytd_premiums(query_year: int):
            """从日表取截至统计日的期交保费累计，无数据则回退None"""
            if not use_daily:
                return {}
            if not channel_cutoffs:
                return {}
            clauses = []
            params = [query_year]
            for channel, (month, day) in channel_cutoffs.items():
                clauses.append('(channel = ? AND (month < ? OR (month = ? AND day <= ?)))')
                params.extend([channel, month, month, day])
            c.execute(f'''
                SELECT org, channel, SUM(qj_premium) AS qj_total
                FROM agg_org_daily_performance
                WHERE year = ?
                  AND ({' OR '.join(clauses)})
                GROUP BY org, channel
            ''', params)
            return {f"{r['org']}|{r['channel']}": round(r['qj_total'] or 0, 2)
                    for r in c.fetchall()}

        def _ytd_products(query_year: int):
            """从日表取截至统计日的产品指标累计。"""
            if not use_daily:
                return {}
            if not channel_cutoffs:
                return {}
            clauses = []
            params = [query_year]
            for channel, (month, day) in channel_cutoffs.items():
                clauses.append('(channel = ? AND (month < ? OR (month = ? AND day <= ?)))')
                params.extend([channel, month, month, day])
            c.execute(f'''
                SELECT org, channel,
                       SUM(product_10year) AS p10_total,
                       SUM(product_annuity) AS annuity_total,
                       SUM(product_protection) AS protection_total
                FROM agg_org_daily_performance
                WHERE year = ?
                  AND ({' OR '.join(clauses)})
                GROUP BY org, channel
            ''', params)
            return {
                f"{r['org']}|{r['channel']}": {
                    'product_10year': round(r['p10_total'] or 0, 2),
                    'product_annuity': round(r['annuity_total'] or 0, 2),
                    'product_protection': round(r['protection_total'] or 0, 2),
                }
                for r in c.fetchall()
            }

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
                WHERE year = ? AND month <= ?
                GROUP BY org, channel, month
            ''', (query_year, ytd_end_month))
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
                # 年度累计仅累加 ≤ 统计截止月的月份；有日表时产品分解稍后用日累计覆盖。
                if month <= ytd_end_month:
                    if not use_daily:
                        item['year']['product_10year'] = round(item['year']['product_10year'] + month_data['product_10year'], 2)
                        item['year']['product_annuity'] = round(item['year']['product_annuity'] + month_data['product_annuity'], 2)
                        item['year']['product_protection'] = round(item['year']['product_protection'] + month_data['product_protection'], 2)
                    # 无日数据时用月表累加期交保费
                    if not use_daily:
                        item['year']['qj_premium'] = round(item['year']['qj_premium'] + month_data['qj_premium'], 2)

            # 有日数据时用日累计覆盖年度期交保费和产品指标（更精确到天）
            ytd_map = _ytd_premiums(query_year)
            product_map = _ytd_products(query_year)
            for key, item in result.items():
                if key in ytd_map:
                    item['year']['qj_premium'] = ytd_map[key]
                elif use_daily:
                    # 日表无该组合则置零
                    item['year']['qj_premium'] = 0
                if use_daily:
                    products = product_map.get(key, {})
                    item['year']['product_10year'] = products.get('product_10year', 0)
                    item['year']['product_annuity'] = products.get('product_annuity', 0)
                    item['year']['product_protection'] = products.get('product_protection', 0)
            return result

        def collect_value(query_year: int):
            c.execute('''
                SELECT org, channel, month, SUM(value_premium) AS value_total
                FROM agg_org_value
                WHERE year = ? AND month <= ?
                GROUP BY org, channel, month
            ''', (query_year, ytd_end_month))
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

        def collect_longterm(query_year: int):
            result = {}
            if use_daily and channel_cutoffs:
                clauses = []
                params = [query_year]
                for channel, (month, day) in channel_cutoffs.items():
                    clauses.append('(channel = ? AND (month < ? OR (month = ? AND day <= ?)))')
                    params.extend([channel, month, month, day])
                c.execute(f'''
                    SELECT org, channel, SUM(qj_premium) AS total
                    FROM agg_longterm_qj
                    WHERE year = ?
                      AND business_type = '转型'
                      AND ({' OR '.join(clauses)})
                    GROUP BY org, channel
                ''', params)
            else:
                c.execute('''
                    SELECT org, channel, SUM(qj_premium) AS total
                    FROM agg_longterm_qj
                    WHERE year = ?
                      AND business_type = '转型'
                      AND month <= ?
                    GROUP BY org, channel
                ''', (query_year, ytd_end_month))
            for r in c.fetchall():
                result[f"{r['org']}|{r['channel']}"] = {'year': round(r['total'] or 0, 2)}
            return result

        org_perf = collect_perf(year)
        org_value = collect_value(year)
        org_longterm = collect_longterm(year)
        org_perf_prev = collect_perf(year - 1)
        org_value_prev = collect_value(year - 1)
        org_keys = set(org_perf.keys()) | set(org_value.keys()) | set(org_longterm.keys())
        orgs = sorted({key.split('|', 1)[0] for key in org_keys})

        return {
            'year': year,
            'orgs': orgs,
            'perf': org_perf,
            'value': org_value,
            'longterm': org_longterm,
            'perf_prev': org_perf_prev,
            'value_prev': org_value_prev,
            'as_of': as_of_context,
        }
