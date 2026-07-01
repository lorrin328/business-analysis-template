"""Personal monthly honor diamond MVP calculator."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .rules import diamond_delta, diamond_delta_units, is_new_star, membership_level, reward_for_level
from .sources import load_policies, load_staff, metric_for_staff
from .summary import build_org_summary, build_quarter_rewards


def calculate_personal_mvp(batch_id: int, year: int, month: int) -> dict[str, list[dict[str, Any]]]:
    staff_rows, source_staff, current_staff = load_staff(year, month)
    for row in source_staff:
        row["batch_id"] = batch_id
    policy_index, source_policy, policy_exceptions = load_policies(year, month, batch_id, staff_rows=staff_rows)

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
            metric = metric_for_staff(policy_index, y, m, staff_code, business_line, staff.get("role_type"))
            premium = float(metric.get("premium") or 0)
            longterm_count = int(metric.get("policy_count") or 0)
            earned_diamonds = int(metric.get("earned_diamonds") or (1 if metric.get("qualified") else 0))
            qualified = earned_diamonds > 0
            protected = bool(metric.get("protected"))
            employed = bool(staff.get("is_employed_end_month"))
            previous_balance = int(balances[staff_code] or 0)
            balance_before_month[(staff_code, y, m)] = previous_balance
            if business_line not in {"OTO", "证保"}:
                qualified, protected, earned_diamonds = False, False, 0
                flags = ["非星钻MVP计算业务线"]
            else:
                flags = []
            if not employed:
                flags.append("月末非在职，按离职清零")
            delta, balance = diamond_delta_units(
                previous_balance,
                earned_units=earned_diamonds,
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
                totals[staff_code]["qualified"] += earned_diamonds
            if metric.get("personal_qualified"):
                flags.append("个人星钻达标")
            if metric.get("team_qualified"):
                flags.append("团队星钻达标")
            if metric.get("quarter_protected"):
                flags.append("证保季度通算达标")
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

    org_summary = build_org_summary(batch_id, year, month, person_summary, person_month)
    quarter_rewards = build_quarter_rewards(batch_id, year, month, person_summary)
    return {
        "source_staff_month": source_staff,
        "source_policy": source_policy,
        "person_month": person_month,
        "person_summary": person_summary,
        "org_summary": org_summary,
        "quarter_rewards": quarter_rewards,
        "exceptions": exceptions,
    }


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
