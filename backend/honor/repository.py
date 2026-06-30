"""SQLite persistence helpers for the honor alliance domain."""
from __future__ import annotations

import json
from typing import Any

from db.connection import get_db
from honor.dashboard import build_honor_dashboard_payload


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
    return build_honor_dashboard_payload(
        summary=summary,
        person_summary=person_summary,
        person_month=person_month,
        org_rows=org_rows,
        exceptions=exceptions,
        source_staff=source_staff,
        source_policy=source_policy,
    )


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
