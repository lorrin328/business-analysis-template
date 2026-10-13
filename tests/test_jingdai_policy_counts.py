"""Authoritative net counts, missing coverage and both query paths."""
from contextlib import contextmanager
import io
import sqlite3

import pandas as pd
import pytest

from etl.aggregates.dashboard import aggregate_jingdai_product_daily
from etl.aggregates.payment import aggregate_jingdai_payment_period, aggregate_jingdai_payment_period_daily
from services.excel_pipeline import ExcelSource, build_excel_pipeline_result
from services.import_preview import build_import_preview
from services.import_safety import append_raw_frame, validate_replacement_fields, RawIncrementalWriteError


BASE = {'时间': '2026-09-02', '缴费年限': 5, '产品名称': '合成产品',
        '经代机构': '合成机构', '承保年化规保': 120000, '期交保费': 100000}


def source(rows):
    out = io.BytesIO()
    pd.DataFrame(rows).to_excel(out, index=False)
    return ExcelSource('jingdai', 'synthetic.xlsx', out.getvalue())


@pytest.mark.parametrize('aggregate', [aggregate_jingdai_product_daily,
    aggregate_jingdai_payment_period, aggregate_jingdai_payment_period_daily])
def test_net_count_is_sum_including_zero_and_reversals(aggregate):
    rows = [dict(BASE, 承保件数=8), dict(BASE, 承保件数=-2, 期交保费=-20000),
            dict(BASE, 承保件数=0, 期交保费=10000)]
    result = aggregate(pd.DataFrame(rows))
    assert len(result) == 1
    assert result[0]['count'] == 6  # Three source rows are not three policies.
    assert result[0]['count_missing'] == 0
    assert result[0]['qj_premium'] == 9


@pytest.mark.parametrize('aggregate', [aggregate_jingdai_payment_period, aggregate_jingdai_payment_period_daily])
def test_unknown_payment_period_keeps_premium_and_authoritative_count(aggregate):
    result = aggregate(pd.DataFrame([dict(BASE, 缴费年限=None, 承保件数=8)]))
    assert result[0]['category'] == '未分类'
    assert result[0]['count'] == 8 and result[0]['qj_premium'] == 10


@pytest.mark.parametrize('value', [None, ''])
@pytest.mark.parametrize('aggregate', [aggregate_jingdai_product_daily, aggregate_jingdai_payment_period_daily])
def test_missing_count_is_tracked_separately_from_real_zero(aggregate, value):
    result = aggregate(pd.DataFrame([dict(BASE, 承保件数=0), dict(BASE, 承保件数=value)]))
    assert result[0]['count'] == 0
    assert result[0]['count_missing'] == 1
    legacy = aggregate(pd.DataFrame([BASE]))
    assert legacy[0]['count'] == 0 and legacy[0]['count_missing'] == 1


def test_counted_footer_preview_and_pipeline_agree(auth_db):
    data = source([dict(BASE, 承保件数=6),
        {'时间': '合计', '期交保费': 100000, '承保年化规保': 120000, '承保件数': 6}])
    with sqlite3.connect(':memory:') as conn:
        preview = build_import_preview(conn, [data])
    assert preview['canImport']
    assert preview['files'][0]['ignoredSummaryRows'] == 1
    result = build_excel_pipeline_result([data])
    assert len(result.raw_tables['jingdai']) == 1
    for table in ('agg_product_daily', 'agg_payment_period', 'agg_payment_period_daily'):
        assert sum(r['count'] for r in result.rows_by_table[table]) == 6


def test_actual_export_count_alias_is_normalized(auth_db):
    data = source([dict(BASE, 承保保单件数=7),
        {'时间': '合计', '期交保费': 100000, '承保年化规保': 120000, '承保保单件数': 7}])
    with sqlite3.connect(':memory:') as conn:
        assert build_import_preview(conn, [data])['canImport']
    result = build_excel_pipeline_result([data])
    assert '承保件数' in result.raw_tables['jingdai'].columns
    assert result.rows_by_table['agg_product_daily'][0]['count'] == 7


def test_conflicting_count_aliases_are_rejected():
    with pytest.raises(ValueError, match='不一致'):
        build_excel_pipeline_result([source([dict(BASE, 承保件数=7, 承保保单件数=8)])])


@pytest.mark.parametrize('aggregate', [aggregate_jingdai_product_daily,
    aggregate_jingdai_payment_period, aggregate_jingdai_payment_period_daily])
def test_sqlite_rebuild_accepts_old_alias_and_mixed_import_history(aggregate):
    frame = pd.DataFrame([dict(BASE, 承保保单件数=7), dict(BASE, 承保件数=2)])
    assert aggregate(frame)[0]['count'] == 9
    assert aggregate(frame)[0]['count_missing'] == 0


@pytest.mark.parametrize('bad', ['invalid', '1,00', float('inf'), 1.5])
def test_bad_count_is_rejected_in_preview_and_import(bad):
    data = source([dict(BASE, 承保件数=bad)])
    with sqlite3.connect(':memory:') as conn:
        assert not build_import_preview(conn, [data])['canImport']
    with pytest.raises(ValueError, match='承保件数'):
        build_excel_pipeline_result([data])


