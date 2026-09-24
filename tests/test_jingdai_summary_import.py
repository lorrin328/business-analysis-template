import io
import sqlite3

import pandas as pd
import pytest

from etl.parser import parse_jingdai_excel
from services.excel_pipeline import ExcelSource, build_excel_pipeline_result
from services.import_preview import build_import_preview


def source(rows):
    out = io.BytesIO()
    pd.DataFrame(rows).to_excel(out, index=False)
    return ExcelSource('jingdai', 'synthetic.xlsx', out.getvalue())


DETAIL = {'时间': '2026-09-02', '缴费年限': 10, '产品名称': '合成产品',
          '经代机构': '合成机构', '承保年化规保': 100, '期交保费': 100}


@pytest.mark.parametrize('label', ['合计', '总计', 'Grand Total'])
def test_export_footer_is_excluded_consistently_from_preview_and_import(auth_db, label):
    data = source([DETAIL, {'时间': label, '承保年化规保': 100, '期交保费': 100}])
    parsed = parse_jingdai_excel(data.content)
    assert len(parsed) == 1
    assert parsed.attrs['ignored_summary_rows'] == 1
    with sqlite3.connect(':memory:') as conn:
        preview = build_import_preview(conn, [data])
    assert preview['canImport']
    assert preview['files'][0]['rowCount'] == 1
    assert preview['files'][0]['ignoredSummaryRows'] == 1
    assert any('合计' in warning for warning in preview['warnings'])
    pipeline = build_excel_pipeline_result([data])
    assert len(pipeline.raw_tables['jingdai']) == 1
    assert sum(row['qj_premium'] for row in pipeline.rows_by_table['agg_jingdai']) == .01


@pytest.mark.parametrize('bad', [dict(DETAIL, 时间=None), dict(DETAIL, 时间='invalid'),
                                dict(DETAIL, 时间='合计')])
def test_real_detail_with_invalid_period_is_not_silently_removed(bad):
    data = source([DETAIL, bad])
    assert len(parse_jingdai_excel(data.content)) == 2
    with sqlite3.connect(':memory:') as conn:
        preview = build_import_preview(conn, [data])
    assert not preview['canImport']


def test_total_inside_detail_is_not_automatically_removed():
    data = source([{'时间': '合计', '期交保费': 100}, DETAIL])
    with sqlite3.connect(':memory:') as conn:
        assert not build_import_preview(conn, [data])['canImport']


@pytest.mark.parametrize('column', ['当前缴别大类', '当前缴别小类', '缴费年限范围',
                                   '保障期限', '业务类型', '产品大类', '经代机构', '中介公司'])
def test_month_replacement_cannot_erase_existing_jingdai_dimensions(column):
    from services.import_safety import append_raw_frame, validate_replacement_fields, RawIncrementalWriteError
    with sqlite3.connect(':memory:') as conn:
        append_raw_frame(conn, 'jingdai', pd.DataFrame([dict(DETAIL, **{column: '已知维度'})]))
        replacement = pd.DataFrame([DETAIL]).drop(columns=[column], errors='ignore')
        with pytest.raises(RawIncrementalWriteError, match=column):
            validate_replacement_fields(conn, 'jingdai', replacement)
        # A missing field in an unrelated month does not block import.
        replacement['时间'] = '2026-08-01'
        validate_replacement_fields(conn, 'jingdai', replacement)


def test_expanded_jingdai_columns_survive_raw_storage_without_changing_totals(auth_db):
    from services.import_safety import append_raw_frame
    new_columns = {'当前缴别小类': '年交', '保障期限': 99, '业务类型': '线上', '产品大类': '普通寿险'}
    data = source([dict(DETAIL, **new_columns), {'时间': '合计', '期交保费': 100, '承保年化规保': 100}])
    result = build_excel_pipeline_result([data])
    with sqlite3.connect(':memory:') as conn:
        append_raw_frame(conn, 'jingdai', pd.DataFrame([DETAIL]))
        conn.execute('DELETE FROM jingdai')
        append_raw_frame(conn, 'jingdai', result.raw_tables['jingdai'])
        row = conn.execute('SELECT "当前缴别小类", "保障期限", "业务类型", "产品大类" FROM jingdai').fetchone()
        assert row == ('年交', '99.0', '线上', '普通寿险')
    assert sum(row['qj_premium'] for row in result.rows_by_table['agg_jingdai']) == .01
