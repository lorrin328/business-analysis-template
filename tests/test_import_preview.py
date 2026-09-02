import hashlib
import io
import json
import sqlite3

import pandas as pd
import pytest

from services.excel_pipeline import ExcelSource, build_excel_pipeline_result, write_excel_pipeline_result
from services.import_preview import build_import_manifest, build_import_preview


def workbook(kind="performance", rows=None, name="synthetic.xlsx"):
    if rows is None:
        rows = [{"年月": "202608", "业务模式": "OTO", "投保单号": "1234567890123",
                 "投保人id": "synthetic-customer", "期交保费": 10000}]
    defaults = {"performance": {"年": 2026, "缴费年限": 10, "人员工号": "synthetic-staff", "销售机构名称": "上海"},
                "jingdai": {"缴费年限": 10}, "hr": {"统计年": 2026}}
    rows = [dict(defaults.get(kind, {}), **row) for row in rows]
    buffer = io.BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return ExcelSource(kind, name, buffer.getvalue())


def read_only_connection():
    from db.connection import DB_PATH
    from pathlib import Path
    return sqlite3.connect(Path(DB_PATH).as_uri() + "?mode=ro", uri=True)


def test_preview_is_read_only_and_returns_only_counts_and_periods(auth_db):
    from db import get_db
    source = workbook()
    with get_db() as conn:
        pd.DataFrame([{"年月": "202608", "业务模式": "OTO", "投保单号": "5555555555555",
                       "投保人id": "old-customer", "期交保费": 5}]).to_sql("performance", conn, index=False, if_exists="replace")
    with read_only_connection() as conn:
        before = list(conn.iterdump())
        result = build_import_preview(conn, [source])
        assert result["canImport"] is True
        assert result["files"][0]["rowCount"] == 1
        assert result["files"][0]["periods"] == ["2026-08"]
        assert result["files"][0]["existingRows"] == 1
        assert result["files"][0]["writeRows"] == 1
        assert list(conn.iterdump()) == before
        assert conn.total_changes == 0
        assert not conn.in_transaction
    text = json.dumps(result)
    assert "1234567890123" not in text
    assert "synthetic-customer" not in text
    assert "old-customer" not in text


def test_preview_blocks_replacement_missing_enabled_business_field(auth_db):
    from db import get_db
    with get_db() as conn:
        pd.DataFrame([{"年月": "202608", "业务模式": "OTO", "期交保费": 5,
                       "是否职拓": "是"}]).to_sql("performance", conn, index=False, if_exists="replace")
    with read_only_connection() as conn:
        result = build_import_preview(conn, [workbook()])
    assert result["canImport"] is False
    assert "是否职拓" in result["errors"][0]
    assert "保留原数据" in result["errors"][0]


def test_supplement_preview_is_idempotent_and_blocks_conflicts(auth_db):
    from db import get_db
    rows = [{"年月": "202608", "业务模式": "OTO", "投保单号": "1234567890123", "期交保费": 10000}]
    with get_db() as conn:
        pd.read_excel(io.BytesIO(workbook(rows=rows).content)).to_sql("performance", conn, index=False, if_exists="replace")
    with read_only_connection() as conn:
        same = build_import_preview(conn, [workbook(rows=rows)], import_mode="supplement")
        assert same["canImport"] is True
        assert same["files"][0]["writeRows"] == 0
        new = build_import_preview(conn, [workbook(rows=rows + [dict(rows[0], 投保单号="1234567890124")])], import_mode="supplement")
        assert new["files"][0]["writeRows"] == 1
        conflict = build_import_preview(conn, [workbook(rows=[dict(rows[0], 期交保费=20000)])], import_mode="supplement")
        assert conflict["canImport"] is False
        assert "不一致" in conflict["errors"][0]
        assert conn.execute("SELECT COUNT(*) FROM performance").fetchone()[0] == 1


