"""Bounded reads of the four daily-import source tables, preserving stored fields."""
from __future__ import annotations

import json
import math

from db.connection import get_db
from services.raw_table_reader import quote_identifier


DATASETS = {
    "performance": "转型业绩明细",
    "jingdai": "经代业绩明细",
    "hr_data": "人力明细",
    "value_data": "价值明细",
}


class ImportChangedError(ValueError):
    pass


def _columns(conn, dataset):
    if dataset not in DATASETS:
        raise LookupError("Unknown daily-import dataset")
    return [
        {"name": row[1], "sqliteType": row[2]}
        for row in conn.execute(f"PRAGMA table_info({quote_identifier(dataset)})")
    ]


def _latest_import_id(conn):
    return conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM data_imports WHERE status IN ('success', 'partial')"
    ).fetchone()[0]


def list_raw_datasets():
    with get_db() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        datasets = []
        for name, label in DATASETS.items():
            columns = _columns(conn, name)
            datasets.append({
                "dataset": name, "label": label, "available": bool(columns),
                "columns": columns, "fieldCount": len(columns),
            })
        return {"datasets": datasets, "latestImportId": _latest_import_id(conn)}


def read_raw_page(
    dataset: str, *, limit: int = 200, after_row_id: int = 0,
    columns: list[str] | None = None, filters: str | None = None,
    expected_import_id: int | None = None,
):
    if dataset not in DATASETS:
        raise LookupError("Unknown daily-import dataset")
    if not 1 <= limit <= 1000 or not 0 <= after_row_id <= 9223372036854775807:
        raise ValueError("Invalid page size or cursor")
    predicates = {}
    if filters is not None:
        if len(filters) > 8000:
            raise ValueError("Filters are too long")
        try:
            predicates = json.loads(filters)
        except (ValueError, RecursionError) as exc:
            raise ValueError("Filters must be a JSON object") from exc
        if not isinstance(predicates, dict) or len(predicates) > 20:
            raise ValueError("Filters must be an object with at most 20 fields")
        for value in predicates.values():
            if (value is not None and type(value) not in (str, int, float)) or (
                isinstance(value, float) and not math.isfinite(value)
            ) or (type(value) is int and not -9223372036854775808 <= value <= 9223372036854775807):
                raise ValueError("Filter values must be strings, finite numbers or null")

    with get_db() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        latest_import_id = _latest_import_id(conn)
        if expected_import_id is not None and expected_import_id != latest_import_id:
            raise ImportChangedError("Imported data changed; restart from the first page")
        schema = _columns(conn, dataset)
        if not schema:
            raise LookupError("Dataset has not been imported")
        names = [column["name"] for column in schema]
        selected = names if columns is None else columns
        if not selected or len(selected) > len(names) or len(set(selected)) != len(selected):
            raise ValueError("Select distinct existing columns")
        if any(name not in names for name in [*selected, *predicates]):
            raise ValueError("Unknown source column")
        # Do not let an imported field named 'rowid' shadow SQLite's cursor.
        cursor = next((name for name in ("rowid", "_rowid_", "oid")
                       if name not in {column.lower() for column in names}), None)
        if cursor is None:
            raise ValueError("This source schema does not support row cursors")
        where, params = [f"{cursor} > ?"], [after_row_id]
        for column, value in predicates.items():
            if value is None:
                where.append(f"{quote_identifier(column)} IS NULL")
            else:
                where.append(f"{quote_identifier(column)} = ?")
                params.append(value)
        fields = ",".join(map(quote_identifier, selected))
        rows = conn.execute(
            f"SELECT {cursor}, {fields} FROM {quote_identifier(dataset)} "
            f"WHERE {' AND '.join(where)} ORDER BY {cursor} LIMIT ?",
            [*params, limit + 1],
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "dataset": dataset, "columns": selected,
            "rows": [dict(zip(selected, tuple(row)[1:])) for row in rows],
            "returnedRows": len(rows), "limit": limit, "afterRowId": after_row_id,
            "hasMore": has_more,
            "nextAfterRowId": rows[-1][0] if has_more else None,
            "latestImportId": latest_import_id,
        }
