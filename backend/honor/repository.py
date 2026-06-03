"""SQLite persistence helpers for the honor alliance domain."""
from __future__ import annotations

import json
from typing import Any

from db.connection import get_db
from honor.config import MONTHLY_RULES


def create_batch(
    *,
    year: int,
    month: int | None,
    rule_version: str,
    source_cutoff: str | None = None,
    data_source_mode: str = "existing_data",
    source_tables: dict[str, Any] | None = None,
    created_by: str = "system",
    status: str = "success",
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO honor_import_batches (
                year, month, rule_version, source_cutoff, data_source_mode,
                source_tables, source_files, status, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, '{}', ?, ?)
            """,
            (
                year,
                month,
                rule_version,
                source_cutoff,
                data_source_mode,
                json.dumps(source_tables or {}, ensure_ascii=False),
                status,
                created_by,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def latest_batch(year: int | None = None, month: int | None = None) -> dict | None:
    params: list[Any] = []
    where: list[str] = []
    if year is not None:
        where.append("year = ?")
        params.append(year)
    if month is not None:
        where.append("month = ?")
        params.append(month)
    sql = """
        SELECT b.*
        FROM honor_import_batches b
        LEFT JOIN (
            SELECT batch_id, COUNT(*) AS row_count
            FROM honor_person_summary
            GROUP BY batch_id
        ) s ON s.batch_id = b.id
    """
    if where:
        sql += " WHERE " + " AND ".join([f"b.{item}" for item in where])
    sql += " ORDER BY CASE WHEN COALESCE(s.row_count, 0) > 0 THEN 0 ELSE 1 END, b.id DESC LIMIT 1"
    with get_db() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def save_field_audit(batch_id: int, audit: dict[str, Any]) -> None:
    rows = []
    for table in audit.get("rawTables", {}).values():
        rows.extend(table.get("fields", []))
    with get_db() as conn:
        conn.executemany(
            """
            INSERT INTO honor_field_audit_results (
                batch_id, table_name, required_field, matched_column,
                required_level, available, impact, fallback_strategy
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    batch_id,
                    row["tableName"],
                    row["requiredField"],
                    row.get("matchedColumn"),
                    row["requiredLevel"],
                    1 if row.get("available") else 0,
                    row.get("impact"),
                    row.get("fallbackStrategy"),
                )
                for row in rows
            ],
        )
        conn.commit()


