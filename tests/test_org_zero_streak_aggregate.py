"""Synthetic boundary and import-chain checks; no production detail is persisted."""
import io
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from etl import aggregate_org_daily_activity


def _row(**changes):
    return {
        "年": 2026, "年月": "202608", "年月日": "2026-08-28",
        "入账时间": "2026-08-29", "承保时间": "2026-08-27",
        "业务模式": "OTO", "销售机构名称": "上海",
        "期交保费": 10000, "承保件数": 1, "年化规保": 10000,
        "折算保费": 10000, "缴费年限": 5, "长短险": "一年期以上",
        "人员工号": "synthetic-1", "产品名称": "测试产品", "产品代码": "TEST",
        **changes,
    }


def _aggregate(*rows):
    return aggregate_org_daily_activity(pd.DataFrame(rows))


@pytest.mark.parametrize("refund", [-10000, -20000])
def test_acceptance_is_not_cancelled_by_zero_or_negative_net(refund):
    row = _aggregate(_row(), _row(期交保费=refund, 承保件数=-1))[0]
    assert (row["day"], row["has_positive_qj"], row["uncertain"]) == (28, 1, 0)


@pytest.mark.parametrize("premium,count,positive,uncertain", [
    (-10000, -1, 0, 0), (0, 1, 0, 0), (0.01, 1, 1, 0),
    (10000, 0, 0, 1), (10000, -1, 0, 1), (10000, None, 0, 1),
    (10000, "bad", 0, 1), (10000, float("inf"), 0, 1),
    (None, 1, 0, 1), ("bad", 1, 0, 1), (float("inf"), 1, 0, 1),
    (float("-inf"), 1, 0, 1), (float("nan"), 1, 0, 1),
])
def test_amount_and_acceptance_evidence(premium, count, positive, uncertain):
    row = _aggregate(_row(期交保费=premium, 承保件数=count))[0]
    assert (row["has_positive_qj"], row["uncertain"]) == (positive, uncertain)


def test_missing_columns_are_uncertain_and_good_acceptance_survives_uncertain_row():
    for column in ("期交保费", "承保件数"):
        frame = pd.DataFrame([_row()]).drop(columns=[column])
        assert aggregate_org_daily_activity(frame)[0]["uncertain"] == 1
    row = _aggregate(_row(), _row(承保件数=0))[0]
    assert (row["has_positive_qj"], row["uncertain"]) == (1, 1)


@pytest.mark.parametrize("value", [
    "2026-08-28", "2026/8/28", "2026.08.28", "2026年8月28日", "20260828",
    20260828, 20260828.0, "20260828.0", datetime(2026, 8, 28, 12, 30),
    "2026-08-28T12:30:59.123", "2026-08-28 00:00:00",
])
def test_only_complete_business_dates_are_positive(value):
    row = _aggregate(_row(年月日=value))[0]
    assert (row["year"], row["month"], row["day"], row["has_positive_qj"]) == (2026, 8, 28, 1)


@pytest.mark.parametrize("value,month", [
    ("202608", 8), (202608, 8), ("2026-08", 8), ("2026年8月", 8),
    ("2026-02-30", 2), ("20260230", 2), (None, 8), ("bad", 8),
    ("2026-08-28 25:00:00", 8),
])
def test_bad_or_month_only_date_creates_uncertain_sentinel(value, month):
    row = _aggregate(_row(年月日=value))[0]
    assert (row["month"], row["day"], row["has_positive_qj"], row["uncertain"]) == (month, 0, 0, 1)


def test_date_column_priority_is_global_and_never_uses_acceptance_date():
    original = pd.DataFrame([_row(年月日=None)])
    assert aggregate_org_daily_activity(original)[0]["day"] == 0
    no_primary = original.drop(columns=["年月日"])
    assert aggregate_org_daily_activity(no_primary)[0]["day"] == 29
    no_business_date = no_primary.drop(columns=["入账时间"])
    assert aggregate_org_daily_activity(no_business_date)[0]["day"] == 0
    no_business_date["年月"] = 8
    assert aggregate_org_daily_activity(no_business_date)[0]["month"] == 8


def test_unknown_attribution_month_aborts_without_logging_record_details():
    with pytest.raises(ValueError, match="无法识别业绩归属年月") as error:
        _aggregate(_row(年月日="bad", 年月="bad", 人员工号="do-not-disclose"))
    assert "do-not-disclose" not in str(error.value)


