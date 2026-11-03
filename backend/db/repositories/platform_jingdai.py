"""Read-only sales-platform breakdown; authoritative historical totals stay untouched."""
from collections import defaultdict
import math

from db.connection import get_db
from services.raw_table_reader import compact_period_expr, pick_existing_column
from etl.normalize import _fee_weight


def _known_fee_weight(value):
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    return _fee_weight(years) if math.isfinite(years) and years >= 0 else None


def get_jingdai_platform_trend(year: int) -> dict:
    with get_db() as conn:
        conn.create_function('jingdai_fee_weight', 1, _known_fee_weight, deterministic=True)
        period = compact_period_expr('时间')
        pay = '"缴费年限"' if pick_existing_column(conn, 'jingdai', ['缴费年限']) else 'NULL'
        weight = f'jingdai_fee_weight({pay})'
        rows = [dict(row) for row in conn.execute(f'''
            SELECT COALESCE(TRIM("经代机构"), '') AS platform,
                   CAST(substr({period}, 5, 2) AS INTEGER) AS month,
                   CAST(substr({period}, 7, 2) AS INTEGER) AS day,
                   ROUND(SUM("期交保费")/10000.0, 4) AS qj_premium,
                   ROUND(SUM("承保年化规保")/10000.0, 4) AS gm_premium,
                   CASE WHEN COUNT(*)=COUNT({weight})
                        THEN ROUND(SUM("期交保费" * ({weight}))/10000.0, 4) END AS zs_premium
            FROM jingdai WHERE "时间">=? AND "时间"<?
            GROUP BY platform, month, day ORDER BY platform, month, day
        ''', (str(year), str(year + 1))) if 1 <= (row['month'] or 0) <= 12]
        totals = {row['month']: dict(row) for row in conn.execute(
            'SELECT month, qj_premium, gm_premium FROM agg_jingdai WHERE year=?', (year,))}

    observed = defaultdict(lambda: {'qj_premium': 0, 'gm_premium': 0})
    for row in rows:
        for metric in ('qj_premium', 'gm_premium'):
            observed[row['month']][metric] += row[metric] or 0
    incomplete = [month for month, total in totals.items()
                  if month not in observed or any(abs(observed[month][metric] - total[metric]) > 0.02
                                                 for metric in ('qj_premium', 'gm_premium'))]
    return {'year': year, 'platforms': sorted({row['platform'] for row in rows}),
            'daily': rows, 'incompleteMonths': sorted(incomplete)}
