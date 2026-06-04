"""Runtime health checks for deployment and monitoring."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from config.version import get_app_version
from db import AGG_TABLES, DB_PATH, get_db


ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "经营分析模板.html"
REQUIRED_TABLES = [
    "target_config",
    "target_values",
    "data_imports",
    "users",
    "user_sessions",
    "user_module_permissions",
    *AGG_TABLES,
]


def _page_version() -> str | None:
    if not HTML_PATH.exists():
        return None
    text = HTML_PATH.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"v\d+\.\d+\.\d+", text)
    return match.group(0) if match else None


def _latest_period(conn) -> int | None:
    periods: list[int] = []
    for table in ["agg_daily_performance", "agg_jingdai_daily", "agg_performance", "agg_jingdai"]:
        try:
            row = conn.execute(f"SELECT MAX(year * 100 + month) AS period FROM {table}").fetchone()
        except sqlite3.Error:
            continue
        if row and row["period"]:
            periods.append(int(row["period"]))
    return max(periods) if periods else None


def run_health_check() -> dict:
    checks: dict[str, object] = {
        "database_exists": os.path.exists(DB_PATH),
        "account_auth_enabled": True,
        "app_version": get_app_version(),
        "page_exists": HTML_PATH.exists(),
        "page_version": _page_version(),
    }
    status = "ok"
    db_info: dict[str, object] = {"path": DB_PATH}
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            missing = [table for table in REQUIRED_TABLES if table not in tables]
            db_info["missing_tables"] = missing
            db_info["latest_period"] = _latest_period(conn)
            db_info["table_count"] = len(tables)
            if missing:
                status = "warn"
    except Exception as exc:
        status = "error"
        db_info["error"] = str(exc)

    checks["database"] = db_info
    if not checks["database_exists"] or not checks["page_exists"]:
        status = "error"
    return {
        "status": status,
        "checks": checks,
    }
