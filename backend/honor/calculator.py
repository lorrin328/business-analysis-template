"""Personal monthly honor diamond MVP calculator."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from db.connection import get_db

from .config import RULE_VERSION, SENIOR_PLUS_LEVELS
from .rules import diamond_delta, is_new_star, membership_level, monthly_result, reward_for_level


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
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


def normalize_business_line(value: Any) -> str:
    text = _text(value)
    if text in {"证券", "证保"}:
        return "证保"
    if text in {"网服", "蚁桥"}:
        return "蚁桥"
    return text


def calculate_personal_mvp(batch_id: int, year: int, month: int) -> dict[str, list[dict[str, Any]]]:
    staff_rows, source_staff = _load_staff(year, month)
    for row in source_staff:
        row["batch_id"] = batch_id
    policy_index, source_policy, policy_exceptions = _load_policies(year, month, batch_id)

    person_month: list[dict[str, Any]] = []
    person_summary: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = policy_exceptions
    balances: dict[tuple[str, str], int] = defaultdict(int)
    totals: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"gain": 0, "deduct": 0, "qualified": 0})
    latest: dict[tuple[str, str], dict[str, Any]] = {}

    for ym in sorted(staff_rows):
        y, m = ym
        for key, staff in sorted(staff_rows[ym].items()):
            staff_code, business_line = key
            premium, longterm_count = policy_index.get((y, m, staff_code, business_line), (0.0, 0))
            employed = bool(staff.get("is_employed_end_month"))
            if business_line not in {"OTO", "证保"}:
                qualified, protected = False, False
                flags = ["非星钻MVP计算业务线"]
            else:
                qualified, protected = monthly_result(business_line, premium, longterm_count)
                flags = []
            if not employed:
                flags.append("月末非在职，按离职清零")
            delta, balance = diamond_delta(
                balances[(staff_code, business_line)],
                qualified=qualified,
                protected_month=protected,
                employed=employed,
            )
            balances[(staff_code, business_line)] = balance
            level = membership_level(balance, employed=employed)
            new_star = is_new_star(staff.get("entry_year"), staff.get("entry_month"), y, m, balance)
            if delta > 0:
                totals[(staff_code, business_line)]["gain"] += delta
            elif delta < 0:
                totals[(staff_code, business_line)]["deduct"] += abs(delta)
            if qualified:
                totals[(staff_code, business_line)]["qualified"] += 1
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
            latest[(staff_code, business_line)] = {**row, **staff}

    current_month_keys = set(staff_rows.get((year, month), {}).keys())
    for key, row in list(latest.items()):
        if key in current_month_keys:
            continue
        staff_code, business_line = key
        previous_balance = int(balances[key] or 0)
        delta, balance = diamond_delta(
            previous_balance,
            qualified=False,
            protected_month=False,
            employed=False,
        )
        balances[key] = balance
        if delta < 0:
            totals[key]["deduct"] += abs(delta)
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
            "standard_premium": 0,
            "longterm_policy_count": 0,
            "monthly_qualified": 0,
            "protected_month": 0,
            "diamond_delta": int(delta),
            "diamond_balance": int(balance),
            "membership_level": membership_level(balance, employed=False),
            "is_new_star": 0,
            "exception_flags": json.dumps(["当月人力基表不存在，按离职清零"], ensure_ascii=False),
        }
        person_month.append(departure_row)
        latest[key] = {**row, **departure_row}

    for key, row in latest.items():
        staff_code, business_line = key
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
                "total_gain": int(totals[key]["gain"]),
                "total_deduct": int(totals[key]["deduct"]),
                "qualified_months": int(totals[key]["qualified"]),
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


def _load_staff(year: int, month: int) -> tuple[dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]], list[dict[str, Any]]]:
    staff_rows: dict[tuple[int, int], dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    source_rows: list[dict[str, Any]] = []
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT "统计年", "统计月", "销售机构名称", "业务模式名称", "人员代码", "人员姓名",
                   "职等", "职级", "入职年", "入职月", "月末在职人力", "营业组CODE", "营业部CODE"
            FROM hr_data
            WHERE CAST("统计年" AS INTEGER) = ? AND CAST("统计月" AS INTEGER) <= ?
            """,
            (year, month),
        ).fetchall()
    for row in rows:
        y = _int(row["统计年"])
        m = _int(row["统计月"])
        staff_code = _text(row["人员代码"])
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
        staff_rows[(y, m)][(staff_code, business_line)] = item
        source_rows.append({"batch_id": 0, "year": y, "month": m, **item})
    return staff_rows, source_rows


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


