"""Explicit, read-only catalog and bounded queries for stored business data.

Only tables listed here can be exposed. Account, session, log and deployment
metadata tables are deliberately outside the business-data contract.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time

from db.connection import get_db
from services.ai_raw_data import DATASETS as DAILY_DATASETS, ImportChangedError, _latest_import_id
from services.raw_table_reader import quote_identifier


# Dataset -> (business label, existing module permission). Keep this explicit:
# newly created SQLite tables must not silently become externally readable.
BUSINESS_DATASETS = {
    **{name: (label, "ai_raw_data") for name, label in DAILY_DATASETS.items()},
    "agg_performance": ("转型月度业绩", "kpi"),
    "agg_jingdai": ("经代月度业绩", "kpi"),
    "agg_jingdai_daily": ("经代日度业绩", "kpi"),
    "agg_hr_data": ("月度人力", "team_enhanced"),
    "agg_org_hr_data": ("机构人力", "team_enhanced"),
    "agg_value_data": ("价值保费", "kpi"),
    "agg_product_structure": ("产品结构", "product_structure"),
    "agg_staff_month_performance": ("人员月度业绩", "team_enhanced"),
    "agg_product_daily": ("产品日度业绩", "product_structure"),
    "agg_zhituo_performance": ("职拓业绩", "kpi"),
    "agg_org_performance": ("机构业绩", "org"),
    "agg_org_value": ("机构价值", "org"),
    "agg_payment_period": ("交费期间", "payment_period"),
    "agg_payment_period_daily": ("交费期间日度", "payment_period"),
    "agg_longterm_qj": ("长险期交", "kpi"),
    "agg_daily_performance": ("转型日度业绩", "kpi"),
    "agg_org_daily_performance": ("机构日度业绩", "org"),
    "agg_org_daily_activity": ("机构日度活动", "org"),
    "target_config": ("目标配置", "targets"),
    "target_values": ("正式目标明细", "targets"),
    "product_config": ("经代产品配置", "product_config"),
    "honor_source_staff_month": ("荣誉人力来源", "honor_view"),
    "honor_source_policy": ("荣誉保单来源", "honor_view"),
    "honor_person_month": ("荣誉个人月度结果", "honor_view"),
    "honor_person_summary": ("荣誉个人汇总", "honor_view"),
    "honor_org_summary": ("荣誉机构汇总", "honor_view"),
    "honor_quarter_rewards": ("荣誉季度奖励", "honor_view"),
    "honor_exceptions": ("荣誉异常", "honor_audit"),
    "branch_reference": ("网点主数据", "branch_analysis"),
    "history_reconciliation": ("历史数据对账", "customer_analysis"),
    "customer_policy_snapshot": ("客户保单快照", "customer_analysis"),
    "customer_policy_key_ambiguity": ("客户保单键歧义", "customer_analysis"),
    "customer_master": ("客户主档", "customer_analysis"),
    "customer_policy_month_fact": ("客户保单月度事实", "customer_analysis"),
}


def _bound_query(conn):
    deadline = time.monotonic() + 15
    conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)


def _schema(conn, dataset):
    if dataset not in BUSINESS_DATASETS:
        raise LookupError("Unknown business dataset")
    return [{"name": row[1], "sqliteType": row[2]} for row in
            conn.execute(f"PRAGMA table_info({quote_identifier(dataset)})")]


def _cursor_name(schema):
    names = {item["name"].lower() for item in schema}
    return next((name for name in ("rowid", "_rowid_", "oid") if name not in names), None)


def _filters(text, names):
    if text is None:
        return [], []
    if len(text) > 8000:
        raise ValueError("Filters are too long")
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, RecursionError) as exc:
        raise ValueError("Filters must be a JSON object") from exc
    if not isinstance(value, dict) or len(value) > 20:
        raise ValueError("Filters must be an object with at most 20 fields")
    clauses, params = [], []
    for column, condition in value.items():
        if column not in names:
            raise ValueError("Unknown source column")
        operator, operand = (next(iter(condition.items())) if isinstance(condition, dict) and len(condition) == 1
                             else ("eq", condition))
        if operator not in {"eq", "gte", "lte", "in", "isNull"}:
            raise ValueError("Unsupported filter operator")
        if operator == "isNull":
            if type(operand) is not bool:
                raise ValueError("isNull requires a boolean")
            clauses.append(f"{quote_identifier(column)} IS {'NULL' if operand else 'NOT NULL'}")
            continue
        operands = operand if operator == "in" else [operand]
        if not isinstance(operands, list) or not 1 <= len(operands) <= 50:
            raise ValueError("Invalid filter values")
        for item in operands:
            if item is not None and type(item) not in (str, int, float):
                raise ValueError("Invalid filter value")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Invalid filter value")
            if type(item) is int and not -9223372036854775808 <= item <= 9223372036854775807:
                raise ValueError("Invalid filter value")
        q = quote_identifier(column)
        if operator == "eq" and operand is None:
            clauses.append(f"{q} IS NULL")
        elif operator == "in":
            if any(item is None for item in operands):
                raise ValueError("Use isNull for null filters")
            clauses.append(f"{q} IN ({','.join('?' for _ in operands)})")
            params.extend(operands)
        else:
            if operand is None:
                raise ValueError("Use isNull for null filters")
            clauses.append(f"{q} {dict(eq='=', gte='>=', lte='<=')[operator]} ?")
            params.append(operand)
    return clauses, params


def catalog(allowed):
    with get_db() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        _bound_query(conn)
        result = []
        for name, (label, permission) in BUSINESS_DATASETS.items():
            if not allowed(name, permission):
                continue
            columns = _schema(conn, name)
            result.append({"dataset": name, "label": label, "modulePermission": permission,
                           "available": bool(columns), "columns": columns,
                           "fieldCount": len(columns), "kind": "source" if name in DAILY_DATASETS else "business"})
        return {"datasets": result, "latestImportId": _latest_import_id(conn)}


def page(dataset, *, limit=200, after_row_id=0, columns=None, filters=None, expected_import_id=None):
    if not 1 <= limit <= 1000 or not 0 <= after_row_id <= 9223372036854775807:
        raise ValueError("Invalid page size or cursor")
    with get_db() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        _bound_query(conn)
        latest = _latest_import_id(conn)
        if expected_import_id is not None and expected_import_id != latest:
            raise ImportChangedError("Imported data changed; restart from the first page")
        schema = _schema(conn, dataset)
        if not schema:
            raise LookupError("Dataset has not been imported")
        names = [item["name"] for item in schema]
        selected = names if columns is None else columns
        if not selected or len(set(selected)) != len(selected) or any(name not in names for name in selected):
            raise ValueError("Select distinct existing columns")
        cursor = _cursor_name(schema)
        if cursor is None:
            raise ValueError("This dataset does not support row cursors")
        clauses, params = _filters(filters, names)
        fields = ",".join(quote_identifier(name) for name in selected)
        rows = conn.execute(
            f"SELECT {cursor}, {fields} FROM {quote_identifier(dataset)} WHERE {cursor} > ? "
            f"{' '.join('AND '+clause for clause in clauses)} ORDER BY {cursor} LIMIT ?",
            [after_row_id, *params, limit + 1],
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {"dataset": dataset, "columns": selected,
                "rows": [dict(zip(selected, tuple(row)[1:])) for row in rows],
                "returnedRows": len(rows), "hasMore": has_more,
                "nextAfterRowId": rows[-1][0] if has_more else None,
                "latestImportId": latest}


def analyze(dataset, *, group_by=None, measure=None, aggregation="count", filters=None, limit=100):
    group_by = group_by or []
    if len(group_by) > 3 or len(set(group_by)) != len(group_by) or not 1 <= limit <= 500:
        raise ValueError("Invalid grouping or limit")
    if aggregation not in {"count", "sum", "avg", "min", "max"}:
        raise ValueError("Unsupported aggregation")
    with get_db() as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        _bound_query(conn)
        schema = _schema(conn, dataset)
        if not schema:
            raise LookupError("Dataset has not been imported")
        names = [item["name"] for item in schema]
        if any(name not in names for name in group_by) or (measure is not None and measure not in names):
            raise ValueError("Unknown source column")
        if aggregation != "count" and (measure is None or measure in group_by):
            raise ValueError("A separate measure column is required")
        if aggregation in {"sum", "avg"} and not any(
            item["name"] == measure and item["sqliteType"].upper() in {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}
            for item in schema
        ):
            raise ValueError("Sum and average require a numeric SQLite column")
        clauses, params = _filters(filters, names)
        group_sql = ",".join(quote_identifier(name) for name in group_by)
        metric_sql = "COUNT(*)" if aggregation == "count" else f"{aggregation.upper()}({quote_identifier(measure)})"
        prefix = f"{group_sql}," if group_sql else ""
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        grouped = f" GROUP BY {group_sql}" if group_sql else ""
        rows = conn.execute(
            f"SELECT {prefix}{metric_sql} AS result FROM {quote_identifier(dataset)}{where_sql}{grouped} "
            "ORDER BY result DESC LIMIT ?", [*params, limit + 1],
        ).fetchall()
        truncated = len(rows) > limit
        return {"dataset": dataset, "groupBy": group_by, "measure": measure,
                "aggregation": aggregation, "rows": [dict(row) for row in rows[:limit]],
                "truncated": truncated, "limit": limit,
                "note": "Stored values and units; this is a direct SQLite calculation, not a dashboard KPI definition."}
