"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from db.connection import get_db
from db.schema import init_db
from metrics.formulas import avg_policy_premium
from services.cutoff_policy import build_period_context, date_range_filter_sql


PAYMENT_PERIOD_CATEGORY_ORDER = [
    "趸交",
    "短期险",
    "3年交",
    "5年交",
    "10年及以上",
]


def _average_premium_payload(premium, count):
    premium_value = float(premium or 0)
    count_value = int(count or 0)
    average_value = avg_policy_premium(premium_value, count_value)
    return {
        "premium": round(premium_value, 2),
        "count": count_value,
        "average": average_value,
        "calculable": average_value is not None,
        "reason": None if average_value is not None else "承保件数净额小于或等于0",
    }


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

        # 转型业务件均保费：沿用当前交期分类、筛选条件和承保件数净额口径。
        # 经代源表没有承保件数/投保单号，不能以记录行数代替件数。
        c.execute(f'''
            SELECT channel, org, category,
                   SUM({premium_field}) AS premium_total,
                   SUM(count) AS count_total
            FROM {table}
            WHERE {where} AND business_type = '转型'
            GROUP BY channel, org, category
            ORDER BY
                CASE channel WHEN 'OTO' THEN 1 WHEN '证保' THEN 2 WHEN '蚁桥' THEN 3 ELSE 9 END,
                org,
                CASE category
                    WHEN '趸交' THEN 1
                    WHEN '短期险' THEN 2
                    WHEN '3年交' THEN 3
                    WHEN '5年交' THEN 4
                    WHEN '10年及以上' THEN 5
                    ELSE 9
                END
        ''', params)

        grouped_average_rows = {}
        for r in c.fetchall():
            key = (r['channel'], r['org'])
            group = grouped_average_rows.setdefault(key, {
                "org": r['org'],
                "business_mode": r['channel'],
                "premium_total": 0.0,
                "count_total": 0,
                "terms": [],
            })
            premium_total = float(r['premium_total'] or 0)
            count_total = int(r['count_total'] or 0)
            group["premium_total"] += premium_total
            group["count_total"] += count_total
            group["terms"].append({
                "category": r['category'],
                "premium_total": premium_total,
                "count_total": count_total,
            })

        category_rank = {
            category: index for index, category in enumerate(PAYMENT_PERIOD_CATEGORY_ORDER)
        }
        average_rows = []
        for group in grouped_average_rows.values():
            group["terms"].sort(
                key=lambda item: (category_rank.get(item["category"], 99), item["category"])
            )
            average_rows.append({
                "org": group["org"],
                "business_mode": group["business_mode"],
                "terms": [
                    {
                        "category": term["category"],
                        **_average_premium_payload(
                            term["premium_total"],
                            term["count_total"],
                        ),
                    }
                    for term in group["terms"]
                ],
                "total": _average_premium_payload(
                    group["premium_total"],
                    group["count_total"],
                ),
            })

        # 为表内“全部 / 单机构 / 单模式 / 机构×模式”筛选预聚合合计。
        # 前端只选择与当前筛选完全匹配的后端结果，不对件均值做简单平均。
        grouped_average_summaries = {}
        for row in grouped_average_rows.values():
            summary_keys = [
                ("all", "all"),
                (row["org"], "all"),
                ("all", row["business_mode"]),
                (row["org"], row["business_mode"]),
            ]
            for key in summary_keys:
                summary = grouped_average_summaries.setdefault(key, {
                    "org": key[0],
                    "business_mode": key[1],
                    "premium_total": 0.0,
                    "count_total": 0,
                    "terms": {},
                })
                summary["premium_total"] += row["premium_total"]
                summary["count_total"] += row["count_total"]
                for term in row["terms"]:
                    term_summary = summary["terms"].setdefault(term["category"], {
                        "premium": 0.0,
                        "count": 0,
                    })
                    term_summary["premium"] += term["premium_total"]
                    term_summary["count"] += term["count_total"]

        average_summaries = []
        for summary in grouped_average_summaries.values():
            terms = []
            for category in PAYMENT_PERIOD_CATEGORY_ORDER:
                term_summary = summary["terms"].get(category)
                if term_summary is None:
                    continue
                terms.append({
                    "category": category,
                    **_average_premium_payload(
                        term_summary["premium"],
                        term_summary["count"],
                    ),
                })
            average_summaries.append({
                "org": summary["org"],
                "business_mode": summary["business_mode"],
                "terms": terms,
                "total": _average_premium_payload(
                    summary["premium_total"],
                    summary["count_total"],
                ),
            })

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
            'average_premium': {
                'scope': '转型',
                'metric': metric if metric == 'gm' else 'qj',
                'premium_label': '规模保费' if metric == 'gm' else '期交保费',
                'unit': '万元/件',
                'formula': '所选范围保费净额 ÷ 承保件数净额',
                'categories': PAYMENT_PERIOD_CATEGORY_ORDER,
                'rows': average_rows,
                'summaries': average_summaries,
            },
            'jingdai_orgs': jd_orgs,
        }


