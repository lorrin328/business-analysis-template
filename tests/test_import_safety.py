import os
import sqlite3
import sys

import pandas as pd
import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from main import _check_skip, _set_import_status, _validate_daily_cutoff_alignment
from services.import_safety import RawIncrementalWriteError, write_raw_table_incremental


def test_check_skip_only_uses_successful_hashes():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE data_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO data_imports (file_hash, status) VALUES (?, ?)", ("same", "partial"))
        assert _check_skip(conn, "x.xlsx", "same") is False

        conn.execute("INSERT INTO data_imports (file_hash, status) VALUES (?, ?)", ("same", "success"))
        assert _check_skip(conn, "x.xlsx", "same") is True
    finally:
        conn.close()


def test_import_status_marks_partial_data_integrity():
    result = _set_import_status(
        {"uploaded": ["performance"], "errors": ["value failed"], "skipped": []},
        has_written_rows=True,
    )
    assert result["status"] == "partial"
    assert result["data_integrity"]["complete"] is False
    assert result["data_integrity"]["uploadedCount"] == 1
    assert result["data_integrity"]["errorCount"] == 1


def test_import_rejects_mismatched_transform_and_jingdai_daily_cutoffs():
    errors = _validate_daily_cutoff_alignment(
        [{"year": 2026, "month": 5, "day": 13}],
        [{"year": 2026, "month": 5, "day": 20}],
    )
    assert len(errors) == 1
    assert "截止日不一致" in errors[0]


def test_import_accepts_aligned_transform_and_jingdai_daily_cutoffs():
    errors = _validate_daily_cutoff_alignment(
        [{"year": 2026, "month": 5, "day": 13}],
        [{"year": 2026, "month": 5, "day": 13}],
    )
    assert errors == []


def test_write_raw_table_incremental_preserves_other_months():
    conn = sqlite3.connect(":memory:")
    try:
        initial = pd.DataFrame(
            [
                {"年月": "202601", "业务模式": "OTO", "期交保费": 10},
                {"年月": "202602", "业务模式": "OTO", "期交保费": 20},
            ]
        )
        initial.to_sql("performance", conn, if_exists="replace", index=False)

        replacement = pd.DataFrame(
            [
                {"年月": "202601", "业务模式": "OTO", "期交保费": 99},
            ]
        )
        write_raw_table_incremental(conn, "performance", replacement)

        rows = conn.execute(
            'SELECT "年月", SUM("期交保费") FROM performance GROUP BY "年月" ORDER BY "年月"'
        ).fetchall()
        assert rows == [("202601", 99), ("202602", 20)]
    finally:
        conn.close()


def test_write_raw_table_incremental_rejects_existing_table_without_periods():
    conn = sqlite3.connect(":memory:")
    try:
        initial = pd.DataFrame(
            [
                {"年月": "202601", "业务模式": "OTO", "期交保费": 10},
            ]
        )
        initial.to_sql("performance", conn, if_exists="replace", index=False)

        invalid = pd.DataFrame(
            [
                {"业务模式": "OTO", "期交保费": 99},
            ]
        )
        with pytest.raises(RawIncrementalWriteError):
            write_raw_table_incremental(conn, "performance", invalid)

        rows = conn.execute('SELECT COUNT(*), SUM("期交保费") FROM performance').fetchall()
        assert rows == [(1, 10)]
    finally:
        conn.close()


def test_write_raw_table_incremental_rejects_schema_drift_without_rebuild():
    conn = sqlite3.connect(":memory:")
    try:
        initial = pd.DataFrame(
            [
                {"年月": "202601", "业务模式": "OTO", "期交保费": 10},
            ]
        )
        initial.to_sql("performance", conn, if_exists="replace", index=False)

        changed = pd.DataFrame(
            [
                {"年月": "202601", "业务模式": "OTO", "期交保费": 99, "新增字段": "x"},
            ]
        )
        with pytest.raises(RawIncrementalWriteError):
            write_raw_table_incremental(conn, "performance", changed)

        rows = conn.execute('SELECT COUNT(*), SUM("期交保费") FROM performance').fetchall()
        assert rows == [(1, 10)]
    finally:
        conn.close()
