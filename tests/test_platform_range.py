"""The trend and raw platform contracts must honor the dashboard range."""
import pytest

from db import get_db
from db.repositories.platform import get_platform_data
from services.query_service import get_platform_trend


@pytest.fixture()
def range_db(auth_db):
    with get_db() as conn:
        for year in (2025, 2026):
            for month, day, amount in ((5, 19, 10), (5, 20, 20), (5, 31, 30), (6, 1, 40), (6, 10, 50), (6, 11, 60)):
                conn.execute('INSERT INTO agg_daily_performance(year,month,day,channel,qj_premium,gm_premium,zs_premium) VALUES(?,?,?,?,?,?,?)',
                             (year, month, day, 'OTO', amount, amount * 2, amount / 2))
                conn.execute('INSERT INTO agg_jingdai_daily(year,month,day,ymd,qj_premium,gm_premium,zs_premium) VALUES(?,?,?,?,?,?,?)',
                             (year, month, day, f'{year}-{month:02}-{day:02}', amount, amount * 2, amount / 2))
            for month in (5, 6):
                conn.execute('INSERT INTO agg_performance(year,month,channel,qj_premium,gm_premium,zs_premium) VALUES(?,?,?,?,?,?)',
                             (year, month, 'OTO', 9999, 9999, 9999))
                conn.execute('INSERT INTO agg_jingdai(year,month,qj_premium,gm_premium,zs_premium) VALUES(?,?,?,?,?)',
                             (year, month, 9999, 9999, 9999))
        conn.commit()


def _amount(data, key='performance'):
    return sum(row['qj_premium'] for row in data[key])


@pytest.mark.parametrize('mode,start,end,expected', [
    ('day', None, '2026-06-10', 50),
    ('month', None, '2026-05-05', 60),
    ('custom', '2026-05-20', '2026-06-10', 140),
])
def test_explicit_range_filters_both_sources_and_monthly_totals(range_db, mode, start, end, expected):
    data = get_platform_data(2026, range_type=mode, start_date=start, end_date=end)
    assert _amount(data) == expected
    assert _amount(data, 'jingdai') == expected
    assert data['rangeApplied'] is True
    assert data['sourcePrecision']['performance'] == 'day'
    assert data['period']['rangeType'] == mode
    for row in data['daily_performance'] + data['jingdai_daily']:
        ymd = f'2026-{row["month"]:02}-{row["day"]:02}'
        assert data['period']['startDate'] <= ymd <= data['period']['endDate']


def test_selected_day_without_sales_does_not_revive_whole_month(range_db):
    data = get_platform_data(2026, range_type='day', end_date='2026-06-05')
    assert data['performance'] == data['jingdai'] == []
    assert data['daily_performance'] == data['jingdai_daily'] == []


