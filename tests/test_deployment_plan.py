import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))

from deployment_plan import build_plan, main, required_migrations


def test_existing_database_skips_aggregate_rebuild_without_new_required_migration():
    plan = build_plan(
        database_existed=True,
        excel_count=0,
        rebuild_database="0",
        rebuild_aggregates="auto",
        required_before=("m1",),
        required_after=("m1",),
    )

    assert plan.rebuild_from_excel is False
    assert plan.rebuild_aggregates is False
    assert "未出现" in plan.reason


def test_new_required_migration_forces_rebuild_even_when_skip_requested():
    plan = build_plan(
        database_existed=True,
        excel_count=0,
        rebuild_database="0",
        rebuild_aggregates="0",
        required_before=("m1",),
        required_after=("m1", "m2"),
    )

    assert plan.rebuild_aggregates is True
    assert plan.new_required_migrations == ("m2",)
    assert "覆盖跳过设置" in plan.reason


def test_force_aggregate_rebuild_without_new_migration():
    plan = build_plan(
        database_existed=True,
        excel_count=0,
        rebuild_database="auto",
        rebuild_aggregates="1",
    )

    assert plan.rebuild_from_excel is False
    assert plan.rebuild_aggregates is True


def test_first_deploy_with_excel_sources_uses_full_rebuild():
    plan = build_plan(
        database_existed=False,
        excel_count=4,
        rebuild_database="auto",
        rebuild_aggregates="auto",
    )

    assert plan.rebuild_from_excel is True
    assert plan.rebuild_aggregates is False


def test_forced_excel_rebuild_rejects_incomplete_sources():
    with pytest.raises(ValueError, match="at least three"):
        build_plan(
            database_existed=True,
            excel_count=2,
            rebuild_database="1",
            rebuild_aggregates="auto",
        )


def test_first_empty_database_does_not_attempt_raw_rebuild():
    plan = build_plan(
        database_existed=False,
        excel_count=0,
        rebuild_database="auto",
        rebuild_aggregates="auto",
        required_after=("m1",),
    )

    assert plan.rebuild_from_excel is False
    assert plan.rebuild_aggregates is False


def test_required_migration_snapshot_reads_only_marked_rows(tmp_path):
    database = tmp_path / "business.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE schema_migrations ("
            "version TEXT PRIMARY KEY, requires_aggregate_rebuild INTEGER NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO schema_migrations VALUES (?, ?)",
            [("m2", 1), ("m1", 0), ("m3", 1)],
        )

    assert required_migrations(database) == ("m2", "m3")


def test_snapshot_cli_emits_json(tmp_path, monkeypatch, capsys):
    database = tmp_path / "empty.db"
    sqlite3.connect(database).close()
    monkeypatch.setattr(
        "sys.argv",
        ["deployment_plan.py", "snapshot", "--database", str(database)],
    )

    main()

    assert json.loads(capsys.readouterr().out) == []
