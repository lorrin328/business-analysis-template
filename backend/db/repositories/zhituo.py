"""职拓业务分析查询。"""
from __future__ import annotations

import sqlite3

from db.connection import get_db
from services.cutoff_policy import Cutoff, date_range_filter_sql


def _csv_text(value: str | None) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in str(value or "").split(",") if part.strip()))


def _csv_int(value: str | None, *, minimum: int, maximum: int) -> list[int]:
    result = []
    for part in _csv_text(value):
        try:
            number = int(part)
        except ValueError:
            continue
        if minimum <= number <= maximum and number not in result:
            result.append(number)
    return result


def _placeholders(values: list) -> str:
    return ",".join("?" for _ in values)


def get_zhituo_kpi(
    conn: sqlite3.Connection,
    year: int,
    start_cutoff: Cutoff,
    end_cutoff: Cutoff,
) -> dict:
    date_sql, date_params = date_range_filter_sql(start_cutoff, end_cutoff)
    row = conn.execute(
        f"""
        SELECT SUM(qj_premium) AS qj_premium,
               SUM(gm_premium) AS gm_premium,
               SUM(policy_count) AS policy_count,
               COUNT(DISTINCT CASE WHEN staff_id != '人员待确认' THEN staff_id END) AS staff_count
        FROM agg_zhituo_performance
        WHERE year = ? AND {date_sql}
        """,
        [int(year), *date_params],
    ).fetchone()
    return {
        "qj_premium": round((row["qj_premium"] if row else 0) or 0, 2),
        "gm_premium": round((row["gm_premium"] if row else 0) or 0, 2),
        "policy_count": int(round((row["policy_count"] if row else 0) or 0)),
        "staff_count": int((row["staff_count"] if row else 0) or 0),
    }


