"""Synthetic-only equivalence and bounded-scan checks for batched import periods."""
import io
import json
import sqlite3

import pandas as pd
import pytest

from services.excel_pipeline import ExcelSource
from services.import_preview import _existing_rows, build_import_preview
from services.import_safety import (
    RawIncrementalWriteError, delete_raw_period, raw_period_predicate,
    raw_periods_predicate, read_raw_periods, validate_replacement_fields,
    write_raw_table_incremental,
)
from services.raw_table_reader import quote_identifier


def _legacy_predicate(periods, columns):
    clauses, params = [], []
    for year, month in sorted(periods):
        clause, values = raw_period_predicate(year, month, columns)
        clauses.append(f"({clause})")
        params.extend(values)
    return " OR ".join(clauses), params


PERIOD_VALUES = [
    None, "", "invalid", 1, 8, 12, "01", "08", "8.0", "08月", " 8 ",
    202601, 202608, 202512, 202608.0, "2026-08", "2026/08", "2026.08",
    "2026年08月", "2026-08-03", "2026/08/03", "2026.08.03",
    "2026年08月03日", "2026-08-03 12:34:56", "2026-08-03T12:34:56",
    " 2026 / 08 / 03 ", "2026-8-03", "2026年8月3日", "2025-12-31", "2027-01-01",
]


@pytest.mark.parametrize("affinity", ["TEXT", "NUMERIC", "BLOB"])
@pytest.mark.parametrize("columns", [
    (None, None, 'd"ate'), (None, 'm"onth', None), ('y"ear', 'm"onth', None),
    ('y"ear', 'm"onth', 'd"ate'), ('y"ear', None, 'd"ate'),
])
@pytest.mark.parametrize("periods", [
    [(2026, 8)], [(2026, 1), (2026, 8), (2025, 12), (2026, 8)],
    [(2026, month) for month in range(1, 13)] + [(2025, 12), (2027, 1)],
])
def test_batched_predicate_matches_legacy_or_for_existing_formats(affinity, columns, periods):
    with sqlite3.connect(":memory:") as conn:
        conn.execute(f'CREATE TABLE sample(id INTEGER PRIMARY KEY,"y""ear" {affinity},"m""onth" {affinity},"d""ate" {affinity})')
        rows = []
        for year in [None, "", "invalid", 2025, 2026, "2026.0", "2026年", 2027]:
            for index, month in enumerate(PERIOD_VALUES):
                # Deliberately conflicting date and month/year values exercise
                # the existing date-column precedence, including NULL dates.
                rows.append((year, month, PERIOD_VALUES[(index + 7) % len(PERIOD_VALUES)]))
        conn.executemany('INSERT INTO sample("y""ear","m""onth","d""ate") VALUES (?,?,?)', rows)
        legacy, old_params = _legacy_predicate(periods, columns)
        batched, new_params = raw_periods_predicate(periods, columns)
        expected = conn.execute(f"SELECT id FROM sample WHERE {legacy} ORDER BY id", old_params).fetchall()
        actual = conn.execute(f"SELECT id FROM sample WHERE {batched} ORDER BY id", new_params).fetchall()
        assert actual == expected


def test_empty_periods_select_nothing_and_missing_period_columns_fail():
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE sample(value TEXT)")
        conn.execute("INSERT INTO sample VALUES ('synthetic')")
        where, params = raw_periods_predicate([], (None, None, None))
        assert conn.execute(f"SELECT COUNT(*) FROM sample WHERE {where}", params).fetchone()[0] == 0
    with pytest.raises(RawIncrementalWriteError):
        raw_periods_predicate({(2026, 8)}, (None, None, None))


@pytest.mark.parametrize("table,column", [("performance", "年月日"), ("jingdai", "时间"), ("value_data", "年月")])
def test_preview_count_and_raw_period_read_match_legacy_selection(table, column):
    periods = {(2025, 12), (2026, 8)}
    with sqlite3.connect(":memory:") as conn:
        conn.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY,{quote_identifier(column)} TEXT)')
        conn.executemany(f'INSERT INTO {table}({quote_identifier(column)}) VALUES (?)', [(value,) for value in PERIOD_VALUES])
        config = (None, None, column) if table == "performance" else (None, column, None)
        where, params = _legacy_predicate(periods, config)
        expected_ids = {row[0] for row in conn.execute(f"SELECT id FROM {table} WHERE {where}", params)}
        assert _existing_rows(conn, table, periods) == len(expected_ids)
        assert set(read_raw_periods(conn, table, periods)["id"]) == expected_ids


