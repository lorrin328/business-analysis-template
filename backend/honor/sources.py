"""Source-data loaders for honor alliance calculations."""
from __future__ import annotations

import calendar
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from db.connection import get_db

from .config import MONTHLY_RULES, TEAM_RULES
from .normalizers import (
    normalize_business_line,
    number_value,
    optional_int,
    parse_date,
    role_type,
    staff_code as normalize_staff_code,
    text_value,
    ym_from_value,
)
from .rules import is_longterm_policy, monthly_result, premium_factor


def _as_of_date(year: int, month: int) -> datetime:
    configured = os.getenv("HONOR_AS_OF_DATE")
    if configured:
        parsed = parse_date(configured)
        if parsed:
            return parsed
    last_day = calendar.monthrange(int(year), int(month))[1]
    return datetime(int(year), int(month), last_day) + timedelta(days=45)


def load_staff(year: int, month: int) -> tuple[
    dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]],
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    staff_rows: dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    source_rows: list[dict[str, Any]] = []
    with get_db() as conn:
        latest = conn.execute(
            """
            SELECT CAST("统计年" AS INTEGER) AS year, CAST("统计月" AS INTEGER) AS month
            FROM hr_data
            WHERE CAST("统计年" AS INTEGER) = ?
            ORDER BY CAST("统计年" AS INTEGER) DESC, CAST("统计月" AS INTEGER) DESC
            LIMIT 1
            """,
            (year,),
        ).fetchone()
        latest_month = int(latest["month"] if latest and latest["month"] else month)
        status_month = min(int(month), latest_month)
        load_until = int(month)
        rows = conn.execute(
            """
            SELECT "统计年", "统计月", "销售机构名称", "业务模式名称", "人员代码", "人员姓名",
                   "职等", "职级", "入职年", "入职月", "月末在职人力", "营业组CODE", "营业部CODE"
            FROM hr_data
            WHERE CAST("统计年" AS INTEGER) = ? AND CAST("统计月" AS INTEGER) <= ?
            """,
            (year, load_until),
        ).fetchall()
    current_staff: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        y = optional_int(row["统计年"])
        m = optional_int(row["统计月"])
        staff_code = normalize_staff_code(row["人员代码"])
        if not y or not m or not staff_code:
            continue
        business_line = normalize_business_line(row["业务模式名称"])
        if business_line not in {"OTO", "证保"}:
            continue
        item = {
            "org": text_value(row["销售机构名称"]),
            "business_line": business_line,
            "staff_code": staff_code,
            "staff_name": text_value(row["人员姓名"]),
            "rank_name": text_value(row["职等"] or row["职级"]),
            "role_type": role_type(row["职等"] or row["职级"]),
            "entry_year": optional_int(row["入职年"]),
            "entry_month": optional_int(row["入职月"]),
            "is_employed_end_month": 1 if number_value(row["月末在职人力"]) > 0 else 0,
            "group_code": text_value(row["营业组CODE"]),
            "department_code": text_value(row["营业部CODE"]),
            "raw_payload": json.dumps(dict(row), ensure_ascii=False, default=str),
        }
        if m <= month:
            staff_rows[(y, m)][(staff_code, business_line)] = item
            source_rows.append({"batch_id": 0, "year": y, "month": m, **item})
        if m == status_month:
            current_staff[(staff_code, business_line)] = item
    return staff_rows, source_rows, current_staff


