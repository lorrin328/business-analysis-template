from __future__ import annotations

import json

from db.connection import get_db


def create_scheme_batch(
    *,
    scheme_id: str,
    scheme_name: str,
    rule_version: str,
    file_name: str,
    file_hash: str,
    file_size: int,
    result: dict,
    imported_by: str,
) -> dict:
    summary_payload = {
        "scheme": result.get("scheme") or {},
        "summary": result.get("summary") or {},
        "warnings": result.get("warnings") or [],
        "definitions": result.get("definitions") or {},
        "sourceAudit": result.get("sourceAudit") or {},
    }
    detail_payload = result.get("details") or {"rows": []}
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO scheme_import_batches
                (scheme_id, scheme_name, rule_version, file_name, file_hash, file_size,
                 summary_json, detail_json, imported_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scheme_id,
                scheme_name,
                rule_version,
                file_name,
                file_hash,
                file_size,
                json.dumps(summary_payload, ensure_ascii=False),
                json.dumps(detail_payload, ensure_ascii=False),
                imported_by,
            ),
        )
        conn.commit()
        batch_id = cur.lastrowid
        row = conn.execute("SELECT * FROM scheme_import_batches WHERE id = ?", (batch_id,)).fetchone()
    return _row_to_result(row)


def latest_scheme_batch(scheme_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM scheme_import_batches
            WHERE scheme_id = ? AND status = 'success'
            ORDER BY id DESC
            LIMIT 1
            """,
            (scheme_id,),
        ).fetchone()
    return _row_to_result(row) if row else None


def _loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _row_to_result(row) -> dict:
    summary_payload = _loads(row["summary_json"], {})
    detail_payload = _loads(row["detail_json"], {"rows": []})
    return {
        "batch": {
            "id": row["id"],
            "schemeId": row["scheme_id"],
            "schemeName": row["scheme_name"],
            "ruleVersion": row["rule_version"],
            "fileName": row["file_name"],
            "fileHash": row["file_hash"],
            "fileSize": row["file_size"],
            "status": row["status"],
            "importedBy": row["imported_by"],
            "importedAt": row["imported_at"],
        },
        "scheme": summary_payload.get("scheme") or {"id": row["scheme_id"], "name": row["scheme_name"]},
        "summary": summary_payload.get("summary") or {},
        "details": detail_payload,
        "warnings": summary_payload.get("warnings") or [],
        "definitions": summary_payload.get("definitions") or {},
        "sourceAudit": summary_payload.get("sourceAudit") or {},
    }
