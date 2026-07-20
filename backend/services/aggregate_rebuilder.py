"""Rebuild aggregate tables from raw SQLite detail tables."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from db import clear_table_year_data, get_db, init_db, replace_rows
from db.schema import AGG_TABLES
from etl import (
    aggregate_active_headcount,
    aggregate_daily_performance,
    aggregate_hr,
    aggregate_jingdai,
    aggregate_jingdai_daily,
    aggregate_jingdai_longterm,
    aggregate_jingdai_payment_period,
    aggregate_jingdai_payment_period_daily,
    aggregate_org_active_headcount,
    aggregate_org_daily_performance,
    aggregate_org_hr,
    aggregate_org_performance,
    aggregate_org_value,
    aggregate_payment_period,
    aggregate_payment_period_daily,
    aggregate_performance,
    aggregate_product_structure,
    aggregate_transform_longterm,
    aggregate_value,
)
from services.raw_table_reader import read_raw_table_dataframe


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


def build_aggregate_rows_from_raw(raw_tables: dict[str, pd.DataFrame]) -> dict[str, list[dict]]:
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
        table_rows["agg_product_structure"] = aggregate_product_structure(perf)
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


def rebuild_aggregates_from_raw_tables() -> RebuildResult:
    """Rebuild aggregate tables from raw detail tables already stored in SQLite."""
    init_db()
    with get_db() as conn:
        raw_tables = {
            table: df
            for table in RAW_TABLES
            if (df := _read_raw_table(conn, table)) is not None
        }
        raw_counts = {table: len(df) for table, df in raw_tables.items()}
        if not any(raw_counts.values()):
            raise RuntimeError("SQLite raw tables are empty; upload Excel or run rebuild_from_excels.py first")

        table_rows = build_aggregate_rows_from_raw(raw_tables)
        years = _years_from_rows(table_rows)
        if not years:
            raise RuntimeError("raw tables did not produce any aggregate rows")

        conn.execute("BEGIN IMMEDIATE")
        try:
            for year in years:
                for table in AGG_TABLES:
                    clear_table_year_data(conn, table, year)
            table_counts = {}
            for table, rows in table_rows.items():
                replace_rows(conn, table, rows)
                table_counts[table] = len(rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return RebuildResult(years=years, table_counts=table_counts, raw_counts=raw_counts)
