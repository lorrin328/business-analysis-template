"""Period parsing must survive historical SQLite formats and source row order."""
import sqlite3
import pandas as pd
import pytest
from etl.normalize import NumericSourceError, _period_year_month, _to_number
from etl.aggregates.performance import aggregate_daily_performance, aggregate_performance
from services.excel_pipeline import _refresh_hr_from_current_sources

@pytest.mark.parametrize('reverse', [False, True])
def test_mixed_calendar_formats_keep_all_rows(reverse):
    values = ['2024-01', '2026-09-01 00:00:00', '202609', '2026/09/02',
              '2026年9月3日', '2026-09-04T12:34:56.123']
    if reverse:
        values.reverse()
    result = _period_year_month(pd.DataFrame({'年月': values}), None, '年月')
    assert len(result) == len(values)
    assert set(zip(result['_year'], result['_month'])) == {(2024, 1), (2026, 9)}

@pytest.mark.parametrize('value', [9, 9.0, '9.0', 202609, 202609.0, '202609.0', 20260901.0])
def test_integral_numeric_periods_never_become_epoch(value):
    result = _period_year_month(pd.DataFrame({'年': [2026], '年月': [value]}), '年', '年月')
    assert list(zip(result['_year'], result['_month'])) == [(2026, 9)]

@pytest.mark.parametrize('value', [9.5, '9.5', '202609.5', '2026-13-01', 'invalid'])
def test_invalid_periods_are_not_truncated(value):
    assert _period_year_month(pd.DataFrame({'年': [2026], '年月': [value]}), '年', '年月').empty


def test_month_only_source_keeps_month_total_without_fabricating_daily_rows():
    frame = pd.DataFrame({
        '年': [2026, 2026], '年月': ['2026-09', '2026-09-02'],
        '业务模式': ['OTO', 'OTO'], '期交保费': [10000, 5000],
    })
    assert aggregate_performance(frame)[0]['qj_premium'] == 1.5
    assert aggregate_daily_performance(frame) == []


def test_amount_parser_distinguishes_valid_zero_thousands_and_invalid_text():
    parsed = _to_number(pd.Series(['0', '1,000', None], name='期交保费'))
    assert parsed.tolist() == [0, 1000, 0]
    with pytest.raises(NumericSourceError, match='1个非法数值'):
        _to_number(pd.Series(['1,00'], name='期交保费'))
    with pytest.raises(NumericSourceError, match='1个必填缺失'):
        _to_number(pd.Series([None], name='期交保费'), required=True)

@pytest.mark.parametrize('numeric', [False, True])
def test_refresh_activity_with_historical_sqlite_formats(numeric):
    with sqlite3.connect(':memory:') as c:
        affinity = 'REAL' if numeric else 'TEXT'
        c.execute(f'CREATE TABLE performance("年" REAL,"年月" {affinity},"业务模式" TEXT,"销售机构名称" TEXT,"人员工号" TEXT,"折算保费" REAL,"长短险" TEXT)')
        c.executemany('INSERT INTO performance VALUES(?,?,?,?,?,?,?)', [
            (2024, 1 if numeric else '2024-01', 'OTO', '上海', 'synthetic-old', 100, '长期'),
            (2026, 9 if numeric else '2026-09-01 00:00:00', 'OTO', '上海', 'synthetic-new', 100, '长期')])
        pd.DataFrame([{'统计年': y, '统计日期': f'{y}-{m:02}', '业务模式名称': 'OTO',
                       '销售机构名称': '上海', '月初在职人力': 10, '月末在职人力': 10}
                      for y,m in [(2024,1),(2026,9)]]).to_sql('hr_data',c,index=False)
        for table,org in [('agg_hr_data',''),('agg_org_hr_data','org TEXT,')]:
            c.execute(f'CREATE TABLE {table}(year INTEGER,month INTEGER,{org}channel TEXT,start_headcount INTEGER,end_headcount INTEGER,active_headcount INTEGER)')
        _refresh_hr_from_current_sources(c,{(2024,1),(2026,9)})
        for table in ['agg_hr_data','agg_org_hr_data']:
            assert c.execute(f'SELECT year,month,active_headcount FROM {table} ORDER BY year').fetchall() == [(2024,1,1),(2026,9,1)]
