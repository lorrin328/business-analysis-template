"""Rebuild aggregate tables from raw SQLite detail tables."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from db import clear_table_year_data, get_db, init_db, replace_rows
from db.schema import AGG_TABLES
from etl import (
    aggregate_active_headcount,
    aggregate_daily_performance,
    aggregate_jingdai_product_daily,
    aggregate_hr,
    aggregate_jingdai,
    aggregate_jingdai_daily,
    aggregate_jingdai_longterm,
    aggregate_jingdai_payment_period,
    aggregate_jingdai_payment_period_daily,
    aggregate_org_active_headcount,
    aggregate_org_daily_performance,
    aggregate_org_daily_activity,
    aggregate_org_hr,
    aggregate_org_performance,
    aggregate_org_value,
    aggregate_payment_period,
    aggregate_payment_period_daily,
    aggregate_performance,
    aggregate_product_structure,
    aggregate_staff_month_performance,
    aggregate_transform_product_daily,
    aggregate_transform_longterm,
    aggregate_zhituo_performance,
    aggregate_value,
)
from services.raw_table_reader import (
    append_indexed_year_filter,
    compact_period_expr,
    pick_existing_column,
    quote_identifier,
    raw_table_columns,
    read_raw_table_dataframe,
)
from etl.aggregates.org_zero_streak import ACTIVITY_SOURCE_COLUMNS


RAW_TABLES = ("performance", "jingdai", "hr_data", "value_data")


@dataclass
class RebuildResult:
    years: list[int]
    table_counts: dict[str, int]
    raw_counts: dict[str, int]


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _read_raw_table(conn, table: str) -> pd.DataFrame | None:
    if not _table_exists(conn, table):
        return None
    return read_raw_table_dataframe(conn, table).drop_duplicates()


PERIOD_COLUMNS = {
    "performance": ["年月", "年月日", "入账时间", "承保时间"],
    "jingdai": ["时间", "年月", "年月日", "承保日期"],
    "hr_data": ["统计日期", "年月", "统计月"],
    "value_data": ["年月", "时间"],
}


def _period_column(conn, table: str) -> str | None:
    return pick_existing_column(conn, table, PERIOD_COLUMNS.get(table, []))


def _raw_years(conn, table: str) -> list[int]:
    column = _period_column(conn, table)
    if not column:
        return []
    expression = compact_period_expr(column)
    rows = conn.execute(
        f"""SELECT DISTINCT CAST(substr({expression},1,4) AS INTEGER)
            FROM {quote_identifier(table)}
            WHERE CAST(substr({expression},1,4) AS INTEGER) BETWEEN 1900 AND 2100
            ORDER BY 1"""
    ).fetchall()
    return [int(row[0]) for row in rows]


def _read_raw_table_year(conn, table: str, year: int) -> pd.DataFrame | None:
    if not _table_exists(conn, table):
        return None
    columns = raw_table_columns(conn, table)
    period_column = _period_column(conn, table)
    if not columns or not period_column:
        return None
    select_list = ", ".join(quote_identifier(column) for column in columns)
    expression = compact_period_expr(period_column)
    params: list = []
    coarse_where = ""
    if (table, period_column) in {("performance", "年月"), ("jingdai", "时间")}:
        coarse_where = append_indexed_year_filter(period_column, year, params)
    params.append(year)
    frame = pd.read_sql_query(
        f"""SELECT {select_list} FROM {quote_identifier(table)}
            WHERE 1=1 {coarse_where}
              AND CAST(substr({expression},1,4) AS INTEGER)=?""",
        conn,
        params=params,
    )
    return frame.drop_duplicates()


def _merge_active_headcount(hr_rows: list[dict], active_rows: list[dict]) -> None:
    active_index = {
        (r["year"], r["month"], r["channel"]): r["active_headcount"]
        for r in active_rows
    }
    for row in hr_rows:
        row["active_headcount"] = active_index.get(
            (row["year"], row["month"], row["channel"]),
            0,
        )


def _merge_org_active_headcount(org_hr_rows: list[dict], org_active_rows: list[dict]) -> None:
    active_index = {
        (r["year"], r["month"], r["org"], r["channel"]): r["active_headcount"]
        for r in org_active_rows
    }
    for row in org_hr_rows:
        row["active_headcount"] = active_index.get(
            (row["year"], row["month"], row["org"], row["channel"]),
            0,
        )


def _years_from_rows(table_rows: dict[str, list[dict]]) -> list[int]:
    years = {
        int(row["year"])
        for rows in table_rows.values()
        for row in rows
        if row.get("year")
    }
    return sorted(years)


def build_aggregate_rows_from_raw(
    raw_tables: dict[str, pd.DataFrame], *, include_org_activity: bool = True,
) -> dict[str, list[dict]]:
    """Build all aggregate table rows from raw DataFrames."""
    perf = raw_tables.get("performance")
    jingdai = raw_tables.get("jingdai")
    hr = raw_tables.get("hr_data")
    value = raw_tables.get("value_data")

    table_rows: dict[str, list[dict]] = {table: [] for table in AGG_TABLES}

    if perf is not None and not perf.empty:
        table_rows["agg_performance"] = aggregate_performance(perf)
        table_rows["agg_daily_performance"] = aggregate_daily_performance(perf)
        table_rows["agg_org_daily_performance"] = aggregate_org_daily_performance(perf)
        if include_org_activity:
            table_rows["agg_org_daily_activity"] = aggregate_org_daily_activity(perf)
        table_rows["agg_product_structure"] = aggregate_product_structure(perf)
        table_rows["agg_staff_month_performance"] = aggregate_staff_month_performance(perf)
        table_rows["agg_product_daily"].extend(aggregate_transform_product_daily(perf))
        table_rows["agg_zhituo_performance"] = aggregate_zhituo_performance(perf)
        table_rows["agg_org_performance"] = aggregate_org_performance(perf)
        table_rows["agg_payment_period"].extend(aggregate_payment_period(perf))
        table_rows["agg_payment_period_daily"].extend(aggregate_payment_period_daily(perf))
        table_rows["agg_longterm_qj"].extend(aggregate_transform_longterm(perf))
        active_rows = aggregate_active_headcount(perf)
        org_active_rows = aggregate_org_active_headcount(perf)
    else:
        active_rows = []
        org_active_rows = []

    if jingdai is not None and not jingdai.empty:
        table_rows["agg_jingdai"] = aggregate_jingdai(jingdai)
        table_rows["agg_jingdai_daily"] = aggregate_jingdai_daily(jingdai)
        table_rows["agg_payment_period"].extend(aggregate_jingdai_payment_period(jingdai))
        table_rows["agg_payment_period_daily"].extend(aggregate_jingdai_payment_period_daily(jingdai))
        table_rows["agg_longterm_qj"].extend(aggregate_jingdai_longterm(jingdai))
        table_rows["agg_product_daily"].extend(aggregate_jingdai_product_daily(jingdai))

    if hr is not None and not hr.empty:
        table_rows["agg_hr_data"] = aggregate_hr(hr)
        table_rows["agg_org_hr_data"] = aggregate_org_hr(hr)
        if active_rows:
            _merge_active_headcount(table_rows["agg_hr_data"], active_rows)
        if org_active_rows:
            _merge_org_active_headcount(table_rows["agg_org_hr_data"], org_active_rows)

    if value is not None and not value.empty:
        table_rows["agg_value_data"] = aggregate_value(value)
        table_rows["agg_org_value"] = aggregate_org_value(value)

    return table_rows


def _read_org_activity_rows(conn, *, source_columns: list[str] | None = None) -> list[dict]:
    """Scan only required columns in bounded chunks, independent of legacy year slicing.

    A malformed 年月 must not hide an otherwise valid 业绩归属日, nor may an
    unidentifiable date disappear from this new quality-sensitive aggregate.
    """
    available = set(raw_table_columns(conn, "performance"))
    if not available:
        return []
    effective = available if source_columns is None else set(source_columns)
    columns = [column for column in ACTIVITY_SOURCE_COLUMNS if column in effective]
    if not columns:
        return []
    # Read-only import preflight can project the schema after new columns are
    # added: a newly introduced 年月日 is NULL for all retained historical rows.
    select_list = ", ".join(
        quote_identifier(column) if column in available else f"NULL AS {quote_identifier(column)}"
        for column in columns
    )
    merged: dict[tuple, dict] = {}
    for frame in pd.read_sql_query(f'SELECT {select_list} FROM "performance"', conn, chunksize=50000):
        for row in aggregate_org_daily_activity(frame):
            key = tuple(row[column] for column in ("year", "month", "day", "org", "channel"))
            if key in merged:
                merged[key]["has_positive_qj"] = max(merged[key]["has_positive_qj"], row["has_positive_qj"])
                merged[key]["uncertain"] = max(merged[key]["uncertain"], row["uncertain"])
            else:
                merged[key] = row
    return list(merged.values())


def replace_org_activity_from_raw(conn) -> int:
    """Replace this table only, after all evidence has been read successfully."""
    activity_rows = _read_org_activity_rows(conn)
    conn.execute("DELETE FROM agg_org_daily_activity")
    replace_rows(conn, "agg_org_daily_activity", activity_rows)
    return len(activity_rows)


def rebuild_aggregates_from_raw_tables() -> RebuildResult:
    """Rebuild aggregates one year at a time so multi-million-row history stays bounded."""
    init_db()
    with get_db() as conn:
        stored_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()[0]
            for table in RAW_TABLES
            if _table_exists(conn, table)
        }
        if not any(stored_counts.values()):
            raise RuntimeError("SQLite raw tables are empty; upload Excel or run rebuild_from_excels.py first")
        raw_counts = {table: 0 for table in stored_counts}
        years = sorted({year for table in RAW_TABLES for year in _raw_years(conn, table)})
        if not years:
            raise RuntimeError("raw tables did not produce any aggregate rows")

        conn.execute("BEGIN IMMEDIATE")
        try:
            table_counts = {table: 0 for table in AGG_TABLES}
            activity_rows = _read_org_activity_rows(conn)
            for year in years:
                raw_tables = {
                    table: frame
                    for table in RAW_TABLES
                    if (frame := _read_raw_table_year(conn, table, year)) is not None
                }
                for table, frame in raw_tables.items():
                    raw_counts[table] += len(frame)
                table_rows = build_aggregate_rows_from_raw(raw_tables, include_org_activity=False)
                for table in AGG_TABLES:
                    if table == "agg_org_daily_activity":
                        continue
                    clear_table_year_data(conn, table, year)
                    rows = table_rows.get(table, [])
                    replace_rows(conn, table, rows)
                    table_counts[table] += len(rows)
            conn.execute("DELETE FROM agg_org_daily_activity")
            replace_rows(conn, "agg_org_daily_activity", activity_rows)
            table_counts["agg_org_daily_activity"] = len(activity_rows)
            conn.commit()
            # Refresh planner statistics after a bulk rebuild so the first
            # dashboard request does not pay for stale index choices.
            conn.execute("PRAGMA optimize")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return RebuildResult(years=years, table_counts=table_counts, raw_counts=raw_counts)
