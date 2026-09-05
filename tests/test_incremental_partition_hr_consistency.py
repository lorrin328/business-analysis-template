"""Synthetic end-to-end regressions for source-dependent incremental aggregates."""
import io
import sqlite3

import pandas as pd
import pytest

from services.excel_pipeline import ExcelSource, build_excel_pipeline_result, write_excel_pipeline_result


@pytest.fixture
def connection(tmp_path, monkeypatch):
    import db
    import db.connection as database
    path = tmp_path / "partition.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    with sqlite3.connect(path) as conn:
        yield conn


def perf(month=9, staff="SYNTHETIC-1", **updates):
    row = {
        "年": 2026, "年月": f"2026{month:02d}", "年月日": f"2026-{month:02d}-01",
        "业务模式": "OTO", "销售机构名称": "上海", "人员工号": staff,
        "期交保费": 10000, "折算保费": 10000, "年化规保": 10000,
        "承保件数": 1, "长短险": "长期", "缴费年限": 10, "产品代码": "SYNTHETIC",
    }
    row.update(updates)
    return row


def hr(month=9):
    return {"统计年": 2026, "统计日期": f"2026{month:02d}", "业务模式名称": "OTO",
            "销售机构名称": "上海", "月初在职人力": 10, "月末在职人力": 10}


def write(conn, *, performance=None, human=None, incremental=True):
    sources = []
    for kind, rows in (("performance", performance), ("hr", human)):
        if rows is not None:
            buffer = io.BytesIO()
            pd.DataFrame(rows).to_excel(buffer, index=False)
            sources.append(ExcelSource(kind, "synthetic.xlsx", buffer.getvalue()))
    result = build_excel_pipeline_result(sources)
    write_excel_pipeline_result(conn, result, incremental=incremental)
    conn.commit()


def activity(conn, table="agg_hr_data"):
    return conn.execute(f"SELECT month, active_headcount FROM {table} ORDER BY month").fetchall()


def test_corrected_month_with_no_longterm_clears_only_its_source(connection):
    c = connection
    write(c, performance=[perf(8), perf(9), perf(10)], incremental=False)
    c.execute("INSERT INTO agg_longterm_qj(year,month,day,business_type,channel,org,qj_premium) VALUES(2026,9,1,'经代','','上海',99)")
    c.commit()
    write(c, performance=[perf(9, 长短险="短期", 缴费年限=1), perf(10)])
    assert c.execute("SELECT month,business_type,qj_premium FROM agg_longterm_qj ORDER BY month,business_type").fetchall() == [
        (8, "转型", 1.0), (9, "经代", 99.0), (10, "转型", 1.0)]


def test_hr_only_import_preserves_real_activity_and_performance_only_recomputes_it(connection):
    c = connection
    write(c, performance=[perf(8), perf(9), perf(9, staff="SYNTHETIC-2")], human=[hr(8), hr(9)], incremental=False)
    write(c, human=[hr(9)])
    assert activity(c) == [(8, 1), (9, 2)]
    assert activity(c, "agg_org_hr_data") == [(8, 1), (9, 2)]
    write(c, performance=[perf(9, 期交保费=0, 折算保费=0)])
    assert activity(c) == [(8, 1), (9, 0)]
    assert activity(c, "agg_org_hr_data") == [(8, 1), (9, 0)]


def test_different_uploaded_hr_and_performance_months_use_persisted_counterpart(connection):
    c = connection
    write(c, performance=[perf(8), perf(9)], human=[hr(8), hr(9)], incremental=False)
    write(c, performance=[perf(8), perf(8, staff="SYNTHETIC-2")], human=[hr(9)])
    assert activity(c) == [(8, 2), (9, 1)]


def test_changed_source_month_refreshes_old_and_new_hr_without_booking_day_confusion(connection):
    c = connection
    # Both records book in September but activity is grouped by their source month.
    write(c, performance=[perf(8, 年月日="2026-09-01"), perf(8, staff="SYNTHETIC-RETAINED")], human=[hr(8), hr(9)], incremental=False)
    write(c, performance=[perf(9, 年月日="2026-09-01")])
    # September replacement removes the cross-month record, not the retained August record.
    assert activity(c) == [(8, 1), (9, 1)]
    assert activity(c, "agg_org_hr_data") == [(8, 1), (9, 1)]


def test_same_schema_import_scans_org_activity_once_and_rolls_back_on_failure(connection, monkeypatch):
    import services.aggregate_rebuilder as rebuilder
    import services.excel_pipeline as pipeline
    c = connection
    write(c, performance=[perf(8), perf(9)], human=[hr(8), hr(9)], incremental=False)
    real_read = rebuilder._read_org_activity_rows
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return real_read(*args, **kwargs)
    monkeypatch.setattr(rebuilder, "_read_org_activity_rows", counted)
    monkeypatch.setattr(pipeline, "_read_org_activity_rows", counted)
    write(c, performance=[perf(9), perf(9, staff="SYNTHETIC-2")])
    assert len(calls) == 1
    before_raw = c.execute("SELECT * FROM performance").fetchall()
    before_hr = activity(c)
    before_longterm = c.execute("SELECT * FROM agg_longterm_qj").fetchall()
    def fail(*args, **kwargs):
        raise ValueError("synthetic history validation failure")
    monkeypatch.setattr(rebuilder, "_read_org_activity_rows", fail)
    with pytest.raises(ValueError, match="synthetic history"):
        write(c, performance=[perf(9, 期交保费=0, 折算保费=0)])
    assert c.execute("SELECT * FROM performance").fetchall() == before_raw
    assert activity(c) == before_hr
    assert c.execute("SELECT * FROM agg_longterm_qj").fetchall() == before_longterm


def test_consistency_migration_requires_rebuild(connection):
    assert connection.execute("SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version='20260905_incremental_partition_and_hr_consistency'").fetchall() == [(1,)]


def test_jingdai_zero_longterm_preserves_transform_partition(connection):
    c = connection
    write(c, performance=[perf(9)], incremental=False)
    def upload_jingdai(pay_years):
        buffer = io.BytesIO()
        pd.DataFrame([{"时间": "2026-09-02", "缴费年限": pay_years,
                       "产品名称": "合成产品", "经代机构": "合成机构",
                       "当前缴别大类": "期交", "承保年化规保": 20000,
                       "期交保费": 20000}]).to_excel(buffer, index=False)
        result = build_excel_pipeline_result([ExcelSource("jingdai", "synthetic.xlsx", buffer.getvalue())])
        c.row_factory = sqlite3.Row
        write_excel_pipeline_result(c, result, incremental=True)
        c.row_factory = None
        c.commit()
    upload_jingdai(10)
    assert c.execute("SELECT COUNT(*) FROM agg_longterm_qj WHERE business_type='经代'").fetchone()[0] == 1
    upload_jingdai(1)
    assert c.execute("SELECT business_type,qj_premium FROM agg_longterm_qj").fetchall() == [("转型", 1.0)]
