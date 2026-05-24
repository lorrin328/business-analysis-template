"""Data quality audit checks for metric and aggregate consistency."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from db import get_db, get_kpi_data, init_db
from db.schema import AGG_TABLES
from services.aggregate_rebuilder import RAW_TABLES, _read_raw_table, build_aggregate_rows_from_raw


@dataclass
class AuditIssue:
    severity: str
    code: str
    message: str
    context: dict


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
    checks = {
        "agg_hr_data": ["start_headcount", "end_headcount", "active_headcount"],
        "agg_org_hr_data": ["start_headcount", "end_headcount", "active_headcount"],
        "agg_daily_performance": ["qj_premium", "gm_premium", "zs_premium"],
        "agg_jingdai_daily": ["qj_premium", "gm_premium", "zs_premium"],
        "agg_longterm_qj": ["qj_premium"],
    }
    for table, columns in checks.items():
        expected = expected_rows.get(table, [])
        if not expected or not _table_exists(conn, table):
            continue
        for year in years:
            current_count = _row_count(conn, table)
            expected_count = len([r for r in expected if int(r.get("year") or 0) == year])
            if current_count and expected_count and table in {"agg_hr_data", "agg_org_hr_data"}:
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


def _kpi_invariant_issues(year: int) -> list[AuditIssue]:
    kpi = get_kpi_data(year)
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
    init_db()
    with get_db() as conn:
        raw_tables = {
            table: df
            for table in RAW_TABLES
            if (df := _read_raw_table(conn, table)) is not None
        }
        expected_rows = build_aggregate_rows_from_raw(raw_tables) if raw_tables else {table: [] for table in AGG_TABLES}
        years = sorted({
            int(row["year"])
            for rows in expected_rows.values()
            for row in rows
            if row.get("year")
        })
        audit_years = [year] if year in years else years[-1:]
        issues = []
        issues.extend(_raw_duplicate_issues(raw_tables))
        issues.extend(_compare_aggregates(conn, expected_rows, audit_years))
    issues.extend(_kpi_invariant_issues(year))
    status = "fail" if any(i.severity == "error" for i in issues) else ("warn" if issues else "ok")
    return {
        "status": status,
        "year": year,
        "issue_count": len(issues),
        "issues": [asdict(i) for i in issues],
    }
