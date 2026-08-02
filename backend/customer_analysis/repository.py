"""Business-facing customer and policy analysis queries."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Literal

from db.connection import get_db


PeriodType = Literal["year", "quarter", "month"]
ObservationWindow = Literal["first_month", "twelve_months", "calendar_year"]
STATUS_LABELS = {
    "active": "有效",
    "suspended": "停效",
    "surrender": "退保",
    "cooling_off": "犹豫期撤保",
    "maturity": "到期/满期",
    "short_expiry": "短险逾期",
    "claim": "理赔/身故",
    "other_terminated": "其他终止",
    "unmatched": "未关联",
    "unknown": "状态待确认",
}
STATUS_ORDER = [
    "active", "suspended", "surrender", "cooling_off", "maturity", "short_expiry",
    "claim", "other_terminated", "unmatched", "unknown",
]


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _wan(value: float | None) -> float:
    return round(float(value or 0) / 10_000, 4)


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _window(year: int, cutoff: date, period_type: PeriodType, period_value: int | None):
    if period_type == "year":
        start, natural_end, label = date(year, 1, 1), date(year, 12, 31), f"{year}年度累计"
    elif period_type == "quarter":
        if period_value not in {1, 2, 3, 4}:
            raise ValueError("季度筛选必须选择1至4季度")
        start_month = (period_value - 1) * 3 + 1
        end_month = start_month + 2
        start = date(year, start_month, 1)
        natural_end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        label = f"{year}年Q{period_value}"
    elif period_type == "month":
        if period_value is None or not 1 <= period_value <= 12:
            raise ValueError("月度筛选必须选择1至12月")
        start = date(year, period_value, 1)
        natural_end = date(year, period_value, calendar.monthrange(year, period_value)[1])
        label = f"{year}年{period_value}月"
    else:
        raise ValueError("统计周期仅支持年度累计、季度或月度")
    if cutoff < start:
        raise ValueError(f"{label}尚未到达数据截止日")
    return start, min(cutoff, natural_end), label


def _filters(start: date, end: date, business_line: str | None, org: str | None, policy_scope: str):
    clauses = ["(year*100+month) BETWEEN ? AND ?"]
    params: list = [start.year * 100 + start.month, end.year * 100 + end.month]
    if business_line:
        clauses.append("business_line=?")
        params.append(business_line)
    if org:
        clauses.append("org=?")
        params.append(org)
    if policy_scope == "longterm":
        clauses.append("is_longterm=1")
    elif policy_scope != "all":
        raise ValueError("保单范围仅支持全部或长险")
    return " AND ".join(clauses), params


def _segment_sql(alias: str, start: date, end: date) -> str:
    return f"""CASE
        WHEN substr({alias}.first_customer_underwriting_time,1,10) BETWEEN '{start.isoformat()}' AND '{end.isoformat()}' THEN 'new'
        WHEN substr({alias}.first_customer_underwriting_time,1,10) < '{start.isoformat()}' THEN 'existing'
        ELSE 'unknown' END"""


def _monthly_segment_sql(alias: str) -> str:
    return f"""CASE
        WHEN substr({alias}.first_customer_underwriting_time,1,7)=printf('%04d-%02d',{alias}.year,{alias}.month) THEN 'new'
        WHEN substr({alias}.first_customer_underwriting_time,1,7)<printf('%04d-%02d',{alias}.year,{alias}.month) THEN 'existing'
        ELSE 'unknown' END"""


def _latest_batch(conn):
    return conn.execute(
        """SELECT id, source_cutoff, performance_rows, customer_source_rows, customer_policy_rows,
                  source_text_issue_rows, imported_at, completed_at
           FROM history_import_batches WHERE status='success' ORDER BY id DESC LIMIT 1"""
    ).fetchone()


def _available_years(conn) -> list[int]:
    return [
        int(row[0]) for row in conn.execute(
            "SELECT DISTINCT year FROM customer_policy_month_fact ORDER BY year"
        ).fetchall()
    ]


def _analysis_period(conn, batch, year: int | None, period_type: PeriodType, period_value: int | None):
    available_years = _available_years(conn)
    if not available_years:
        raise ValueError("客户分析事实表为空")
    year = year or max(available_years)
    if year not in available_years:
        raise ValueError(f"当前客户分析没有{year}年业绩")
    source_cutoff = datetime.fromisoformat(str(batch["source_cutoff"])[:19]).date()
    cutoff = min(source_cutoff, date(year, 12, 31)) if year == source_cutoff.year else date(year, 12, 31)
    start, end, period_label = _window(year, cutoff, period_type, period_value)
    return available_years, year, source_cutoff, start, end, period_label


def _raw_product_profile_sql(conn) -> str:
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(performance)").fetchall()}
    if "投保单号" not in columns:
        return """product_profile AS (
            SELECT policy_no, '产品待确认' product_name, '产品类型待确认' product_type
            FROM policy_keys
        )"""
    name_parts = [
        f'MAX(NULLIF(TRIM(p."{column}"),\'\'))'
        for column in ("产品名称", "产品类型", "产品代码") if column in columns
    ]
    type_parts = [
        f'MAX(NULLIF(TRIM(p."{column}"),\'\'))'
        for column in ("产品类型", "产品名称") if column in columns
    ]
    product_name = ", ".join(name_parts + ["'产品待确认'"])
    product_type = ", ".join(type_parts + ["'产品类型待确认'"])
    return f"""product_profile AS (
        SELECT k.policy_no, COALESCE({product_name}) product_name,
               COALESCE({product_type}) product_type
        FROM policy_keys k
        LEFT JOIN performance p ON p."投保单号"=k.policy_no
        GROUP BY k.policy_no
    )"""


def get_new_customer_cohort_analysis(
    *, year: int | None = None, period_type: PeriodType = "year", period_value: int | None = None,
    observation_window: ObservationWindow = "twelve_months", business_line: str | None = None,
    org: str | None = None, policy_scope: str = "all", product: str | None = None,
) -> dict:
    """Track system-new customers through a clearly bounded observation window."""
    window_end_sql = {
        "first_month": "date(first_date,'start of month','+1 month','-1 day')",
        "twelve_months": "date(first_date,'+12 months','-1 day')",
        "calendar_year": "date(substr(first_date,1,4)||'-12-31')",
    }.get(observation_window)
    if not window_end_sql:
        raise ValueError("观察窗口仅支持首现月、首现后12个月或首现当年度")
    if policy_scope not in {"all", "longterm"}:
        raise ValueError("保单范围仅支持全部或长险")

    with get_db() as conn:
        batch = _latest_batch(conn)
        if not batch:
            raise ValueError("尚未导入全量客户与历史业绩数据")
        available_years, year, source_cutoff, start, end, period_label = _analysis_period(
            conn, batch, year, period_type, period_value
        )
        named = {
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "source_cutoff": source_cutoff.isoformat(),
        }
        conn.execute("DROP TABLE IF EXISTS temp.new_customer_cohort")
        conn.execute(
            f"""CREATE TEMP TABLE new_customer_cohort AS
                WITH base AS (
                    SELECT customer_id, first_policy_no,
                           date(substr(first_underwriting_time,1,10)) first_date
                    FROM customer_master
                    WHERE date(substr(first_underwriting_time,1,10))
                          BETWEEN date(:period_start) AND date(:period_end)
                ), bounded AS (
                    SELECT *, {window_end_sql} natural_end FROM base
                )
                SELECT *,
                       CASE WHEN natural_end<=date(:source_cutoff) THEN natural_end
                            ELSE date(:source_cutoff) END observed_end,
                       CASE WHEN natural_end<=date(:source_cutoff) THEN 1 ELSE 0 END window_complete
                FROM bounded""",
            named,
        )
        conn.execute("CREATE INDEX temp.ix_new_customer_cohort_customer ON new_customer_cohort(customer_id)")

        product_profile_sql = _raw_product_profile_sql(conn)
        conn.execute("DROP TABLE IF EXISTS temp.new_customer_policy_base")
        conn.execute(
            f"""CREATE TEMP TABLE new_customer_policy_base AS
                WITH policy_contribution AS (
                    SELECT f.customer_id, f.policy_no,
                           MIN(date(substr(f.underwriting_time,1,10))) policy_date,
                           f.business_line, f.org, MAX(f.is_longterm) is_longterm,
                           SUM(f.qj_premium) qj_premium
                    FROM customer_policy_month_fact f
                    JOIN new_customer_cohort c ON c.customer_id=f.customer_id
                    WHERE f.customer_match=1
                      AND date(substr(f.underwriting_time,1,10)) BETWEEN c.first_date AND c.observed_end
                    GROUP BY f.customer_id, f.policy_no, f.business_line, f.org
                ), policy_keys AS (
                    SELECT DISTINCT policy_no FROM policy_contribution
                ), {product_profile_sql}
                SELECT p.customer_id, p.policy_no, p.policy_date, p.business_line, p.org,
                       p.is_longterm, p.qj_premium, pr.product_name, pr.product_type,
                       c.first_policy_no, c.first_date, c.natural_end, c.observed_end,
                       c.window_complete,
                       CASE WHEN p.policy_no=c.first_policy_no THEN 0 ELSE 1 END is_repeat,
                       ((CAST(strftime('%Y',p.policy_date) AS INTEGER)-CAST(strftime('%Y',c.first_date) AS INTEGER))*12
                        + CAST(strftime('%m',p.policy_date) AS INTEGER)-CAST(strftime('%m',c.first_date) AS INTEGER)) month_index
                FROM policy_contribution p
                JOIN product_profile pr ON pr.policy_no=p.policy_no
                JOIN new_customer_cohort c ON c.customer_id=p.customer_id"""
        )
        conn.execute("CREATE INDEX temp.ix_new_customer_policy_dims ON new_customer_policy_base(business_line, org, product_name)")
        conn.execute("CREATE INDEX temp.ix_new_customer_policy_customer ON new_customer_policy_base(customer_id, is_repeat)")

        dimension_clauses = ["1=1"]
        dimension_params: list = []
        if business_line:
            dimension_clauses.append("business_line=?")
            dimension_params.append(business_line)
        if org:
            dimension_clauses.append("org=?")
            dimension_params.append(org)
        if policy_scope == "longterm":
            dimension_clauses.append("is_longterm=1")
        dimension_where = " AND ".join(dimension_clauses)
        conn.execute("DROP TABLE IF EXISTS temp.new_customer_policy_dimension")
        conn.execute(
            f"CREATE TEMP TABLE new_customer_policy_dimension AS SELECT * FROM new_customer_policy_base WHERE {dimension_where}",
            dimension_params,
        )
        available_products = [
            str(row[0]) for row in conn.execute(
                """SELECT product_name FROM new_customer_policy_dimension
                   GROUP BY product_name ORDER BY SUM(qj_premium) DESC, product_name"""
            ).fetchall()
        ]
        conn.execute("DROP TABLE IF EXISTS temp.new_customer_policy_selected")
        if product:
            conn.execute(
                "CREATE TEMP TABLE new_customer_policy_selected AS SELECT * FROM new_customer_policy_dimension WHERE product_name=?",
                (product,),
            )
        else:
            conn.execute("CREATE TEMP TABLE new_customer_policy_selected AS SELECT * FROM new_customer_policy_dimension")
        conn.execute("CREATE INDEX temp.ix_new_customer_selected_customer ON new_customer_policy_selected(customer_id, is_repeat)")

        system_new_customers = int(conn.execute("SELECT COUNT(*) FROM new_customer_cohort").fetchone()[0])
        summary_row = conn.execute(
            """SELECT COUNT(DISTINCT customer_id) tracked_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=0 THEN customer_id END) first_policy_tracked_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN customer_id END) repeat_customers,
                      COUNT(DISTINCT policy_no) tracked_policies,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN policy_no END) repeat_policies,
                      SUM(CASE WHEN is_repeat=0 THEN qj_premium ELSE 0 END) first_qj,
                      SUM(CASE WHEN is_repeat=1 THEN qj_premium ELSE 0 END) repeat_qj,
                      SUM(qj_premium) total_qj
               FROM new_customer_policy_selected"""
        ).fetchone()
        tracked_customers = int(summary_row["tracked_customers"] or 0)
        repeat_customers = int(summary_row["repeat_customers"] or 0)
        repeat_policies = int(summary_row["repeat_policies"] or 0)
        maturity_row = conn.execute(
            """SELECT COUNT(*) tracked_customers,
                      SUM(c.window_complete) completed_customers
               FROM new_customer_cohort c
               JOIN (SELECT DISTINCT customer_id FROM new_customer_policy_selected) s
                 ON s.customer_id=c.customer_id"""
        ).fetchone()
        completed_customers = int(maturity_row["completed_customers"] or 0)

        product_rows = conn.execute(
            """SELECT product_name, MAX(product_type) product_type,
                      COUNT(DISTINCT customer_id) customers,
                      COUNT(DISTINCT policy_no) policies, SUM(qj_premium) qj_premium,
                      COUNT(DISTINCT CASE WHEN is_repeat=0 THEN customer_id END) first_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=0 THEN policy_no END) first_policies,
                      SUM(CASE WHEN is_repeat=0 THEN qj_premium ELSE 0 END) first_qj,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN customer_id END) repeat_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN policy_no END) repeat_policies,
                      SUM(CASE WHEN is_repeat=1 THEN qj_premium ELSE 0 END) repeat_qj
               FROM new_customer_policy_selected
               GROUP BY product_name ORDER BY qj_premium DESC, product_name"""
        ).fetchall()
        products = []
        for row in product_rows:
            total_qj = float(row["qj_premium"] or 0)
            repeat_qj = float(row["repeat_qj"] or 0)
            products.append({
                "product": row["product_name"], "productType": row["product_type"],
                "customers": int(row["customers"] or 0), "policies": int(row["policies"] or 0),
                "qjPremiumWan": _wan(total_qj), "firstCustomers": int(row["first_customers"] or 0),
                "firstPolicies": int(row["first_policies"] or 0), "firstQjPremiumWan": _wan(row["first_qj"]),
                "repeatCustomers": int(row["repeat_customers"] or 0),
                "repeatPolicies": int(row["repeat_policies"] or 0),
                "repeatQjPremiumWan": _wan(repeat_qj), "repeatPremiumShare": _ratio(repeat_qj, total_qj),
            })

        line_rows = conn.execute(
            """SELECT business_line, COUNT(DISTINCT customer_id) customers,
                      COUNT(DISTINCT policy_no) policies, SUM(qj_premium) qj_premium,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN customer_id END) repeat_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN policy_no END) repeat_policies,
                      SUM(CASE WHEN is_repeat=1 THEN qj_premium ELSE 0 END) repeat_qj
               FROM new_customer_policy_selected GROUP BY business_line
               ORDER BY CASE business_line WHEN 'OTO' THEN 1 WHEN '证保' THEN 2 ELSE 3 END"""
        ).fetchall()
        lines = []
        for row in line_rows:
            customers = int(row["customers"] or 0)
            total_qj = float(row["qj_premium"] or 0)
            repeat_qj = float(row["repeat_qj"] or 0)
            lines.append({
                "businessLine": row["business_line"], "customers": customers,
                "policies": int(row["policies"] or 0), "qjPremiumWan": _wan(total_qj),
                "repeatCustomers": int(row["repeat_customers"] or 0),
                "repeatCustomerRate": _ratio(row["repeat_customers"] or 0, customers),
                "repeatPolicies": int(row["repeat_policies"] or 0),
                "repeatQjPremiumWan": _wan(repeat_qj), "repeatPremiumShare": _ratio(repeat_qj, total_qj),
            })

        timeline_rows = conn.execute(
            """SELECT month_index, COUNT(DISTINCT customer_id) customers,
                      COUNT(DISTINCT policy_no) policies, SUM(qj_premium) qj_premium,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN customer_id END) repeat_customers,
                      COUNT(DISTINCT CASE WHEN is_repeat=1 THEN policy_no END) repeat_policies,
                      SUM(CASE WHEN is_repeat=1 THEN qj_premium ELSE 0 END) repeat_qj
               FROM new_customer_policy_selected GROUP BY month_index ORDER BY month_index"""
        ).fetchall()
        timeline_map = {int(row["month_index"]): row for row in timeline_rows}
        month_count = 1 if observation_window == "first_month" else 12
        timeline = []
        for index in range(month_count):
            row = timeline_map.get(index)
            timeline.append({
                "monthIndex": index, "label": "首现月" if index == 0 else f"第{index + 1}个月",
                "customers": int(row["customers"] or 0) if row else 0,
                "policies": int(row["policies"] or 0) if row else 0,
                "qjPremiumWan": _wan(row["qj_premium"]) if row else 0.0,
                "repeatCustomers": int(row["repeat_customers"] or 0) if row else 0,
                "repeatPolicies": int(row["repeat_policies"] or 0) if row else 0,
                "repeatQjPremiumWan": _wan(row["repeat_qj"]) if row else 0.0,
            })

        cohort_month_rows = conn.execute(
            """SELECT substr(c.first_date,1,7) first_month,
                      COUNT(DISTINCT c.customer_id) system_new_customers,
                      COUNT(DISTINCT s.customer_id) tracked_customers,
                      COUNT(DISTINCT CASE WHEN s.is_repeat=1 THEN s.customer_id END) repeat_customers,
                      SUM(s.qj_premium) qj_premium,
                      SUM(CASE WHEN s.is_repeat=1 THEN s.qj_premium ELSE 0 END) repeat_qj
               FROM new_customer_cohort c
               LEFT JOIN new_customer_policy_selected s ON s.customer_id=c.customer_id
               GROUP BY substr(c.first_date,1,7) ORDER BY first_month"""
        ).fetchall()
        cohort_months = []
        for row in cohort_month_rows:
            tracked = int(row["tracked_customers"] or 0)
            cohort_months.append({
                "firstAppearanceMonth": row["first_month"],
                "systemNewCustomers": int(row["system_new_customers"] or 0),
                "trackedCustomers": tracked, "repeatCustomers": int(row["repeat_customers"] or 0),
                "repeatCustomerRate": _ratio(row["repeat_customers"] or 0, tracked),
                "qjPremiumWan": _wan(row["qj_premium"]), "repeatQjPremiumWan": _wan(row["repeat_qj"]),
            })
        organizations = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT org FROM customer_policy_month_fact WHERE TRIM(org)<>'' ORDER BY org"
            ).fetchall()
        ]

    first_qj = float(summary_row["first_qj"] or 0)
    repeat_qj = float(summary_row["repeat_qj"] or 0)
    total_qj = float(summary_row["total_qj"] or 0)
    definitions = {
        "newCustomer": "客户在当前客户清单覆盖的系统历史中，最早承保日期落在所选首现期间。",
        "firstAppearanceMonth": "客户最早承保日期所在的自然月。",
        "firstMonthWindow": "自客户首次承保日起，观察至该自然月最后一天。",
        "twelveMonthWindow": "自客户首次承保日起（含当日）观察12个月；满12个月当日不计入。",
        "calendarYearWindow": "自客户首次承保日起，观察至该自然年度12月31日。",
        "repeatUnderwriting": "同一客户除系统首张保单外的其他保单；同日多单也按首张1单、再次承保其余单统计。",
        "contributionScope": "产品、保费和再次承保仅统计已关联客户清单的OTO、证保、蚁桥业绩保单。",
        "dimensionFilter": "业务、机构、长险和产品筛选作用于观察窗口内的业绩保单；新客身份仍按系统最早承保日期判断。",
        "windowCompleteness": "只有数据截止日达到客户观察窗口自然结束日，才计为完整观察客户。",
    }
    return {
        "meta": {
            "year": year, "periodType": period_type, "periodValue": period_value,
            "periodLabel": period_label, "periodStart": start.isoformat(), "periodEnd": end.isoformat(),
            "sourceCutoff": str(batch["source_cutoff"]), "batchId": int(batch["id"]),
            "observationWindow": observation_window, "businessLine": business_line or "全部",
            "org": org or "全部", "policyScope": policy_scope, "product": product or "全部",
            "availableYears": available_years, "organizations": organizations,
            "availableProducts": available_products,
        },
        "summary": {
            "systemNewCustomers": system_new_customers, "trackedNewCustomers": tracked_customers,
            "trackingRate": _ratio(tracked_customers, system_new_customers),
            "firstPolicyTrackedCustomers": int(summary_row["first_policy_tracked_customers"] or 0),
            "repeatCustomers": repeat_customers, "repeatCustomerRate": _ratio(repeat_customers, tracked_customers),
            "trackedPolicies": int(summary_row["tracked_policies"] or 0), "repeatPolicies": repeat_policies,
            "averageRepeatPolicies": _ratio(repeat_policies, tracked_customers),
            "firstQjPremiumWan": _wan(first_qj), "repeatQjPremiumWan": _wan(repeat_qj),
            "qjPremiumWan": _wan(total_qj), "repeatPremiumShare": _ratio(repeat_qj, total_qj),
            "completedObservationCustomers": completed_customers,
            "incompleteObservationCustomers": tracked_customers - completed_customers,
            "observationCompletenessRate": _ratio(completed_customers, tracked_customers),
        },
        "products": products, "lines": lines, "timeline": timeline, "cohortMonths": cohort_months,
        "quality": {"definitions": definitions},
    }


def get_customer_analysis(
    *, year: int | None = None, period_type: PeriodType = "year", period_value: int | None = None,
    business_line: str | None = None, org: str | None = None, policy_scope: str = "all",
) -> dict:
    with get_db() as conn:
        batch = _latest_batch(conn)
        if not batch:
            raise ValueError("尚未导入全量客户与历史业绩数据")
        available_years = [
            int(row[0]) for row in conn.execute(
                "SELECT DISTINCT year FROM customer_policy_month_fact ORDER BY year"
            ).fetchall()
        ]
        if not available_years:
            raise ValueError("客户分析事实表为空")
        year = year or max(available_years)
        if year not in available_years:
            raise ValueError(f"当前客户分析没有{year}年业绩")
        source_cutoff = datetime.fromisoformat(str(batch["source_cutoff"])[:19]).date()
        cutoff = min(source_cutoff, date(year, 12, 31)) if year == source_cutoff.year else date(year, 12, 31)
        start, end, period_label = _window(year, cutoff, period_type, period_value)
        where_sql, params = _filters(start, end, business_line, org, policy_scope)
        segment = _segment_sql("f", start, end)

        premium_rows = conn.execute(
            f"""SELECT {segment} segment, COUNT(DISTINCT customer_id) customers,
                       COUNT(DISTINCT policy_no) policies, SUM(qj_premium) qj_premium
                FROM customer_policy_month_fact f WHERE {where_sql}
                GROUP BY 1""",
            params,
        ).fetchall()
        segments = {
            row["segment"]: {
                "customers": int(row["customers"] or 0),
                "policies": int(row["policies"] or 0),
                "qjPremiumWan": _wan(row["qj_premium"]),
            }
            for row in premium_rows
        }
        for key in ("new", "existing", "unknown"):
            segments.setdefault(key, {"customers": 0, "policies": 0, "qjPremiumWan": 0.0})

        totals = conn.execute(
            f"""SELECT COUNT(DISTINCT customer_id), COUNT(DISTINCT policy_no), SUM(qj_premium),
                       COUNT(DISTINCT CASE WHEN customer_match=1 THEN policy_no END),
                       SUM(CASE WHEN customer_match=1 THEN qj_premium ELSE 0 END),
                       SUM(ABS(qj_premium)), SUM(CASE WHEN customer_match=1 THEN ABS(qj_premium) ELSE 0 END)
                FROM customer_policy_month_fact WHERE {where_sql}""",
            params,
        ).fetchone()
        total_customers, total_policies, total_qj, matched_policies, matched_qj, absolute_qj, matched_absolute_qj = totals

        status_rows = conn.execute(
            f"""WITH policies AS (
                    SELECT policy_no, MAX(status_group) status_group
                    FROM customer_policy_month_fact WHERE {where_sql} GROUP BY policy_no
                ) SELECT status_group, COUNT(*) policies FROM policies GROUP BY status_group""",
            params,
        ).fetchall()
        status_counts = {row["status_group"]: int(row["policies"]) for row in status_rows}
        status_distribution = [
            {"code": code, "label": STATUS_LABELS[code], "policies": status_counts.get(code, 0),
             "rate": _ratio(status_counts.get(code, 0), total_policies or 0)}
            for code in STATUS_ORDER if status_counts.get(code, 0)
        ]

        monthly_segment = _monthly_segment_sql("f")
        monthly_rows = conn.execute(
            f"""SELECT year, month, {monthly_segment} segment,
                       COUNT(DISTINCT customer_id) customers, COUNT(DISTINCT policy_no) policies,
                       SUM(qj_premium) qj_premium
                FROM customer_policy_month_fact f WHERE {where_sql}
                GROUP BY year, month, segment ORDER BY year, month, segment""",
            params,
        ).fetchall()
        monthly: dict[str, dict] = {}
        for row in monthly_rows:
            key = f"{int(row['year']):04d}-{int(row['month']):02d}"
            item = monthly.setdefault(key, {"period": key, "new": {}, "existing": {}, "unknown": {}})
            item[row["segment"]] = {
                "customers": int(row["customers"] or 0), "policies": int(row["policies"] or 0),
                "qjPremiumWan": _wan(row["qj_premium"]),
            }

        line_rows = conn.execute(
            f"""SELECT business_line,
                       COUNT(DISTINCT customer_id) customers,
                       COUNT(DISTINCT CASE WHEN {segment}='new' THEN customer_id END) new_customers,
                       COUNT(DISTINCT CASE WHEN {segment}='existing' THEN customer_id END) existing_customers,
                       COUNT(DISTINCT policy_no) policies, SUM(qj_premium) qj_premium,
                       SUM(CASE WHEN {segment}='new' THEN qj_premium ELSE 0 END) new_qj,
                       SUM(CASE WHEN {segment}='existing' THEN qj_premium ELSE 0 END) existing_qj,
                       COUNT(DISTINCT CASE WHEN status_group='active' THEN policy_no END) active_policies,
                       COUNT(DISTINCT CASE WHEN status_group='surrender' THEN policy_no END) surrender_policies,
                       COUNT(DISTINCT CASE WHEN customer_match=1 THEN policy_no END) matched_policies
                FROM customer_policy_month_fact f WHERE {where_sql}
                GROUP BY business_line ORDER BY CASE business_line WHEN 'OTO' THEN 1 WHEN '证保' THEN 2 ELSE 3 END""",
            params,
        ).fetchall()
        lines = []
        for row in line_rows:
            policies = int(row["policies"] or 0)
            lines.append({
                "businessLine": row["business_line"], "customers": int(row["customers"] or 0),
                "newCustomers": int(row["new_customers"] or 0),
                "existingCustomers": int(row["existing_customers"] or 0), "policies": policies,
                "qjPremiumWan": _wan(row["qj_premium"]), "newQjPremiumWan": _wan(row["new_qj"]),
                "existingQjPremiumWan": _wan(row["existing_qj"]),
                "activePolicies": int(row["active_policies"] or 0),
                "activeRate": _ratio(row["active_policies"] or 0, policies),
                "surrenderPolicies": int(row["surrender_policies"] or 0),
                "surrenderRate": _ratio(row["surrender_policies"] or 0, policies),
                "matchRate": _ratio(row["matched_policies"] or 0, policies),
            })

        holding_rows = conn.execute(
            f"""WITH selected AS (
                    SELECT DISTINCT customer_id FROM customer_policy_month_fact
                    WHERE {where_sql} AND customer_match=1 AND customer_id IS NOT NULL
                ), ranked AS (
                    SELECT p.customer_id, p.policy_no, p.status_group,
                           date(substr(p.underwriting_time,1,10)) underwriting_date,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.customer_id
                               ORDER BY date(substr(p.underwriting_time,1,10)), p.policy_no
                           ) policy_order
                    FROM customer_policy_snapshot p
                    JOIN selected s ON s.customer_id=p.customer_id
                )
                SELECT customer_id, COUNT(*) policy_count,
                       SUM(CASE WHEN status_group='active' THEN 1 ELSE 0 END) active_policy_count,
                       MAX(CASE WHEN policy_order=1 THEN underwriting_date END) first_date,
                       MAX(CASE WHEN policy_order=2 THEN underwriting_date END) second_date
                FROM ranked GROUP BY customer_id""",
            params,
        ).fetchall()

        policy_bands = [
            {"band": "1份", "customers": 0}, {"band": "2份", "customers": 0},
            {"band": "3份", "customers": 0}, {"band": "4份及以上", "customers": 0},
        ]
        active_bands = [
            {"band": "0份有效", "customers": 0}, {"band": "1份有效", "customers": 0},
            {"band": "2份有效", "customers": 0}, {"band": "3份及以上有效", "customers": 0},
        ]
        interval_bands = [
            {"band": "30天内", "customers": 0}, {"band": "31—90天", "customers": 0},
            {"band": "91—180天", "customers": 0}, {"band": "181—365天", "customers": 0},
            {"band": "365天以上", "customers": 0},
        ]
        first_repeat_days: list[int] = []
        total_known_policies = total_active_policies = multi_policy_customers = active_customers = 0
        for row in holding_rows:
            policy_count = int(row["policy_count"] or 0)
            active_count = int(row["active_policy_count"] or 0)
            total_known_policies += policy_count
            total_active_policies += active_count
            multi_policy_customers += int(policy_count >= 2)
            active_customers += int(active_count >= 1)
            policy_bands[min(max(policy_count, 1), 4) - 1]["customers"] += 1
            active_bands[min(active_count, 3)]["customers"] += 1
            if row["first_date"] and row["second_date"]:
                first_date = date.fromisoformat(row["first_date"])
                second_date = date.fromisoformat(row["second_date"])
                days = max(0, (second_date - first_date).days)
                first_repeat_days.append(days)
                if days <= 30:
                    index = 0
                elif days <= 90:
                    index = 1
                elif days <= 180:
                    index = 2
                elif days <= 365:
                    index = 3
                else:
                    index = 4
                interval_bands[index]["customers"] += 1
        covered_customers = len(holding_rows)
        repeat_within_180 = sum(item["customers"] for item in interval_bands[:3])

        cohort_where = ["CAST(substr(f.underwriting_time,1,4) AS INTEGER) BETWEEN ? AND ?"]
        cohort_params: list = [max(min(available_years), year - 7), year]
        if business_line:
            cohort_where.append("f.business_line=?")
            cohort_params.append(business_line)
        if org:
            cohort_where.append("f.org=?")
            cohort_params.append(org)
        if policy_scope == "longterm":
            cohort_where.append("f.is_longterm=1")
        cohort_rows = conn.execute(
            f"""WITH policies AS (
                    SELECT policy_no, MIN(CAST(substr(underwriting_time,1,4) AS INTEGER)) cohort_year,
                           MAX(status_group) status_group
                    FROM customer_policy_month_fact f WHERE {' AND '.join(cohort_where)} GROUP BY policy_no
                ) SELECT cohort_year, status_group, COUNT(*) policies
                  FROM policies WHERE cohort_year BETWEEN ? AND ?
                  GROUP BY cohort_year, status_group ORDER BY cohort_year, status_group""",
            cohort_params + [max(min(available_years), year - 7), year],
        ).fetchall()
        cohorts: dict[int, dict] = {}
        for row in cohort_rows:
            item = cohorts.setdefault(int(row["cohort_year"]), {"year": int(row["cohort_year"]), "total": 0, "status": {}})
            item["status"][row["status_group"]] = int(row["policies"])
            item["total"] += int(row["policies"])
        cohort_list = []
        for item in cohorts.values():
            cohort_list.append({
                **item,
                "activeRate": _ratio(item["status"].get("active", 0), item["total"]),
                "surrenderRate": _ratio(item["status"].get("surrender", 0), item["total"]),
            })

        reason_rows = conn.execute(
            f"""WITH policies AS (
                    SELECT policy_no, MAX(NULLIF(TRIM(termination_reason),'')) reason
                    FROM customer_policy_month_fact WHERE {where_sql} GROUP BY policy_no
                ) SELECT reason, COUNT(*) policies FROM policies WHERE reason IS NOT NULL
                  GROUP BY reason ORDER BY policies DESC LIMIT 12""",
            params,
        ).fetchall()
        orgs = [
            row[0] for row in conn.execute(
                "SELECT DISTINCT org FROM customer_policy_month_fact WHERE TRIM(org)<>'' ORDER BY org"
            ).fetchall()
        ]

    new_qj = segments["new"]["qjPremiumWan"]
    old_qj = segments["existing"]["qjPremiumWan"]
    known_qj = new_qj + old_qj
    active = status_counts.get("active", 0)
    surrender = status_counts.get("surrender", 0)
    return {
        "meta": {
            "year": year, "periodType": period_type, "periodValue": period_value,
            "periodLabel": period_label, "periodStart": start.isoformat(), "periodEnd": end.isoformat(),
            "sourceCutoff": str(batch["source_cutoff"]), "batchId": int(batch["id"]),
            "availableYears": available_years, "organizations": orgs,
            "businessLine": business_line or "全部", "org": org or "全部", "policyScope": policy_scope,
        },
        "summary": {
            "customers": int(total_customers or 0), "policies": int(total_policies or 0),
            "qjPremiumWan": _wan(total_qj), "newCustomers": segments["new"]["customers"],
            "existingCustomers": segments["existing"]["customers"],
            "newQjPremiumWan": new_qj, "existingQjPremiumWan": old_qj,
            "newPremiumShare": _ratio(new_qj, known_qj), "existingPremiumShare": _ratio(old_qj, known_qj),
            "activePolicies": active, "activeRate": _ratio(active, total_policies or 0),
            "surrenderPolicies": surrender, "surrenderRate": _ratio(surrender, total_policies or 0),
            "coolingOffPolicies": status_counts.get("cooling_off", 0),
            "matchedPolicies": int(matched_policies or 0),
            "policyMatchRate": _ratio(matched_policies or 0, total_policies or 0),
            "premiumMatchRate": _ratio(matched_absolute_qj or 0, absolute_qj or 0),
            "unknownQjPremiumWan": segments["unknown"]["qjPremiumWan"],
        },
        "segments": segments,
        "monthly": list(monthly.values()),
        "statusDistribution": status_distribution,
        "lines": lines,
        "holdings": {
            "summary": {
                "coveredCustomers": covered_customers,
                "knownPolicies": total_known_policies,
                "averagePolicies": _ratio(total_known_policies, covered_customers),
                "multiPolicyCustomers": multi_policy_customers,
                "multiPolicyRate": _ratio(multi_policy_customers, covered_customers),
                "customersWithActivePolicy": active_customers,
                "activeCustomerRate": _ratio(active_customers, covered_customers),
                "zeroActiveCustomers": covered_customers - active_customers,
                "averageActivePolicies": _ratio(total_active_policies, covered_customers),
                "firstRepeatEligibleCustomers": len(first_repeat_days),
                "firstRepeatMedianDays": _median(first_repeat_days),
                "firstRepeatWithin180Rate": _ratio(repeat_within_180, len(first_repeat_days)),
            },
            "policyCountBands": policy_bands,
            "activePolicyCountBands": active_bands,
            "firstRepeatIntervalBands": interval_bands,
        },
        "cohorts": cohort_list,
        "terminationReasons": [{"reason": row["reason"], "policies": int(row["policies"])} for row in reason_rows],
        "quality": {
            "performanceRows": int(batch["performance_rows"]),
            "customerSourceRows": int(batch["customer_source_rows"]),
            "customerPolicyRows": int(batch["customer_policy_rows"]),
            "sourceTextIssueRows": int(batch["source_text_issue_rows"]),
            "definitions": {
                "newCustomer": "客户在当前客户清单覆盖的系统历史中，最早承保日期落在所选期间，且期间内产生OTO、证保或蚁桥业绩。",
                "existingCustomer": "客户在所选期间开始前已有系统承保记录，且期间内产生OTO、证保或蚁桥业绩。",
                "systemCoverage": "新老客身份以本次客户清单可追溯的2007年以来历史为准；在接入公司统一客户主数据前，不表述为公司全量客户口径。",
                "policyStatus": "客户清单数据截止日的当前保单状态，不等同于13个月或25个月继续率。",
                "surrender": "仅统计终止原因为“退保终止”的保单；契撤、到期、满期和理赔均单列。",
                "holdingScope": "所选期间产生业绩且已关联客户清单的客户，其在客户清单中的全部已知保单。",
                "firstRepeatInterval": "同一客户第一张与第二张保单承保日期的间隔；日期不完整的客户不进入间隔分布。",
            },
        },
    }
