import os
import sys

import pytest

os.environ.setdefault("AUTH_TEST_BYPASS", "1")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "Aaaaasynology8888%")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_test.db"
    import db as db_module
    import db.connection as connection
    from db import init_db

    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setenv("AUTH_TEST_BYPASS", "0")
    monkeypatch.setenv("AUTH_ALLOW_PUBLIC_REGISTRATION", "1")
    init_db()
    yield
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
