"""Shared Excel import pipeline for uploads and full rebuilds."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from db import clear_table_year_data, replace_rows, replace_rows_incremental
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
    parse_hr_excel,
    parse_jingdai_excel,
    parse_performance_excel,
    parse_value_excel,
)
from services.import_safety import (
    RawIncrementalWriteError,
    extract_raw_periods,
    write_raw_table_incremental,
    append_raw_frame,
    validate_replacement_fields,
    read_raw_periods,
    IMPORT_MODES,
    raw_period_config, raw_periods_predicate,
)
from etl.aggregates.org_zero_streak import ACTIVITY_SOURCE_COLUMNS, extract_org_activity_periods
from services.aggregate_rebuilder import _read_org_activity_rows, replace_org_activity_from_raw
from services.raw_table_reader import raw_table_columns, quote_identifier
from etl.normalize import _period_year_month
from services.product_config_service import extract_jingdai_products_to_config
from etl.aggregates.jingdai import _load_jingdai_product_config
from validators.data_validator import validate_rows
from services.customer_fact_refresh import policy_key, refresh_customer_facts


AGGREGATE_TABLE_ORDER = [
    "agg_performance",
    "agg_daily_performance",
    "agg_org_daily_performance",
    "agg_org_daily_activity",
    "agg_product_structure",
    "agg_staff_month_performance",
    "agg_product_daily",
    "agg_zhituo_performance",
    "agg_jingdai",
    "agg_jingdai_daily",
    "agg_hr_data",
    "agg_org_hr_data",
    "agg_value_data",
    "agg_org_performance",
    "agg_org_value",
    "agg_payment_period",
    "agg_payment_period_daily",
    "agg_longterm_qj",
]

RAW_TABLE_ORDER = ["performance", "jingdai", "hr_data", "value_data"]

# Source coverage drives deletion even when a corrected source produces no rows.
# Shared tables must retain the other source's business_type partition.
CONDITIONAL_AGGREGATE_SOURCES = {
    "agg_zhituo_performance": (("performance", None),),
    "agg_org_daily_activity": (("performance", None),),
    "agg_daily_performance": (("performance", None),),
    "agg_org_daily_performance": (("performance", None),),
    "agg_longterm_qj": (("performance", "转型"), ("jingdai", "经代")),
    "agg_payment_period": (("performance", "转型"), ("jingdai", "经代")),
    "agg_payment_period_daily": (("performance", "转型"), ("jingdai", "经代")),
    "agg_product_daily": (("performance", "转型"), ("jingdai", "经代")),
}


def _monthly_periods(table: str, frame: pd.DataFrame) -> set[tuple[int, int]]:
    if frame.empty:
        return set()
    year_col, month_col, _ = raw_period_config(table, frame)
    if not month_col:
        return set()
    work = _period_year_month(frame, year_col, month_col)
    return set(map(tuple, work[["_year", "_month"]].drop_duplicates().itertuples(index=False, name=None)))


def _read_monthly_source(conn, table: str, periods: set[tuple[int, int]]) -> pd.DataFrame:
    """Human-resource activity follows the monthly field, not the booking day."""
    columns = raw_table_columns(conn, table)
    if not columns or not periods:
        return pd.DataFrame(columns=columns)
    year_col, month_col, _ = raw_period_config(table, pd.DataFrame(columns=columns))
    if not month_col:
        return pd.DataFrame(columns=columns)
    where, params = raw_periods_predicate(periods, (year_col, month_col, None))
    names = ",".join(map(quote_identifier, columns))
    return pd.read_sql_query(f'SELECT {names} FROM {quote_identifier(table)} WHERE {where}', conn, params=params)


def _refresh_hr_from_current_sources(conn, periods: set[tuple[int, int]]) -> dict[str, int]:
    """Refresh dependent monthly HR totals inside the import savepoint."""
    if not periods:
        return {}
    hr = _read_monthly_source(conn, "hr_data", periods)
    performance = _read_monthly_source(conn, "performance", periods)
    rows = aggregate_hr(hr) if not hr.empty else []
    org_rows = aggregate_org_hr(hr) if not hr.empty else []
    result = {"agg_hr_data": rows, "agg_org_hr_data": org_rows}
    if rows and not performance.empty:
        result["_active_headcount"] = aggregate_active_headcount(performance)
    if org_rows and not performance.empty:
        result["_org_active_headcount"] = aggregate_org_active_headcount(performance)
    _backfill_active_headcount(result)
    for table in ("agg_hr_data", "agg_org_hr_data"):
        for year, month in sorted(periods):
            conn.execute(f'DELETE FROM "{table}" WHERE year=? AND month=?', (int(year), int(month)))
        replace_rows(conn, table, result[table])
    return {table: len(result[table]) for table in ("agg_hr_data", "agg_org_hr_data")}


@dataclass(frozen=True)
class ExcelSource:
    """One logical source workbook loaded as bytes."""

    kind: str
    filename: str
    content: bytes


@dataclass
class ExcelPipelineResult:
    """Parsed raw tables and derived aggregate rows."""

    rows_by_table: dict[str, list[dict]] = field(default_factory=dict)
    raw_tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    source_summaries: list[str] = field(default_factory=list)
    data_years: list[int] = field(default_factory=list)
    cutoff_warnings: list[str] = field(default_factory=list)

    def row_count(self, table: str) -> int:
        rows = self.rows_by_table.get(table)
        if rows is not None:
            return len(rows)
        frame = self.raw_tables.get(table)
        return len(frame) if frame is not None else 0


def _daily_cutoffs_by_year(rows: list[dict]) -> dict[int, tuple[int, int]]:
    cutoffs: dict[int, tuple[int, int]] = {}
    for row in rows or []:
        year = row.get("year")
        month = row.get("month")
        day = row.get("day")
        if not year or not month or not day:
            continue
        key = int(year)
        value = (int(month), int(day))
        if key not in cutoffs or value > cutoffs[key]:
            cutoffs[key] = value
    return cutoffs


def validate_daily_cutoff_alignment(
    performance_daily_rows: list[dict],
    jingdai_daily_rows: list[dict],
) -> list[str]:
    """Return warnings when transform and jingdai daily cutoffs differ."""

    perf_cutoffs = _daily_cutoffs_by_year(performance_daily_rows)
    jd_cutoffs = _daily_cutoffs_by_year(jingdai_daily_rows)
    warnings = []
    for year in sorted(set(perf_cutoffs) & set(jd_cutoffs)):
        if perf_cutoffs[year] != jd_cutoffs[year]:
            pm, pd = perf_cutoffs[year]
            jm, jd = jd_cutoffs[year]
            cm, cd = min(perf_cutoffs[year], jd_cutoffs[year])
            warnings.append(
                f"{year}年转型与经代日级数据截止日不同：转型{pm}月{pd}日，经代{jm}月{jd}日；"
                f"混合统计将按共同截止日{cm}月{cd}日计算。"
            )
    return warnings


def _require_valid_rows(rows: list[dict], required: list[str], unique_keys: list[str]) -> None:
    validation = validate_rows(rows, required=required, unique_keys=unique_keys)
    if not validation.valid:
        raise ValueError(validation.to_dict())


def _merge_rows(target: dict[str, list[dict]], table: str, rows: list[dict]) -> None:
    if rows:
        target.setdefault(table, []).extend(rows)


def _collect_years(rows_by_table: dict[str, list[dict]]) -> list[int]:
    years = {
        int(row["year"])
        for table in AGGREGATE_TABLE_ORDER
        for row in rows_by_table.get(table, [])
        if row.get("year")
    }
    return sorted(years)


def _backfill_active_headcount(rows_by_table: dict[str, list[dict]]) -> None:
    hr_rows = rows_by_table.get("agg_hr_data", [])
    active_rows = rows_by_table.pop("_active_headcount", [])
    if hr_rows and active_rows:
        active_index = {
            (row["year"], row["month"], row["channel"]): row["active_headcount"]
            for row in active_rows
        }
        for row in hr_rows:
            row["active_headcount"] = active_index.get((row["year"], row["month"], row["channel"]), 0)

    org_hr_rows = rows_by_table.get("agg_org_hr_data", [])
    org_active_rows = rows_by_table.pop("_org_active_headcount", [])
    if org_hr_rows and org_active_rows:
        org_active_index = {
            (row["year"], row["month"], row["org"], row["channel"]): row["active_headcount"]
            for row in org_active_rows
        }
        for row in org_hr_rows:
            row["active_headcount"] = org_active_index.get(
                (row["year"], row["month"], row["org"], row["channel"]),
                0,
            )


def _parse_performance(source: ExcelSource, result: ExcelPipelineResult) -> None:
    frame = parse_performance_excel(source.content)
    result.raw_tables["performance"] = frame

    perf_rows = aggregate_performance(frame)
    _require_valid_rows(perf_rows, ["year", "month", "channel"], ["year", "month", "channel"])
    daily_rows = aggregate_daily_performance(frame)
    org_perf_rows = aggregate_org_performance(frame)
    pay_period_rows = aggregate_payment_period(frame)
    pay_period_daily_rows = aggregate_payment_period_daily(frame)
    longterm_rows = aggregate_transform_longterm(frame)

    rows = result.rows_by_table
    _merge_rows(rows, "agg_performance", perf_rows)
    _merge_rows(rows, "agg_daily_performance", daily_rows)
    _merge_rows(rows, "agg_org_daily_performance", aggregate_org_daily_performance(frame))
    _merge_rows(rows, "agg_org_daily_activity", aggregate_org_daily_activity(frame))
    _merge_rows(rows, "agg_product_structure", aggregate_product_structure(frame))
    _merge_rows(rows, "agg_staff_month_performance", aggregate_staff_month_performance(frame))
    _merge_rows(rows, "agg_product_daily", aggregate_transform_product_daily(frame))
    _merge_rows(rows, "agg_zhituo_performance", aggregate_zhituo_performance(frame))
    _merge_rows(rows, "_active_headcount", aggregate_active_headcount(frame))
    _merge_rows(rows, "_org_active_headcount", aggregate_org_active_headcount(frame))
    _merge_rows(rows, "agg_org_performance", org_perf_rows)
    _merge_rows(rows, "agg_payment_period", pay_period_rows)
    _merge_rows(rows, "agg_payment_period_daily", pay_period_daily_rows)
    _merge_rows(rows, "agg_longterm_qj", longterm_rows)
    result.source_summaries.append(
        f"performance: {source.filename} -> {len(perf_rows)} monthly, "
        f"{len(daily_rows)} daily, {len(org_perf_rows)} org rows, "
        f"{len(pay_period_rows)} pay period rows, {len(longterm_rows)} longterm rows"
    )


def _parse_jingdai(source: ExcelSource, result: ExcelPipelineResult) -> None:
    frame = parse_jingdai_excel(source.content)
    result.raw_tables["jingdai"] = frame
    # Parsing must not access or update product settings. Final classification is
    # calculated with the transaction's configuration when the import is written.
    jd_rows = aggregate_jingdai(frame, config_map={})
    _require_valid_rows(jd_rows, ["year", "month"], ["year", "month"])
    jd_daily_rows = aggregate_jingdai_daily(frame, config_map={})
    jd_pay_period_rows = aggregate_jingdai_payment_period(frame)
    jd_pay_period_daily_rows = aggregate_jingdai_payment_period_daily(frame)
    jd_longterm_rows = aggregate_jingdai_longterm(frame)

    rows = result.rows_by_table
    _merge_rows(rows, "agg_jingdai", jd_rows)
    _merge_rows(rows, "agg_jingdai_daily", jd_daily_rows)
    _merge_rows(rows, "agg_payment_period", jd_pay_period_rows)
    _merge_rows(rows, "agg_payment_period_daily", jd_pay_period_daily_rows)
    _merge_rows(rows, "agg_longterm_qj", jd_longterm_rows)
    _merge_rows(rows, "agg_product_daily", aggregate_jingdai_product_daily(frame))
    result.source_summaries.append(
        f"jingdai: {source.filename} -> {len(jd_rows)} monthly, "
        f"{len(jd_daily_rows)} daily, {len(jd_pay_period_rows)} pay period rows, "
        f"{len(jd_longterm_rows)} longterm rows"
    )


def _parse_hr(source: ExcelSource, result: ExcelPipelineResult) -> None:
    frame = parse_hr_excel(source.content)
    result.raw_tables["hr_data"] = frame
    hr_rows = aggregate_hr(frame)
    org_hr_rows = aggregate_org_hr(frame)
    _merge_rows(result.rows_by_table, "agg_hr_data", hr_rows)
    _merge_rows(result.rows_by_table, "agg_org_hr_data", org_hr_rows)
    result.source_summaries.append(f"hr: {source.filename} -> {len(hr_rows)} rows, {len(org_hr_rows)} org rows")


def _parse_value(source: ExcelSource, result: ExcelPipelineResult) -> None:
    frame = parse_value_excel(source.content)
    result.raw_tables["value_data"] = frame
    value_rows = aggregate_value(frame)
    org_value_rows = aggregate_org_value(frame)
    _merge_rows(result.rows_by_table, "agg_value_data", value_rows)
    _merge_rows(result.rows_by_table, "agg_org_value", org_value_rows)
    result.source_summaries.append(
        f"value: {source.filename} -> {len(value_rows)} rows, {len(org_value_rows)} org rows"
    )


PARSERS: dict[str, Callable[[ExcelSource, ExcelPipelineResult], None]] = {
    "performance": _parse_performance,
    "jingdai": _parse_jingdai,
    "hr": _parse_hr,
    "value": _parse_value,
}


def append_excel_source(result: ExcelPipelineResult, source: ExcelSource) -> None:
    parser = PARSERS.get(source.kind)
    if parser is None:
        raise ValueError(f"Unsupported Excel source kind: {source.kind}")
    # A failing aggregate must not leave its raw source in a partial import.
    parsed = ExcelPipelineResult()
    parser(source, parsed)
    result.raw_tables.update(parsed.raw_tables)
    for table, rows in parsed.rows_by_table.items():
        _merge_rows(result.rows_by_table, table, rows)
    result.source_summaries.extend(parsed.source_summaries)


def finalize_excel_pipeline_result(result: ExcelPipelineResult) -> ExcelPipelineResult:
    _backfill_active_headcount(result.rows_by_table)
    result.data_years = _collect_years(result.rows_by_table)
    result.cutoff_warnings = validate_daily_cutoff_alignment(
        result.rows_by_table.get("agg_daily_performance", []),
        result.rows_by_table.get("agg_jingdai_daily", []),
    )
    return result


def build_excel_pipeline_result(sources: list[ExcelSource]) -> ExcelPipelineResult:
    result = ExcelPipelineResult()
    for source in sources:
        append_excel_source(result, source)
    return finalize_excel_pipeline_result(result)


def replace_aggregate_rows(
    conn, result: ExcelPipelineResult, *, incremental: bool, include_org_activity: bool = True,
) -> dict[str, int]:
    table_counts: dict[str, int] = {}
    writer = replace_rows_incremental if incremental else replace_rows
    for table in AGGREGATE_TABLE_ORDER:
        if table == "agg_org_daily_activity" and not include_org_activity:
            continue
        rows = result.rows_by_table.get(table, [])
        sources = CONDITIONAL_AGGREGATE_SOURCES.get(table, ()) if incremental else ()
        covered = False
        for source_table, business_type in sources:
            source_frame = result.raw_tables.get(source_table)
            if source_frame is None or source_frame.empty:
                continue
            if table == "agg_org_daily_activity":
                periods = extract_org_activity_periods(source_frame)
            elif source_table == "jingdai" and table != "agg_product_daily":
                # These jingdai aggregates use 时间/年月 even if a date column exists.
                periods = _monthly_periods(source_table, source_frame)
            else:
                periods, _ = extract_raw_periods(source_table, source_frame)
            if not periods:
                raise RawIncrementalWriteError(f"conditional aggregate {table} has no recognizable source year/month period")
            for year, month in sorted(periods):
                sql = f'DELETE FROM "{table}" WHERE year = ? AND month = ?'
                params = [int(year), int(month)]
                if business_type is not None:
                    sql += ' AND business_type = ?'
                    params.append(business_type)
                conn.execute(sql, params)
            covered = True
        if covered:
            replace_rows(conn, table, rows)
            table_counts[table] = len(rows)
            continue
        if rows:
            writer(conn, table, rows)
            table_counts[table] = len(rows)
    return table_counts


def replace_raw_tables(conn, result: ExcelPipelineResult, *, incremental: bool, import_mode: str = "replace_months") -> dict[str, int]:
    table_counts: dict[str, int] = {}
    for table in RAW_TABLE_ORDER:
        frame = result.raw_tables.get(table)
        if frame is None:
            continue
        if incremental:
            count = write_raw_table_incremental(conn, table, frame, mode=import_mode)
        else:
            # Explicit full rebuild only. Native writes preserve the transaction.
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            append_raw_frame(conn, table, frame)
            count = len(frame)
        table_counts[table] = count
    return table_counts


def write_excel_pipeline_result(conn, result: ExcelPipelineResult, *, incremental: bool, import_mode: str = "replace_months") -> dict[str, int]:
    if import_mode not in IMPORT_MODES:
        raise RawIncrementalWriteError("导入模式仅支持完整月替换或明确的补充模式")
    if import_mode == "supplement" and (not incremental or any(table != "performance" for table in result.raw_tables)):
        raise RawIncrementalWriteError("补充模式仅接受业绩源；人力、经代和价值源请单独使用完整月替换")
    performance = result.raw_tables.get("performance")
    if incremental and import_mode == "replace_months":
        for table, frame in result.raw_tables.items():
            validate_replacement_fields(conn, table, frame)
    affected_keys = set()
    performance_periods = set()
    hr_periods = set()
    hr_source = result.raw_tables.get("hr_data")
    if hr_source is not None:
        hr_periods.update(_monthly_periods("hr_data", hr_source))
    if performance is not None and not performance.empty:
        performance_periods, _ = extract_raw_periods("performance", performance)
        hr_periods.update(_monthly_periods("performance", performance))
        if incremental:
            old = read_raw_periods(conn, "performance", performance_periods)
            hr_periods.update(_monthly_periods("performance", old))
            if "投保单号" in old.columns:
                affected_keys.update(policy_key(value) for value in old["投保单号"])
        if "投保单号" in performance.columns:
            affected_keys.update(policy_key(value) for value in performance["投保单号"])
        affected_keys.discard(None)
    refresh_activity = performance is not None and (not incremental or not performance.empty)
    if refresh_activity:
        if incremental:
            effective_columns = set(raw_table_columns(conn, "performance")) | set(performance.columns)
            activity_columns = [column for column in ACTIVITY_SOURCE_COLUMNS if column in effective_columns]
            # Normal imports need only the post-write scan under the savepoint.
            # A new higher-priority date column can reinterpret every historical
            # row, so preserve the fail-closed schema-change preflight.
            existing_columns = set(raw_table_columns(conn, "performance"))
            date_priority = ("年月日", "入账时间")
            old_date = next((c for c in date_priority if c in existing_columns), None)
            new_date = next((c for c in date_priority if c in effective_columns), None)
            if existing_columns and old_date != new_date:
                _read_org_activity_rows(conn, source_columns=activity_columns)
            aggregate_org_daily_activity(performance.reindex(columns=activity_columns))
        else:
            aggregate_org_daily_activity(performance)
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT excel_pipeline_write")
    try:
        jingdai = result.raw_tables.get("jingdai")
        if jingdai is not None:
            extract_jingdai_products_to_config(jingdai, conn=conn)
        table_counts = replace_raw_tables(conn, result, incremental=incremental, import_mode=import_mode)
        aggregate_result = result
        if jingdai is not None:
            config_map = _load_jingdai_product_config(conn)
            aggregate_result = ExcelPipelineResult(
                raw_tables=result.raw_tables, rows_by_table=dict(result.rows_by_table),
            )
            aggregate_result.rows_by_table["agg_jingdai"] = aggregate_jingdai(jingdai, config_map=config_map)
            aggregate_result.rows_by_table["agg_jingdai_daily"] = aggregate_jingdai_daily(jingdai, config_map=config_map)
        if import_mode == "supplement":
            from services.aggregate_rebuilder import build_aggregate_rows_from_raw
            persisted = {
                table: frame for table in RAW_TABLE_ORDER
                if not (frame := read_raw_periods(conn, table, performance_periods)).empty
            }
            aggregate_result = ExcelPipelineResult(
                raw_tables=persisted,
                rows_by_table=build_aggregate_rows_from_raw(persisted, include_org_activity=False),
            )
        table_counts.update(replace_aggregate_rows(
            conn, aggregate_result, incremental=incremental, include_org_activity=not refresh_activity,
        ))
        if incremental and (performance is not None or hr_source is not None):
            table_counts.update(_refresh_hr_from_current_sources(conn, hr_periods))
        if refresh_activity:
            table_counts["agg_org_daily_activity"] = replace_org_activity_from_raw(conn)
        if performance is not None:
            refreshed = refresh_customer_facts(conn, affected_keys if incremental else None)
            if not refreshed["skipped"]:
                table_counts["customer_policy_month_fact"] = refreshed["refreshedRows"]
        conn.execute("RELEASE SAVEPOINT excel_pipeline_write")
        return table_counts
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT excel_pipeline_write")
        conn.execute("RELEASE SAVEPOINT excel_pipeline_write")
        raise


def clear_pipeline_years(conn, years: list[int]) -> None:
    for year in years:
        for table in AGGREGATE_TABLE_ORDER:
            clear_table_year_data(conn, table, year)