def metric_for_staff(
    policy_index: dict[str, dict[Any, dict[str, Any]]],
    year: int,
    month: int,
    staff_code: str,
    business_line: str,
    role_type: str | None,
) -> dict[str, Any]:
    empty = {"premium": 0.0, "policy_count": 0, "qualified": False, "protected": False}
    personal = policy_index["personal"].get(
        (year, month, staff_code, business_line),
        empty,
    )
    if role_type == "主管":
        team = policy_index["supervisor"].get(
            (year, month, staff_code, business_line),
            empty,
        )
    elif role_type == "经理":
        team = policy_index["manager"].get(
            (year, month, staff_code, business_line),
            empty,
        )
    else:
        team = empty
    team_qualified = bool(team.get("qualified"))
    personal_qualified = bool(personal.get("qualified"))
    return {
        "premium": float(personal.get("premium") or 0) + (float(team.get("premium") or 0) if team_qualified else 0),
        "policy_count": int(personal.get("policy_count") or 0) + (int(team.get("policy_count") or 0) if team_qualified else 0),
        "qualified": personal_qualified or team_qualified,
        "protected": bool(personal.get("protected")) and not team_qualified,
        "personal_qualified": personal_qualified,
        "team_qualified": team_qualified,
        "earned_diamonds": (1 if personal_qualified else 0) + (1 if team_qualified else 0),
        "personal_premium": float(personal.get("premium") or 0),
        "team_premium": float(team.get("premium") or 0),
        "personal_policy_count": int(personal.get("policy_count") or 0),
        "team_star_count": int(team.get("policy_count") or 0),
        "quarter_protected": bool(personal.get("quarter_protected")),
    }


