"""Synthetic policy identities prove non-additive range counts and safe legacy use."""
from contextlib import contextmanager
import sqlite3

import pandas as pd
import pytest

from etl.aggregates.jingdai_policy import aggregate_jingdai_policy_daily
from etl.aggregates.dashboard import aggregate_jingdai_product_daily
from etl.aggregates.payment import aggregate_jingdai_payment_period, aggregate_jingdai_payment_period_daily
from db.repositories.jingdai_policy import query_policy_counts


BASE = {'时间': '2026-09-01', '经代机构': '平台甲', '产品名称': '产品甲', '缴费年限': 5,
        '期交保费': 10000, '年化规保': 20000, '经代源格式': 'policy_detail'}


def install(monkeypatch, rows):
    from db.repositories import product, payment
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    frame = pd.DataFrame(rows)
    frame.to_sql('jingdai', conn, index=False)
    for name, fn in [('agg_jingdai_policy_daily', aggregate_jingdai_policy_daily),
                     ('agg_product_daily', aggregate_jingdai_product_daily),
                     ('agg_payment_period', aggregate_jingdai_payment_period),
                     ('agg_payment_period_daily', aggregate_jingdai_payment_period_daily)]:
        pd.DataFrame(fn(frame)).to_sql(name, conn, index=False)
    @contextmanager
    def db():
        yield conn
    monkeypatch.setattr(product, 'get_db', db)
    monkeypatch.setattr(payment, 'get_db', db)
    monkeypatch.setattr(payment, 'init_db', lambda: None)
    return conn, product, payment


def test_daily_fact_keeps_identity_and_net_amounts_without_counting_rows():
    rows = [dict(BASE, 投保单号='0001', 期交保费=100.01),
            dict(BASE, 投保单号='0001', 期交保费=-20.02),
            dict(BASE, 投保单号='0002', 期交保费=0)]
    facts = aggregate_jingdai_policy_daily(pd.DataFrame(rows))
    assert len(facts) == 2
    assert {r['policy_no'] for r in facts} == {'0001', '0002'}
    assert sum(r['source_rows'] for r in facts) == 3
    assert sum(r['qj_premium'] for r in facts) == pytest.approx(79.99 / 10000)


def test_cross_day_and_cross_product_counts_are_distinct_at_each_scope(monkeypatch):
    rows = [dict(BASE, 投保单号='0001'), dict(BASE, 投保单号='0001', 时间='2026-09-02'),
            dict(BASE, 投保单号='0001', 产品名称='产品乙'), dict(BASE, 投保单号='0002', 期交保费=-1000)]
    conn, product, payment = install(monkeypatch, rows)
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert {r['name']: r['value'] for r in result['count']} == {'产品甲': 2, '产品乙': 1}
    assert result['countBasis'] == 'policy_identity'
    assert '净承保' in result['countNote']
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['count'] == [{'name': '5年交', 'value': 2}]
    assert result['average_premium']['rows'][0]['total']['count'] == 2
    assert result['average_premium']['summaries'][0]['total']['count'] == 2
    bounded = product.get_product_structure(2026, dimension='product_mix', include_transform=False,
        range_type='custom', start_date='2026-09-02', end_date='2026-09-02')
    assert bounded['count'] == [{'name': '产品甲', 'value': 1}]
    conn.close()


def test_cross_platform_total_is_not_sum_of_platform_counts(monkeypatch):
    conn, _, payment = install(monkeypatch, [dict(BASE, 投保单号='0001'),
        dict(BASE, 投保单号='0001', 经代机构='平台乙'), dict(BASE, 投保单号='0002', 经代机构='平台乙')])
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['count'][0]['value'] == 2
    summaries = result['average_premium']['summaries']
    assert next(r for r in summaries if r['org']=='all' and r['business_mode']=='all')['total']['count'] == 2
    assert next(r for r in summaries if r['org']=='平台乙' and r['business_mode']=='经代')['total']['count'] == 2
    conn.close()


def test_missing_identity_blocks_denominator_but_keeps_premium(monkeypatch):
    conn, product, payment = install(monkeypatch, [dict(BASE, 投保单号='0001'), dict(BASE, 投保单号=None)])
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['premium'] == [{'name': '产品甲', 'value': 2}]
    assert result['count'] == []
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['average_premium']['rows'][0]['total']['count'] is None
    assert result['average_premium']['rows'][0]['total']['average'] is None
    conn.close()


def test_raw_product_fallback_uses_same_identity_semantics(monkeypatch):
    conn, product, _ = install(monkeypatch, [dict(BASE, 投保单号='0001'),
        dict(BASE, 投保单号='0001', 时间='2026-09-02'), dict(BASE, 投保单号='0002')])
    conn.execute('DROP TABLE agg_product_daily')
    conn.execute('DROP TABLE agg_jingdai_policy_daily')
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['count'] == [{'name': '产品甲', 'value': 2}]
    assert result['countBasis'] == 'policy_identity'
    conn.close()


