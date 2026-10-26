"""Unknown payment terms must not turn into zero or a partial discount total."""
from datetime import date
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pandas as pd
import pytest

from etl.aggregates.jingdai import aggregate_jingdai, aggregate_jingdai_daily
from db.repositories.platform import _jingdai_discount_expr, get_platform_data
from services.query_service import (
    build_month_daily_cumulative, build_period_cumulative, build_quarter_daily_cumulative,
)


BASE = {'时间': '2026-01-01', '产品名称': '合成产品', '期交保费': 10000, '承保年化规保': 20000}


@pytest.mark.parametrize('aggregate', [aggregate_jingdai, aggregate_jingdai_daily])
def test_unknown_payment_terms_are_flagged_and_real_zero_stays_known(aggregate):
    missing = aggregate(pd.DataFrame([BASE]), config_map={})[0]
    assert missing['zs_premium'] == 0
    assert missing['zs_missing'] == 1
    zero = aggregate(pd.DataFrame([dict(BASE, 期交保费=0, 缴费年限=10)]), config_map={})[0]
    assert zero['zs_premium'] == 0 and zero['zs_missing'] == 0
    mixed = aggregate(pd.DataFrame([dict(BASE, 缴费年限=10), dict(BASE, 缴费年限=None)]), config_map={})[0]
    assert mixed['zs_premium'] == 1 and mixed['zs_missing'] == 1


@pytest.mark.parametrize('aggregate', [aggregate_jingdai, aggregate_jingdai_daily])
def test_annuity_source_flags_override_manual_and_missing_flags_preserve_history(aggregate):
    config = {'合成产品': {'is_annuity': True, 'is_protection': True}}
    rows = [dict(BASE, 是否商保年金产品='N'),
            dict(BASE, 是否商保年金产品='Y', 期交保费=-2000),
            dict(BASE, 是否商保年金产品=None),
            dict(BASE, 是否商保年金产品='')]
    result = aggregate(pd.DataFrame(rows), config_map=config)[0]
    assert result['product_annuity'] == 1.8
    assert result['product_protection'] == 2.8
    assert aggregate(pd.DataFrame([dict(BASE, 是否商保年金产品='Y')]), config_map={})[0]['product_annuity'] == 1


def test_export_masks_internal_zero_discount_and_keeps_real_zero():
    from services.excel_exporter import _platform_rows
    rows = _platform_rows({'jingdai': [dict(month=1, qj_premium=5, gm_premium=6, zs_premium=0, zs_missing=1),
                                     dict(month=2, qj_premium=0, gm_premium=0, zs_premium=0, zs_missing=0)]})
    assert rows[0][-1] is None
    assert rows[1][-1] == 0


def test_discount_query_does_not_sum_known_part_of_an_unknown_period():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE agg_jingdai (zs_premium REAL, zs_missing INTEGER)')
    conn.executemany('INSERT INTO agg_jingdai VALUES (?,?)', [(10, 0), (0, 1)])
    expr = _jingdai_discount_expr(conn, 'agg_jingdai', aggregate=True)
    assert conn.execute(f'SELECT {expr} FROM agg_jingdai').fetchone()[0] is None
    conn.execute('UPDATE agg_jingdai SET zs_missing=0')
    assert conn.execute(f'SELECT {expr} FROM agg_jingdai').fetchone()[0] == 10
    conn.close()


def test_platform_returns_null_for_unknown_month_but_known_day_remains_available(auth_db):
    from db import get_db, replace_rows
    with get_db() as conn:
        replace_rows(conn, 'agg_jingdai', [dict(year=2026, month=1, qj_premium=2,
                     gm_premium=4, zs_premium=1, zs_missing=1)])
        replace_rows(conn, 'agg_jingdai_daily', [
            dict(year=2026, month=1, day=1, ymd='2026-01-01', qj_premium=1,
                 gm_premium=2, zs_premium=1, zs_missing=0),
            dict(year=2026, month=1, day=2, ymd='2026-01-02', qj_premium=1,
                 gm_premium=2, zs_premium=0, zs_missing=1),
        ])
        conn.commit()
    data = get_platform_data(2026, as_of='2026-01-02')
    assert data['jingdai'][0]['zs_premium'] is None
    assert [row['zs_premium'] for row in data['jingdai_daily']] == [1, None]
    assert get_platform_data(2026, as_of='2026-01-01')['jingdai'][0]['zs_premium'] == 1


