"""Regressions for AI amount reads and transactional product-setting refreshes."""
import json

import pandas as pd
import pytest

from db import get_db, replace_rows
from services.ai_business_data import BUSINESS_DATASETS, analyze, page
from services.import_safety import append_raw_frame


@pytest.mark.parametrize('table', ['agg_jingdai', 'agg_jingdai_daily'])
def test_ai_discount_page_masks_unknown_and_preserves_pagination_and_real_zero(auth_db, table):
    rows = [dict(year=2026, month=month, qj_premium=1, gm_premium=1,
                 zs_premium=amount, zs_missing=missing)
            for month, amount, missing in [(1, 10, 0), (2, 3, 1), (3, 0, 0)]]
    if table.endswith('_daily'):
        for row in rows:
            row.update(day=1, ymd=f"2026-{row['month']:02d}-01")
    with get_db() as conn:
        replace_rows(conn, table, rows)
        conn.commit()
    first = page(table, columns=['month', 'zs_premium'], limit=2)
    assert first['rows'] == [{'month': 1, 'zs_premium': 10}, {'month': 2, 'zs_premium': None}]
    assert first['hasMore'] and first['nextAfterRowId'] is not None
    second = page(table, columns=['month', 'zs_premium'], after_row_id=first['nextAfterRowId'])
    assert second['rows'] == [{'month': 3, 'zs_premium': 0}]
    filtered = page(table, columns=['month'], filters=json.dumps({'zs_premium': {'isNull': True}}))
    assert filtered['rows'] == [{'month': 2}]
    for operation in ('sum', 'avg', 'min', 'max'):
        assert analyze(table, measure='zs_premium', aggregation=operation)['rows'] == [{'result': None}]
    assert analyze(table, measure='zs_premium', aggregation='sum',
                   filters=json.dumps({'month': {'in': [1, 3]}}))['rows'] == [{'result': 10}]
    assert analyze(table, aggregation='count')['rows'] == [{'result': 3}]
    assert 'agg_jingdai_policy_daily' not in BUSINESS_DATASETS
    with get_db() as conn:
        assert conn.execute(f'SELECT zs_premium FROM {table} WHERE month=2').fetchone()[0] == 3


def _seed_product_source():
    raw = pd.DataFrame([
        {'时间': f'2026-01-{day:02d}', '产品名称': '合成产品', '经代机构': '合成平台',
         '期交保费': 10000, '承保年化规保': 10000, '是否商保年金产品': flag}
        for day, flag in [(1, 'Y'), (2, 'N'), (3, None), (4, '')]
    ])
    with get_db() as conn:
        append_raw_frame(conn, 'jingdai', raw)
        conn.execute("INSERT INTO product_config(product_code,product_name,business_type,is_annuity,is_protection) "
                     "VALUES ('合成产品','合成产品','经代','N','N')")
        conn.commit()


def test_product_save_refreshes_daily_and_monthly_with_source_flags_and_legacy_fallback(auth_db, monkeypatch):
    from api import product_config
    _seed_product_source()
    monkeypatch.setattr(product_config, 'log_operation', lambda *args, **kwargs: None)
    result = product_config._save_product_config_locked({'products': [
        {'product_code': '合成产品', 'business_type': '经代', 'is_annuity': 'Y', 'is_protection': 'Y'}
    ]}, {'username': 'synthetic'})
    assert result['data']['recalculated'] == 1
    with get_db() as conn:
        month = dict(conn.execute('SELECT * FROM agg_jingdai').fetchone())
        days = [dict(row) for row in conn.execute('SELECT * FROM agg_jingdai_daily ORDER BY day')]
        assert month['product_annuity'] == 3 and month['product_protection'] == 4
        assert [row['product_annuity'] for row in days] == [1, 0, 1, 1]
        assert [row['product_protection'] for row in days] == [1, 1, 1, 1]
        assert month['zs_missing'] == 4 and all(row['zs_missing'] == 1 for row in days)
        assert month['zs_premium'] == 0 and all(row['zs_premium'] == 0 for row in days)


def test_product_save_rolls_back_settings_and_both_aggregates_if_daily_write_fails(auth_db, monkeypatch):
    from api import product_config
    _seed_product_source()
    with get_db() as conn:
        replace_rows(conn, 'agg_jingdai', [dict(year=2026, month=1, qj_premium=99, gm_premium=99, zs_premium=99)])
        replace_rows(conn, 'agg_jingdai_daily', [dict(year=2026, month=1, day=1, ymd='2026-01-01',
                                                   qj_premium=99, gm_premium=99, zs_premium=99)])
        conn.commit()
    original = product_config.replace_rows_incremental
    def fail_daily(conn, table, rows):
        if table == 'agg_jingdai_daily':
            raise RuntimeError('synthetic daily write failure')
        return original(conn, table, rows)
    monkeypatch.setattr(product_config, 'replace_rows_incremental', fail_daily)
    with pytest.raises(RuntimeError, match='synthetic daily write'):
        product_config._save_product_config_locked({'products': [
            {'product_code': '合成产品', 'business_type': '经代', 'is_annuity': 'Y', 'is_protection': 'Y'}
        ]}, {'username': 'synthetic'})
    with get_db() as conn:
        assert conn.execute("SELECT is_annuity FROM product_config WHERE product_code='合成产品'").fetchone()[0] == 'N'
        assert conn.execute('SELECT qj_premium FROM agg_jingdai').fetchone()[0] == 99
        assert conn.execute('SELECT qj_premium FROM agg_jingdai_daily').fetchone()[0] == 99
