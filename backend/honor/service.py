"""Application service for honor audit and calculation workflows."""
from __future__ import annotations

from typing import Any

from .calculator import calculate_personal_mvp
from .config import DATA_SOURCE_MODE, RULE_VERSION
from .field_audit import audit_fields
from .repository import create_batch, replace_calculation_results, save_field_audit


def run_field_audit(*, user: dict | None = None, persist: bool = True) -> dict[str, Any]:
    audit = audit_fields()
    batch_id = None
    if persist:
        source_tables = {
            table: {
                "exists": payload.get("exists"),
                "rowCount": payload.get("rowCount"),
                "columns": payload.get("columns"),
            }
            for table, payload in audit.get("rawTables", {}).items()
        }
        batch_id = create_batch(
            year=0,
            month=None,
            rule_version=RULE_VERSION,
            data_source_mode=DATA_SOURCE_MODE,
            source_tables=source_tables,
            created_by=(user or {}).get("username") or "system",
            status="field_audit",
        )
        save_field_audit(batch_id, audit)
    audit["batchId"] = batch_id
    audit["ruleVersion"] = RULE_VERSION
    audit["dataSourceMode"] = DATA_SOURCE_MODE
    return audit


def recalculate_honor(year: int, month: int, *, user: dict | None = None) -> dict[str, Any]:
    audit = audit_fields()
    source_tables = {
        table: {
            "exists": payload.get("exists"),
            "rowCount": payload.get("rowCount"),
            "columns": payload.get("columns"),
        }
        for table, payload in audit.get("rawTables", {}).items()
    }
    batch_id = create_batch(
        year=year,
        month=month,
        rule_version=RULE_VERSION,
        data_source_mode=DATA_SOURCE_MODE,
        source_tables=source_tables,
        created_by=(user or {}).get("username") or "system",
    )
    save_field_audit(batch_id, audit)
    payload = calculate_personal_mvp(batch_id, year, month)
    replace_calculation_results(batch_id, payload, len(payload.get("exceptions", [])))
    return {
        "batchId": batch_id,
        "year": year,
        "month": month,
        "ruleVersion": RULE_VERSION,
        "dataSourceMode": DATA_SOURCE_MODE,
        "exceptionCount": len(payload.get("exceptions", [])),
        "personCount": len(payload.get("person_summary", [])),
        "orgCount": len(payload.get("org_summary", [])),
    }