def test_unified_raw_daily_count_is_not_a_range_denominator(monkeypatch):
    rows = [dict(BASE, 投保单号='0001', 承保件数=1, 件数来源='policy_identity_daily'),
            dict(BASE, 投保单号='0001', 承保件数=1, 件数来源='policy_identity_daily', 时间='2026-09-02')]
    conn, product, payment = install(monkeypatch, rows)
    assert conn.execute('SELECT SUM("承保件数") FROM jingdai').fetchone()[0] == 2
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['count'] == [{'name': '产品甲', 'value': 1}]
    assert result['countSources'] == ['policy_identity']
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['count'] == [{'name': '5年交', 'value': 1}]
    assert result['average_premium']['summaries'][0]['total']['count'] == 1
    assert all(r['legacy_count'] == 0 for r in conn.execute('SELECT legacy_count FROM agg_jingdai_policy_daily'))
    conn.execute('DROP TABLE agg_product_daily')
    conn.execute('DROP TABLE agg_jingdai_policy_daily')
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['count'] == [{'name': '产品甲', 'value': 1}]
    conn.close()


def test_legacy_raw_query_uses_canonical_time_over_empty_new_date_columns(monkeypatch):
    row = dict(BASE, 时间='2020-09-01', 年月日=None, 统计时间_年月日=None,
               投保单号=None, 经代源格式='legacy_aggregate', 件数来源='source_net', 承保件数=8)
    from db.repositories import product
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    pd.DataFrame([row]).to_sql('jingdai', conn, index=False)
    @contextmanager
    def db():
        yield conn
    monkeypatch.setattr(product, 'get_db', db)
    result = product.get_product_structure(2020, dimension='product_mix', include_transform=False)
    assert result['count'] == [{'name': '产品甲', 'value': 8}]
    assert result['premium'] == [{'name': '产品甲', 'value': 1}]
    assert result['topProducts'][0]['premium'] == 1
    assert result['countSources'] == ['source_net']
    conn.close()


def test_mixed_transform_and_identity_summary_does_not_sum_definitions(monkeypatch):
    conn, _, payment = install(monkeypatch, [dict(BASE, 投保单号='0001')])
    columns = [r[1] for r in conn.execute('PRAGMA table_info(agg_payment_period_daily)')]
    values = dict(year=2026, month=9, day=1, business_type='转型', channel='证保', org='机构甲', category='5年交', qj_premium=2, gm_premium=2, count=3, count_missing=0)
    conn.execute('INSERT INTO agg_payment_period_daily (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')', [values.get(c) for c in columns])
    result = payment.get_payment_period_structure(2026)
    assert result['count'] == []
    assert result['countBasis'] == 'mixed'
    summaries = result['average_premium']['summaries']
    assert next(r for r in summaries if r['org']=='all' and r['business_mode']=='all')['total']['count'] is None
    assert next(r for r in summaries if r['org']=='all' and r['business_mode']=='经代')['total']['count'] == 1
    conn.close()


def test_legacy_and_identity_mix_does_not_create_false_count(monkeypatch):
    conn, product, payment = install(monkeypatch, [dict(BASE, 投保单号='0001'),
        dict(BASE, 时间='2026-09-02', 投保单号=None, 经代源格式=None, 承保件数=8)])
    result = product.get_product_structure(2026, dimension='product_mix', include_transform=False)
    assert result['count'] == [] and '混有' in result['countNote']
    result = payment.get_payment_period_structure(2026, business_types=['经代'])
    assert result['count'] == [] and result['countBasis'] == 'mixed'
    assert result['average_premium']['rows'][0]['total']['count'] is None
    old = query_policy_counts(conn, 'year=? AND day=?', [2026, 2])
    assert old[()] == {'count': 8, 'basis': 'source_net', 'identity': False}
    conn.close()


def test_fact_schema_migration_is_idempotent_and_requires_rebuild(auth_db):
    from db import init_db, get_db
    init_db()
    with get_db() as conn:
        row = conn.execute("SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version='20261025_jingdai_policy_identity'").fetchone()
        assert row[0] == 1
        row = conn.execute("SELECT requires_aggregate_rebuild FROM schema_migrations WHERE version='20261026_jingdai_source_contract'").fetchone()
        assert row[0] == 1
        assert {'policy_no', 'identity_source', 'source_rows'} <= {r[1] for r in conn.execute('PRAGMA table_info(agg_jingdai_policy_daily)')}
        for table in ['agg_jingdai', 'agg_jingdai_daily']:
            assert 'zs_missing' in {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
