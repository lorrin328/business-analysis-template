"""Read-only aggregate reconciliation for the dashboard; never migrates the source DB."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def run(db_path):
    from db.repositories import kpi, platform, product, payment
    from services.cutoff_policy import latest_dashboard_cutoff

    @contextmanager
    def readonly_db():
        conn = sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        # mode=ro protects the source; range projection uses connection-local TEMP
        # tables only, kept in memory so no audit state is persisted.
        conn.execute('PRAGMA temp_store=MEMORY')
        try:
            yield conn
        finally:
            conn.close()

    # Existing repositories import get_db directly. Replace only their connection
    # provider for this process; no production configuration or data is changed.
    for module in list(sys.modules.values()):
        if getattr(module, '__name__', '').startswith(('db.', 'services.')) and hasattr(module, 'get_db'):
            module.get_db = readonly_db
    payment.init_db = lambda: None
    with readonly_db() as conn:
        year = conn.execute('SELECT MAX(year) FROM agg_daily_performance').fetchone()[0]
        cutoff = latest_dashboard_cutoff(conn, year)
    end = f'{year}-{cutoff["month"]:02}-{cutoff["day"]:02}'
    ranges = [('ytd', None, end), ('day', None, end),
              ('month', None, end), ('custom', f'{year}-{max(1,cutoff["month"]-1):02}-15', end)]
    results = []
    for mode, start, finish in ranges:
        args = dict(range_type=mode, start_date=start, end_date=finish)
        row = {'rangeType': mode, 'requestedStart': start, 'requestedEnd': finish}
        values = {}
        for name, calculate in (
            ('kpi', lambda: kpi.get_kpi_data(year, **args)),
            ('platform', lambda: platform.get_platform_data(year, **args)),
            ('product', lambda: product.get_product_structure(year, dimension='product_mix', **args)),
            ('payment', lambda: payment.get_payment_period_structure(year, **args)),
        ):
            try:
                data = calculate()
                if name == 'kpi':
                    total = data['qj_premium']['total']
                elif name == 'platform':
                    amounts = [item['qj_premium'] for key in ('performance', 'jingdai') for item in data[key]]
                    total = None if any(value is None for value in amounts) else sum(amounts)
                else:
                    amounts = [item['value'] for item in data['premium']]
                    total = data.get('premiumTotal', None if any(value is None for value in amounts) else sum(amounts))
                values[name] = total
                row[name] = {'totalWan': total, 'period': data.get('period', {}).get('label'),
                             'warnings': data.get('rangeWarnings', [])}
                if name in ('product', 'payment'):
                    row[name]['displayedCategorySumWan'] = None if any(value is None for value in amounts) else round(sum(amounts), 2)
            except Exception as error:
                row[name] = {'errorType': type(error).__name__}
        row['maxDifferenceWan'] = round(max(values.values()) - min(values.values()), 4) if len(values) == 4 and all(v is not None for v in values.values()) else None
        row['consistentAtTwoDecimals'] = len(values) == 4 and all(v is not None for v in values.values()) and len({round(value, 2) for value in values.values()}) == 1
        results.append(row)
    return {'mode': 'read-only', 'source': 'local database; not verified as current production',
            'latestDate': end, 'unit': '万元', 'scope': 'all business lines, all organizations, qj premium', 'ranges': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--output', required=True)
    options = parser.parse_args()
    report = run(options.db)
    Path(options.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