def get_zhituo_analysis(
    *,
    years: str | None = None,
    months: str | None = None,
    orgs: str | None = None,
) -> dict:
    selected_years = _csv_int(years, minimum=1900, maximum=2100)
    selected_months = _csv_int(months, minimum=1, maximum=12)
    selected_orgs = _csv_text(orgs)

    with get_db() as conn:
        available_years = [int(row[0]) for row in conn.execute(
            "SELECT DISTINCT year FROM agg_zhituo_performance ORDER BY year DESC"
        ).fetchall()]
        available_months = [int(row[0]) for row in conn.execute(
            "SELECT DISTINCT month FROM agg_zhituo_performance ORDER BY month"
        ).fetchall()]
        available_orgs = [str(row[0]) for row in conn.execute(
            "SELECT DISTINCT org FROM agg_zhituo_performance ORDER BY org"
        ).fetchall() if row[0]]
        if not selected_years and available_years:
            selected_years = [available_years[0]]

        clauses = ["1=1"]
        params: list = []
        if selected_years:
            clauses.append(f"year IN ({_placeholders(selected_years)})")
            params.extend(selected_years)
        if selected_months:
            clauses.append(f"month IN ({_placeholders(selected_months)})")
            params.extend(selected_months)
        if selected_orgs:
            clauses.append(f"org IN ({_placeholders(selected_orgs)})")
            params.extend(selected_orgs)
        where = " AND ".join(clauses)

        summary_row = conn.execute(
            f"""
            SELECT SUM(qj_premium) AS qj_premium, SUM(gm_premium) AS gm_premium,
                   SUM(policy_count) AS policy_count,
                   COUNT(DISTINCT CASE WHEN staff_id != '人员待确认' THEN staff_id END) AS staff_count,
                   COUNT(DISTINCT CASE WHEN product_name != '产品待确认' THEN product_name END) AS product_count,
                   COUNT(DISTINCT org) AS org_count
            FROM agg_zhituo_performance WHERE {where}
            """,
            params,
        ).fetchone()
        summary = {
            "qjPremium": round((summary_row["qj_premium"] if summary_row else 0) or 0, 2),
            "gmPremium": round((summary_row["gm_premium"] if summary_row else 0) or 0, 2),
            "policyCount": int(round((summary_row["policy_count"] if summary_row else 0) or 0)),
            "staffCount": int((summary_row["staff_count"] if summary_row else 0) or 0),
            "productCount": int((summary_row["product_count"] if summary_row else 0) or 0),
            "orgCount": int((summary_row["org_count"] if summary_row else 0) or 0),
        }

        def rows(sql: str) -> list[dict]:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

        monthly = rows(f"""
            SELECT year, month, ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT CASE WHEN staff_id != '人员待确认' THEN staff_id END) AS staffCount
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY year, month ORDER BY year, month
        """)
        organizations = rows(f"""
            SELECT org, ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT CASE WHEN staff_id != '人员待确认' THEN staff_id END) AS staffCount,
                   COUNT(DISTINCT product_name) AS productCount
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY org ORDER BY qjPremium DESC, org
        """)
        total_qj = summary["qjPremium"]
        for item in organizations:
            item["share"] = round((item["qjPremium"] or 0) / total_qj, 4) if total_qj else None

        staff = rows(f"""
            SELECT staff_id AS staffId, GROUP_CONCAT(DISTINCT org) AS orgs,
                   ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT product_name) AS productCount,
                   COUNT(DISTINCT printf('%04d-%02d', year, month)) AS activeMonths
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY staff_id ORDER BY qjPremium DESC, staff_id
        """)
        products = rows(f"""
            SELECT product_name AS productName, product_type AS productType,
                   ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT CASE WHEN staff_id != '人员待确认' THEN staff_id END) AS staffCount
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY product_name, product_type ORDER BY qjPremium DESC, productName
        """)
        product_types = rows(f"""
            SELECT product_type AS productType, ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT product_name) AS productCount
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY product_type ORDER BY qjPremium DESC, productType
        """)
        payment_periods = rows(f"""
            SELECT payment_period AS paymentPeriod, ROUND(SUM(qj_premium), 2) AS qjPremium,
                   ROUND(SUM(gm_premium), 2) AS gmPremium,
                   CAST(ROUND(SUM(policy_count)) AS INTEGER) AS policyCount,
                   COUNT(DISTINCT product_name) AS productCount
            FROM agg_zhituo_performance WHERE {where}
            GROUP BY payment_period ORDER BY qjPremium DESC, paymentPeriod
        """)
        last_business_row = conn.execute(
            """SELECT year, month, day FROM agg_zhituo_performance
               ORDER BY year DESC, month DESC, day DESC LIMIT 1"""
        ).fetchone()
        source_cutoff_row = conn.execute(
            """SELECT year, month, day FROM agg_daily_performance
               ORDER BY year DESC, month DESC, day DESC LIMIT 1"""
        ).fetchone()
        last_business_date = (
            f"{int(last_business_row['year']):04d}-{int(last_business_row['month']):02d}-{int(last_business_row['day']):02d}"
            if last_business_row else None
        )
        data_cutoff = (
            f"{int(source_cutoff_row['year']):04d}-{int(source_cutoff_row['month']):02d}-{int(source_cutoff_row['day']):02d}"
            if source_cutoff_row else last_business_date
        )

    return {
        "filters": {
            "availableYears": available_years,
            "availableMonths": available_months,
            "availableOrgs": available_orgs,
            "selectedYears": selected_years,
            "selectedMonths": selected_months,
            "selectedOrgs": selected_orgs,
        },
        "summary": summary,
        "monthly": monthly,
        "organizations": organizations,
        "staff": staff,
        "products": products,
        "productTypes": product_types,
        "paymentPeriods": payment_periods,
        "meta": {
            "dataCutoff": data_cutoff,
            "lastBusinessDate": last_business_date,
            "unit": "万元",
            "sourceFlag": "是否职拓=是",
            "policyCountDefinition": "承保件数净额",
        },
    }
