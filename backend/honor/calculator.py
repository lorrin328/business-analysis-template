"""Personal monthly honor diamond MVP calculator."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from db.connection import get_db

from .config import MONTHLY_RULES, RULE_VERSION, SENIOR_PLUS_LEVELS
from .rules import diamond_delta, is_new_star, membership_level, monthly_result, reward_for_level


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _staff_code(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    if text.isdigit():
        return text.zfill(8)
    return text


def _num(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _ym_from_value(value: Any) -> tuple[int | None, int | None]:
    dt = _parse_date(value)
    if dt:
        return dt.year, dt.month
    text = str(value or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return int(digits[:4]), int(digits[4:6])
    return None, None


def _as_of_date() -> datetime:
    configured = os.getenv("HONOR_AS_OF_DATE")
    if configured:
        parsed = _parse_date(configured)
        if parsed:
            return parsed
    return datetime.now()


def normalize_business_line(value: Any) -> str:
    text = _text(value)
    if text in {"证券", "证保"}:
        return "证保"
    if text in {"网服", "蚁桥"}:
        return "蚁桥"
    return text


def calculate_personal_mvp(batch_id: int, year: int, month: int) -> dict[str, list[dict[str, Any]]]:
    staff_rows, source_staff, current_staff = _load_staff(year, month)
    for row in source_staff:
        row["batch_id"] = batch_id
    policy_index, source_policy, policy_exceptions = _load_policies(year, month, batch_id)

    person_month: list[dict[str, Any]] = []
    person_summary: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = policy_exceptions
    balances: dict[str, int] = defaultdict(int)
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"gain": 0, "deduct": 0, "qualified": 0})
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    latest_by_staff: dict[str, dict[str, Any]] = {}
    balance_before_month: dict[tuple[str, int, int], int] = {}
    person_month_index: dict[tuple[str, str, int, int], dict[str, Any]] = {}

    for ym in sorted(staff_rows):
        y, m = ym
        for key, staff in sorted(staff_rows[ym].items()):
            staff_code, business_line = key
            metric = _metric_for_staff(policy_index, y, m, staff_code, business_line, staff.get("role_type"))
            premium = float(metric.get("premium") or 0)
            longterm_count = int(metric.get("policy_count") or 0)
            qualified = bool(metric.get("qualified"))
            protected = bool(metric.get("protected"))
            employed = bool(staff.get("is_employed_end_month"))
            previous_balance = int(balances[staff_code] or 0)
            balance_before_month[(staff_code, y, m)] = previous_balance
            if business_line not in {"OTO", "证保"}:
                qualified, protected = False, False
                flags = ["非星钻MVP计算业务线"]
            else:
                flags = []
            if not employed:
                flags.append("月末非在职，按离职清零")
            delta, balance = diamond_delta(
                previous_balance,
                qualified=qualified,
                protected_month=protected,
                employed=employed,
            )
            balances[staff_code] = balance
            level = membership_level(balance, employed=employed)
            new_star = is_new_star(staff.get("entry_year"), staff.get("entry_month"), y, m, balance)
            if delta > 0:
                totals[staff_code]["gain"] += delta
            elif delta < 0:
                totals[staff_code]["deduct"] += abs(delta)
            if qualified:
                totals[staff_code]["qualified"] += 1
            row = {
                "batch_id": batch_id,
                "year": y,
                "month": m,
                "org": staff.get("org"),
                "business_line": business_line,
                "staff_code": staff_code,
                "staff_name": staff.get("staff_name"),
                "role_type": staff.get("role_type"),
                "is_employed_end_month": 1 if employed else 0,
                "standard_premium": round(premium, 2),
                "longterm_policy_count": int(longterm_count),
                "monthly_qualified": 1 if qualified else 0,
                "protected_month": 1 if protected else 0,
                "diamond_delta": int(delta),
                "diamond_balance": int(balance),
                "membership_level": level,
                "is_new_star": 1 if new_star else 0,
                "exception_flags": json.dumps(flags, ensure_ascii=False),
            }
            person_month.append(row)
            person_month_index[(staff_code, business_line, y, m)] = row
            latest[(staff_code, business_line)] = {**row, **staff}
            latest_by_staff[staff_code] = {**row, **staff}

    current_staff_by_code: dict[str, dict[str, Any]] = {}
    for (staff_code, _business_line), staff in current_staff.items():
        if staff_code not in current_staff_by_code or int(staff.get("is_employed_end_month") or 0) > 0:
            current_staff_by_code[staff_code] = staff
    current_month_codes = set(current_staff_by_code.keys())
    for staff_code, row in list(latest_by_staff.items()):
        current_status = current_staff_by_code.get(staff_code)
        if current_status and int(current_status.get("is_employed_end_month") or 0) > 0:
            continue
        business_line = row.get("business_line")
        previous_balance = int(balance_before_month.get((staff_code, year, month), balances[staff_code]) or 0)
        delta, balance = diamond_delta(
            previous_balance,
            qualified=False,
            protected_month=False,
            employed=False,
        )
        balances[staff_code] = balance
        if delta < 0:
            totals[staff_code]["deduct"] += abs(delta)
        flags = ["最新人力清单不存在，按离职清零"] if staff_code not in current_month_codes else ["最新人力清单显示非在职，按离职清零"]
        existing = person_month_index.get((staff_code, business_line, year, month))
        departure_row = {
            "batch_id": batch_id,
            "year": year,
            "month": month,
            "org": row.get("org"),
            "business_line": business_line,
            "staff_code": staff_code,
            "staff_name": row.get("staff_name"),
            "role_type": row.get("role_type"),
            "is_employed_end_month": 0,
            "standard_premium": round(float((existing or {}).get("standard_premium") or 0), 2),
            "longterm_policy_count": int((existing or {}).get("longterm_policy_count") or 0),
            "monthly_qualified": 0,
            "protected_month": 0,
            "diamond_delta": int(delta),
            "diamond_balance": int(balance),
            "membership_level": membership_level(balance, employed=False),
            "is_new_star": 0,
            "exception_flags": json.dumps(flags, ensure_ascii=False),
        }
        if existing:
            existing.update(departure_row)
        else:
            person_month.append(departure_row)
            person_month_index[(staff_code, business_line, year, month)] = departure_row
        latest_by_staff[staff_code] = {**row, **departure_row}

    for staff_code, row in latest_by_staff.items():
        business_line = row.get("business_line")
        warning_tags = _json_list(row.get("exception_flags"))
        if business_line == "蚁桥":
            warning_tags.append("蚁桥/网服不涉及星钻")
        reward_amount, reward_label = reward_for_level(row["membership_level"])
        person_summary.append(
            {
                "batch_id": batch_id,
                "year": year,
                "latest_month": int(month),
                "org": row.get("org"),
                "business_line": business_line,
                "staff_code": staff_code,
                "staff_name": row.get("staff_name"),
                "role_type": row.get("role_type"),
                "diamond_balance": int(row["diamond_balance"]),
                "membership_level": row["membership_level"],
                "total_gain": int(totals[staff_code]["gain"]),
                "total_deduct": int(totals[staff_code]["deduct"]),
                "qualified_months": int(totals[staff_code]["qualified"]),
                "is_new_star": int(row["is_new_star"]),
                "warning_tags": json.dumps(warning_tags, ensure_ascii=False),
            }
        )

    org_summary = _build_org_summary(batch_id, year, month, person_summary, person_month)
    quarter_rewards = _build_rewards(batch_id, year, month, person_summary)
    return {
        "source_staff_month": source_staff,
        "source_policy": source_policy,
        "person_month": person_month,
        "person_summary": person_summary,
        "org_summary": org_summary,
        "quarter_rewards": quarter_rewards,
        "exceptions": exceptions,
    }


def _load_staff(year: int, month: int) -> tuple[
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
        status_month = int(latest["month"] if latest and latest["month"] else month)
        load_until = max(int(month), status_month)
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
        y = _int(row["统计年"])
        m = _int(row["统计月"])
        staff_code = _staff_code(row["人员代码"])
        if not y or not m or not staff_code:
            continue
        business_line = normalize_business_line(row["业务模式名称"])
        if business_line not in {"OTO", "证保"}:
            continue
        item = {
            "org": _text(row["销售机构名称"]),
            "business_line": business_line,
            "staff_code": staff_code,
            "staff_name": _text(row["人员姓名"]),
            "rank_name": _text(row["职等"] or row["职级"]),
            "role_type": _role_type(row["职等"] or row["职级"]),
            "entry_year": _int(row["入职年"]),
            "entry_month": _int(row["入职月"]),
            "is_employed_end_month": 1 if _num(row["月末在职人力"]) > 0 else 0,
            "group_code": _text(row["营业组CODE"]),
            "department_code": _text(row["营业部CODE"]),
            "raw_payload": json.dumps(dict(row), ensure_ascii=False, default=str),
        }
        if m <= month:
            staff_rows[(y, m)][(staff_code, business_line)] = item
            source_rows.append({"batch_id": 0, "year": y, "month": m, **item})
        if m == status_month:
            current_staff[(staff_code, business_line)] = item
    return staff_rows, source_rows, current_staff


def _json_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _metric_for_staff(policy_index: dict[str, dict[Any, dict[str, Any]]], year: int, month: int, staff_code: str, business_line: str, role_type: str | None) -> dict[str, Any]:
    personal = policy_index["personal"].get((year, month, staff_code, business_line), {"premium": 0.0, "policy_count": 0, "qualified": False, "protected": False})
    if role_type == "主管":
        team = policy_index["supervisor"].get((year, month, staff_code), {"premium": 0.0, "policy_count": 0, "qualified": False, "protected": False})
        return team if team.get("qualified") else personal
    if role_type == "经理":
        team = policy_index["manager"].get((year, month, staff_code), {"premium": 0.0, "policy_count": 0, "qualified": False, "protected": False})
        return team if team.get("qualified") else personal
    return personal


def _load_policies(year: int, month: int, batch_id: int) -> tuple[dict[str, dict[Any, dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    personal_agg: dict[tuple[int, int, str, str], dict[str, float]] = defaultdict(lambda: {"premium": 0.0, "policy_count": 0.0})
    supervisor_premium: dict[tuple[int, int, str], float] = defaultdict(float)
    manager_premium: dict[tuple[int, int, str], float] = defaultdict(float)
    supervisor_by_person: dict[tuple[int, int, str, str], str] = {}
    manager_by_person: dict[tuple[int, int, str, str], str] = {}
    source_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    as_of = _as_of_date()
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
        issue_dt = _parse_date(row["承保时间"])
        account_dt = _parse_date(row["入账时间"])
        y, m = (issue_dt.year, issue_dt.month) if issue_dt else ((account_dt.year, account_dt.month) if account_dt else _ym_from_value(row["年月"]))
        if y != year or not m or m > month:
            continue
        fallback_date = not issue_dt and not account_dt
        staff_code = _staff_code(row["人员工号"])
        supervisor_code = _staff_code(row["supervisor_code"])
        manager_code = _staff_code(row["manager_code"])
        business_line = normalize_business_line(row["业务模式"])
        if business_line not in {"OTO", "证保"}:
            continue
        policy_no = _text(row["投保单号"])
        standard_premium = _num(row["折算保费"])
        qj_premium = _num(row["期交保费"])
        annualized_premium = _num(row["年化规保"])
        policy_count = _num(row["policy_count"]) or 1
        is_longterm = policy_count > 0
        callback_dt = _parse_date(row["回销时间"])
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
                        _text(row["销售机构名称"]),
                        staff_code,
                        policy_no,
                        "承保满45个自然日后未回销成功，保费不计入星钻统计。",
                    )
                )
        if standard_premium < 0:
            valid_policy = False
            exceptions.append(_exception(batch_id, "warning", "negative_premium", _text(row["销售机构名称"]), staff_code, policy_no, "发现负数折算保费或退保冲减，保费不计入星钻统计。"))
        if fallback_date:
            exceptions.append(_exception(batch_id, "info", "date_fallback", _text(row["销售机构名称"]), staff_code, policy_no, "业绩归属使用年月字段降级口径。"))
        if not staff_code:
            exceptions.append(_exception(batch_id, "warning", "missing_staff_code", _text(row["销售机构名称"]), None, policy_no, "业绩明细缺人员工号，未纳入个人星钻计算。"))
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
                supervisor_premium[(int(y), int(m), supervisor_code)] += standard_premium
            if manager_code:
                manager_premium[(int(y), int(m), manager_code)] += standard_premium
        source_rows.append(
            {
                "batch_id": batch_id,
                "year": int(y),
                "month": int(m),
                "org": _text(row["销售机构名称"]),
                "business_line": business_line,
                "staff_code": staff_code,
                "policy_no": policy_no,
                "is_longterm": int(policy_count) if valid_policy else 0,
                "payment_years": _num(row["缴费年限"]),
                "standard_premium": round(counted_standard_premium, 2),
                "annualized_premium": round(counted_annualized_premium, 2),
                "qj_premium": round(counted_qj_premium, 2),
                "premium_source": "source_zs_premium",
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
        quarter_protected = False
        qualified, protected = monthly_result(business_line, premium, count)
        if business_line == "证保":
            quarter = ((m - 1) // 3) + 1
            months = list(range((quarter - 1) * 3 + 1, quarter * 3 + 1))
            quarter_premium = sum(float(personal_agg.get((y, qm, staff_code, business_line), {}).get("premium") or 0) for qm in months)
            every_month_has_policy = all(float(personal_agg.get((y, qm, staff_code, business_line), {}).get("policy_count") or 0) > 0 for qm in months)
            quarter_protected = every_month_has_policy and quarter_premium >= float(MONTHLY_RULES["证保"]["premium_threshold"] * 3)
            if quarter_protected:
                qualified, protected = True, False
        personal_metrics[key] = {
            "premium": premium,
            "policy_count": count,
            "qualified": qualified,
            "protected": protected,
            "quarter_protected": quarter_protected,
        }
        personal_qualified_by_key[key] = bool(qualified)

    supervisor_star_count: dict[tuple[int, int, str], int] = defaultdict(int)
    manager_star_count: dict[tuple[int, int, str], int] = defaultdict(int)
    for key, qualified in personal_qualified_by_key.items():
        if not qualified:
            continue
        y, m, person_code, _business_line = key
        supervisor_code = supervisor_by_person.get(key)
        manager_code = manager_by_person.get(key)
        if supervisor_code:
            supervisor_star_count[(y, m, supervisor_code)] += 1
        if manager_code:
            manager_star_count[(y, m, manager_code)] += 1

    supervisor_metrics: dict[tuple[int, int, str], dict[str, Any]] = {}
    for key, premium in supervisor_premium.items():
        star_count = int(supervisor_star_count.get(key) or 0)
        supervisor_metrics[key] = {
            "premium": float(premium or 0),
            "policy_count": star_count,
            "qualified": float(premium or 0) >= 100_000 and star_count >= 4,
            "protected": False,
        }

    manager_metrics: dict[tuple[int, int, str], dict[str, Any]] = {}
    for key, premium in manager_premium.items():
        star_count = int(manager_star_count.get(key) or 0)
        manager_metrics[key] = {
            "premium": float(premium or 0),
            "policy_count": star_count,
            "qualified": float(premium or 0) >= 320_000 and star_count >= 12,
            "protected": False,
        }

    return {"personal": personal_metrics, "supervisor": supervisor_metrics, "manager": manager_metrics}, source_rows, exceptions


def _build_org_summary(batch_id: int, year: int, month: int, summaries: list[dict[str, Any]], months: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_month = [row for row in months if row["year"] == year and row["month"] == month]
    current_index = {(row["staff_code"], row["business_line"]): row for row in current_month}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in summaries:
        key = (row.get("org") or "未归属", row.get("business_line") or "")
        item = grouped.setdefault(
            key,
            {
                "batch_id": batch_id,
                "year": year,
                "month": month,
                "org": key[0],
                "business_line": key[1],
                "tracked_headcount": 0,
                "member_count": 0,
                "senior_plus_count": 0,
                "monthly_gain_count": 0,
                "monthly_deduct_count": 0,
                "total_diamond": 0,
                "member_rate": 0,
                "avg_diamond": 0,
                "estimated_reward": 0,
            },
        )
        current = current_index.get((row["staff_code"], row["business_line"]))
        current_employed = bool(current and int(current.get("is_employed_end_month") or 0) > 0)
        item["tracked_headcount"] += 1 if current_employed else 0
        item["member_count"] += 1 if current_employed and row["membership_level"] != "未入会" else 0
        item["senior_plus_count"] += 1 if current_employed and row["membership_level"] in SENIOR_PLUS_LEVELS else 0
        item["total_diamond"] += int(row["diamond_balance"] or 0)
        if current:
            item["monthly_gain_count"] += 1 if int(current["diamond_delta"] or 0) > 0 else 0
            item["monthly_deduct_count"] += 1 if int(current["diamond_delta"] or 0) < 0 else 0
        reward, _ = reward_for_level(row["membership_level"])
        item["estimated_reward"] += reward if current_employed else 0
    for item in grouped.values():
        tracked = int(item["tracked_headcount"] or 0)
        item["member_rate"] = item["member_count"] / tracked if tracked else 0
        item["avg_diamond"] = item["total_diamond"] / tracked if tracked else 0
    return list(grouped.values())


def _build_rewards(batch_id: int, year: int, month: int, summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    quarter = ((month - 1) // 3) + 1
    rows = []
    for row in summaries:
        amount, label = reward_for_level(row["membership_level"])
        rows.append(
            {
                "batch_id": batch_id,
                "year": year,
                "quarter": quarter,
                "org": row.get("org") or "未归属",
                "staff_code": row["staff_code"],
                "staff_name": row.get("staff_name"),
                "membership_level": row["membership_level"],
                "reward_amount": amount,
                "reward_label": label,
                "is_estimated": 1,
            }
        )
    return rows


def _role_type(rank_name: Any) -> str:
    text = _text(rank_name)
    if "创新经理" in text:
        return "经理"
    if "创新主管" in text or "主管" in text or "服务经理" in text:
        return "主管"
    return "个人"


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
