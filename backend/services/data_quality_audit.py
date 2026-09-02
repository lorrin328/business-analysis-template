"""Data quality audit checks for metric and aggregate consistency."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pandas as pd

from db import get_kpi_data
from db import connection
from db.schema import AGG_TABLES
from etl.aggregates.jingdai import _load_jingdai_product_config
from services.aggregate_rebuilder import RAW_TABLES, PERIOD_COLUMNS, build_aggregate_rows_from_raw
from services.raw_table_reader import (
    append_indexed_year_filter, compact_period_expr, pick_existing_column,
    quote_identifier, raw_table_columns,
)


@dataclass
class AuditIssue:
    severity: str
    code: str
    message: str
    context: dict


@contextmanager
def get_db():
    """An audit must never initialize, repair or create the database it checks."""
    conn = sqlite3.connect(Path(connection.DB_PATH).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        # Every raw, configuration, aggregate and KPI read shares one snapshot.
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


def _read_raw_table_year(conn, table: str, year: int) -> pd.DataFrame | None:
    """Keep exact duplicate rows visible to the audit; ETL still deduplicates."""
    columns = raw_table_columns(conn, table)
    period_column = pick_existing_column(conn, table, PERIOD_COLUMNS[table])
    if not columns or not period_column:
        return None
    select_list = ", ".join(quote_identifier(column) for column in columns)
    expression = compact_period_expr(period_column)
    params: list = []
    coarse_where = ""
    if (table, period_column) in {("performance", "年月"), ("jingdai", "时间")}:
        coarse_where = append_indexed_year_filter(period_column, year, params)
    params.append(year)
    return pd.read_sql_query(
        f"SELECT {select_list} FROM {quote_identifier(table)} WHERE 1=1 {coarse_where} "
        f"AND CAST(substr({expression},1,4) AS INTEGER)=?", conn, params=params,
    )


def _table_exists(conn, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    )


def _row_count(conn, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] or 0)


def _sum_column(conn, table: str, column: str, year: int | None = None) -> float:
    if not _table_exists(conn, table):
        return 0.0
    where = " WHERE year = ?" if year is not None else ""
    params = (year,) if year is not None else ()
    row = conn.execute(f'SELECT SUM("{column}") FROM "{table}"{where}', params).fetchone()
    return round(float(row[0] or 0), 2)


def _expected_sum(rows: list[dict], column: str, year: int | None = None) -> float:
    total = 0.0
    for row in rows:
        if year is not None and int(row.get("year") or 0) != year:
            continue
        total += float(row.get(column) or 0)
    return round(total, 2)


def _raw_duplicate_issues(raw_tables: dict[str, pd.DataFrame]) -> list[AuditIssue]:
    issues = []
    for table, df in raw_tables.items():
        if df.empty:
            continue
        duplicate_rows = len(df) - len(df.drop_duplicates())
        if duplicate_rows <= 0:
            continue
        ratio = duplicate_rows / len(df)
        severity = "error" if ratio >= 0.1 else "warning"
        issues.append(
            AuditIssue(
                severity=severity,
                code="raw_duplicate_rows",
                message=f"{table} contains duplicate raw rows",
                context={
                    "table": table,
                    "rows": len(df),
                    "duplicate_rows": duplicate_rows,
                    "duplicate_ratio": round(ratio, 4),
                },
            )
        )
    return issues


def _compare_aggregates(conn, expected_rows: dict[str, list[dict]], years: list[int]) -> list[AuditIssue]:
    issues = []
    # Explicit dimensions/columns make a missing schema element a failure rather
    # than quietly dropping it from the comparison. Values never enter reports.
    monthly = ["year", "month", "channel"]
    daily = ["year", "month", "day", "channel"]
    premiums = ["qj_premium", "gm_premium", "zs_premium"]
    headcounts = ["start_headcount", "end_headcount", "active_headcount"]
    checks = {
        "agg_performance": (monthly, premiums),
        "agg_org_performance": (monthly + ["org"], premiums),
        "agg_jingdai": (["year", "month"], premiums),
        "agg_hr_data": (monthly, headcounts),
        "agg_org_hr_data": (monthly + ["org"], headcounts),
        "agg_daily_performance": (daily, premiums),
        "agg_jingdai_daily": (["year", "month", "day"], premiums),
        "agg_longterm_qj": (daily + ["business_type", "org"], ["qj_premium"]),
        "agg_org_daily_performance": (daily + ["org"], premiums),
        "agg_product_daily": (daily + ["business_type", "org", "product_category", "product_name"], ["qj_premium", "gm_premium", "count"]),
        "agg_zhituo_performance": (daily + ["org", "product_name", "product_type", "payment_period"], ["qj_premium", "gm_premium", "policy_count"]),
        "agg_value_data": (monthly, ["value_premium"]),
        "agg_org_value": (monthly + ["org"], ["value_premium"]),
    }
    for table, (dimensions, columns) in checks.items():
        if table not in expected_rows:
            continue
        expected = expected_rows[table]
        if not _table_exists(conn, table):
            issues.append(AuditIssue("error", "missing_aggregate_table", "Required aggregate table is missing", {"table": table}))
            continue
        available = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        missing = sorted(set(dimensions + columns) - available)
        if missing:
            issues.append(AuditIssue("error", "missing_aggregate_columns", "Required aggregate columns are missing", {"table": table, "columns": missing}))
            continue
        for year in years:
            expected_count = len([r for r in expected if int(r.get("year") or 0) == year])
            if table in {"agg_hr_data", "agg_org_hr_data"}:
                year_current_count = int(conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE year = ?', (year,)).fetchone()[0] or 0)
                if year_current_count != expected_count:
                    issues.append(
                        AuditIssue(
                            severity="error",
                            code="aggregate_row_count_mismatch",
                            message=f"{table} row count differs from rebuilt raw-table expectation",
                            context={"table": table, "year": year, "current": year_current_count, "expected": expected_count},
                        )
                    )
        # Annual totals can agree while individual months/branches are wrong.
        # Keep diagnostics at business dimensions; never return policy/person IDs.
        if dimensions and columns:
            expected_groups = defaultdict(lambda: defaultdict(float))
            for row in expected:
                if int(row.get("year") or 0) not in years:
                    continue
                key = tuple(row.get(dim) for dim in dimensions)
                for column in columns:
                    expected_groups[key][column] += float(row.get(column) or 0)
            dims = ", ".join(f'"{dim}"' for dim in dimensions)
            sums = ", ".join(f'SUM("{column}") AS "{column}"' for column in columns)
            marks = ",".join("?" for _ in years)
            rows = conn.execute(f'SELECT {dims}, {sums} FROM "{table}" WHERE year IN ({marks}) GROUP BY {dims}', years).fetchall()
            current_groups = {tuple(row[dim] for dim in dimensions): dict(row) for row in rows}
            mismatch_count = 0
            for key in set(expected_groups) | set(current_groups):
                if key not in expected_groups or key not in current_groups or any(abs(expected_groups.get(key, {}).get(col, 0) - float(current_groups.get(key, {}).get(col) or 0)) > 0.010001 for col in columns):
                    mismatch_count += 1
            if mismatch_count:
                issues.append(AuditIssue("error", "aggregate_dimension_mismatch", "Business-dimension totals differ from raw-table expectation", {"table": table, "dimensions": dimensions, "mismatch_groups": mismatch_count}))
        for year in years:
            for column in columns:
                current_sum = _sum_column(conn, table, column, year)
                expected_sum = _expected_sum(expected, column, year)
                if abs(current_sum - expected_sum) > 0.01:
                    issues.append(
                        AuditIssue(
                            severity="error",
                            code="aggregate_sum_mismatch",
                            message=f"{table}.{column} differs from rebuilt raw-table expectation",
                            context={
                                "table": table,
                                "column": column,
                                "year": year,
                                "current": current_sum,
                                "expected": expected_sum,
                                "gap": round(current_sum - expected_sum, 2),
                            },
                        )
                    )
    return issues


def _kpi_invariant_issues(conn, year: int) -> list[AuditIssue]:
    kpi = get_kpi_data(year, connection_override=conn)
    issues = []
    qj_total = float(kpi.get("qj_premium", {}).get("total") or 0)
    longterm = float(kpi.get("longterm_qj") or 0)
    if qj_total > 0 and longterm - qj_total > 0.01:
        issues.append(
            AuditIssue(
                severity="error",
                code="longterm_exceeds_total_qj",
                message="longterm qj premium exceeds total qj premium",
                context={"year": year, "qj_total": qj_total, "longterm_qj": longterm},
            )
        )

    hr = kpi.get("hr") or {}
    total_avg_headcount = 0.0
    total_active = 0.0
    for channel, row in hr.items():
        months = float(row.get("months") or 0)
        avg_sum = float(row.get("avg_sum") or 0)
        avg_headcount = avg_sum / months if months > 0 else float(row.get("avg") or 0)
        active = float(row.get("active") or 0)
        total_avg_headcount += avg_headcount
        total_active += active
        if avg_headcount > 0 and active / avg_headcount > 1.2:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="activity_rate_high",
                    message="activity headcount is unusually high compared with average headcount",
                    context={
                        "year": year,
                        "channel": channel,
                        "active": active,
                        "avg_headcount": round(avg_headcount, 2),
                        "rate": round(active / avg_headcount, 4),
                    },
                )
            )
    transform_premium = float(kpi.get("qj_premium", {}).get("total_transform") or 0)
    if transform_premium > 0 and total_avg_headcount <= 0:
        issues.append(
            AuditIssue(
                severity="error",
                code="missing_headcount_denominator",
                message="transform premium exists but average headcount denominator is empty",
                context={"year": year, "transform_premium": transform_premium},
            )
        )
    return issues


def run_data_quality_audit(year: int) -> dict:
    issues = []
    raw_tables = {}
    try:
        with get_db() as conn:
            for table in RAW_TABLES:
                frame = _read_raw_table_year(conn, table, year)
                if frame is None:
                    issues.append(AuditIssue("error", "missing_raw_schema", "Required raw table or period column is missing", {"table": table}))
                else:
                    raw_tables[table] = frame
            if not any(not frame.empty for frame in raw_tables.values()):
                issues.append(AuditIssue("error", "missing_raw_data", "No source data is available for the requested year", {"year": year}))
            issues.extend(_raw_duplicate_issues(raw_tables))
            # Keep existing rebuild semantics, while reporting duplicates above.
            config_map = _load_jingdai_product_config(conn) if "jingdai" in raw_tables and not raw_tables["jingdai"].empty else {}
            expected_rows = build_aggregate_rows_from_raw(
                {table: frame.drop_duplicates() for table, frame in raw_tables.items()},
                jingdai_config_map=config_map,
            ) if raw_tables else {table: [] for table in AGG_TABLES}
            issues.extend(_compare_aggregates(conn, expected_rows, [year]))
            try:
                issues.extend(_kpi_invariant_issues(conn, year))
            except sqlite3.Error:
                issues.append(AuditIssue("error", "kpi_schema_unavailable", "KPI prerequisites are missing; no schema repair was attempted", {}))
    except (sqlite3.Error, ValueError, KeyError) as exc:
        # Exception text may include business values or local paths. Report only
        # its class, and fail closed without attempting repairs or migrations.
        issues.append(AuditIssue("error", "audit_execution_failed", "Read-only audit could not complete; no repair was attempted", {"error_type": type(exc).__name__}))
    status = "fail" if any(i.severity == "error" for i in issues) else ("warn" if issues else "ok")
    return {
        "status": status,
        "year": year,
        "issue_count": len(issues),
        "issues": [asdict(i) for i in issues],
        "source_coverage": {table: {"available": table in raw_tables, "rows": len(raw_tables[table]) if table in raw_tables else None} for table in RAW_TABLES},
    }
