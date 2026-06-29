from pathlib import Path

from etl import (
    parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel,
    aggregate_performance, aggregate_jingdai, aggregate_jingdai_daily, aggregate_hr, aggregate_value,
    aggregate_product_structure, aggregate_active_headcount,
    aggregate_daily_performance, aggregate_org_daily_performance,
    aggregate_org_performance, aggregate_org_value,
    aggregate_payment_period, aggregate_jingdai_payment_period,
    aggregate_transform_longterm, aggregate_jingdai_longterm,
    aggregate_org_hr, aggregate_org_active_headcount,
)
from db import clear_year_data, get_db, init_db, replace_rows
from services.operation_lock import operation_lock
from services.product_config_service import extract_jingdai_products_to_config, purge_non_jingdai_product_config


ROOT = Path(__file__).resolve().parent.parent

EXCEL_SOURCE_PATTERNS = {
    'performance': 'AI-\u7ecf\u8425\u5206\u6790\u4e1a\u7ee9\u57fa\u8868*.xlsx',
    'value': 'AI-\u7ecf\u8425\u5206\u6790\u4ef7\u503c\u57fa\u8868*.xlsx',
    'hr': 'N1AI-\u4eba\u529b\u57fa\u8868*.xlsx',
    'jingdai': '*\u7ecf\u4ee3*\u4e1a\u7ee9*.xlsx',
}


def _pick(pattern: str) -> Path | None:
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def find_excel_sources(required: bool = True) -> dict[str, Path | None]:
    sources = {name: _pick(pattern) for name, pattern in EXCEL_SOURCE_PATTERNS.items()}
    if required:
        missing = [name for name, path in sources.items() if path is None]
        if missing:
            existing = ', '.join(sorted(p.name for p in ROOT.glob('*.xlsx'))) or 'none'
            raise FileNotFoundError(
                f"Missing required Excel source(s): {', '.join(missing)}. "
                f"Existing root Excel files: {existing}"
            )
    return sources


def main():
    with operation_lock("excel-rebuild", timeout=1.0):
        _main_locked()


def _main_locked():
    init_db()
    with get_db() as conn:
        purged = purge_non_jingdai_product_config(conn)
        conn.commit()
        if purged:
            print(f'product_config: purged {purged} non-jingdai rows')

    sources = find_excel_sources(required=True)
    performance_file = sources['performance']
    value_file = sources['value']
    hr_file = sources['hr']
    jingdai_file = sources['jingdai']

    perf_rows, daily_rows, org_daily_rows = [], [], []
    product_rows, value_rows, org_value_rows = [], [], []
    hr_rows, jd_rows, jd_daily_rows, active_rows, org_perf_rows, org_hr_rows, org_active_rows = [], [], [], [], [], [], []
    pay_period_rows, jd_pay_period_rows = [], []
    longterm_rows, jd_longterm_rows = [], []
    raw_tables = {}

    if performance_file:
        df = parse_performance_excel(performance_file.read_bytes())
        raw_tables['performance'] = df
        perf_rows = aggregate_performance(df)
        daily_rows = aggregate_daily_performance(df)
        org_daily_rows = aggregate_org_daily_performance(df)
        product_rows = aggregate_product_structure(df)
        active_rows = aggregate_active_headcount(df)
        org_active_rows = aggregate_org_active_headcount(df)
        org_perf_rows = aggregate_org_performance(df)
        pay_period_rows = aggregate_payment_period(df)
        longterm_rows = aggregate_transform_longterm(df)
        print(
            f'performance: {performance_file.name} -> {len(perf_rows)} monthly, '
            f'{len(daily_rows)} daily, {len(org_perf_rows)} org rows, '
            f'{len(pay_period_rows)} pay period rows, '
            f'{len(longterm_rows)} longterm rows'
        )

    if jingdai_file:
        df = parse_jingdai_excel(jingdai_file.read_bytes())
        raw_tables['jingdai'] = df
        extract_jingdai_products_to_config(df)
        jd_rows = aggregate_jingdai(df)
        jd_daily_rows = aggregate_jingdai_daily(df)
        jd_pay_period_rows = aggregate_jingdai_payment_period(df)
        jd_longterm_rows = aggregate_jingdai_longterm(df)
        print(f'jingdai: {jingdai_file.name} -> {len(jd_rows)} monthly, {len(jd_daily_rows)} daily, '
              f'{len(jd_pay_period_rows)} pay period rows, '
              f'{len(jd_longterm_rows)} longterm rows')

    if hr_file:
        df = parse_hr_excel(hr_file.read_bytes())
        raw_tables['hr_data'] = df
        hr_rows = aggregate_hr(df)
        org_hr_rows = aggregate_org_hr(df)
        print(f'hr: {hr_file.name} -> {len(hr_rows)} rows, {len(org_hr_rows)} org rows')

    if value_file:
        df = parse_value_excel(value_file.read_bytes())
        raw_tables['value_data'] = df
        value_rows = aggregate_value(df)
        org_value_rows = aggregate_org_value(df)
        print(f'value: {value_file.name} -> {len(value_rows)} rows, {len(org_value_rows)} org rows')

    if hr_rows and active_rows:
        active_index = {
            (r['year'], r['month'], r['channel']): r['active_headcount']
            for r in active_rows
        }
        for row in hr_rows:
            row['active_headcount'] = active_index.get((row['year'], row['month'], row['channel']), 0)

    if org_hr_rows and org_active_rows:
        org_active_index = {
            (r['year'], r['month'], r['org'], r['channel']): r['active_headcount']
            for r in org_active_rows
        }
        for row in org_hr_rows:
            row['active_headcount'] = org_active_index.get((row['year'], row['month'], row['org'], row['channel']), 0)

    years = sorted({
        int(row['year'])
        for rows in [
            perf_rows, daily_rows, org_daily_rows, product_rows,
            value_rows, org_value_rows, hr_rows, jd_rows, jd_daily_rows, org_perf_rows,
            pay_period_rows, jd_pay_period_rows, longterm_rows, jd_longterm_rows,
            org_hr_rows,
        ]
        for row in rows
        if row.get('year')
    })

    for year in years:
        clear_year_data(year)

    with get_db() as conn:
        replace_rows(conn, 'agg_performance', perf_rows)
        replace_rows(conn, 'agg_daily_performance', daily_rows)
        replace_rows(conn, 'agg_org_daily_performance', org_daily_rows)
        replace_rows(conn, 'agg_jingdai', jd_rows)
        replace_rows(conn, 'agg_jingdai_daily', jd_daily_rows)
        replace_rows(conn, 'agg_hr_data', hr_rows)
        replace_rows(conn, 'agg_org_hr_data', org_hr_rows)
        replace_rows(conn, 'agg_value_data', value_rows)
        replace_rows(conn, 'agg_org_value', org_value_rows)
        replace_rows(conn, 'agg_product_structure', product_rows)
        replace_rows(conn, 'agg_org_performance', org_perf_rows)
        replace_rows(conn, 'agg_payment_period', pay_period_rows + jd_pay_period_rows)
        replace_rows(conn, 'agg_longterm_qj', longterm_rows + jd_longterm_rows)
        for table, df in raw_tables.items():
            df.to_sql(table, conn, if_exists='replace', index=False)
        conn.commit()

    print(f'loaded years: {years}')


if __name__ == '__main__':
    main()
