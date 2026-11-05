import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from db.repositories.platform_jingdai import get_jingdai_platform_trend
from db.repositories.platform_jingdai import _known_fee_weight
from main import app


def test_payment_year_normalization_matches_etl():
    for value in (None, '', '未知', -1, float('inf'), float('nan')):
        assert _known_fee_weight(value) is None
    assert _known_fee_weight('3') == .3
    assert _known_fee_weight(0) == .1
    assert _known_fee_weight(10) == 1


def test_platform_breakdown_keeps_blanks_reversals_and_unknown_discount(auth_db):
    from db.connection import get_db
    with get_db() as conn:
        conn.executemany('''INSERT INTO jingdai
            ("时间", "经代机构", "期交保费", "承保年化规保", "缴费年限") VALUES (?, ?, ?, ?, ?)''', [
            ('2026-01-01', '平台甲', 10000, 20000, 3),
            ('2026-01-02', '平台甲', -2000, -4000, 3),
            ('2026-01-01', '平台乙', 30000, 60000, None),
            ('2026-02-01', '', 5000, 5000, 0),
            ('2025-01-01', '旧平台', 90000, 90000, 5),
        ])
        conn.executemany('INSERT INTO agg_jingdai(year,month,qj_premium,gm_premium) VALUES(?,?,?,?)',
                         [(2026, 1, 3.8, 7.6), (2026, 2, .5, .5), (2026, 3, 99, 99)])
        conn.commit()
    result = get_jingdai_platform_trend(2026)
    assert result['platforms'] == ['', '平台乙', '平台甲']
    assert result['incompleteMonths'] == [3]
    rows = result['daily']
    assert sum(row['qj_premium'] for row in rows if row['platform'] == '平台甲') == .8
    assert sum(row['zs_premium'] for row in rows if row['platform'] == '平台甲') == .24
    assert next(row for row in rows if row['platform'] == '平台乙')['zs_premium'] is None
    assert next(row for row in rows if row['platform'] == '')['zs_premium'] == .05
    client = TestClient(app)
    assert client.get('/api/platform-jingdai?year=2026').status_code == 401


def test_platform_endpoint_uses_trend_permission(auth_db, approved_user):
    client = TestClient(app)
    login = approved_user(client, 'trendplatform', 'Test-only-platform-2026!')
    headers = {'Authorization': 'Bearer ' + login['token']}
    assert client.get('/api/platform-jingdai?year=2026', headers=headers).status_code == 200
    from db.connection import get_db
    with get_db() as conn:
        conn.execute("UPDATE user_module_permissions SET allowed=0 WHERE user_id=? AND module_key='platform_trend'",
                     (login['user']['id'],))
        conn.commit()
    assert client.get('/api/platform-jingdai?year=2026', headers=headers).status_code == 403


def test_frontend_platform_filter_changes_amounts_and_daily_without_leaking_totals():
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const source = fs.readFileSync('js/platform-trend-main.js', 'utf8');
const scope = {window:{}, document:{getElementById:()=>null},
 echarts:{init:()=>({setOption:()=>{}})}, DEFAULT_DASHBOARD_YEAR:2026,
 months:Array.from({length:12},(_,i)=>i+1), platformMock:{}, apiCache:{},
 platformDateInRange:()=>true,
 dailyDisplayEndDay:()=>3,
 completeDailySeries:values=>Array.from({length:3},(_,i)=>values[i] ?? values[values.length-1])};
vm.createContext(scope);
// Load real state and functions while omitting the page's eager initialization.
vm.runInContext(source.slice(0, source.indexOf('    if (!window.ALLOW_LOCAL_FALLBACK)'))
 + source.slice(source.indexOf('    // 根据机构筛选获取某渠道某月的数值')), scope);
vm.runInContext(`
 platformMock[2026] = {year:{qj:{'经代':[100]},gm:{'经代':[200]},zs:{'经代':[null]}}};
 jingdaiPlatformCache[2026] = {daily:[
 {platform:'甲',month:1,day:1,qj_premium:10,gm_premium:20,zs_premium:3},
 {platform:'甲',month:1,day:2,qj_premium:-2,gm_premium:-4,zs_premium:-.6},
 {platform:'乙',month:1,day:1,qj_premium:30,gm_premium:60,zs_premium:null}]};
 selectedJingdaiPlatforms=['甲'];
`, scope);
assert.equal(scope.getChannelValue(2026,'qj','经代',0),8);
assert.equal(scope.getChannelValue(2026,'gm','经代',0),16);
assert.equal(scope.platformDiscountUnavailable(2026,'zs',['经代']),false);
assert.deepEqual(Array.from(scope.getMonthDailyCumulative(2026,'qj',['经代'],1)),[10,8,8]);
vm.runInContext(`selectedJingdaiPlatforms=['甲','乙']`,scope);
assert.equal(scope.getChannelValue(2026,'qj','经代',0),38);
assert.equal(scope.platformDiscountUnavailable(2026,'zs',['经代']),true);
vm.runInContext(`selectedJingdaiPlatforms=[]`,scope);
assert.equal(scope.getChannelValue(2026,'qj','经代',0),0);
assert.deepEqual(Array.from(scope.getMonthDailyCumulative(2026,'qj',['经代'],1)),[0,0,0]);
vm.runInContext(`selectedJingdaiPlatforms=null`,scope);
assert.equal(scope.getChannelValue(2026,'qj','经代',0),100);
vm.runInContext(`
 selectedJingdaiPlatforms=['甲'];
 apiCache['2026']={platform:{daily_performance:[{month:1,day:1,channel:'OTO',qj_premium:7}]}};
`,scope);
assert.deepEqual(Array.from(scope.getMonthDailyCumulative(2026,'qj',['经代','OTO'],1)),[17,15,15]);
vm.runInContext(`
 jingdaiPlatformCache[2026].daily.push({platform:'乙',month:1,day:3,qj_premium:100});
 apiCache['2026'].platform.daily_performance.push({month:1,day:3,channel:'OTO',qj_premium:70});
`,scope);
assert.deepEqual(Array.from(scope.getMonthDailyCumulative(2026,'qj',['经代','OTO'],1)),[17,15,85]);
'''
    result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True,
                            text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stdout + result.stderr