@pytest.mark.parametrize('count', [0, 5, -1])
def test_replacement_protects_count_column_including_zero(count):
    with sqlite3.connect(':memory:') as conn:
        append_raw_frame(conn, 'jingdai', pd.DataFrame([dict(BASE, 承保件数=count)]))
        with pytest.raises(RawIncrementalWriteError, match='承保件数'):
            validate_replacement_fields(conn, 'jingdai', pd.DataFrame([BASE]))
        validate_replacement_fields(conn, 'jingdai', pd.DataFrame([dict(BASE, 时间='2026-08-01')]))


def setup_queries(monkeypatch, *, daily, missing=False):
    from db.repositories import product, payment
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    rows = [dict(BASE, 承保件数=6), dict(BASE, 时间='2026-09-03', 承保件数=-1,
            期交保费=-10000, 承保年化规保=-12000)]
    if missing:
        rows.append(dict(BASE, 时间='2026-09-04', 承保件数=None))
    pd.DataFrame(rows).to_sql('jingdai', conn, index=False)
    @contextmanager
    def fake_db():
        yield conn
    monkeypatch.setattr(product, 'get_db', fake_db)
    monkeypatch.setattr(payment, 'get_db', fake_db)
    monkeypatch.setattr(payment, 'init_db', lambda: None)
    for name, aggregate in [('agg_payment_period', aggregate_jingdai_payment_period),
                            ('agg_payment_period_daily', aggregate_jingdai_payment_period_daily)]:
        pd.DataFrame(aggregate(pd.DataFrame(rows))).to_sql(name, conn, index=False)
    if daily:
        pd.DataFrame(aggregate_jingdai_product_daily(pd.DataFrame(rows))).to_sql('agg_product_daily', conn, index=False)
    return conn, product, payment


@pytest.mark.parametrize('daily', [True, False])
def test_product_raw_and_aggregate_authoritative_counts(monkeypatch, daily):
    conn, product, _ = setup_queries(monkeypatch, daily=daily)
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False,
        include_jingdai=True, months=[9])
    assert result['premium'] == [{'name': '合成产品', 'value': 9}]
    assert result['count'] == [{'name': '合成产品', 'value': 5}]
    assert result['countBasis'] == 'policy' and result['countNote'] == ''
    bounded = product.get_product_structure(2026, dimension='product_mix', include_transform=False,
        include_jingdai=True, start_date='2026-09-03', end_date='2026-09-03', range_type='custom')
    assert bounded['count'] == [{'name': '合成产品', 'value': -1}]
    conn.close()


def test_product_raw_count_normalizes_thousands_and_stored_alias(monkeypatch):
    from db.repositories import product
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    pd.DataFrame([dict(BASE, 承保保单件数='1,000')]).to_sql('jingdai', conn, index=False)
    @contextmanager
    def fake_db():
        yield conn
    monkeypatch.setattr(product, 'get_db', fake_db)
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['count'] == [{'name': '合成产品', 'value': 1000}]
    conn.close()


def test_product_count_does_not_drop_categories_below_premium_top_twenty(monkeypatch):
    conn, product, _ = setup_queries(monkeypatch, daily=False)
    pd.DataFrame([dict(BASE, 产品名称=f'产品{i}', 期交保费=100+i, 承保件数=1)
                  for i in range(25)]).to_sql('jingdai', conn, if_exists='replace', index=False)
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert len(result['count']) == 25
    assert sum(r['value'] for r in result['count']) == 25
    conn.close()


@pytest.mark.parametrize('daily', [True, False])
def test_missing_count_never_creates_partial_denominator(monkeypatch, daily):
    conn, product, payment = setup_queries(monkeypatch, daily=daily, missing=True)
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False, include_jingdai=True)
    assert result['premium'] and result['count'] == []
    assert result['countBasis'] == 'unavailable' and '缺少' in result['countNote']
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['count'] == []
    average = result['average_premium']
    assert average['rows'][0]['total']['count'] is None
    assert average['rows'][0]['total']['average'] is None
    assert all(r['total']['average'] is None for r in average['summaries'])
    conn.close()


@pytest.mark.parametrize('metric, expected', [('qj', 1.8), ('gm', 2.16)])
def test_payment_average_and_excel_rows_use_authoritative_counts(monkeypatch, metric, expected):
    from services.excel_exporter import _payment_rows
    conn, _, payment = setup_queries(monkeypatch, daily=True)
    result = payment.get_payment_period_structure(2026, business_types=['经代'], metric=metric)
    total = result['average_premium']['rows'][0]['total']
    assert total['count'] == 5 and total['average'] == expected
    assert result['average_premium']['rows'][0]['business_mode'] == '经代'
    assert _payment_rows(result) == [['5年交', 9 if metric=='qj' else 10.8, 5]]
    conn.close()


def test_schema_migration_requires_rebuild_and_is_idempotent(auth_db):
    from db import get_db, init_db
    init_db()
    init_db()
    with get_db() as conn:
        assert conn.execute("SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version='20261013_jingdai_policy_counts'").fetchone()[0] == 1
        for table in ('agg_product_daily', 'agg_payment_period', 'agg_payment_period_daily'):
            assert 'count_missing' in {r[1] for r in conn.execute('PRAGMA table_info('+table+')')}