def _load_policies(year: int, month: int, batch_id: int) -> tuple[dict[tuple[int, int, str, str], tuple[float, int]], list[dict[str, Any]], list[dict[str, Any]]]:
    agg: dict[tuple[int, int, str, str], list[float]] = defaultdict(lambda: [0.0, 0])
    source_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT "年月", "销售机构名称", "业务模式", "人员工号", "投保单号", "承保时间",
                   "回销时间", "入账时间", "长短险", "缴费年限", "折算保费",
                   "年化规保", "期交保费", "产品代码", "产品名称"
            FROM performance
            WHERE CAST(substr("年月", 1, 4) AS INTEGER) = ?
            """,
            (year,),
        ).fetchall()
    for row in rows:
        issue_dt = _parse_date(row["承保时间"])
        account_dt = _parse_date(row["入账时间"])
        y, m = (issue_dt.year, issue_dt.month) if issue_dt else ((account_dt.year, account_dt.month) if account_dt else _ym_from_value(row["年月"]))
        if y != year or not m or m > month:
            continue
        fallback_date = not issue_dt and not account_dt
        staff_code = _text(row["人员工号"])
        business_line = normalize_business_line(row["业务模式"])
        if business_line not in {"OTO", "证保"}:
            continue
        policy_no = _text(row["投保单号"])
        standard_premium = _num(row["折算保费"])
        qj_premium = _num(row["期交保费"])
        annualized_premium = _num(row["年化规保"])
        is_longterm = _text(row["长短险"]) == "一年期以上"
        callback_dt = _parse_date(row["回销时间"])
        valid_callback = True
        if is_longterm and issue_dt and callback_dt and standard_premium > 0:
            valid_callback = (callback_dt - issue_dt).days <= 30
        if standard_premium < 0:
            exceptions.append(_exception(batch_id, "warning", "negative_premium", _text(row["销售机构名称"]), staff_code, policy_no, "发现负数折算保费，MVP按原值计入并标记，后续需按正负冲减规则复核。"))
        if fallback_date:
            exceptions.append(_exception(batch_id, "info", "date_fallback", _text(row["销售机构名称"]), staff_code, policy_no, "业绩归属使用年月字段降级口径。"))
        if not staff_code:
            exceptions.append(_exception(batch_id, "warning", "missing_staff_code", _text(row["销售机构名称"]), None, policy_no, "业绩明细缺人员工号，未纳入个人星钻计算。"))
            continue
        if valid_callback:
            key = (int(y), int(m), staff_code, business_line)
            agg[key][0] += standard_premium
            if is_longterm:
                agg[key][1] += 1
        source_rows.append(
            {
                "batch_id": batch_id,
                "year": int(y),
                "month": int(m),
                "org": _text(row["销售机构名称"]),
                "business_line": business_line,
                "staff_code": staff_code,
                "policy_no": policy_no,
                "is_longterm": 1 if is_longterm else 0,
                "payment_years": _num(row["缴费年限"]),
                "standard_premium": round(standard_premium, 2),
                "annualized_premium": round(annualized_premium, 2),
                "qj_premium": round(qj_premium, 2),
                "premium_source": "source_zs_premium",
                "issue_date": str(row["承保时间"] or ""),
                "callback_date": str(row["回销时间"] or ""),
                "account_date": str(row["入账时间"] or ""),
                "raw_payload": json.dumps(dict(row), ensure_ascii=False, default=str),
            }
        )
    return {k: (v[0], int(v[1])) for k, v in agg.items()}, source_rows, exceptions


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
    if "经理" in text:
        return "经理"
    if "主管" in text or "服务经理" in text:
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
