"""Failure-path checks for read-only audit and release gates; synthetic data only."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _set_database(monkeypatch, path):
    import db
    from db import connection
    monkeypatch.setattr(connection, "DB_PATH", str(path))
    monkeypatch.setattr(db, "DB_PATH", str(path))


def _synthetic_database(path, monkeypatch):
    from db import init_db, replace_rows
    from services.aggregate_rebuilder import build_aggregate_rows_from_raw
    _set_database(monkeypatch, path)
    init_db()
    frames = {
        "performance": pd.DataFrame([{
            "年": 2026, "年月": "202605", "年月日": "2026-05-24", "业务模式": "OTO",
            "销售机构名称": "测试机构", "产品代码": "4281", "长短险": "一年期以上",
            "缴费年限": 10, "人员工号": "SYNTHETIC001", "期交保费": 10000,
            "年化规保": 10000, "折算保费": 10000,
        }]),
        "hr_data": pd.DataFrame([{
            "统计年": 2026, "统计日期": "2026-05-01", "业务模式名称": "OTO",
            "销售机构名称": "测试机构", "月初在职人力": 10, "月末在职人力": 12,
        }]),
        "jingdai": pd.DataFrame([{
            "时间": "2026-05-24", "产品名称": "测试产品", "期交保费": 20000,
            "承保年化规保": 20000, "缴费年限": 10,
        }]),
        "value_data": pd.DataFrame({"年月": pd.Series(dtype=str)}),
    }
    with sqlite3.connect(path) as conn:
        for table, frame in frames.items():
            frame.to_sql(table, conn, if_exists="replace", index=False)
        for table, rows in build_aggregate_rows_from_raw(frames, jingdai_config_map={}).items():
            replace_rows(conn, table, rows)
        conn.commit()
        conn.execute("PRAGMA journal_mode=DELETE")


def test_audit_cannot_create_missing_database(tmp_path, monkeypatch):
    from services.data_quality_audit import run_data_quality_audit
    path = tmp_path / "missing.db"
    _set_database(monkeypatch, path)
    result = run_data_quality_audit(2026)
    assert result["status"] == "fail"
    assert result["issues"][0]["code"] == "audit_execution_failed"
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_audit_missing_schema_fails_without_migration(tmp_path, monkeypatch):
    from services.data_quality_audit import run_data_quality_audit
    path = tmp_path / "incomplete.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE original_only(value TEXT)")
    _set_database(monkeypatch, path)
    before = path.read_bytes()
    result = run_data_quality_audit(2026)
    assert result["status"] == "fail"
    assert {issue["code"] for issue in result["issues"]} >= {"missing_raw_schema", "missing_aggregate_table", "kpi_schema_unavailable"}
    assert path.read_bytes() == before
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("original_only",)]


def test_complete_audit_uses_only_one_readonly_snapshot(tmp_path, monkeypatch):
    import db.repositories.kpi as kpi_repository
    import etl.aggregates.jingdai as jingdai_aggregate
    from services.data_quality_audit import get_db, run_data_quality_audit
    path = tmp_path / "complete.db"
    _synthetic_database(path, monkeypatch)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    attempted_connections = []
    def forbidden_connection():
        attempted_connections.append(True)
        raise AssertionError("Audit attempted to open a write-capable connection")
    monkeypatch.setattr(kpi_repository, "get_db", forbidden_connection)
    monkeypatch.setattr(jingdai_aggregate, "get_db", forbidden_connection)
    result = run_data_quality_audit(2026)
    assert result["status"] == "ok", result["issues"]
    assert attempted_connections == []
    with get_db() as conn:
        assert conn.in_transaction
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE forbidden(value TEXT)")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["complete.db"]


def test_audit_reports_duplicates_before_rebuild_deduplication(tmp_path, monkeypatch):
    from services.data_quality_audit import run_data_quality_audit
    path = tmp_path / "duplicates.db"
    _synthetic_database(path, monkeypatch)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO performance SELECT * FROM performance")
    result = run_data_quality_audit(2026)
    assert result["status"] == "fail"
    duplicates = [issue for issue in result["issues"] if issue["code"] == "raw_duplicate_rows"]
    assert len(duplicates) == 1
    assert duplicates[0]["context"]["duplicate_rows"] == 1
    assert not any(issue["code"] == "aggregate_sum_mismatch" for issue in result["issues"])


def _comparison(rows, expected):
    from services.data_quality_audit import _compare_aggregates
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        pd.DataFrame(rows).to_sql("agg_daily_performance", conn, index=False)
        return _compare_aggregates(conn, {"agg_daily_performance": expected}, [2026])


def test_equal_annual_sum_does_not_hide_month_or_channel_mismatch():
    expected = [
        {"year": 2026, "month": 5, "day": 1, "channel": "OTO", "qj_premium": 1, "gm_premium": 1, "zs_premium": 1},
        {"year": 2026, "month": 6, "day": 1, "channel": "OTO", "qj_premium": 2, "gm_premium": 2, "zs_premium": 2},
    ]
    rows = [dict(row, month=11 - row["month"]) for row in expected]
    issues = _comparison(rows, expected)
    assert any(issue.code == "aggregate_dimension_mismatch" for issue in issues)
    assert not any(issue.code == "aggregate_sum_mismatch" for issue in issues)


@pytest.mark.parametrize("missing", ["channel", "qj_premium"])
def test_missing_aggregate_column_is_failure(missing):
    expected = [{"year": 2026, "month": 5, "day": 1, "channel": "OTO", "qj_premium": 1, "gm_premium": 1, "zs_premium": 1}]
    issues = _comparison([{key: value for key, value in expected[0].items() if key != missing}], expected)
    assert any(issue.code == "missing_aggregate_columns" for issue in issues)


def test_stale_zero_groups_are_not_silently_accepted():
    rows = [{"year": 2026, "month": 5, "day": 1, "channel": "OTO", "qj_premium": 0, "gm_premium": 0, "zs_premium": 0}]
    assert any(issue.code == "aggregate_dimension_mismatch" for issue in _comparison(rows, []))


def test_duplicate_audit_keeps_channel_boundary_and_reports_no_identifiers():
    from services.data_quality_audit import _raw_duplicate_issues
    rows = [{"policy": "synthetic-policy", "channel": "OTO"}, {"policy": "synthetic-policy", "channel": "证保"}]
    assert _raw_duplicate_issues({"performance": pd.DataFrame(rows)}) == []
    issues = _raw_duplicate_issues({"performance": pd.DataFrame(rows + [rows[0]])})
    assert issues[0].severity == "error"
    assert issues[0].context["duplicate_rows"] == 1
    assert "synthetic-policy" not in str(issues)


def test_raw_reader_preserves_exact_duplicates(tmp_path, monkeypatch):
    from services.data_quality_audit import _read_raw_table_year
    with sqlite3.connect(":memory:") as conn:
        frame = pd.DataFrame([{"年月": "202605", "业务模式": "OTO", "期交保费": 1}] * 2)
        frame.to_sql("performance", conn, index=False)
        assert len(_read_raw_table_year(conn, "performance", 2026)) == 2


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("status,strict,code", [("ok", False, 0), ("warn", False, 0), ("warn", True, 1), ("fail", False, 1), ("error", False, 1)])
def test_cli_status_and_strict_exit_code(monkeypatch, capsys, as_json, status, strict, code):
    import audit_data_quality as cli
    monkeypatch.setattr(cli, "run_data_quality_audit", lambda year: {"status": status, "year": year, "issue_count": 0, "issues": []})
    args = ["--year", "2026"] + (["--json"] if as_json else []) + (["--strict"] if strict else [])
    assert cli.main(args) == code
    output = capsys.readouterr().out
    if as_json:
        assert json.loads(output)["status"] == status
    else:
        assert f"status: {status}" in output


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_missing_database_really_exits_nonzero(tmp_path, as_json):
    path = tmp_path / "missing.db"
    result = subprocess.run(
        [sys.executable, str(ROOT / "backend/audit_data_quality.py"), "--year", "2026"] + (["--json"] if as_json else []),
        env={**os.environ, "BUSINESS_ANALYSIS_DB": str(path), "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 1
    assert not path.exists()
    if as_json:
        assert json.loads(result.stdout)["status"] == "fail"
    else:
        assert "status: fail" in result.stdout


def test_cli_json_error_does_not_print_exception_content(monkeypatch, capsys):
    import audit_data_quality as cli
    def fail(_):
        raise RuntimeError("synthetic sensitive input must stay private")
    monkeypatch.setattr(cli, "run_data_quality_audit", fail)
    assert cli.main(["--json"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "error"
    assert "sensitive" not in output
