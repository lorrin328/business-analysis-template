import os
import sqlite3
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from db.repository import replace_rows_incremental


def test_incremental_longterm_write_preserves_other_business_type(tmp_path):
    db_path = tmp_path / "repo_incremental.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE agg_longterm_qj (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            business_type TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT '',
            org TEXT NOT NULL DEFAULT '',
            qj_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, business_type, channel, org)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO agg_longterm_qj (year, month, business_type, channel, org, qj_premium)
        VALUES (2026, 5, '转型', 'OTO', '上海', 10)
        """
    )

    replace_rows_incremental(
        conn,
        "agg_longterm_qj",
        [
            {
                "year": 2026,
                "month": 5,
                "business_type": "经代",
                "channel": "",
                "org": "支付宝",
                "qj_premium": 20,
            }
        ],
    )

    rows = conn.execute(
        """
        SELECT business_type, channel, org, qj_premium
        FROM agg_longterm_qj
        WHERE year = 2026 AND month = 5
        ORDER BY business_type, channel, org
        """
    ).fetchall()
    assert rows == [
        ("经代", "", "支付宝", 20),
        ("转型", "OTO", "上海", 10),
    ]
    conn.close()
