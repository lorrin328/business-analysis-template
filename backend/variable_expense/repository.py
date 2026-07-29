from __future__ import annotations

import json

from db.connection import get_db


def _loads(value: str | None, default):
    try:
        return json.loads(value) if value else default
    except json.JSONDecodeError:
        return default


def _row_to_result(row) -> dict:
    summary = _loads(row["summary_json"], {})
    return {
        "batch": {
            "id": row["id"],
            "period": row["period"],
            "ruleVersion": row["rule_version"],
            "fileName": row["file_name"],
            "fileHash": row["file_hash"],
            "fileSize": row["file_size"],
            "status": row["status"],
            "importedBy": row["imported_by"],
            "importedAt": row["imported_at"],
        },
        "period": row["period"],
        "summary": summary.get("summary") or {},
        "details": _loads(row["detail_json"], {}),
        "quality": _loads(row["quality_json"], {}),
        "reportComparison": summary.get("reportComparison"),
        "definitions": summary.get("definitions") or {},
    }


def find_by_hash(file_hash: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM variable_expense_batches WHERE file_hash = ? AND status = 'success' ORDER BY id DESC LIMIT 1",
            (file_hash,),
        ).fetchone()
    return _row_to_result(row) if row else None


def create_batch(*, file_name: str, file_hash: str, file_size: int, result: dict, imported_by: str) -> dict:
    summary_payload = {
        "summary": result.get("summary") or {},
        "reportComparison": result.get("reportComparison"),
        "definitions": result.get("definitions") or {},
    }
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO variable_expense_batches
                (period, rule_version, file_name, file_hash, file_size,
                 summary_json, detail_json, quality_json, imported_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["period"],
                result["ruleVersion"],
                file_name,
                file_hash,
                file_size,
                json.dumps(summary_payload, ensure_ascii=False),
                json.dumps(result.get("details") or {}, ensure_ascii=False),
                json.dumps(result.get("quality") or {}, ensure_ascii=False),
                imported_by,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM variable_expense_batches WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_result(row)


def latest_batch(period: str | None = None) -> dict | None:
    sql = "SELECT * FROM variable_expense_batches WHERE status = 'success'"
    params: tuple = ()
    if period:
        sql += " AND period = ?"
        params = (period,)
    sql += " ORDER BY period DESC, id DESC LIMIT 1"
    with get_db() as conn:
        row = conn.execute(sql, params).fetchone()
    return _row_to_result(row) if row else None


def list_batches(limit: int = 12) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, period, rule_version, file_name, file_hash, file_size,
                   status, imported_by, imported_at
            FROM variable_expense_batches
            WHERE status = 'success'
            ORDER BY period DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "period": row["period"],
            "ruleVersion": row["rule_version"],
            "fileName": row["file_name"],
            "fileHash": row["file_hash"],
            "fileSize": row["file_size"],
            "status": row["status"],
            "importedBy": row["imported_by"],
            "importedAt": row["imported_at"],
        }
        for row in rows
    ]
