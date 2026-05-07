from pathlib import Path

from aggregator import (
    parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel,
    aggregate_performance, aggregate_jingdai, aggregate_hr, aggregate_value,
    aggregate_product_structure, aggregate_active_headcount,
)
from database import clear_year_data, get_db, init_db, replace_rows


ROOT = Path(__file__).resolve().parent.parent


def _pick(pattern: str) -> Path | None:
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def main():
    init_db()

    performance_file = _pick('AI-经营分析业绩基表*.xlsx')
    value_file = _pick('AI-经营分析价值基表*.xlsx')
    hr_file = _pick('N1AI-人力基表*.xlsx')
    jingdai_file = _pick('*经代*业绩*.xlsx')

    perf_rows, product_rows, value_rows, hr_rows, jd_rows, active_rows = [], [], [], [], [], []

    if performance_file:
        df = parse_performance_excel(performance_file.read_bytes())
        perf_rows = aggregate_performance(df)
        product_rows = aggregate_product_structure(df)
        active_rows = aggregate_active_headcount(df)
        print(f'performance: {performance_file.name} -> {len(perf_rows)} rows')

    if jingdai_file:
        df = parse_jingdai_excel(jingdai_file.read_bytes())
        jd_rows = aggregate_jingdai(df)
        print(f'jingdai: {jingdai_file.name} -> {len(jd_rows)} rows')

    if hr_file:
        df = parse_hr_excel(hr_file.read_bytes())
        hr_rows = aggregate_hr(df)
        print(f'hr: {hr_file.name} -> {len(hr_rows)} rows')

    if value_file:
        df = parse_value_excel(value_file.read_bytes())
        value_rows = aggregate_value(df)
        print(f'value: {value_file.name} -> {len(value_rows)} rows')

    if hr_rows and active_rows:
        active_index = {
            (r['year'], r['month'], r['channel']): r['active_headcount']
            for r in active_rows
        }
        for row in hr_rows:
            row['active_headcount'] = active_index.get((row['year'], row['month'], row['channel']), 0)

    years = sorted({
        int(row['year'])
        for rows in [perf_rows, product_rows, value_rows, hr_rows, jd_rows]
        for row in rows
        if row.get('year')
    })

    for year in years:
        clear_year_data(year)

    with get_db() as conn:
        replace_rows(conn, 'agg_performance', perf_rows)
        replace_rows(conn, 'agg_jingdai', jd_rows)
        replace_rows(conn, 'agg_hr_data', hr_rows)
        replace_rows(conn, 'agg_value_data', value_rows)
        replace_rows(conn, 'agg_product_structure', product_rows)
        conn.commit()

    print(f'loaded years: {years}')


if __name__ == '__main__':
    main()
