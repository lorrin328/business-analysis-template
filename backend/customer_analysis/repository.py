"""Business-facing customer and policy analysis queries."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Literal

from db.connection import get_db


PeriodType = Literal["year", "quarter", "month"]
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
                "newCustomer": "在本次客户清单覆盖范围内，所选期间首次承保的客户。",
                "existingCustomer": "在本次客户清单覆盖范围内，所选期间开始前已有承保记录、且期间内产生业绩的客户。",
                "policyStatus": "客户清单数据截止日的当前保单状态，不等同于13个月或25个月继续率。",
                "surrender": "仅统计终止原因为“退保终止”的保单；契撤、到期、满期和理赔均单列。",
                "holdingScope": "所选期间产生业绩且已关联客户清单的客户，其在客户清单中的全部已知保单。",
                "firstRepeatInterval": "同一客户第一张与第二张保单承保日期的间隔；日期不完整的客户不进入间隔分布。",
            },
        },
    }
