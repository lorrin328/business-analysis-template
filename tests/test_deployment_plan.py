import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))

from deployment_plan import CUSTOMER_FACT_MIGRATIONS, build_plan, main, rebuild_scope, required_migrations


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


@pytest.mark.parametrize("migrations", [
    ("20260902_customer_fact_consistency",),
    ("20260902_customer_alias_exact_fallback",),
    tuple(sorted(CUSTOMER_FACT_MIGRATIONS)),
])
@pytest.mark.parametrize("mode", ["auto", "0", "skip"])
def test_known_customer_only_migrations_use_scoped_rebuild(migrations, mode):
    plan = build_plan(database_existed=True, excel_count=0, rebuild_database="0",
                      rebuild_aggregates=mode, required_before=("old",), required_after=("old", *migrations))
    assert plan.rebuild_aggregates is True
    assert rebuild_scope(plan, rebuild_database="0", rebuild_aggregates=mode) == "customer_facts"


@pytest.mark.parametrize("mode", ["1", "true", "force"])
def test_forcing_aggregates_never_narrows_customer_migrations(mode):
    plan = build_plan(database_existed=True, excel_count=0, rebuild_database="0",
                      rebuild_aggregates=mode, required_after=tuple(CUSTOMER_FACT_MIGRATIONS))
    assert rebuild_scope(plan, rebuild_database="0", rebuild_aggregates=mode) == "full"


@pytest.mark.parametrize("migrations", [("unknown_main_aggregate",), ("20260902_customer_fact_consistency", "unknown_main_aggregate")])
def test_unknown_or_mixed_migrations_keep_full_rebuild(migrations):
    plan = build_plan(database_existed=True, excel_count=0, rebuild_database="0",
                      rebuild_aggregates="0", required_after=migrations)
    assert plan.rebuild_aggregates is True
    assert rebuild_scope(plan, rebuild_database="0", rebuild_aggregates="0") == "full"


def test_old_customer_migrations_do_not_trigger_rebuild_again():
    migrations = tuple(CUSTOMER_FACT_MIGRATIONS)
    plan = build_plan(database_existed=True, excel_count=0, rebuild_database="0",
                      rebuild_aggregates="auto", required_before=migrations, required_after=migrations)
    assert rebuild_scope(plan, rebuild_database="0", rebuild_aggregates="auto") == "none"


def test_explicit_excel_rebuild_keeps_excel_scope():
    plan = build_plan(database_existed=True, excel_count=3, rebuild_database="1",
                      rebuild_aggregates="auto", required_after=tuple(CUSTOMER_FACT_MIGRATIONS))
    assert rebuild_scope(plan, rebuild_database="1", rebuild_aggregates="auto") == "excel"


def test_plan_cli_scope_preserves_original_four_line_interface(tmp_path, monkeypatch, capsys):
    database = tmp_path / "scope.db"
    snapshot = tmp_path / "before.json"
    snapshot.write_text('["old"]', encoding="utf-8")
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, requires_aggregate_rebuild INTEGER)")
        conn.executemany("INSERT INTO schema_migrations VALUES (?,1)", [("old",), *[(item,) for item in CUSTOMER_FACT_MIGRATIONS]])
    args = ["deployment_plan.py", "plan", "--database", str(database), "--snapshot", str(snapshot),
            "--database-existed", "1", "--excel-count", "0", "--rebuild-database", "0", "--rebuild-aggregates", "0"]
    monkeypatch.setattr("sys.argv", args + ["--format", "lines"])
    main()
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 4
    assert lines[:2] == ["0", "1"]
    assert set(lines[2].split(",")) == CUSTOMER_FACT_MIGRATIONS
    monkeypatch.setattr("sys.argv", args + ["--format", "scope"])
    main()
    assert capsys.readouterr().out.strip() == "customer_facts"
