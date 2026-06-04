import os
import sqlite3
import sys

import pandas as pd
import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

pytest.importorskip("fastapi")
from main import _check_skip, _set_import_status, _skip_duplicate_upload, _validate_daily_cutoff_alignment
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


def test_force_upload_bypasses_duplicate_skip():
    results = {"skipped": []}
    assert _skip_duplicate_upload("x.xlsx", "same", "performance", results, force=True) is False
    assert results["skipped"] == []


def test_upload_endpoint_defaults_to_force_false():
    import inspect
    from main import upload_files

    default = inspect.signature(upload_files).parameters["force"].default
    assert getattr(default, "default", None) is False


def test_import_status_marks_partial_data_integrity():
    result = _set_import_status(
        {"uploaded": ["performance"], "errors": ["value failed"], "skipped": []},
        has_written_rows=True,
    )
    assert result["status"] == "partial"
    assert result["data_integrity"]["complete"] is False
    assert result["data_integrity"]["uploadedCount"] == 1
    assert result["data_integrity"]["errorCount"] == 1


def test_import_warns_for_mismatched_transform_and_jingdai_daily_cutoffs():
    warnings = _validate_daily_cutoff_alignment(
        [{"year": 2026, "month": 5, "day": 13}],
        [{"year": 2026, "month": 5, "day": 20}],
    )
    assert len(warnings) == 1
    assert "混合统计将按共同截止日5月13日计算" in warnings[0]


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


def test_write_raw_table_incremental_expands_schema_drift_without_rebuild():
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
        write_raw_table_incremental(conn, "performance", changed)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(performance)").fetchall()}
        assert "新增字段" in columns
        rows = conn.execute('SELECT COUNT(*), SUM("期交保费"), MAX("新增字段") FROM performance').fetchall()
        assert rows == [(1, 99, "x")]
    finally:
        conn.close()


def test_write_raw_table_incremental_deletes_date_like_month_column():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE hr_data (
                "统计年" INTEGER,
                "统计日期" TEXT,
                "业务模式名称" TEXT,
                "月初在职人力" INTEGER,
                "月末在职人力" INTEGER
            )
            """
        )
        conn.execute(
            'INSERT INTO hr_data VALUES (?, ?, ?, ?, ?)',
            (2026, "2026-05-01", "OTO", 10, 11),
        )
        replacement = pd.DataFrame(
            [
                {
                    "统计年": 2026,
                    "统计日期": "2026-05-01",
                    "业务模式名称": "OTO",
                    "月初在职人力": 12,
                    "月末在职人力": 13,
                }
            ]
        )

        write_raw_table_incremental(conn, "hr_data", replacement)

        rows = conn.execute('SELECT "月初在职人力", "月末在职人力" FROM hr_data').fetchall()
        assert rows == [(12, 13)]
    finally:
        conn.close()


def test_write_raw_table_incremental_deletes_dot_and_chinese_date_text():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE performance (
                "年月日" TEXT,
                "业务模式" TEXT,
                "期交保费" REAL
            )
            """
        )
        conn.executemany(
            'INSERT INTO performance VALUES (?, ?, ?)',
            [
                ("2026.05.01", "OTO", 10),
                ("2026年05月02日", "OTO", 20),
                ("2026-06-01", "OTO", 30),
            ],
        )
        replacement = pd.DataFrame(
            [
                {"年月日": "2026/05/03", "业务模式": "OTO", "期交保费": 99},
            ]
        )

        write_raw_table_incremental(conn, "performance", replacement)

        rows = conn.execute(
            'SELECT "年月日", "期交保费" FROM performance ORDER BY "年月日"'
        ).fetchall()
        assert rows == [("2026-06-01", 30), ("2026/05/03", 99)]
    finally:
        conn.close()