def test_missing_discount_propagates_through_mixed_period_cumulative():
    data = {
        'performance': [dict(month=1, channel='证保', zs_premium=5, qj_premium=5)],
        'jingdai': [dict(month=1, zs_premium=None, qj_premium=10),
                    dict(month=2, zs_premium=2, qj_premium=2)],
    }
    unknown = build_period_cumulative(data, ['证保', '经代'], 'zs')
    assert unknown['values'] == [None] * 12
    assert not unknown['calculable'] and '不可计算' in unknown['message']
    assert build_period_cumulative(data, ['证保'], 'zs')['values'][0] == 5
    assert build_period_cumulative(data, ['证保', '经代'], 'qj')['values'][:2] == [15, 17]


def test_missing_discount_propagates_after_first_unknown_day_across_months():
    data = {'jingdai_daily': [dict(month=1, day=1, zs_premium=1, qj_premium=1),
                             dict(month=1, day=2, zs_premium=None, qj_premium=2),
                             dict(month=2, day=1, zs_premium=3, qj_premium=3)]}
    month = build_month_daily_cumulative(data, 2026, 1, ['经代'], 'zs', date(2026, 3, 31))
    assert month['values'][0] == 1 and month['values'][1:] == [None] * 30
    assert not month['calculable']
    quarter = build_quarter_daily_cumulative(data, 2026, 1, ['经代'], 'zs', date(2026, 3, 31))
    assert quarter['values'][0] == 1 and all(value is None for value in quarter['values'][1:])


def test_frontend_keeps_unknown_discount_and_does_not_show_partial_mixed_chart():
    node = shutil.which('node')
    assert node, 'Node.js is required for frontend regression verification'
    script = r'''
      const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
      const source = fs.readFileSync('js/data-integration.js', 'utf8');
      function extract(s, start, end) { return s.slice(s.indexOf(start), s.indexOf(end, s.indexOf(start))); }
      const scope = {platformOrgPerfData: {}, normalizeMonth: Number, dailyRowsContainJingdai: () => false,
                     dailyDisplayEndDay: () => 3};
      vm.createContext(scope);
      vm.runInContext(extract(source, '    function convertApiToPlatformMock(', '    function mergeProductRows('), scope);
      const rows = [{month:1,day:1,qj_premium:1,gm_premium:2,zs_premium:null}];
      const result = scope.convertApiToPlatformMock({jingdai:rows,jingdai_daily:rows},2026);
      assert.equal(result[2026].year.zs['经代'][0], null);
      assert.equal(result[2026].year.qj['经代'][0], 1);
      const trend = fs.readFileSync('js/platform-trend-main.js', 'utf8');
      scope.platformMock = result;
      vm.runInContext(extract(trend,'    function platformDiscountUnavailable(', '    function getMonthDailyCumulative('), scope);
      assert.equal(scope.platformDiscountUnavailable(2026, 'zs', ['经代','证保'], [1]), true);
      assert.equal(scope.platformDiscountUnavailable(2026, 'zs', ['证保'], [1]), false);
      assert.equal(scope.platformDiscountUnavailable(2026, 'qj', ['经代'], [1]), false);
      assert.equal(scope.platformDiscountUnavailable(2026, 'zs', ['经代'], [2]), false);
      assert.equal(scope.addTrendAmount(5, null), null);
      scope.selectedSeries = {'经代':true,'证保':true}; scope.selectedYear=2026;
      scope.currentTimeDim='year'; scope.currentPremiumType='zs';
      vm.runInContext(extract(trend,'    function getPlatformOption()', '    if (!window.ALLOW_LOCAL_FALLBACK)'), scope);
      const option = scope.getPlatformOption();
      assert.match(option.title.text, /不可计算/); assert.equal(option.series.length, 0);
    '''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '-e', script], cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
