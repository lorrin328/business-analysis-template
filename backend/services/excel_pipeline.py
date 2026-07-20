"""Shared Excel import pipeline for uploads and full rebuilds."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from db import clear_table_year_data, replace_rows, replace_rows_incremental
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
    parse_hr_excel,
    parse_jingdai_excel,
    parse_performance_excel,
    parse_value_excel,
)
from services.import_safety import write_raw_table_incremental
from services.product_config_service import extract_jingdai_products_to_config
from validators.data_validator import validate_rows


AGGREGATE_TABLE_ORDER = [
    "agg_performance",
    "agg_daily_performance",
    "agg_org_daily_performance",
    "agg_product_structure",
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
    _merge_rows(rows, "agg_product_structure", aggregate_product_structure(frame))
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
    extract_jingdai_products_to_config(frame)

    jd_rows = aggregate_jingdai(frame)
    _require_valid_rows(jd_rows, ["year", "month"], ["year", "month"])
    jd_daily_rows = aggregate_jingdai_daily(frame)
    jd_pay_period_rows = aggregate_jingdai_payment_period(frame)
    jd_pay_period_daily_rows = aggregate_jingdai_payment_period_daily(frame)
    jd_longterm_rows = aggregate_jingdai_longterm(frame)

    rows = result.rows_by_table
    _merge_rows(rows, "agg_jingdai", jd_rows)
    _merge_rows(rows, "agg_jingdai_daily", jd_daily_rows)
    _merge_rows(rows, "agg_payment_period", jd_pay_period_rows)
    _merge_rows(rows, "agg_payment_period_daily", jd_pay_period_daily_rows)
    _merge_rows(rows, "agg_longterm_qj", jd_longterm_rows)
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
    parser(source, result)


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


def replace_aggregate_rows(conn, result: ExcelPipelineResult, *, incremental: bool) -> dict[str, int]:
    table_counts: dict[str, int] = {}
    writer = replace_rows_incremental if incremental else replace_rows
    for table in AGGREGATE_TABLE_ORDER:
        rows = result.rows_by_table.get(table, [])
        if rows:
            writer(conn, table, rows)
            table_counts[table] = len(rows)
    return table_counts


def replace_raw_tables(conn, result: ExcelPipelineResult, *, incremental: bool) -> dict[str, int]:
    table_counts: dict[str, int] = {}
    for table in RAW_TABLE_ORDER:
        frame = result.raw_tables.get(table)
        if frame is None:
            continue
        if incremental:
            write_raw_table_incremental(conn, table, frame)
        else:
            frame.to_sql(table, conn, if_exists="replace", index=False)
        table_counts[table] = len(frame)
    return table_counts


def write_excel_pipeline_result(conn, result: ExcelPipelineResult, *, incremental: bool) -> dict[str, int]:
    table_counts = replace_aggregate_rows(conn, result, incremental=incremental)
    table_counts.update(replace_raw_tables(conn, result, incremental=incremental))
    return table_counts


def clear_pipeline_years(conn, years: list[int]) -> None:
    for year in years:
        for table in AGGREGATE_TABLE_ORDER:
            clear_table_year_data(conn, table, year)