def test_preview_all_four_types_and_supplement_limit(auth_db):
    sources = [workbook(),
               workbook("jingdai", [{"时间": "2026-08-31", "期交保费": 10000, "承保年化规保": 10000, "产品名称": "合成产品"}]),
               workbook("hr", [{"统计日期": "202608", "业务模式名称": "OTO", "月初在职人力": 1, "月末在职人力": 1}]),
               workbook("value", [{"年月": "202608", "业务模式名称": "OTO", "价值": 100}])]
    with read_only_connection() as conn:
        before = list(conn.iterdump())
        result = build_import_preview(conn, sources)
        assert result["canImport"] is True
        assert len(result["files"]) == 4
        assert all(item["periods"] == ["2026-08"] for item in result["files"])
        assert list(conn.iterdump()) == before
        rejected = build_import_preview(conn, sources, import_mode="supplement")
        assert not rejected["canImport"]
        assert "仅允许转型业务清单" in rejected["errors"][0]


def test_preview_duplicate_and_force_match_import_rules(auth_db):
    from db import get_db
    source = workbook()
    with get_db() as conn:
        conn.execute("INSERT INTO data_imports(file_name,file_hash,file_size,status,data_years,table_counts) VALUES(?,?,?,'success','[]','{}')",
                     (source.filename, hashlib.sha256(source.content).hexdigest(), len(source.content)))
        conn.commit()
    with read_only_connection() as conn:
        skipped = build_import_preview(conn, [source])
        forced = build_import_preview(conn, [source], force=True)
    assert skipped["files"][0]["duplicateSkipped"]
    assert skipped["files"][0]["writeRows"] == 0
    assert not forced["files"][0]["duplicateSkipped"]
    assert forced["files"][0]["writeRows"] == 1


@pytest.mark.parametrize("rows", [[{"业务模式": "OTO", "期交保费": 1}],
                                  [{"业务模式": "OTO", "期交保费": 1, "年月": "invalid"}]])
def test_preview_rejects_missing_period(auth_db, rows):
    with read_only_connection() as conn:
        result = build_import_preview(conn, [workbook(rows=rows)])
    assert not result["canImport"]
    assert "统计年月" in result["errors"][0]


def test_preview_sanitizes_parser_error(auth_db, monkeypatch):
    import services.import_preview as preview
    def fail(_):
        raise ValueError("secret-customer-cell")
    label, table, _, required = preview.SOURCE_TYPES["performance"]
    monkeypatch.setitem(preview.SOURCE_TYPES, "performance", (label, table, fail, required))
    with read_only_connection() as conn:
        result = build_import_preview(conn, [ExcelSource("performance", "synthetic.xlsx", b"invalid")])
    assert not result["canImport"]
    assert "secret-customer-cell" not in json.dumps(result)


def test_manifest_binds_all_files_source_slots_modes_and_force():
    a, b = ExcelSource("performance", "a.xlsx", b"a"), ExcelSource("hr", "b.xlsx", b"b")
    base = build_import_manifest([a, b])
    assert build_import_manifest([b, a]) == base
    for sources, mode, force in [([a], "replace_months", False),
                                  ([a, b], "supplement", False),
                                  ([a, b], "replace_months", True),
                                  ([a, ExcelSource("hr", "b.xlsx", b"changed")], "replace_months", False),
                                  ([a, ExcelSource("value", "b.xlsx", b"b")], "replace_months", False)]:
        assert build_import_manifest(sources, mode, force) != base


def test_jingdai_parse_has_no_configuration_side_effects(auth_db, monkeypatch):
    import etl.aggregates.jingdai as jd
    import services.product_config_service as config
    def forbidden():
        raise AssertionError("parse must not open a database")
    monkeypatch.setattr(jd, "get_db", forbidden)
    monkeypatch.setattr(config, "get_db", forbidden)
    result = build_excel_pipeline_result([workbook("jingdai", [{"时间": "2026-08-31", "期交保费": 10000,
                                                                "承保年化规保": 10000, "缴费年限": 10, "产品名称": "合成新产品"}])])
    assert result.row_count("jingdai") == 1
    with read_only_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_config").fetchone()[0] == 0


