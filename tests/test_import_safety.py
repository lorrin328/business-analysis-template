import os
import sqlite3
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from main import _check_skip
from services.import_safety import write_raw_table_incremental


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
