"""SQLite persistence helpers for the honor alliance domain."""
from __future__ import annotations

import json
from typing import Any

from db.connection import get_db


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
        data = dict(overview) if overview else {}
        tracked = int(data.get("tracked_headcount") or 0)
        members = int(data.get("member_count") or 0)
        data["member_rate"] = members / tracked if tracked else 0
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
    person_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in person_summary
    }
    for row in person_summary:
        row["warning_tags"] = _load_json_list(row.get("warning_tags"))

    project_rows = _aggregate_rows(person_summary, person_month, "business_line")
    specialist_rows = _aggregate_rows(
        [row for row in person_summary if row.get("role_type") not in {"主管", "经理"}],
        person_month,
        "org",
        extra_key="business_line",
    )
    manager_rows = _aggregate_rows(
        [row for row in person_summary if row.get("role_type") in {"主管", "经理"}],
        person_month,
        "role_type",
        extra_key="business_line",
    )
    warnings = _build_monthly_warnings(person_month, person_index, exceptions)
    levels = _level_distribution(person_summary)
    trend = _monthly_trend(person_month)

    return {
        "batch": summary.get("batch"),
        "overview": summary.get("overview") or {},
        "orgs": _rank_rows(org_rows, "member_rate", "total_diamond"),
        "projects": _rank_rows(project_rows, "member_rate", "total_diamond"),
        "specialists": _rank_rows(specialist_rows, "member_rate", "total_diamond"),
        "managers": _rank_rows(manager_rows, "member_rate", "total_diamond"),
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
) -> list[dict[str, Any]]:
    current_index = {
        (str(row.get("staff_code") or ""), str(row.get("business_line") or "")): row
        for row in months
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
        item["tracked_headcount"] += 1
        item["member_count"] += 1 if row.get("membership_level") != "未入会" else 0
        item["total_diamond"] += int(row.get("diamond_balance") or 0)
        item["estimated_reward"] += _reward_amount(row.get("membership_level"))
        current = current_index.get((str(row.get("staff_code") or ""), str(row.get("business_line") or "")))
        if current:
            item["monthly_gain_count"] += 1 if int(current.get("diamond_delta") or 0) > 0 else 0
            item["monthly_deduct_count"] += 1 if int(current.get("diamond_delta") or 0) < 0 else 0
    for item in grouped.values():
        tracked = int(item["tracked_headcount"] or 0)
        item["member_rate"] = item["member_count"] / tracked if tracked else 0
        item["avg_diamond"] = item["total_diamond"] / tracked if tracked else 0
    return list(grouped.values())


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
    for row in [item for item in months if int(item.get("month") or 0) == latest_month]:
        staff_key = (str(row.get("staff_code") or ""), str(row.get("business_line") or ""))
        person = person_index.get(staff_key, {})
        delta = int(row.get("diamond_delta") or 0)
        qualified = int(row.get("monthly_qualified") or 0)
        protected = int(row.get("protected_month") or 0)
        if delta < 0 or protected or not qualified:
            warning_type = "月度扣减" if delta < 0 else ("证保保号" if protected else "本月未达标")
            action = "本月已扣减，需跟进次月恢复达标" if delta < 0 else ("有长险件但标保未达标，需补足标保缺口" if protected else "无月度入围结果，需关注保单件数和标保")
            rows.append(
                {
                    "warning_type": warning_type,
                    "month": row.get("month"),
                    "org": row.get("org"),
                    "business_line": row.get("business_line"),
                    "staff_code": row.get("staff_code"),
                    "staff_name": row.get("staff_name") or person.get("staff_name"),
                    "role_type": row.get("role_type") or person.get("role_type"),
                    "membership_level": row.get("membership_level"),
                    "diamond_balance": row.get("diamond_balance"),
                    "diamond_delta": delta,
                    "standard_premium": row.get("standard_premium"),
                    "longterm_policy_count": row.get("longterm_policy_count"),
                    "suggested_action": action,
                    "priority": 1 if delta < 0 else (2 if protected else 3),
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
                "diamond_balance": person.get("diamond_balance"),
                "diamond_delta": "",
                "standard_premium": "",
                "longterm_policy_count": "",
                "suggested_action": row.get("suggested_action") or row.get("message"),
                "priority": 0 if row.get("severity") == "error" else 2,
            }
        )
    return sorted(rows, key=lambda row: (int(row.get("priority") or 9), str(row.get("org") or ""), str(row.get("staff_code") or "")))[:1000]


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
        item["tracked_headcount"] += 1
        item["member_count"] += 1 if row.get("membership_level") != "未入会" else 0
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