def test_jingdai_configuration_and_aggregates_share_write_transaction(auth_db, monkeypatch):
    from db import get_db
    import services.excel_pipeline as pipeline
    source = workbook("jingdai", [{"时间": "2026-08-31", "期交保费": 10000,
                                    "承保年化规保": 10000, "缴费年限": 10, "产品名称": "合成年金"},
                                   {"时间": "2026-08-31", "期交保费": 10000,
                                    "承保年化规保": 10000, "缴费年限": 10, "产品名称": "合成新产品"}])
    result = build_excel_pipeline_result([source])
    with get_db() as conn:
        conn.execute("INSERT INTO product_config(product_code,product_name,business_type,is_annuity) VALUES('合成年金','合成年金','经代','Y')")
        conn.commit()
        with monkeypatch.context() as patch:
            def fail(*args, **kwargs):
                raise RuntimeError("synthetic late failure")
            patch.setattr(pipeline, "replace_aggregate_rows", fail)
            with pytest.raises(RuntimeError, match="synthetic late failure"):
                write_excel_pipeline_result(conn, result, incremental=True)
        assert conn.execute("SELECT COUNT(*) FROM product_config").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM jingdai").fetchone()[0] == 0
        write_excel_pipeline_result(conn, result, incremental=True)
        assert conn.execute("SELECT product_annuity FROM agg_jingdai WHERE year=2026 AND month=8").fetchone()[0] == 1
        assert conn.execute("SELECT product_annuity FROM agg_jingdai_daily WHERE year=2026 AND month=8").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_config").fetchone()[0] == 2
        conn.rollback()
        assert conn.execute("SELECT COUNT(*) FROM product_config").fetchone()[0] == 1


def test_failed_source_parse_does_not_leave_raw_data_in_partial_import(monkeypatch):
    import services.excel_pipeline as pipeline
    result = pipeline.ExcelPipelineResult(raw_tables={"hr_data": pd.DataFrame({"existing": [1]})})
    source = workbook("jingdai", [{"时间": "2026-08-31", "期交保费": 10000,
                                    "承保年化规保": 10000, "产品名称": "合成新产品"}])
    def fail(*args, **kwargs):
        raise ValueError("synthetic parse failure")
    monkeypatch.setattr(pipeline, "aggregate_jingdai_payment_period", fail)
    with pytest.raises(ValueError, match="synthetic parse failure"):
        pipeline.append_excel_source(result, source)
    assert set(result.raw_tables) == {"hr_data"}
    assert result.rows_by_table == {}
    assert result.source_summaries == []


def test_force_repeat_source_without_optional_fields_keeps_them_null(auth_db, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "synthetic.lock"))
    source = workbook()
    client = TestClient(app)
    first = client.post("/api/upload", files={"performance": (source.filename, source.content)})
    assert first.status_code == 200, first.json()
    repeat = client.post("/api/upload?force=true", files={"performance": (source.filename, source.content)})
    assert repeat.status_code == 200, repeat.json()
    with read_only_connection() as conn:
        assert conn.execute('SELECT "年化规保", "承保件数" FROM performance').fetchall() == [(None, None)]
        assert conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0] == 2


def test_source_real_zero_is_protected_when_later_file_omits_field(auth_db, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.setenv("BUSINESS_ANALYSIS_LOCK", str(tmp_path / "synthetic.lock"))
    rows = [{"年月": "202608", "业务模式": "OTO", "投保单号": "1234567890123", "期交保费": 10000}]
    source = workbook(rows=[dict(rows[0], 年化规保=0)])
    client = TestClient(app)
    first = client.post("/api/upload", files={"performance": (source.filename, source.content)})
    assert first.status_code == 200, first.json()
    omitted = workbook(rows=rows)
    rejected = client.post("/api/upload?force=true", files={"performance": (omitted.filename, omitted.content)})
    assert rejected.status_code == 400
    assert "年化规保" in rejected.json()["detail"]["errors"][0]
    with read_only_connection() as conn:
        assert conn.execute('SELECT "年化规保" FROM performance').fetchall() == [(0,)]
        assert conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0] == 1