@pytest.mark.parametrize("source_value", [0, 0.0, "0", " 0 ", 1, "是", "\t"])
def test_missing_fields_remain_blocked_in_any_selected_month_including_real_zero(source_value):
    with sqlite3.connect(":memory:") as conn:
        conn.execute('CREATE TABLE performance("年月日" TEXT,"期交保费" REAL,"年化规保","是否职拓" TEXT)')
        conn.executemany("INSERT INTO performance VALUES (?,?,?,?)", [
            ("2026-01-01", 1, None, None), ("2026-08-01", 2, source_value, "是"),
            ("2025-12-31", 3, 9, "是"),
        ])
        conn.commit()
        before = list(conn.iterdump())
        incoming = pd.DataFrame([{"年月日": "2026-01-02", "期交保费": 10}, {"年月日": "2026-08-02", "期交保费": 20}])
        with pytest.raises(RawIncrementalWriteError) as caught:
            validate_replacement_fields(conn, "performance", incoming)
        assert "年化规保" in str(caught.value)
        assert "是否职拓" in str(caught.value)
        with pytest.raises(RawIncrementalWriteError):
            write_raw_table_incremental(conn, "performance", incoming)
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize("source_value", [None, "", "   "])
def test_blank_fields_and_enabled_fields_outside_selected_months_do_not_block(source_value):
    with sqlite3.connect(":memory:") as conn:
        conn.execute('CREATE TABLE performance("年月日" TEXT,"年化规保")')
        conn.executemany("INSERT INTO performance VALUES (?,?)", [("2026-08-01", source_value), ("2026-09-01", 0)])
        validate_replacement_fields(conn, "performance", pd.DataFrame([{"年月日": "2026-08-02"}]))


def _replace_counter(conn):
    count = [0]
    def counted_replace(value, search, replacement):
        count[0] += 1
        if value is None or search is None or replacement is None:
            return None
        return str(value).replace(str(search), str(replacement))
    conn.create_function("replace", 3, counted_replace, deterministic=True)
    return count


def _dated_rows(conn, *, optional_columns=()):
    extras = "".join(f",{quote_identifier(column)} TEXT" for column in optional_columns)
    conn.execute(f'CREATE TABLE performance("年月日" TEXT,"期交保费" REAL{extras})')
    # Most history is outside the import year. Old per-month OR/DELETE rescans
    # it for each month; the batched expression must normalize each row once.
    rows = [(f"2024-{index % 12 + 1:02d}-01", 1) for index in range(480)]
    rows += [(f"2026-{month:02d}-01", 2) for month in range(1, 13)]
    conn.executemany('INSERT INTO performance("年月日","期交保费") VALUES (?,?)', rows)
    conn.commit()
    return len(rows)


def test_twelve_month_predicate_normalization_does_not_multiply_full_scan_work():
    with sqlite3.connect(":memory:") as conn:
        row_count = _dated_rows(conn)
        calls = _replace_counter(conn)
        periods = {(2026, month) for month in range(1, 13)}
        results = {}
        for label, predicate in [
            ("single", raw_periods_predicate({(2026, 1)}, (None, None, "年月日"))),
            ("batched", raw_periods_predicate(periods, (None, None, "年月日"))),
            ("legacy", _legacy_predicate(periods, (None, None, "年月日"))),
        ]:
            calls[0] = 0
            where, params = predicate
            matches = conn.execute(f"SELECT COUNT(*) FROM performance WHERE {where}", params).fetchone()[0]
            results[label] = (matches, calls[0])
        assert results["single"] == (1, 8 * row_count)
        assert results["batched"] == (12, 8 * row_count)
        assert results["legacy"][0] == 12
        assert results["legacy"][1] > results["batched"][1] * 10


def test_separate_year_month_columns_normalize_once_for_each_relevant_row():
    with sqlite3.connect(":memory:") as conn:
        conn.execute('CREATE TABLE sample("年" INTEGER,"月" TEXT)')
        conn.executemany("INSERT INTO sample VALUES (?,?)", [
            (year, f"{year}-{month:02d}-01")
            for year in [2024, 2025, 2026] for month in range(1, 13) for _ in range(5)
        ])
        calls = _replace_counter(conn)
        for periods, relevant_rows in [
            ({(2026, 1)}, 60),
            ({(2026, month) for month in range(1, 13)}, 60),
            ({(year, month) for year in [2025, 2026] for month in range(1, 13)}, 120),
        ]:
            where, params = raw_periods_predicate(periods, ("年", "月", None))
            calls[0] = 0
            actual = conn.execute(f"SELECT COUNT(*) FROM sample WHERE {where}", params).fetchone()[0]
            assert calls[0] == 8 * relevant_rows
            old_where, old_params = _legacy_predicate(periods, ("年", "月", None))
            expected = conn.execute(f"SELECT COUNT(*) FROM sample WHERE {old_where}", old_params).fetchone()[0]
            assert actual == expected