def test_previous_year_uses_same_calendar_range(range_db):
    data = get_platform_data(2025, range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    assert (data['period']['startDate'], data['period']['endDate']) == ('2025-05-20', '2025-06-10')
    assert _amount(data) == 140


def test_explicit_mixed_range_does_not_drop_newer_source_sales(range_db):
    with get_db() as conn:
        conn.execute('DELETE FROM agg_jingdai_daily WHERE year=2026 AND month=6 AND day=11')
        conn.commit()
    trend = get_platform_trend(2026, channels=['OTO', '经代'], range_type='custom',
                               start_date='2026-06-01', end_date='2026-06-11')
    assert trend['trend']['commonCutoff'] is None
    assert trend['trend']['values'] == [240]
    assert trend['trend']['labels'] == ['6']


def test_daily_curve_starts_at_range_start_and_stops_at_range_end(range_db):
    data = get_platform_trend(2026, channels=['OTO'], period_type='month', period_value=6,
                              range_type='custom', start_date='2026-06-05', end_date='2026-06-10')
    assert data['daily']['labels'] == [f'6-{d}' for d in range(5, 11)]
    assert data['daily']['values'] == [0, 0, 0, 0, 0, 50]


def test_partial_month_without_daily_precision_is_unknown_not_full_month(range_db):
    with get_db() as conn:
        conn.execute('DELETE FROM agg_daily_performance WHERE year=2026 AND month=5')
        conn.commit()
    data = get_platform_data(2026, range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    assert {r['month']: r['qj_premium'] for r in data['performance']}[5] is None
    assert data['sourcePrecision']['performance'] == 'unavailable'
    assert data['rangeWarnings']
    daily = get_platform_trend(2026, channels=['OTO'], period_type='quarter', period_value=2,
                               range_type='custom', start_date='2026-04-01', end_date='2026-06-10')['daily']
    assert daily['values'] == []
    assert not daily['calculable']
    trend = get_platform_trend(2026, channels=['OTO'], range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    assert trend['trend']['values'] == [None, None]
    assert not trend['trend']['calculable']


def test_full_month_without_daily_precision_retains_real_month_total(range_db):
    with get_db() as conn:
        conn.execute('DELETE FROM agg_daily_performance WHERE year=2026 AND month=5')
        conn.commit()
    data = get_platform_data(2026, range_type='month', end_date='2026-05-10')
    assert _amount(data) == 9999
    assert data['sourcePrecision']['performance'] == 'month'
    assert data['rangeWarnings']


def test_legacy_as_of_contract_is_unchanged(range_db):
    data = get_platform_data(2026, as_of='2026-06-10')
    assert _amount(data) == 150
    assert 'rangeApplied' not in data


@pytest.mark.parametrize('start,end,expected', [
    ('2026-05-20', '2026-06-11', 148),
    ('2026-06-05', '2026-06-05', 0),
    ('2026-06-10', '2026-06-10', -12),
])
def test_kpi_platform_product_payment_reconcile_same_range(range_db, start, end, expected):
    from db.repositories.kpi import get_kpi_data
    from db.repositories.product import get_product_structure
    from db.repositories.payment import get_payment_period_structure

    with get_db() as conn:
        # Different source cutoffs, genuine zero activity and negative reversals.
        conn.execute('DELETE FROM agg_jingdai_daily WHERE year=2026 AND month=6 AND day=11')
        conn.execute('UPDATE agg_daily_performance SET qj_premium=0 WHERE year=2026 AND month=6 AND day=1')
        conn.execute('UPDATE agg_jingdai_daily SET qj_premium=0 WHERE year=2026 AND month=6 AND day=1')
        conn.execute('UPDATE agg_daily_performance SET qj_premium=-5 WHERE year=2026 AND month=6 AND day=10')
        conn.execute('UPDATE agg_jingdai_daily SET qj_premium=-7 WHERE year=2026 AND month=6 AND day=10')
        for table, business_type, channel in (('agg_daily_performance', '转型', 'OTO'), ('agg_jingdai_daily', '经代', '经代')):
            for row in conn.execute(f'SELECT month,day,qj_premium FROM {table} WHERE year=2026').fetchall():
                base = (2026, row['month'], row['day'], business_type, channel, '测试机构')
                conn.execute('INSERT INTO agg_product_daily(year,month,day,business_type,channel,org,product_category,product_name,qj_premium,count) VALUES(?,?,?,?,?,?,?,?,?,?)',
                             (*base, '年金', '测试产品', row['qj_premium'], 1))
                conn.execute('INSERT INTO agg_payment_period_daily(year,month,day,business_type,channel,org,category,qj_premium,count) VALUES(?,?,?,?,?,?,?,?,?)',
                             (*base, '5年交', row['qj_premium'], 1))
        conn.commit()

    args = dict(range_type='custom', start_date=start, end_date=end)
    kpi = get_kpi_data(2026, **args)
    platform = get_platform_data(2026, **args)
    product = get_product_structure(2026, dimension='product_mix', **args)
    payment = get_payment_period_structure(2026, **args)
    assert kpi['qj_premium']['total'] == expected
    assert _amount(platform) + _amount(platform, 'jingdai') == expected
    assert sum(row['value'] for row in product['premium']) == expected
    assert sum(row['value'] for row in payment['premium']) == expected
    assert {data['period']['startDate'] for data in (kpi, platform, product, payment)} == {start}
    assert {data['period']['endDate'] for data in (kpi, platform, product, payment)} == {end}


def test_previous_year_shorter_coverage_is_disclosed(range_db):
    with get_db() as conn:
        conn.execute('DELETE FROM agg_daily_performance WHERE year=2025 AND month=6 AND day>1')
        conn.execute('DELETE FROM agg_jingdai_daily WHERE year=2025 AND month=6 AND day>1')
        conn.commit()
    data = get_platform_data(2025, range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    assert data['period']['endDate'] == '2025-06-01'
    assert any('实际统计范围为2025-05-20至2025-06-01' in text for text in data['rangeWarnings'])


def test_excel_platform_uses_selected_range_and_team_keeps_monthly_background(range_db):
    from io import BytesIO
    from openpyxl import load_workbook
    from services.excel_exporter import build_dashboard_export_workbook

    with get_db() as conn:
        conn.execute("INSERT INTO agg_hr_data(year,month,channel,start_headcount,end_headcount,active_headcount) VALUES(2026,1,'OTO',10,10,1)")
        conn.commit()
    binary = build_dashboard_export_workbook(2026, range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    book = load_workbook(BytesIO(binary), data_only=True)
    assert sum(row[2] or 0 for row in book['平台趋势'].iter_rows(min_row=3, values_only=True)) == 280
    assert book['队伍分析']['A3'].value == 1
    explanation = ' '.join(str(row[1]) for row in book['导出说明'].iter_rows(min_row=3, values_only=True))
    assert '平台趋势、产品明细和交期结构按所选范围导出' in explanation


@pytest.fixture()
def mixed_payment_db(range_db):
    with get_db() as conn:
        for month, amount in ((5, 70), (6, 90)):
            conn.execute('INSERT INTO agg_payment_period(year,month,business_type,channel,org,category,qj_premium,gm_premium,count) VALUES(?,?,?,?,?,?,?,?,?)',
                         (2026, month, '经代', '', '经代机构', '5年交', amount, amount * 2, 7))
        for month, day, amount in ((5, 20, 10), (6, 10, 20)):
            conn.execute('INSERT INTO agg_payment_period_daily(year,month,day,business_type,channel,org,category,qj_premium,gm_premium,count) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (2026, month, day, '转型', 'OTO', '上海', '3年交', amount, amount * 2, 1))
        conn.commit()


def test_payment_full_month_retains_monthly_source_beside_daily_source(mixed_payment_db):
    from db.repositories.payment import get_payment_period_structure
    data = get_payment_period_structure(2026, range_type='month', end_date='2026-05-15')
    assert {row['name']: row['value'] for row in data['premium']} == {'3年交': 10, '5年交': 70}
    assert data['precision'] == 'mixed'
    assert data['sourcePrecision'] == {'经代': 'month', '转型': 'day'}
    assert data['calculable']


def test_payment_partial_month_masks_unknown_source_but_preserves_known_source(mixed_payment_db):
    from db.repositories.payment import get_payment_period_structure
    data = get_payment_period_structure(2026, range_type='custom', start_date='2026-05-20', end_date='2026-06-10')
    assert {row['name']: row['value'] for row in data['premium']} == {'3年交': 30, '5年交': None}
    assert data['precision'] == 'unavailable'
    assert not data['calculable']
    assert data['rangeWarnings']
    by_mode = {row['business_mode']: row['total'] for row in data['average_premium']['rows']}
    assert data['premiumTotal'] is None
    assert by_mode['经代']['premium'] is None
    assert by_mode['经代']['count'] is None
    assert by_mode['经代']['average'] is None
    assert by_mode['OTO']['premium'] == 30
    all_summary = next(row for row in data['average_premium']['summaries'] if row['org'] == row['business_mode'] == 'all')
    assert all_summary['total']['premium'] is None
    assert not all_summary['total']['calculable']


def test_payment_source_filters_exclude_irrelevant_missing_precision(mixed_payment_db):
    from db.repositories.payment import get_payment_period_structure
    data = get_payment_period_structure(2026, business_types=['转型'], range_type='day', end_date='2026-06-10')
    assert data['premium'] == [{'name': '3年交', 'value': 20}]
    assert data['precision'] == 'day' and data['calculable']
    assert data['rangeWarnings'] == []


def test_payment_zero_day_does_not_fall_back_to_full_month(mixed_payment_db):
    from db.repositories.payment import get_payment_period_structure
    data = get_payment_period_structure(2026, business_types=['转型'], range_type='day', end_date='2026-06-05')
    assert data['premium'] == []
    assert data['count'] == []


def test_product_and_payment_totals_round_after_summing_categories(range_db):
    from db.repositories.product import get_product_structure
    from db.repositories.payment import get_payment_period_structure

    # Each category displays 0.01; the true combined 0.012 rounds to 0.01.
    with get_db() as conn:
        for category in ('分类甲', '分类乙'):
            conn.execute('INSERT INTO agg_product_daily(year,month,day,business_type,channel,org,product_category,product_name,qj_premium,count) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (2026, 6, 10, '转型', 'OTO', '上海', category, category, 0.006, 1))
            conn.execute('INSERT INTO agg_payment_period_daily(year,month,day,business_type,channel,org,category,qj_premium,count) VALUES(?,?,?,?,?,?,?,?,?)',
                         (2026, 6, 10, '转型', 'OTO', '上海', category, 0.006, 1))
        conn.commit()
    args = dict(range_type='day', end_date='2026-06-10')
    product = get_product_structure(2026, dimension='product_mix', include_jingdai=False, **args)
    payment = get_payment_period_structure(2026, business_types=['转型'], **args)
    for data in (product, payment):
        assert data['premiumTotal'] == 0.01
        assert sum(row['value'] for row in data['premium']) == 0.02
        assert '未舍入金额' in data['roundingNote']
