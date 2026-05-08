import json
import os
import sqlite3
from contextlib import contextmanager


DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'business_data.db')

AGG_TABLES = [
    'agg_performance',
    'agg_jingdai',
    'agg_hr_data',
    'agg_value_data',
    'agg_product_structure',
    'agg_daily_performance',
    'agg_org_daily_performance',
    'agg_org_performance',
    'agg_org_value',
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                channel TEXT NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_jingdai (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_hr_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                channel TEXT NOT NULL,
                start_headcount INTEGER NOT NULL DEFAULT 0,
                end_headcount INTEGER NOT NULL DEFAULT 0,
                active_headcount INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_value_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                channel TEXT NOT NULL,
                value_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_product_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                dimension TEXT NOT NULL,
                label TEXT NOT NULL,
                premium REAL NOT NULL DEFAULT 0,
                count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, dimension, label)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_org_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                org TEXT NOT NULL,
                channel TEXT NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                product_10year REAL NOT NULL DEFAULT 0,
                product_annuity REAL NOT NULL DEFAULT 0,
                product_protection REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, org, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_org_value (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                org TEXT NOT NULL,
                channel TEXT NOT NULL,
                value_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, org, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL DEFAULT 1,
                channel TEXT NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, day, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS agg_org_daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL DEFAULT 1,
                org TEXT NOT NULL,
                channel TEXT NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, day, org, channel)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS target_config (
                year INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()


def clear_year_data(year: int):
    init_db()
    with get_db() as conn:
        c = conn.cursor()
        for table in AGG_TABLES:
            c.execute(f'DELETE FROM {table} WHERE year = ?', (year,))
        conn.commit()


def clear_table_year_data(table: str, year: int):
    if table not in AGG_TABLES:
        raise ValueError(f'unsupported table: {table}')
    init_db()
    with get_db() as conn:
        conn.execute(f'DELETE FROM {table} WHERE year = ?', (year,))
        conn.commit()


def replace_rows(conn: sqlite3.Connection, table: str, rows: list[dict]):
    if not rows:
        return
    keys = list(rows[0].keys())
    placeholders = ', '.join(['?'] * len(keys))
    columns = ', '.join(keys)
    sql = f'INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})'
    conn.executemany(sql, [[row.get(k) for k in keys] for row in rows])


def get_platform_data(year: int):
    init_db()
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            SELECT month, channel, qj_premium, gm_premium, zs_premium
            FROM agg_performance WHERE year = ? ORDER BY month, channel
        ''', (year,))
        perf_rows = c.fetchall()

        c.execute('''
            SELECT month, qj_premium, gm_premium, zs_premium
            FROM agg_jingdai WHERE year = ? ORDER BY month
        ''', (year,))
        jingdai_rows = c.fetchall()

        c.execute('''
            SELECT month, channel, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        hr_rows = c.fetchall()

        c.execute('''
            SELECT month, channel, value_premium
            FROM agg_value_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        value_rows = c.fetchall()

        c.execute('''
            SELECT month, org, channel, qj_premium, gm_premium, zs_premium
            FROM agg_org_performance WHERE year = ? ORDER BY month, org, channel
        ''', (year,))
        org_perf_rows = c.fetchall()

        c.execute('''
            SELECT month, day, channel, qj_premium, gm_premium, zs_premium
            FROM agg_daily_performance WHERE year = ? ORDER BY month, day, channel
        ''', (year,))
        daily_rows = c.fetchall()

        c.execute('''
            SELECT month, day, org, channel, qj_premium, gm_premium, zs_premium
            FROM agg_org_daily_performance WHERE year = ? ORDER BY month, day, org, channel
        ''', (year,))
        org_daily_rows = c.fetchall()

        c.execute('''
            SELECT MAX(year * 100 + month) AS latest_period
            FROM (
              SELECT year, month FROM agg_performance
              UNION ALL SELECT year, month FROM agg_jingdai
              UNION ALL SELECT year, month FROM agg_hr_data
              UNION ALL SELECT year, month FROM agg_value_data
            )
        ''')
        latest = c.fetchone()['latest_period']

        return {
            'performance': [dict(r) for r in perf_rows],
            'jingdai': [dict(r) for r in jingdai_rows],
            'hr': [dict(r) for r in hr_rows],
            'value': [dict(r) for r in value_rows],
            'org_performance': [dict(r) for r in org_perf_rows],
            'daily_performance': [dict(r) for r in daily_rows],
            'org_daily_performance': [dict(r) for r in org_daily_rows],
            'latest_period': latest,
        }


def get_kpi_data(year: int):
    init_db()
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            SELECT channel, SUM(qj_premium) AS total
            FROM agg_performance WHERE year = ? GROUP BY channel
        ''', (year,))
        perf = {r['channel']: r['total'] or 0 for r in c.fetchall()}

        c.execute('''
            SELECT SUM(qj_premium) AS total FROM agg_jingdai WHERE year = ?
        ''', (year,))
        jingdai_qj = c.fetchone()['total'] or 0

        c.execute('''
            SELECT channel,
                   SUM(start_headcount) AS start_sum,
                   SUM(end_headcount) AS end_sum,
                   SUM(active_headcount) AS active_sum,
                   COUNT(*) AS months
            FROM agg_hr_data WHERE year = ? GROUP BY channel
        ''', (year,))
        hr = {}
        for r in c.fetchall():
            months = r['months'] or 0
            avg_sum = ((r['start_sum'] or 0) + (r['end_sum'] or 0)) / 2.0
            hr[r['channel']] = {
                'start': r['start_sum'] or 0,
                'end': r['end_sum'] or 0,
                'active': r['active_sum'] or 0,
                'avg': avg_sum / months if months else 0,
                'avg_sum': avg_sum,
                'months': months,
            }

        c.execute('''
            SELECT channel, SUM(value_premium) AS total
            FROM agg_value_data WHERE year = ? GROUP BY channel
        ''', (year,))
        value = {r['channel']: r['total'] or 0 for r in c.fetchall()}

        total_transform = perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0)
        return {
            'year': year,
            'qj_premium': {
                'jingdai': round(jingdai_qj, 2),
                'oto': round(perf.get('OTO', 0), 2),
                'zhengbao': round(perf.get('证保', 0), 2),
                'yiqiao': round(perf.get('蚁桥', 0), 2),
                'total_transform': round(total_transform, 2),
                'total': round(jingdai_qj + total_transform, 2),
            },
            'hr': hr,
            'value': value,
        }


def get_org_kpi_data(year: int):
    """获取机构维度KPI数据"""
    init_db()
    with get_db() as conn:
        c = conn.cursor()

        def collect_perf(query_year: int):
            c.execute('''
                SELECT org, channel, month,
                       SUM(qj_premium) AS qj_total,
                       SUM(product_10year) AS p10_total,
                       SUM(product_annuity) AS annuity_total,
                       SUM(product_protection) AS protection_total
                FROM agg_org_performance
                WHERE year = ?
                GROUP BY org, channel, month
            ''', (query_year,))
            result = {}
            for r in c.fetchall():
                key = f"{r['org']}|{r['channel']}"
                month = int(r['month'])
                item = result.setdefault(key, {
                    'year': {'qj_premium': 0, 'product_10year': 0, 'product_annuity': 0, 'product_protection': 0},
                    'month': {},
                    'quarter': {},
                })
                month_data = {
                    'qj_premium': round(r['qj_total'] or 0, 2),
                    'product_10year': round(r['p10_total'] or 0, 2),
                    'product_annuity': round(r['annuity_total'] or 0, 2),
                    'product_protection': round(r['protection_total'] or 0, 2),
                }
                item['month'][str(month)] = month_data
                q_label = f"Q{((month - 1) // 3) + 1}"
                q_data = item['quarter'].setdefault(q_label, {
                    'qj_premium': 0, 'product_10year': 0, 'product_annuity': 0, 'product_protection': 0
                })
                for field, value in month_data.items():
                    item['year'][field] = round(item['year'][field] + value, 2)
                    q_data[field] = round(q_data[field] + value, 2)
            return result

        def collect_value(query_year: int):
            c.execute('''
                SELECT org, channel, month, SUM(value_premium) AS value_total
                FROM agg_org_value
                WHERE year = ?
                GROUP BY org, channel, month
            ''', (query_year,))
            result = {}
            for r in c.fetchall():
                key = f"{r['org']}|{r['channel']}"
                month = int(r['month'])
                value = round(r['value_total'] or 0, 2)
                item = result.setdefault(key, {'year': 0, 'month': {}, 'quarter': {}})
                item['year'] = round(item['year'] + value, 2)
                item['month'][str(month)] = value
                q_label = f"Q{((month - 1) // 3) + 1}"
                item['quarter'][q_label] = round(item['quarter'].get(q_label, 0) + value, 2)
            return result

        org_perf = collect_perf(year)
        org_value = collect_value(year)
        org_perf_prev = collect_perf(year - 1)
        org_value_prev = collect_value(year - 1)
        org_keys = set(org_perf.keys()) | set(org_value.keys())
        orgs = sorted({key.split('|', 1)[0] for key in org_keys})

        return {
            'year': year,
            'orgs': orgs,
            'perf': org_perf,
            'value': org_value,
            'perf_prev': org_perf_prev,
            'value_prev': org_value_prev,
        }


def get_product_structure(year: int, dimension: str = 'design_cat'):
    init_db()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT label, premium, count
            FROM agg_product_structure
            WHERE year = ? AND dimension = ?
            ORDER BY premium DESC
            LIMIT 12
        ''', (year, dimension))
        rows = [dict(r) for r in c.fetchall()]
        return {
            'year': year,
            'dimension': dimension,
            'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows],
            'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows],
        }


def get_target_config(year: int):
    init_db()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT payload FROM target_config WHERE year = ?', (year,))
        row = c.fetchone()
        if not row:
            return None
        try:
            return json.loads(row['payload'])
        except json.JSONDecodeError:
            return None


def save_target_config(year: int, payload: dict):
    init_db()
    payload = dict(payload)
    payload['year'] = year
    with get_db() as conn:
        conn.execute(
            '''
            INSERT INTO target_config (year, payload, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(year) DO UPDATE SET
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
            ''',
            (year, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    return payload