def replace_calculation_results(batch_id: int, payload: dict[str, list[dict[str, Any]]], exception_count: int) -> None:
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for table in [
                "honor_source_staff_month",
                "honor_source_policy",
                "honor_person_month",
                "honor_person_summary",
                "honor_org_summary",
                "honor_quarter_rewards",
                "honor_exceptions",
            ]:
                conn.execute(f"DELETE FROM {table} WHERE batch_id = ?", (batch_id,))

            _insert_many(conn, "honor_source_staff_month", payload.get("source_staff_month", []))
            _insert_many(conn, "honor_source_policy", payload.get("source_policy", []))
            _insert_many(conn, "honor_person_month", payload.get("person_month", []))
            _insert_many(conn, "honor_person_summary", payload.get("person_summary", []))
            _insert_many(conn, "honor_org_summary", payload.get("org_summary", []))
            _insert_many(conn, "honor_quarter_rewards", payload.get("quarter_rewards", []))
            _insert_many(conn, "honor_exceptions", payload.get("exceptions", []))
            conn.execute(
                "UPDATE honor_import_batches SET exception_count = ? WHERE id = ?",
                (exception_count, batch_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _insert_many(conn, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ",".join(["?"] * len(columns))
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    conn.executemany(sql, [[_json_value(row.get(col)) for col in columns] for row in rows])


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def fetch_summary(batch_id: int) -> dict[str, Any]:
    with get_db() as conn:
        batch = conn.execute("SELECT * FROM honor_import_batches WHERE id = ?", (batch_id,)).fetchone()
        overview = conn.execute(
            """
            SELECT
                COALESCE(SUM(tracked_headcount), 0) AS tracked_headcount,
                COALESCE(SUM(member_count), 0) AS member_count,
                COALESCE(SUM(senior_plus_count), 0) AS senior_plus_count,
                COALESCE(SUM(monthly_gain_count), 0) AS monthly_gain_count,
                COALESCE(SUM(monthly_deduct_count), 0) AS monthly_deduct_count,
                COALESCE(SUM(total_diamond), 0) AS total_diamond,
                COALESCE(SUM(estimated_reward), 0) AS estimated_reward
            FROM honor_org_summary WHERE batch_id = ?
            """,
            (batch_id,),
        ).fetchone()
        exceptions = conn.execute("SELECT COUNT(*) AS count FROM honor_exceptions WHERE batch_id = ?", (batch_id,)).fetchone()
        new_stars = conn.execute("SELECT COUNT(*) AS count FROM honor_person_summary WHERE batch_id = ? AND is_new_star = 1", (batch_id,)).fetchone()
        annual = conn.execute("SELECT COUNT(*) AS count FROM honor_person_summary WHERE batch_id = ?", (batch_id,)).fetchone()
        departed = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM honor_person_month
            WHERE batch_id = ?
              AND year = ?
              AND month = ?
              AND is_employed_end_month = 0
            """,
            (batch_id, int(batch["year"] or 0), int(batch["month"] or 0)),
        ).fetchone()
        data = dict(overview) if overview else {}
        tracked = int(data.get("tracked_headcount") or 0)
        members = int(data.get("member_count") or 0)
        data["member_rate"] = members / tracked if tracked else 0
        data["annual_tracked_headcount"] = int(annual["count"] if annual else 0)
        data["departed_headcount"] = int(departed["count"] if departed else 0)
        data["new_star_count"] = int(new_stars["count"] if new_stars else 0)
        data["exception_count"] = int(exceptions["count"] if exceptions else 0)
        return {"batch": dict(batch) if batch else None, "overview": data}


def fetch_dashboard(batch_id: int) -> dict[str, Any]:
    """Return an analysis-ready dashboard payload for the honor domain."""
    summary = fetch_summary(batch_id)
    with get_db() as conn:
        person_summary = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_person_summary WHERE batch_id = ? ORDER BY diamond_balance DESC, total_gain DESC",
                (batch_id,),
            ).fetchall()
        ]
        person_month = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_person_month WHERE batch_id = ? ORDER BY month DESC, diamond_delta ASC",
                (batch_id,),
            ).fetchall()
        ]
        org_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_org_summary WHERE batch_id = ? ORDER BY member_rate DESC, total_diamond DESC",
                (batch_id,),
            ).fetchall()
        ]
        exceptions = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_exceptions WHERE batch_id = ? ORDER BY id DESC LIMIT 1000",
                (batch_id,),
            ).fetchall()
        ]
        source_staff = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_source_staff_month WHERE batch_id = ? ORDER BY year, month, org, business_line, staff_code",
                (batch_id,),
            ).fetchall()
        ]
        source_policy = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM honor_source_policy WHERE batch_id = ?",
                (batch_id,),
            ).fetchall()
        ]
    person_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in person_summary
    }
    for row in person_summary:
        row["warning_tags"] = _load_json_list(row.get("warning_tags"))

    current_month = int((summary.get("batch") or {}).get("month") or 0)
    project_rows = _aggregate_rows(person_summary, person_month, "business_line", current_month=current_month)
    project_org_rows = _project_org_rows(org_rows)
    org_member_structure = _org_member_structure(person_summary, person_month, current_month)
    specialist_rows = _aggregate_rows(
        [row for row in person_summary if row.get("role_type") not in {"主管", "经理"}],
        person_month,
        "org",
        extra_key="business_line",
        current_month=current_month,
    )
    manager_rows = _aggregate_rows(
        [row for row in person_summary if row.get("role_type") in {"主管", "经理"}],
        person_month,
        "role_type",
        extra_key="business_line",
        current_month=current_month,
    )
    warnings = _build_monthly_warnings(person_month, person_index, exceptions)
    levels = _level_distribution(person_summary)
    trend = _monthly_trend(person_month)
    qj_index = _policy_qj_index(source_policy)
    specialist_history = _specialist_history(person_month, qj_index)
    manager_history = _manager_history(source_staff, person_month, qj_index)

    return {
        "batch": summary.get("batch"),
        "overview": summary.get("overview") or {},
        "orgs": _rank_rows(org_rows, "member_rate", "total_diamond"),
        "projects": _rank_rows(project_rows, "member_rate", "total_diamond"),
        "projectOrgs": project_org_rows,
        "orgMemberStructure": org_member_structure,
        "specialists": _rank_rows(specialist_rows, "member_rate", "total_diamond"),
        "managers": _rank_rows(manager_rows, "member_rate", "total_diamond"),
        "specialistHistory": specialist_history[:3000],
        "managerHistory": manager_history[:3000],
        "warnings": warnings,
        "persons": person_summary[:1000],
        "levels": levels,
        "trend": trend,
        "exceptions": exceptions,
    }


def _load_json_list(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _aggregate_rows(
    summaries: list[dict[str, Any]],
    months: list[dict[str, Any]],
    key: str,
    *,
    extra_key: str | None = None,
    current_month: int | None = None,
) -> list[dict[str, Any]]:
    if current_month is None:
        current_month = max((int(row.get("month") or 0) for row in months), default=0)
    current_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in months
        if int(row.get("month") or 0) == int(current_month or 0)
    }
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in summaries:
        label = str(row.get(key) or "未列明")
        extra = str(row.get(extra_key) or "") if extra_key else ""
        item = grouped.setdefault(
            (label, extra),
            {
                "dimension": label,
                "business_line": extra or (row.get("business_line") if key != "business_line" else label),
                "tracked_headcount": 0,
                "member_count": 0,
                "monthly_gain_count": 0,
                "monthly_deduct_count": 0,
                "total_diamond": 0,
                "estimated_reward": 0,
                "member_rate": 0,
                "avg_diamond": 0,
            },
        )
        current = current_index.get((str(row.get("staff_code") or ""), str(row.get("business_line") or "")))
        current_employed = bool(current and int(current.get("is_employed_end_month") or 0) > 0)
        item["tracked_headcount"] += 1 if current_employed else 0
        item["member_count"] += 1 if current_employed and row.get("membership_level") != "未入会" else 0
        item["total_diamond"] += int(row.get("diamond_balance") or 0)
        item["estimated_reward"] += _reward_amount(row.get("membership_level")) if current_employed else 0
        if current:
            item["monthly_gain_count"] += 1 if int(current.get("diamond_delta") or 0) > 0 else 0
            item["monthly_deduct_count"] += 1 if int(current.get("diamond_delta") or 0) < 0 else 0
    for item in grouped.values():
        tracked = int(item["tracked_headcount"] or 0)
        item["member_rate"] = item["member_count"] / tracked if tracked else 0
        item["avg_diamond"] = item["total_diamond"] / tracked if tracked else 0
    return list(grouped.values())


def _project_org_rows(org_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in org_rows:
        rows.append(
            {
                "dimension": row.get("business_line"),
                "org": row.get("org"),
                "business_line": row.get("business_line"),
                "tracked_headcount": int(row.get("tracked_headcount") or 0),
                "member_count": int(row.get("member_count") or 0),
                "member_rate": float(row.get("member_rate") or 0),
                "avg_diamond": float(row.get("avg_diamond") or 0),
                "monthly_gain_count": int(row.get("monthly_gain_count") or 0),
                "monthly_deduct_count": int(row.get("monthly_deduct_count") or 0),
                "total_diamond": int(row.get("total_diamond") or 0),
                "estimated_reward": float(row.get("estimated_reward") or 0),
            }
        )
    return _rank_rows(rows, "member_rate", "total_diamond")


def _org_member_structure(
    summaries: list[dict[str, Any]],
    months: list[dict[str, Any]],
    current_month: int,
) -> list[dict[str, Any]]:
    current_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in months
        if int(row.get("month") or 0) == int(current_month or 0)
    }
    grouped: dict[str, dict[str, Any]] = {}
    for row in summaries:
        current = current_index.get((str(row.get("staff_code") or ""), str(row.get("business_line") or "")))
        if not current or int(current.get("is_employed_end_month") or 0) <= 0 or row.get("membership_level") == "未入会":
            continue
        org = str(row.get("org") or "未归属")
        item = grouped.setdefault(
            org,
            {"org": org, "member_count": 0, "specialist_member_count": 0, "manager_member_count": 0},
        )
        item["member_count"] += 1
        if row.get("role_type") in {"主管", "经理"}:
            item["manager_member_count"] += 1
        else:
            item["specialist_member_count"] += 1
    return _rank_rows(list(grouped.values()), "member_count", "specialist_member_count")


def _policy_qj_index(source_policy: list[dict[str, Any]]) -> dict[tuple[int, str, str], dict[str, float]]:
    index: dict[tuple[int, str, str], dict[str, float]] = {}
    for row in source_policy:
        key = (
            int(row.get("month") or 0),
            str(row.get("staff_code") or ""),
            str(row.get("business_line") or ""),
        )
        item = index.setdefault(key, {"qj_premium": 0.0, "standard_premium": 0.0, "policy_count": 0.0})
        item["qj_premium"] += float(row.get("qj_premium") or 0)
        item["standard_premium"] += float(row.get("standard_premium") or 0)
        item["policy_count"] += 1
    return index


def _clean_team_code(value: Any) -> str:
    code = str(value or "").strip()
    if code.lower() in {"none", "nan", "null"}:
        return ""
    return code


def _specialist_history(
    person_month: list[dict[str, Any]],
    qj_index: dict[tuple[int, str, str], dict[str, float]],
) -> list[dict[str, Any]]:
    rows = []
    for row in person_month:
        if row.get("role_type") in {"主管", "经理"}:
            continue
        key = (int(row.get("month") or 0), str(row.get("staff_code") or ""), str(row.get("business_line") or ""))
        premium = qj_index.get(key, {})
        rows.append(
            {
                "org": row.get("org"),
                "business_line": row.get("business_line"),
                "staff_code": row.get("staff_code"),
                "staff_name": row.get("staff_name"),
                "month": row.get("month"),
                "qj_premium": round(float(premium.get("qj_premium") or 0), 2),
                "standard_premium": round(float(row.get("standard_premium") or 0), 2),
                "longterm_policy_count": int(row.get("longterm_policy_count") or 0),
                "monthly_qualified": int(row.get("monthly_qualified") or 0),
                "diamond_delta": int(row.get("diamond_delta") or 0),
                "diamond_balance": int(row.get("diamond_balance") or 0),
                "membership_level": row.get("membership_level"),
                "is_new_star": int(row.get("is_new_star") or 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("org") or ""), str(item.get("business_line") or ""), str(item.get("staff_code") or ""), int(item.get("month") or 0)))


def _manager_history(
    source_staff: list[dict[str, Any]],
    person_month: list[dict[str, Any]],
    qj_index: dict[tuple[int, str, str], dict[str, float]],
) -> list[dict[str, Any]]:
    person_month_index = {
        (int(row.get("month") or 0), str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in person_month
    }
    staff_by_team: dict[tuple[int, str, str, str, str], list[dict[str, Any]]] = {}
    for row in source_staff:
        month = int(row.get("month") or 0)
        line = str(row.get("business_line") or "")
        org = str(row.get("org") or "")
        for scope, code in (("主管", row.get("group_code")), ("经理", row.get("department_code"))):
            team_code = _clean_team_code(code)
            if not team_code:
                continue
            staff_by_team.setdefault((month, org, line, scope, team_code), []).append(row)

    rows = []
    for manager in source_staff:
        role_type = str(manager.get("role_type") or "")
        if role_type not in {"主管", "经理"}:
            continue
        month = int(manager.get("month") or 0)
        line = str(manager.get("business_line") or "")
        org = str(manager.get("org") or "")
        team_code = _clean_team_code(manager.get("group_code") if role_type == "主管" else manager.get("department_code"))
        team_rows = staff_by_team.get((month, org, line, role_type, team_code), []) if team_code else []
        team_person_rows = [
            person_month_index.get((month, str(staff.get("staff_code") or ""), line))
            for staff in team_rows
        ]
        team_person_rows = [row for row in team_person_rows if row]
        manager_person = person_month_index.get((month, str(manager.get("staff_code") or ""), line), {})
        qj_total = 0.0
        standard_total = 0.0
        for staff in team_rows:
            premium = qj_index.get((month, str(staff.get("staff_code") or ""), line), {})
            qj_total += float(premium.get("qj_premium") or 0)
            standard_total += float(premium.get("standard_premium") or 0)
        rows.append(
            {
                "org": org,
                "business_line": line,
                "role_type": role_type,
                "manager_code": manager.get("staff_code"),
                "manager_name": manager.get("staff_name"),
                "month": month,
                "team_code": team_code,
                "team_scope": "营业组" if role_type == "主管" else "营业部",
                "team_tracked_headcount": len(team_rows),
                "star_manpower_count": sum(1 for row in team_person_rows if row.get("membership_level") != "未入会"),
                "monthly_gain_count": sum(1 for row in team_person_rows if int(row.get("diamond_delta") or 0) > 0),
                "monthly_deduct_count": sum(1 for row in team_person_rows if int(row.get("diamond_delta") or 0) < 0),
                "team_qj_premium": round(qj_total, 2),
                "team_standard_premium": round(standard_total, 2),
                "team_diamond_balance": sum(int(row.get("diamond_balance") or 0) for row in team_person_rows),
                "manager_diamond_balance": int(manager_person.get("diamond_balance") or 0),
                "data_note": "" if team_code else "缺团队编码，暂不归集团队",
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("org") or ""), str(item.get("business_line") or ""), str(item.get("manager_code") or ""), int(item.get("month") or 0)))


def _reward_amount(level: str | None) -> int:
    if level in {"金星会员", "恒星会员", "星钻会员", "星曜会员"}:
        return 300
    if level in {"黄金会员", "白金会员", "钻石会员", "至尊会员"}:
        return 200
    if level in {"初级会员", "中级会员", "高级会员", "资深会员"}:
        return 100
    return 0


def _rank_rows(rows: list[dict[str, Any]], *sort_keys: str) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: tuple(-float(row.get(key) or 0) for key in sort_keys),
    )
    return [{"rank": idx + 1, **row} for idx, row in enumerate(ordered)]


def _build_monthly_warnings(
    months: list[dict[str, Any]],
    person_index: dict[tuple[str, str], dict[str, Any]],
    exceptions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_month = max((int(row.get("month") or 0) for row in months), default=0)
    previous_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in months
        if int(row.get("month") or 0) == latest_month - 1
    }
    for row in [item for item in months if int(item.get("month") or 0) == latest_month]:
        staff_key = (str(row.get("staff_code") or ""), str(row.get("business_line") or ""))
        person = person_index.get(staff_key, {})
        delta = int(row.get("diamond_delta") or 0)
        previous = previous_index.get(staff_key)
        previous_level = previous.get("membership_level") if previous else "未入会"
        current_level = row.get("membership_level") or "未入会"
        if _level_rank(current_level) < _level_rank(previous_level):
            reason, gap = _downgrade_reason(row)
            rows.append(
                {
                    "warning_type": "等级下降",
                    "month": row.get("month"),
                    "org": row.get("org"),
                    "business_line": row.get("business_line"),
                    "staff_code": row.get("staff_code"),
                    "staff_name": row.get("staff_name") or person.get("staff_name"),
                    "role_type": row.get("role_type") or person.get("role_type"),
                    "membership_level": row.get("membership_level"),
                    "previous_level": previous_level,
                    "current_level": current_level,
                    "diamond_balance": row.get("diamond_balance"),
                    "diamond_delta": delta,
                    "standard_premium": row.get("standard_premium"),
                    "standard_premium_gap": gap,
                    "longterm_policy_count": row.get("longterm_policy_count"),
                    "suggested_action": reason,
                    "priority": 1,
                }
            )
    for row in exceptions:
        staff_code = str(row.get("staff_code") or "")
        person = next((p for (code, _), p in person_index.items() if code == staff_code), {})
        rows.append(
            {
                "warning_type": row.get("exception_type") or "数据异常",
                "month": "",
                "org": row.get("org") or person.get("org"),
                "business_line": person.get("business_line"),
                "staff_code": staff_code,
                "staff_name": person.get("staff_name"),
                "role_type": person.get("role_type"),
                "membership_level": person.get("membership_level"),
                "previous_level": "",
                "current_level": person.get("membership_level"),
                "diamond_balance": person.get("diamond_balance"),
                "diamond_delta": "",
                "standard_premium": "",
                "standard_premium_gap": "",
                "longterm_policy_count": "",
                "suggested_action": row.get("suggested_action") or row.get("message"),
                "priority": 0 if row.get("severity") == "error" else 2,
            }
        )
    return sorted(rows, key=lambda row: (int(row.get("priority") or 9), str(row.get("org") or ""), str(row.get("staff_code") or "")))[:1000]


def _level_rank(level: str | None) -> int:
    order = {
        "未入会": 0,
        "初级会员": 1,
        "中级会员": 2,
        "高级会员": 3,
        "资深会员": 4,
        "黄金会员": 5,
        "白金会员": 6,
        "钻石会员": 7,
        "至尊会员": 8,
        "金星会员": 9,
        "恒星会员": 10,
        "星钻会员": 11,
        "星曜会员": 12,
    }
    return order.get(str(level or "未入会"), 0)


def _downgrade_reason(row: dict[str, Any]) -> tuple[str, float | str]:
    if int(row.get("is_employed_end_month") or 0) <= 0:
        return "离职/非在职清零", ""
    business_line = str(row.get("business_line") or "")
    premium = float(row.get("standard_premium") or 0)
    longterm_count = int(row.get("longterm_policy_count") or 0)
    threshold = float((MONTHLY_RULES.get(business_line) or {}).get("premium_threshold") or 0)
    gap = max(0.0, threshold - premium) if threshold else ""
    if longterm_count <= 0:
        return "缺少长险件", gap
    if gap:
        return "标保不足", gap
    return "未达成当月星钻条件", gap


def _level_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, int] = {}
    for row in rows:
        level = row.get("membership_level") or "未入会"
        grouped[level] = grouped.get(level, 0) + 1
    total = sum(grouped.values())
    return [
        {"level": level, "count": count, "share": count / total if total else 0}
        for level, count in sorted(grouped.items(), key=lambda item: -item[1])
    ]


def _monthly_trend(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        month = int(row.get("month") or 0)
        item = grouped.setdefault(
            month,
            {"month": month, "tracked_headcount": 0, "member_count": 0, "gain_count": 0, "deduct_count": 0, "qualified_count": 0},
        )
        employed = int(row.get("is_employed_end_month") or 0) > 0
        item["tracked_headcount"] += 1 if employed else 0
        item["member_count"] += 1 if employed and row.get("membership_level") != "未入会" else 0
        item["gain_count"] += 1 if int(row.get("diamond_delta") or 0) > 0 else 0
        item["deduct_count"] += 1 if int(row.get("diamond_delta") or 0) < 0 else 0
        item["qualified_count"] += 1 if int(row.get("monthly_qualified") or 0) > 0 else 0
    for item in grouped.values():
        tracked = int(item["tracked_headcount"] or 0)
        item["member_rate"] = item["member_count"] / tracked if tracked else 0
        item["qualified_rate"] = item["qualified_count"] / tracked if tracked else 0
    return [grouped[key] for key in sorted(grouped)]


def fetch_table(table: str, batch_id: int, limit: int = 500) -> list[dict[str, Any]]:
    allowed = {
        "honor_person_month",
        "honor_person_summary",
        "honor_org_summary",
        "honor_exceptions",
        "honor_field_audit_results",
        "honor_quarter_rewards",
    }
    if table not in allowed:
        raise ValueError(f"Unsupported honor table: {table}")
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE batch_id = ? ORDER BY id DESC LIMIT ?",
            (batch_id, max(1, min(int(limit or 500), 5000))),
        ).fetchall()
        return [dict(row) for row in rows]