def test_dimensions_and_duplicate_records_have_independent_boolean_evidence():
    source = [_row(), _row(), _row(业务模式="证券", 期交保费=-100, 承保件数=-1),
              _row(销售机构名称="湖北", 期交保费=0), _row(销售机构名称="范围外"),
              _row(业务模式="经代")]
    result = _aggregate(*source)
    assert len(result) == 3
    assert {(r["org"], r["channel"], r["has_positive_qj"]) for r in result} == {
        ("上海", "OTO", 1), ("上海", "证保", 0), ("湖北", "OTO", 0),
    }
    assert set(result[0]) == {"year", "month", "day", "org", "channel", "has_positive_qj", "uncertain"}


@pytest.fixture
def activity_db(tmp_path, monkeypatch):
    import db as db_module
    import db.connection as connection
    from db import init_db
    path = tmp_path / "activity.db"
    monkeypatch.setattr(connection, "DB_PATH", str(path))
    monkeypatch.setattr(db_module, "DB_PATH", str(path))
    init_db()
    return path


def _stored(path):
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT year, month, day, org, channel, has_positive_qj, uncertain "
            "FROM agg_org_daily_activity ORDER BY 1, 2, 3, 4, 5"
        ).fetchall()


def test_schema_migration_is_unique_and_requests_rebuild(activity_db):
    from db import init_db
    init_db()
    with sqlite3.connect(activity_db) as conn:
        assert conn.execute(
            "SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version='20260831_org_zero_streak'"
        ).fetchall() == [(1,)]


def test_incremental_correction_clears_covered_month_even_when_filtered_empty(activity_db):
    from db import replace_rows
    from services.excel_pipeline import ExcelPipelineResult, replace_aggregate_rows
    before = pd.DataFrame([_row(), _row(年月="202607", 年月日="2026-07-31")])
    with sqlite3.connect(activity_db) as conn:
        replace_rows(conn, "agg_org_daily_activity", aggregate_org_daily_activity(before))
        corrected = pd.DataFrame([_row(销售机构名称="范围外", 年月日="bad")])
        result = ExcelPipelineResult(
            rows_by_table={"agg_org_daily_activity": aggregate_org_daily_activity(corrected)},
            raw_tables={"performance": corrected},
        )
        # Exercise only this table; unrelated legacy conditional tables have
        # their own (unchanged) date precision contract.
        import services.excel_pipeline as pipeline
        from unittest.mock import patch
        with patch.object(pipeline, "AGGREGATE_TABLE_ORDER", ["agg_org_daily_activity"]):
            counts = replace_aggregate_rows(conn, result, incremental=True)
        assert counts["agg_org_daily_activity"] == 0
    assert _stored(activity_db) == [(2026, 7, 31, "上海", "OTO", 1, 0)]


def test_excel_full_incremental_and_raw_rebuild_produce_same_rows(activity_db):
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables
    from services.excel_pipeline import ExcelSource, build_excel_pipeline_result, write_excel_pipeline_result
    frame = pd.DataFrame([
        _row(), _row(期交保费=-20000, 承保件数=-1), _row(),
        _row(年月日="2026-08-29", 期交保费=0),
        _row(年月日="2026-08-30", 期交保费=0.01),
        _row(年月日="2026-08-31", 承保件数=0),
    ])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    source = ExcelSource("performance", "synthetic.xlsx", buffer.getvalue())
    result = build_excel_pipeline_result([source])
    with sqlite3.connect(activity_db) as conn:
        write_excel_pipeline_result(conn, result, incremental=False)
    expected = [
        (2026, 8, 28, "上海", "OTO", 1, 0), (2026, 8, 29, "上海", "OTO", 0, 0),
        (2026, 8, 30, "上海", "OTO", 1, 0), (2026, 8, 31, "上海", "OTO", 0, 1),
    ]
    assert _stored(activity_db) == expected
    with sqlite3.connect(activity_db) as conn:
        write_excel_pipeline_result(conn, result, incremental=True)
    assert _stored(activity_db) == expected
    rebuilt = rebuild_aggregates_from_raw_tables()
    assert rebuilt.table_counts["agg_org_daily_activity"] == 4
    assert _stored(activity_db) == expected


def test_raw_rebuild_does_not_lose_business_dates_outside_legacy_month_year(activity_db):
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables
    frame = pd.DataFrame([_row(), _row(年月="202608", 年月日="2025-12-31")])
    with sqlite3.connect(activity_db) as conn:
        frame.to_sql("performance", conn, if_exists="replace", index=False)
    rebuild_aggregates_from_raw_tables()
    assert _stored(activity_db) == [
        (2025, 12, 31, "上海", "OTO", 1, 0), (2026, 8, 28, "上海", "OTO", 1, 0),
    ]


