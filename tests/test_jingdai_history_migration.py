import io
import sqlite3

import pandas as pd
import pytest

from services.jingdai_history_migration import migrate_jingdai_history, JINGDAI_SOURCE_COLUMNS
from services.excel_pipeline import ExcelSource, build_excel_pipeline_result, write_excel_pipeline_result
from services.import_preview import build_import_preview
from services.import_safety import append_raw_frame, validate_replacement_fields, RawIncrementalWriteError


def source(day, policy='000001', name='part.xlsx', amount=10000):
    frame = pd.DataFrame([{'统计时间_年月日': day, '销售平台': '测试平台', '投保单号': policy,
                           '产品名称': '测试产品', '产品代码': 'P1', '长短险': '长险',
                           '缴别': '年交', '缴费年限': 5, '期交保费': amount, '年化规保': amount}])
    b = io.BytesIO()
    frame.to_excel(b, index=False)
    return ExcelSource('jingdai', name, b.getvalue())


def test_history_schema_expansion_keeps_signed_counts_rows_and_unknown_identity():
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE jingdai("时间" TEXT,"经代机构" TEXT,"产品名称" TEXT,"缴费年限" REAL,"当前缴别小类" TEXT,"承保保单件数" INTEGER,"期交保费" REAL,"承保年化规保" REAL)')
    rows = [('2020-03', '平台', '产品', 5, '年交', 0, 0, 0),
            ('2023-10-02', '平台', '产品', 5, '年交', -2, -100, -100),
            ('2023-10-02', '平台', '产品', 5, '年交', -2, -100, -100)]
    c.executemany('INSERT INTO jingdai VALUES(?,?,?,?,?,?,?,?)', rows)
    report = migrate_jingdai_history(c)
    assert report['rows'] == 3 and report['legacyRows'] == 3
    assert set(JINGDAI_SOURCE_COLUMNS) <= {r[1] for r in c.execute('PRAGMA table_info(jingdai)')}
    assert c.execute('SELECT "时间","经代机构","产品名称","缴费年限","当前缴别小类","承保保单件数","期交保费","承保年化规保" FROM jingdai').fetchall() == rows
    assert c.execute('SELECT 承保件数,投保单号,产品代码,长短险,件数来源,统计时间_年月日 FROM jingdai').fetchall() == [
        (0, None, None, None, 'source_net', '2020-03'),
        (-2, None, None, None, 'source_net', '2023-10-02'),
        (-2, None, None, None, 'source_net', '2023-10-02')]
    before = list(c.iterdump())
    assert migrate_jingdai_history(c)['addedColumns'] == []
    assert list(c.iterdump()) == before


def test_conflicting_historical_counts_fail_before_mutation():
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE jingdai(承保件数,承保产品件数)')
    c.execute('INSERT INTO jingdai VALUES(0,1)')
    before = list(c.iterdump())
    with pytest.raises(ValueError, match='冲突'):
        migrate_jingdai_history(c)
    assert list(c.iterdump()) == before


def test_multifile_same_month_conserves_premiums_and_range_identity(auth_db):
    from db import get_db
    a, b = source('2026-09-01', name='a.xlsx'), source('2026-09-02', name='b.xlsx', amount=-1000)
    result = build_excel_pipeline_result([a, b])
    assert len(result.raw_tables['jingdai']) == 2
    assert result.raw_tables['jingdai']['承保件数'].sum() == 2  # Daily contributions are not range counts.
    assert result.rows_by_table['agg_jingdai'][0]['qj_premium'] == .9
    with get_db() as c:
        c.execute("INSERT INTO data_imports(file_name,file_hash,file_size,status,data_years,table_counts) VALUES(?,?,?,'success','[2026]','{}')", ('a.xlsx', __import__('hashlib').sha256(a.content).hexdigest(), len(a.content)))
        preview = build_import_preview(c, [a, b])
        assert preview['canImport'] and not any(f['duplicateSkipped'] for f in preview['files'])
        write_excel_pipeline_result(c, result, incremental=True)
        assert c.execute('SELECT COUNT(*),SUM(期交保费) FROM jingdai').fetchone()[:] == (2, 9000)
        assert c.execute('SELECT COUNT(DISTINCT policy_no) FROM agg_jingdai_policy_daily').fetchone()[0] == 1
        write_excel_pipeline_result(c, result, incremental=True)
        assert c.execute('SELECT COUNT(*),SUM(期交保费) FROM jingdai').fetchone()[:] == (2, 9000)


def test_overlap_is_normalized_and_rejected():
    with pytest.raises(RawIncrementalWriteError, match='重叠'):
        build_excel_pipeline_result([source('2026-09-01', name='a.xlsx'), source('2026-09-01 00:00:00', name='b.xlsx')])


def test_legacy_cannot_replace_detail_through_null_placeholder_fields(auth_db):
    from db import get_db
    from etl.jingdai_contract import normalize_jingdai_source
    detail = build_excel_pipeline_result([source('2026-09-01')])
    with get_db() as c:
        write_excel_pipeline_result(c, detail, incremental=True)
        old = normalize_jingdai_source(pd.DataFrame([{'时间':'2026-09-01','期交保费':1,'承保年化规保':1,'承保件数':5}]))
        with pytest.raises(RawIncrementalWriteError, match='旧汇总'):
            validate_replacement_fields(c, 'jingdai', old)
        assert c.execute('SELECT SUM(期交保费) FROM jingdai').fetchone()[0] == 10000


def test_added_null_term_column_preserves_legacy_longterm_classification():
    from etl.aggregates.longterm import aggregate_jingdai_longterm
    from etl.jingdai_contract import normalize_jingdai_source
    old = pd.DataFrame([{'时间':'2023-09-02','经代机构':'平台','期交保费':10000,'承保年化规保':10000,
                         '当前缴别大类':'期交','缴费年限':5,'承保件数':1}])
    assert aggregate_jingdai_longterm(normalize_jingdai_source(old)) == aggregate_jingdai_longterm(old)


def test_web_batch_reads_all_parts_and_failure_cannot_partially_replace(auth_db, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from db import get_db
    monkeypatch.setenv('AUTH_TEST_BYPASS', '1')
    a, b = source('2026-09-01', name='a.xlsx'), source('2026-09-02', name='b.xlsx', amount=-1000)
    client = TestClient(app)
    files = [('jingdai', (a.filename, a.content)), ('jingdai', (b.filename, b.content))]
    preview = client.post('/api/upload/preview', files=files)
    assert preview.status_code == 200 and preview.json()['canImport']
    imported = client.post('/api/upload', files=files, params={'preview_manifest': preview.json()['manifestHash']})
    assert imported.status_code == 200
    with get_db() as c:
        assert c.execute('SELECT COUNT(*),SUM(期交保费) FROM jingdai').fetchone()[:] == (2, 9000)
    bad = client.post('/api/upload', files=[('jingdai', (a.filename, a.content)), ('jingdai', ('bad.xlsx', b'broken'))],
                      params={'force': 'true', 'allow_partial': 'true'})
    assert bad.status_code == 400
    with get_db() as c:
        assert c.execute('SELECT COUNT(*),SUM(期交保费) FROM jingdai').fetchone()[:] == (2, 9000)
