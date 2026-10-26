import io
import sqlite3

import pandas as pd
import pytest

from etl.jingdai_contract import normalize_jingdai_source
from services.excel_pipeline import ExcelSource, ExcelPipelineResult, build_excel_pipeline_result, write_excel_pipeline_result
from services.import_preview import build_import_preview
from services.import_safety import RawIncrementalWriteError, validate_jingdai_detail_years
from services.jingdai_history_migration import restore_jingdai_history


def detail(year):
    return normalize_jingdai_source(pd.DataFrame([{'时间': f'{year}-01-02', '销售平台': '平台',
        '投保单号': '000123', '产品名称': '产品', '缴费年限': 5,
        '期交保费': 10000, '年化规保': 10000}]), source_format='policy_detail')


@pytest.mark.parametrize('year', range(2020, 2025))
def test_new_identity_details_cannot_replace_retained_history(year):
    with pytest.raises(RawIncrementalWriteError, match='2020—2024'):
        validate_jingdai_detail_years(detail(year))


def test_legacy_counts_remain_accepted_and_recent_details_allowed():
    old = normalize_jingdai_source(pd.DataFrame([{'时间':'2024-01', '承保件数':-2,
        '期交保费':-200, '承保年化规保':-1000}]))
    validate_jingdai_detail_years(old)
    assert old['承保件数'].iloc[0] == -2 and old['投保单号'].isna().all()
    validate_jingdai_detail_years(detail(2025))
    validate_jingdai_detail_years(detail(2026))


def test_preview_and_direct_write_enforce_years_before_any_change(auth_db):
    row = {'统计时间_年月日':'2024-01-02', '销售平台':'平台', '投保单号':'000123',
           '期交保费':100, '年化规保':1000, '缴费年限':5}
    b=io.BytesIO();pd.DataFrame([row]).to_excel(b,index=False)
    with sqlite3.connect(':memory:') as c:
        preview=build_import_preview(c,[ExcelSource('jingdai','history.xlsx',b.getvalue())])
        assert not preview['canImport'] and '2020—2024' in preview['errors'][0]
        before=list(c.iterdump())
        with pytest.raises(RawIncrementalWriteError,match='2020—2024'):
            write_excel_pipeline_result(c,ExcelPipelineResult(raw_tables={'jingdai':detail(2024)}),incremental=False)
        assert list(c.iterdump())==before
    with pytest.raises(RawIncrementalWriteError,match='2020—2024'):
        build_excel_pipeline_result([ExcelSource('jingdai','history.xlsx',b.getvalue())])


def test_scoped_restore_retains_original_counts_and_preserves_recent_and_non_jd(tmp_path):
    baseline=tmp_path/'before.db'
    def init(c):
        c.execute('CREATE TABLE jingdai(时间 TEXT,经代机构 TEXT,产品名称 TEXT,期交保费 REAL,承保年化规保 REAL,承保件数 INTEGER)')
        c.execute('CREATE TABLE agg_product_daily(id INTEGER PRIMARY KEY,year INTEGER,business_type TEXT,qj_premium REAL,count INTEGER)')
    with sqlite3.connect(baseline) as c:
        init(c);c.execute("INSERT INTO jingdai VALUES('2024-01-02','平台','产品',-100,-1000,-1)")
        c.execute("INSERT INTO agg_product_daily VALUES(1,2024,'经代',-0.01,-1)");c.commit()
    with sqlite3.connect(':memory:') as c:
        init(c)
        c.executemany('INSERT INTO jingdai VALUES(?,?,?,?,?,?)', [('2024-01-02','新平台','新产品',999,999,1),('2025-01-02','平台','产品',200,1000,1)])
        c.executemany('INSERT INTO agg_product_daily VALUES(?,?,?,?,?)', [(1,2024,'经代',9,9),(2,2024,'转型',5,7),(3,2025,'经代',2,1)])
        counts=restore_jingdai_history(c,baseline)
        assert counts['jingdai']==1
        assert c.execute('SELECT 时间,期交保费,承保件数,投保单号,经代源格式 FROM jingdai ORDER BY 时间').fetchall()==[
            ('2024-01-02',-100,-1,None,'legacy_aggregate'),('2025-01-02',200,1,None,'legacy_aggregate')]
        assert c.execute('SELECT * FROM agg_product_daily ORDER BY id').fetchall()==[(1,2024,'经代',-.01,-1),(2,2024,'转型',5,7),(3,2025,'经代',2,1)]


def test_raw_rebuild_does_not_erase_aggregate_only_history(auth_db):
    from db import get_db
    from services.aggregate_rebuilder import rebuild_aggregates_from_raw_tables
    with get_db() as c:
        c.execute("INSERT INTO agg_jingdai(year,month,qj_premium,gm_premium,zs_premium) VALUES(2024,1,123,321,50)")
        c.execute("INSERT INTO agg_product_daily(year,month,day,business_type,channel,org,product_category,product_name,qj_premium,gm_premium,count) VALUES(2024,1,2,'经代','经代','平台','产品','产品',123,321,8)")
        c.execute("INSERT INTO agg_payment_period(year,month,business_type,channel,org,category,qj_premium,gm_premium,count) VALUES(2024,1,'经代','','平台','5年交',123,321,8)")
        from services.import_safety import append_raw_frame
        append_raw_frame(c,'performance',pd.DataFrame([{'年':2024,'年月':'202401','年月日':'2024-01-02',
            '业务模式':'证保','销售机构名称':'上海','产品名称':'测试','产品代码':'4281','长短险':'长期',
            '缴费年限':5,'人员工号':'test','期交保费':10000,'年化规保':10000,'折算保费':10000,'承保件数':1}]))
        c.commit()
    rebuild_aggregates_from_raw_tables()
    with get_db() as c:
        assert c.execute('SELECT qj_premium,gm_premium,zs_premium FROM agg_jingdai WHERE year=2024').fetchone()[:] == (123,321,50)
        assert c.execute("SELECT SUM(qj_premium),SUM(count) FROM agg_product_daily WHERE year=2024 AND business_type='经代'").fetchone()[:] == (123,8)
        assert c.execute("SELECT SUM(qj_premium),SUM(count) FROM agg_payment_period WHERE year=2024 AND business_type='经代'").fetchone()[:] == (123,8)
        assert c.execute('SELECT COUNT(*) FROM jingdai').fetchone()[0] == 0