def test_raw_rebuild_aborts_on_unknown_month_without_replacing_old_activity(activity_db):
    from db import replace_rows
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables
    with sqlite3.connect(activity_db) as conn:
        replace_rows(conn, "agg_org_daily_activity", _aggregate(_row()))
        pd.DataFrame([_row(), _row(年月="bad", 年月日="bad")]).to_sql(
            "performance", conn, if_exists="replace", index=False,
        )
    before = _stored(activity_db)
    with pytest.raises(ValueError, match="无法识别业绩归属年月"):
        rebuild_aggregates_from_raw_tables()
    assert _stored(activity_db) == before


def _write_source(path, frame, *, incremental):
    from services.excel_pipeline import ExcelPipelineResult, write_excel_pipeline_result
    result = ExcelPipelineResult(
        rows_by_table={"agg_org_daily_activity": aggregate_org_daily_activity(frame)},
        raw_tables={"performance": frame},
    )
    with sqlite3.connect(path) as conn:
        write_excel_pipeline_result(conn, result, incremental=incremental)


def _assert_matches_persisted_raw(path):
    from services.aggregate_rebuilder import _read_org_activity_rows
    keys = ("year", "month", "day", "org", "channel", "has_positive_qj", "uncertain")
    with sqlite3.connect(path) as conn:
        expected = sorted(tuple(row[key] for key in keys) for row in _read_org_activity_rows(conn))
    assert _stored(path) == expected


def test_incremental_changed_date_layout_recomputes_retained_and_removed_business_months(activity_db):
    # The new upload deletes raw rows by 入账时间 because 年月日 is absent in
    # that upload. Its deletion month is not the old rows' 业绩归属月份.
    original = pd.DataFrame([
        _row(年月="202607", 年月日="2026-07-31", 入账时间="2026-08-01"),
        _row(年月="202608", 年月日="2026-08-05", 入账时间="2026-09-01"),
    ])
    _write_source(activity_db, original, incremental=False)
    incoming = pd.DataFrame([
        _row(年月="202607", 入账时间="2026-08-15", 期交保费=0),
    ]).drop(columns=["年月日"])
    _write_source(activity_db, incoming, incremental=True)
    _assert_matches_persisted_raw(activity_db)
    assert _stored(activity_db) == [
        (2026, 7, 0, "上海", "OTO", 0, 1),
        (2026, 8, 5, "上海", "OTO", 1, 0),
    ]


def test_incremental_new_primary_date_column_recomputes_old_rows_under_global_priority(activity_db):
    original = pd.DataFrame([
        _row(年月="202607", 入账时间="2026-07-31"),
        _row(年月="202608", 入账时间="2026-08-05"),
    ]).drop(columns=["年月日"])
    _write_source(activity_db, original, incremental=False)
    incoming = pd.DataFrame([_row(年月="202607", 年月日="2026-07-20", 入账时间="2026-07-20")])
    _write_source(activity_db, incoming, incremental=True)
    _assert_matches_persisted_raw(activity_db)
    assert _stored(activity_db) == [
        (2026, 7, 0, "上海", "OTO", 0, 1),
        (2026, 7, 20, "上海", "OTO", 1, 0),
        (2026, 8, 0, "上海", "OTO", 0, 1),
    ]


@pytest.mark.parametrize("incoming_primary", [True, False])
def test_import_preflight_rejects_unresolvable_combined_date_schema_before_any_write(activity_db, incoming_primary):
    # Both isolated frames have complete dates, but the persisted union of
    # columns makes one source's primary date NULL without a fallback month.
    original = pd.DataFrame([_row()]).drop(columns=["年", "年月"])
    incoming = pd.DataFrame([_row(年月日="2026-08-31", 入账时间="2026-08-31")]).drop(columns=["年", "年月"])
    if incoming_primary:
        original = original.drop(columns=["年月日"])
    else:
        incoming = incoming.drop(columns=["年月日"])
    _write_source(activity_db, original, incremental=False)
    before_activity = _stored(activity_db)
    with sqlite3.connect(activity_db) as conn:
        before_raw = conn.execute("SELECT * FROM performance").fetchall()
        before_columns = conn.execute("PRAGMA table_info(performance)").fetchall()
    with pytest.raises(ValueError, match="无法识别业绩归属年月"):
        _write_source(activity_db, incoming, incremental=True)
    assert _stored(activity_db) == before_activity
    with sqlite3.connect(activity_db) as conn:
        assert conn.execute("SELECT * FROM performance").fetchall() == before_raw
        assert conn.execute("PRAGMA table_info(performance)").fetchall() == before_columns
