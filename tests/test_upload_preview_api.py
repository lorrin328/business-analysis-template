import io
import sqlite3

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app


def workbook():
    buffer = io.BytesIO()
    pd.DataFrame([{"年": 2026, "缴费年限": 10, "人员工号": "SYNTHETIC-STAFF", "年月": "2026-09", "业务模式": "OTO", "销售机构名称": "上海", "期交保费": 100, "投保单号": "SYNTHETIC-1"}]).to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture
def source_db(tmp_path, monkeypatch):
    import db.connection as connection
    import db
    path = tmp_path / "preview.db"
    monkeypatch.setattr(connection, "DB_PATH", str(path))
    monkeypatch.setattr(db, "DB_PATH", str(path))
    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "preview.lock"))
    db.init_db()
    return path


def test_preview_is_readonly_and_confirmation_binds_file_bytes(source_db):
    client = TestClient(app)
    payload = workbook()
    before = source_db.read_bytes()
    preview = client.post("/api/upload/preview", files={"performance": ("synthetic.xlsx", payload)})
    assert preview.status_code == 200
    data = preview.json()
    assert data["canImport"] is True
    assert data["files"][0]["rowCount"] == 1
    assert data["files"][0]["periods"] == ["2026-09"]
    assert source_db.read_bytes() == before
    rejected = client.post("/api/upload?preview_manifest=" + "0" * 64, files={"performance": ("synthetic.xlsx", payload)})
    assert rejected.status_code == 409
    with sqlite3.connect(source_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM performance").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0] == 0


def test_preview_requires_upload_permission_and_bounds_content(source_db, monkeypatch):
    import main
    client = TestClient(app)
    monkeypatch.setenv("AUTH_TEST_BYPASS", "0")
    assert client.post("/api/upload/preview").status_code == 401
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_MB", 0)
    assert client.post("/api/upload/preview", files={"performance": ("synthetic.xlsx", b"x")}).status_code == 413


def test_readiness_failure_is_503_but_liveness_stays_ok(monkeypatch):
    import main
    monkeypatch.setattr(main, "run_health_check", lambda: {"status": "warn", "checks": {"missing_tables": ["users"]}})
    client = TestClient(app)
    assert client.get("/api/health").status_code == 503
    assert client.get("/api/health/live").json() == {"status": "ok"}


def test_missing_health_database_is_not_created(tmp_path, monkeypatch):
    from services import health_check
    path = tmp_path / "absent.db"
    monkeypatch.setattr(health_check, "DB_PATH", str(path))
    assert health_check.run_health_check()["status"] == "error"
    assert not path.exists()