def load_policies(
    year: int,
    month: int,
    batch_id: int,
    *,
    staff_rows: dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]] | None = None,
) -> tuple[dict[str, dict[Any, dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    personal_agg: dict[tuple[int, int, str, str], dict[str, float]] = defaultdict(lambda: {"premium": 0.0, "policy_count": 0.0})
    supervisor_premium: dict[tuple[int, int, str, str], float] = defaultdict(float)
    manager_premium: dict[tuple[int, int, str, str], float] = defaultdict(float)
    supervisor_by_person: dict[tuple[int, int, str, str], str] = {}
    manager_by_person: dict[tuple[int, int, str, str], str] = {}
    source_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    as_of = _as_of_date(year, month)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT "年月", "销售机构名称", "业务模式", "人员工号",
                   "主管工号" AS supervisor_code, "经理工号" AS manager_code,
                   "投保单号", "承保时间", "回销时间", "入账时间", "长短险", "缴费年限", "折算保费",
                   "年化规保", "期交保费", "承保件数" AS policy_count, "产品代码", "产品名称"
            FROM performance
            """,
        ).fetchall()
    for row in rows:
        issue_dt = parse_date(row["承保时间"])
        account_dt = parse_date(row["入账时间"])
        y, m = (issue_dt.year, issue_dt.month) if issue_dt else ((account_dt.year, account_dt.month) if account_dt else ym_from_value(row["年月"]))
        if y != year or not m or m > month:
            continue
        fallback_date = not issue_dt and not account_dt
        staff_code = normalize_staff_code(row["人员工号"])
        supervisor_code = normalize_staff_code(row["supervisor_code"])
        manager_code = normalize_staff_code(row["manager_code"])
        business_line = normalize_business_line(row["业务模式"])
        if business_line not in {"OTO", "证保"}:
            continue
        policy_no = text_value(row["投保单号"])
        source_standard_premium = number_value(row["折算保费"])
        qj_premium = number_value(row["期交保费"])
        annualized_premium = number_value(row["年化规保"])
        raw_policy_count = int(number_value(row["policy_count"]) or 1)
        payment_years = number_value(row["缴费年限"])
        longterm = is_longterm_policy(row["长短险"], payment_years)
        factor = premium_factor(payment_years, row["长短险"])
        calculated_standard_premium = annualized_premium * factor if annualized_premium else 0.0
        if calculated_standard_premium > 0:
            standard_premium = calculated_standard_premium
            premium_source = "calculated_by_payment_years"
        elif not longterm:
            standard_premium = 0.0
            premium_source = "excluded_short_term"
        else:
            standard_premium = source_standard_premium
            premium_source = "source_zs_premium" if source_standard_premium > 0 else "missing_or_zero"
        policy_count = raw_policy_count if longterm else 0
        callback_dt = parse_date(row["回销时间"])
        valid_policy = True
        if standard_premium > 0 and issue_dt:
            deadline = issue_dt + timedelta(days=45)
            if callback_dt:
                valid_policy = 0 <= (callback_dt - issue_dt).days <= 45
            elif as_of > deadline:
                valid_policy = False
            if not valid_policy:
                exceptions.append(
                    _exception(
                        batch_id,
                        "warning",
                        "callback_overdue_or_missing",
                        text_value(row["销售机构名称"]),
                        staff_code,
                        policy_no,
                        "承保满45个自然日后未回销成功，保费不计入星钻统计。",
                    )
                )
        if standard_premium < 0:
            valid_policy = False
            exceptions.append(_exception(batch_id, "warning", "negative_premium", text_value(row["销售机构名称"]), staff_code, policy_no, "发现负数折算保费或退保冲减，保费不计入星钻统计。"))
        if fallback_date:
            exceptions.append(_exception(batch_id, "info", "date_fallback", text_value(row["销售机构名称"]), staff_code, policy_no, "业绩归属使用年月字段降级口径。"))
        if not staff_code:
            exceptions.append(_exception(batch_id, "warning", "missing_staff_code", text_value(row["销售机构名称"]), None, policy_no, "业绩明细缺人员工号，未纳入个人星钻计算。"))
            continue
        counted_standard_premium = standard_premium if valid_policy else 0.0
        counted_qj_premium = qj_premium if valid_policy else 0.0
        counted_annualized_premium = annualized_premium if valid_policy else 0.0
        if valid_policy:
            key = (int(y), int(m), staff_code, business_line)
            personal_agg[key]["premium"] += standard_premium
            personal_agg[key]["policy_count"] += policy_count
            supervisor_by_person[key] = supervisor_code
            manager_by_person[key] = manager_code
            if supervisor_code:
                supervisor_premium[(int(y), int(m), supervisor_code, business_line)] += standard_premium
            if manager_code:
                manager_premium[(int(y), int(m), manager_code, business_line)] += standard_premium
        source_rows.append(
            {
                "batch_id": batch_id,
                "year": int(y),
                "month": int(m),
                "org": text_value(row["销售机构名称"]),
                "business_line": business_line,
                "staff_code": staff_code,
                "policy_no": policy_no,
                "is_longterm": int(policy_count) if valid_policy else 0,
                "payment_years": payment_years,
                "standard_premium": round(counted_standard_premium, 2),
                "annualized_premium": round(counted_annualized_premium, 2),
                "qj_premium": round(counted_qj_premium, 2),
                "premium_source": premium_source,
                "issue_date": str(row["承保时间"] or ""),
                "callback_date": str(row["回销时间"] or ""),
                "account_date": str(row["入账时间"] or ""),
                "raw_payload": json.dumps(dict(row), ensure_ascii=False, default=str),
            }
        )
    personal_metrics: dict[tuple[int, int, str, str], dict[str, Any]] = {}
    personal_qualified_by_key: dict[tuple[int, int, str, str], bool] = {}
    for key, values in personal_agg.items():
        y, m, staff_code, business_line = key
        premium = float(values["premium"] or 0)
        count = int(values["policy_count"] or 0)
        qualified, protected = monthly_result(business_line, premium, count)
        personal_metrics[key] = {
            "premium": premium,
            "policy_count": count,
            "qualified": qualified,
            "protected": protected,
            "quarter_protected": False,
        }

    if staff_rows:
        _apply_zhengbao_quarter_rollup(personal_metrics, staff_rows, month)

    personal_qualified_by_key = {key: bool(metric.get("qualified")) for key, metric in personal_metrics.items()}

    supervisor_star_count: dict[tuple[int, int, str, str], int] = defaultdict(int)
    manager_star_count: dict[tuple[int, int, str, str], int] = defaultdict(int)
    for key, qualified in personal_qualified_by_key.items():
        if not qualified:
            continue
        y, m, _person_code, business_line = key
        supervisor_code = supervisor_by_person.get(key)
        manager_code = manager_by_person.get(key)
        if supervisor_code:
            supervisor_star_count[(y, m, supervisor_code, business_line)] += 1
        if manager_code:
            manager_star_count[(y, m, manager_code, business_line)] += 1

    supervisor_metrics: dict[tuple[int, int, str, str], dict[str, Any]] = {}
    for key, premium in supervisor_premium.items():
        star_count = int(supervisor_star_count.get(key) or 0)
        _y, _m, _code, business_line = key
        rule = TEAM_RULES.get((business_line, "主管")) or {}
        supervisor_metrics[key] = {
            "premium": float(premium or 0),
            "policy_count": star_count,
            "qualified": bool(rule) and float(premium or 0) >= float(rule.get("premium_threshold") or 0) and star_count >= int(rule.get("star_count_threshold") or 0),
            "protected": False,
        }

    manager_metrics: dict[tuple[int, int, str, str], dict[str, Any]] = {}
    for key, premium in manager_premium.items():
        star_count = int(manager_star_count.get(key) or 0)
        _y, _m, _code, business_line = key
        rule = TEAM_RULES.get((business_line, "经理")) or {}
        manager_metrics[key] = {
            "premium": float(premium or 0),
            "policy_count": star_count,
            "qualified": bool(rule) and float(premium or 0) >= float(rule.get("premium_threshold") or 0) and star_count >= int(rule.get("star_count_threshold") or 0),
            "protected": False,
        }

    return {"personal": personal_metrics, "supervisor": supervisor_metrics, "manager": manager_metrics}, source_rows, exceptions


def _apply_zhengbao_quarter_rollup(
    personal_metrics: dict[tuple[int, int, str, str], dict[str, Any]],
    staff_rows: dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]],
    target_month: int,
) -> None:
    grouped: dict[tuple[int, int, str, str], list[int]] = {}
    for (year, month), rows in staff_rows.items():
        if int(month) > int(target_month):
            continue
        quarter = ((int(month) - 1) // 3) + 1
        for (staff_code, business_line), staff in rows.items():
            if business_line != "证保" or not int(staff.get("is_employed_end_month") or 0):
                continue
            grouped.setdefault((int(year), quarter, staff_code, business_line), []).append(int(month))

    threshold = float(MONTHLY_RULES["证保"]["premium_threshold"])
    for (year, quarter, staff_code, business_line), months in grouped.items():
        quarter_end = quarter * 3
        if int(target_month) < quarter_end:
            continue
        in_service_months = sorted(set(months))
        if not in_service_months:
            continue
        metrics = [
            personal_metrics.get((year, month, staff_code, business_line), {"premium": 0.0, "policy_count": 0})
            for month in in_service_months
        ]
        if not all(int(metric.get("policy_count") or 0) > 0 for metric in metrics):
            continue
        quarter_premium = sum(float(metric.get("premium") or 0) for metric in metrics)
        if quarter_premium / len(in_service_months) < threshold:
            continue
        for month in in_service_months:
            metric = personal_metrics.setdefault(
                (year, month, staff_code, business_line),
                {"premium": 0.0, "policy_count": 0, "qualified": False, "protected": False},
            )
            metric["qualified"] = True
            metric["protected"] = False
            metric["quarter_protected"] = True


def _exception(batch_id: int, severity: str, exception_type: str, org: str | None, staff_code: str | None, policy_no: str | None, message: str) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "severity": severity,
        "exception_type": exception_type,
        "org": org,
        "staff_code": staff_code,
        "policy_no": policy_no,
        "message": message,
        "suggested_action": "复核源表字段和星钻规则口径",
    }