@pytest.mark.parametrize("month_count", [1, 8, 12])
@pytest.mark.parametrize("optional_columns", [("年化规保",), ("年化规保", "承保件数", "是否职拓", "产品名称", "产品类型", "价值规保", "人员工号", "销售机构名称")])
def test_batched_field_validation_normalizes_once_per_row_not_month_or_missing_field(month_count, optional_columns):
    with sqlite3.connect(":memory:") as conn:
        row_count = _dated_rows(conn, optional_columns=optional_columns)
        calls = _replace_counter(conn)
        queries = []
        conn.set_trace_callback(queries.append)
        incoming = pd.DataFrame([{"年月日": f"2026-{month:02d}-02", "期交保费": 3} for month in range(1, month_count + 1)])
        validate_replacement_fields(conn, "performance", incoming)
        conn.set_trace_callback(None)
        scans = [query for query in queries if query.startswith("SELECT ") and 'FROM "performance"' in query]
        assert len(scans) == 1
        assert calls[0] == 8 * row_count


def test_batched_delete_scans_once_preserves_other_periods_and_matches_legacy_deletes():
    periods = {(2026, month) for month in range(1, 13)}
    with sqlite3.connect(":memory:") as new, sqlite3.connect(":memory:") as old:
        row_count = _dated_rows(new)
        _dated_rows(old)
        new_calls, old_calls = _replace_counter(new), _replace_counter(old)
        queries = []
        new.set_trace_callback(queries.append)
        incoming = pd.DataFrame([{"年月日": f"2026-{month:02d}-02", "期交保费": 3} for month in range(1, 13)])
        assert write_raw_table_incremental(new, "performance", incoming) == 12
        for year, month in periods:
            delete_raw_period(old, "performance", year, month, (None, None, "年月日"))
        old.executemany("INSERT INTO performance VALUES (?,?)", list(incoming.itertuples(index=False, name=None)))
        new.set_trace_callback(None)
        assert len([query for query in queries if query.startswith('DELETE FROM "performance"')]) == 1
        assert new_calls[0] == 8 * row_count
        assert old_calls[0] > new_calls[0] * 10
        assert new.execute('SELECT * FROM performance ORDER BY "年月日","期交保费"').fetchall() == old.execute('SELECT * FROM performance ORDER BY "年月日","期交保费"').fetchall()


def test_batched_delete_rolls_back_all_selected_months_after_insert_failure():
    with sqlite3.connect(":memory:") as conn:
        _dated_rows(conn)
        conn.execute("CREATE TRIGGER reject_synthetic BEFORE INSERT ON performance WHEN NEW.\"期交保费\"=999 BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        before = list(conn.iterdump())
        incoming = pd.DataFrame([{"年月日": "2026-01-02", "期交保费": 3}, {"年月日": "2026-08-02", "期交保费": 999}])
        with pytest.raises(sqlite3.IntegrityError, match="synthetic failure"):
            write_raw_table_incremental(conn, "performance", incoming)
        assert list(conn.iterdump()) == before


def test_multi_month_preview_is_read_only_blocks_real_zero_and_has_two_bounded_scans():
    with sqlite3.connect(":memory:") as conn:
        row_count = _dated_rows(conn, optional_columns=("年化规保",))
        conn.execute('UPDATE performance SET "年化规保"=0 WHERE "年月日"=\'2026-08-01\'')
        conn.commit()
        before = list(conn.iterdump())
        conn.execute("PRAGMA query_only=ON")
        calls = _replace_counter(conn)
        incoming = pd.DataFrame([{
            "年": 2026, "年月": f"2026{month:02d}", "年月日": f"2026-{month:02d}-02",
            "业务模式": "OTO", "期交保费": 3, "缴费年限": 5,
            "人员工号": "synthetic-person", "销售机构名称": "合成机构",
        } for month in range(1, 9)])
        content = io.BytesIO()
        incoming.to_excel(content, index=False)
        result = build_import_preview(conn, [ExcelSource("performance", "synthetic.xlsx", content.getvalue())])
        assert not result["canImport"]
        assert result["files"][0]["existingRows"] == 8
        assert "年化规保" in result["errors"][0]
        assert calls[0] == 2 * 8 * row_count
        assert list(conn.iterdump()) == before
        assert "synthetic-person" not in json.dumps(result)
