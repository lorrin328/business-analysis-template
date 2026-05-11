import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'business_data.db')

AGG_TABLES = [
    'agg_performance',
    'agg_jingdai',
    'agg_jingdai_daily',
    'agg_hr_data',
    'agg_value_data',
    'agg_product_structure',
    'agg_daily_performance',
    'agg_org_daily_performance',
    'agg_org_performance',
    'agg_org_value',
    'agg_payment_period',
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
            CREATE TABLE IF NOT EXISTS agg_jingdai_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL DEFAULT 1,
                ymd TEXT,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                zs_premium REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, day)
            )
        ''')
        try:
            c.execute("ALTER TABLE agg_jingdai_daily ADD COLUMN ymd TEXT")
        except sqlite3.OperationalError:
            pass

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
            CREATE TABLE IF NOT EXISTS agg_payment_period (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                business_type TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT '',
                org TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                qj_premium REAL NOT NULL DEFAULT 0,
                gm_premium REAL NOT NULL DEFAULT 0,
                count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month, business_type, channel, org, category)
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT DEFAULT 'system'
            )
        ''')
        try:
            c.execute("ALTER TABLE target_config ADD COLUMN updated_by TEXT DEFAULT 'system'")
        except sqlite3.OperationalError:
            pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS target_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                period_type TEXT NOT NULL,
                period_value INTEGER NOT NULL DEFAULT 0,
                business_line TEXT NOT NULL,
                org TEXT,
                metric_code TEXT NOT NULL,
                target_value REAL NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT DEFAULT 'system',
                role_scope TEXT DEFAULT 'admin'
            )
        ''')

        for sql in [
            'CREATE INDEX IF NOT EXISTS ix_perf_year_month_channel ON agg_performance(year, month, channel)',
            'CREATE INDEX IF NOT EXISTS ix_jd_year_month ON agg_jingdai(year, month)',
            'CREATE INDEX IF NOT EXISTS ix_daily_year_month_day_channel ON agg_daily_performance(year, month, day, channel)',
            'CREATE INDEX IF NOT EXISTS ix_org_perf_year_month_org_channel ON agg_org_performance(year, month, org, channel)',
            'CREATE INDEX IF NOT EXISTS ix_product_year_dimension ON agg_product_structure(year, dimension)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_year_period ON target_values(year, period_type, period_value)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_line_org_metric ON target_values(business_line, org, metric_code)',
            'CREATE INDEX IF NOT EXISTS ix_pay_period_year_month_type ON agg_payment_period(year, month, business_type)',
        ]:
            c.execute(sql)

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
            SELECT year, month, day, ymd, qj_premium, gm_premium, zs_premium
            FROM agg_jingdai_daily WHERE year = ? ORDER BY month, day
        ''', (year,))
        jingdai_daily_rows = c.fetchall()

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
            'jingdai_daily': [dict(r) for r in jingdai_daily_rows],
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
    """获取机构维度KPI数据，年度同比使用日累计至统计日截止"""
    init_db()
    with get_db() as conn:
        c = conn.cursor()

        # 找到当前年度统计截止日（日表最新日期），用于截断同比基准
        c.execute('''
            SELECT month, MAX(day) as max_day
            FROM agg_org_daily_performance
            WHERE year = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
        ''', (year,))
        cutoff = c.fetchone()
        if cutoff and cutoff['month']:
            ytd_end_month = cutoff['month']
            ytd_end_day = cutoff['max_day'] or 31
            use_daily = True
        else:
            # 无日数据时回退：当月表最新月份截断
            c.execute('SELECT MAX(month) FROM agg_org_performance WHERE year = ?', (year,))
            row = c.fetchone()
            ytd_end_month = row[0] if row and row[0] else 12
            ytd_end_day = 31
            use_daily = False

        def _ytd_premiums(query_year: int):
            """从日表取截至统计日的期交保费累计，无数据则回退None"""
            if not use_daily:
                return {}
            c.execute('''
                SELECT org, channel, SUM(qj_premium) AS qj_total
                FROM agg_org_daily_performance
                WHERE year = ?
                  AND (month < ? OR (month = ? AND day <= ?))
                GROUP BY org, channel
            ''', (query_year, ytd_end_month, ytd_end_month, ytd_end_day))
            return {f"{r['org']}|{r['channel']}": round(r['qj_total'] or 0, 2)
                    for r in c.fetchall()}

        def collect_perf(query_year: int):
            result = {}
            # 月度明细 + 季度汇总（完整月数据，保留原逻辑）
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
                    q_data[field] = round(q_data[field] + value, 2)
                # 年度累计仅累加 ≤ 统计截止月的月份（产品分解）
                if month <= ytd_end_month:
                    item['year']['product_10year'] = round(item['year']['product_10year'] + month_data['product_10year'], 2)
                    item['year']['product_annuity'] = round(item['year']['product_annuity'] + month_data['product_annuity'], 2)
                    item['year']['product_protection'] = round(item['year']['product_protection'] + month_data['product_protection'], 2)
                    # 无日数据时用月表累加期交保费
                    if not use_daily:
                        item['year']['qj_premium'] = round(item['year']['qj_premium'] + month_data['qj_premium'], 2)

            # 有日数据时用日累计覆盖年度期交保费（更精确到天）
            ytd_map = _ytd_premiums(query_year)
            for key, item in result.items():
                if key in ytd_map:
                    item['year']['qj_premium'] = ytd_map[key]
                elif use_daily:
                    # 日表无该组合则置零
                    item['year']['qj_premium'] = 0
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
                if month <= ytd_end_month:
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


def get_payment_period_structure(
    year: int,
    month: int | None = None,
    business_types: list[str] | None = None,
    channels: list[str] | None = None,
    orgs: list[str] | None = None,
    jingdai_orgs: list[str] | None = None,
    metric: str = 'qj',
):
    """获取交期结构数据，按交期分类聚合保费/件数"""
    init_db()
    premium_field = 'gm_premium' if metric == 'gm' else 'qj_premium'
    with get_db() as conn:
        c = conn.cursor()

        conditions = ['year = ?']
        params = [year]

        if month is not None:
            conditions.append('month = ?')
            params.append(month)

        if business_types:
            placeholders = ','.join(['?'] * len(business_types))
            conditions.append(f'business_type IN ({placeholders})')
            params.extend(business_types)

        if channels:
            placeholders = ','.join(['?'] * len(channels))
            conditions.append(f'channel IN ({placeholders})')
            params.extend(channels)

        if orgs and 'all' not in orgs:
            placeholders = ','.join(['?'] * len(orgs))
            conditions.append(f'org IN ({placeholders})')
            params.extend(orgs)

        if jingdai_orgs and 'all' not in jingdai_orgs:
            placeholders = ','.join(['?'] * len(jingdai_orgs))
            conditions.append(f'business_type != \'经代\' OR org IN ({placeholders})')
            params.extend(jingdai_orgs)

        where = ' AND '.join(conditions) if conditions else '1=1'

        c.execute(f'''
            SELECT category,
                   SUM({premium_field}) AS premium_total,
                   SUM(count) AS count_total
            FROM agg_payment_period
            WHERE {where}
            GROUP BY category
            ORDER BY premium_total DESC
        ''', params)

        premium_rows = []
        count_rows = []
        for r in c.fetchall():
            premium_rows.append({'name': r['category'], 'value': round(r['premium_total'] or 0, 2)})
            count_rows.append({'name': r['category'], 'value': int(r['count_total'] or 0)})

        # 获取经代机构列表
        jd_orgs = []
        if business_types is None or '经代' in business_types:
            c2 = conn.cursor()
            c2.execute('''
                SELECT DISTINCT org FROM agg_payment_period
                WHERE year = ? AND business_type = '经代' AND org != '' AND org != '未知'
                ORDER BY org
            ''', (year,))
            jd_orgs = [r['org'] for r in c2.fetchall()]

        return {
            'year': year,
            'premium': premium_rows,
            'count': count_rows,
            'jingdai_orgs': jd_orgs,
        }


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item and item.strip()]


def _query_product_structure_raw(
    conn: sqlite3.Connection,
    year: int,
    transform_lines: list[str],
    jingdai_orgs: list[str],
    include_transform: bool,
    include_jingdai: bool,
    orgs: list[str] | None = None,
    months: list[int] | None = None,
    metric_type: str = 'qj',
) -> list[dict]:
    rows: list[dict] = []
    c = conn.cursor()

    perf_premium_col = 'COALESCE("年化规保", COALESCE("规模保费", 0))' if metric_type == 'gm' else 'COALESCE("期交保费", 0)'
    jd_premium_col = 'COALESCE("承保年化规保", 0)' if metric_type == 'gm' else 'COALESCE("期交保费", 0)'

    normalized_transform_lines = set(transform_lines or [])
    raw_transform_lines = set(normalized_transform_lines)
    if '证保' in normalized_transform_lines:
        raw_transform_lines.add('证券')
    if '蚁桥' in normalized_transform_lines:
        raw_transform_lines.add('网服')

    raw_transform_line_list = sorted(raw_transform_lines)
    if include_transform and raw_transform_line_list:
        t_params: list = [year]
        extra_where = ''
        if months:
            m_placeholders = ','.join(['?'] * len(months))
            extra_where += f' AND CAST(substr("年月", 5, 2) AS INTEGER) IN ({m_placeholders})'
            t_params.extend(months)
        if orgs:
            o_placeholders = ','.join(['?'] * len(orgs))
            extra_where += f' AND "销售机构名称" IN ({o_placeholders})'
            t_params.extend(orgs)
        placeholders = ','.join(['?'] * len(raw_transform_line_list))
        c.execute(f'''
            SELECT COALESCE(NULLIF(TRIM("产品类型"), ''), '未分类') AS label,
                   SUM({perf_premium_col}) / 10000.0 AS premium,
                   SUM(COALESCE("承保件数", 1)) AS count
            FROM performance
            WHERE CAST(substr("年月", 1, 4) AS INTEGER) = ?
              AND "业务模式" IN ({placeholders})
              {extra_where}
            GROUP BY COALESCE(NULLIF(TRIM("产品类型"), ''), '未分类')
        ''', [*t_params, *raw_transform_line_list])
        for row in c.fetchall():
            item = dict(row)
            item['source'] = '转型'
            rows.append(item)

    if include_jingdai:
        jd_params: list = [year]
        jd_extra_where = ''
        if months:
            m_placeholders = ','.join(['?'] * len(months))
            jd_extra_where += f' AND CAST(substr("时间", 5, 2) AS INTEGER) IN ({m_placeholders})'
            jd_params.extend(months)
        org_clause = ''
        if jingdai_orgs:
            placeholders = ','.join(['?'] * len(jingdai_orgs))
            org_clause = f' AND "经代机构" IN ({placeholders})'
            jd_params.extend(jingdai_orgs)
        c.execute(f'''
            SELECT COALESCE(NULLIF(TRIM("产品名称"), ''), '未分类') AS label,
                   SUM({jd_premium_col}) / 10000.0 AS premium,
                   COUNT(*) AS count
            FROM jingdai
            WHERE CAST(substr("时间", 1, 4) AS INTEGER) = ?
              {jd_extra_where}
              {org_clause}
            GROUP BY COALESCE(NULLIF(TRIM("产品名称"), ''), '未分类')
        ''', jd_params)
        for row in c.fetchall():
            item = dict(row)
            item['source'] = '经代'
            rows.append(item)

    merged: dict[str, dict] = {}
    mixed_sources = include_transform and include_jingdai
    for row in rows:
        label = row.get('label') or '未分类'
        if mixed_sources:
            label = f"{row.get('source')}-{label}"
        item = merged.setdefault(label, {'label': label, 'premium': 0.0, 'count': 0})
        item['premium'] += float(row.get('premium') or 0)
        item['count'] += int(row.get('count') or 0)
    return sorted(merged.values(), key=lambda r: abs(r['premium']), reverse=True)[:20]


def get_jingdai_orgs(year: int | None = None) -> list[str]:
    init_db()
    with get_db() as conn:
        params: list = []
        where = ''
        if year:
            where = 'WHERE CAST(substr("时间", 1, 4) AS INTEGER) = ?'
            params.append(year)
        rows = conn.execute(f'''
            SELECT DISTINCT TRIM("经代机构") AS org
            FROM jingdai
            {where}
            ORDER BY org
        ''', params).fetchall()
        return [r['org'] for r in rows if r['org']]


def get_product_structure(
    year: int,
    dimension: str = 'design_cat',
    transform_lines: str | list[str] | None = None,
    jingdai_orgs: str | list[str] | None = None,
    include_transform: bool = True,
    include_jingdai: bool = True,
    orgs: str | list[str] | None = None,
    months: str | list[int] | None = None,
    metric_type: str = 'qj',
):
    init_db()
    with get_db() as conn:
        transform_list = transform_lines if isinstance(transform_lines, list) else _split_csv(transform_lines)
        jingdai_org_list = jingdai_orgs if isinstance(jingdai_orgs, list) else _split_csv(jingdai_orgs)
        org_list = orgs if isinstance(orgs, list) else _split_csv(orgs) if isinstance(orgs, str) else None
        month_list = months if isinstance(months, list) else [int(m.strip()) for m in months.split(',') if m.strip().isdigit()] if isinstance(months, str) else None
        if not transform_list:
            transform_list = ['OTO', '证保', '蚁桥']

        if dimension == 'product_mix':
            rows = _query_product_structure_raw(
                conn, year, transform_list, jingdai_org_list,
                include_transform, include_jingdai,
                orgs=org_list, months=month_list, metric_type=metric_type,
            )
            return {
                'year': year,
                'dimension': dimension,
                'premium': [{'name': r['label'], 'value': round(r['premium'], 2)} for r in rows if round(r['premium'], 2) != 0],
                'count': [{'name': r['label'], 'value': int(r['count'])} for r in rows if int(r['count']) != 0],
                'jingdaiOrgs': get_jingdai_orgs(year),
            }

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
            'jingdaiOrgs': get_jingdai_orgs(year),
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


def _flatten_target_payload(year: int, payload: dict, updated_by: str = 'system') -> list[dict]:
    rows = []

    def append_row(period_type, period_value, business_line, metric_code, target_value, org=None):
        if target_value is None:
            return
        try:
            value = float(target_value or 0)
        except (TypeError, ValueError):
            value = 0
        rows.append({
            'year': int(year),
            'period_type': period_type,
            'period_value': int(period_value),
            'business_line': business_line,
            'org': org,
            'metric_code': metric_code,
            'target_value': value,
            'updated_by': updated_by,
        })

    categories = (payload or {}).get('categories') or {}
    for metric_code, category in categories.items():
        metrics = (category or {}).get('metrics') or {}
        for business_line, metric in metrics.items():
            append_row('year', 0, business_line, metric_code, metric.get('year') if isinstance(metric, dict) else 0)
            for idx, value in enumerate((metric or {}).get('quarter') or [], start=1):
                append_row('quarter', idx, business_line, metric_code, value)
            for idx, value in enumerate((metric or {}).get('month') or [], start=1):
                append_row('month', idx, business_line, metric_code, value)

    org_targets = (payload or {}).get('orgTargets') or {}
    for org_line_key, metrics in org_targets.items():
        org, business_line = (org_line_key.split('|', 1) + [''])[:2] if '|' in org_line_key else (org_line_key, '')
        for metric_code, metric in (metrics or {}).items():
            append_row('year', 0, business_line, metric_code, metric.get('year') if isinstance(metric, dict) else 0, org)
            for idx, value in enumerate((metric or {}).get('quarter') or [], start=1):
                append_row('quarter', idx, business_line, metric_code, value, org)
            for idx, value in enumerate((metric or {}).get('month') or [], start=1):
                append_row('month', idx, business_line, metric_code, value, org)

    return rows


def save_target_values(conn: sqlite3.Connection, year: int, payload: dict, updated_by: str = 'system'):
    rows = _flatten_target_payload(year, payload, updated_by)
    conn.execute('DELETE FROM target_values WHERE year = ?', (year,))
    if not rows:
        return
    conn.executemany(
        '''
        INSERT INTO target_values (
            year, period_type, period_value, business_line, org, metric_code,
            target_value, updated_by, updated_at
        ) VALUES (
            :year, :period_type, :period_value, :business_line, :org, :metric_code,
            :target_value, :updated_by, CURRENT_TIMESTAMP
        )
        ''',
        rows,
    )


def get_target_values(year: int, period_type: str | None = None, period_value: int | None = None):
    init_db()
    with get_db() as conn:
        sql = 'SELECT * FROM target_values WHERE year = ?'
        params = [year]
        if period_type:
            sql += ' AND period_type = ?'
            params.append(period_type)
        if period_value is not None:
            sql += ' AND period_value = ?'
            params.append(period_value)
        sql += ' ORDER BY metric_code, business_line, org, period_type, period_value'
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def save_target_config(year: int, payload: dict, updated_by: str = 'system'):
    init_db()
    payload = dict(payload)
    payload['year'] = year
    payload['updated_at'] = datetime.now().isoformat(timespec='seconds')
    payload['updated_by'] = updated_by
    with get_db() as conn:
        conn.execute(
            '''
            INSERT INTO target_config (year, payload, updated_at, updated_by)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(year) DO UPDATE SET
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
            ''',
            (year, json.dumps(payload, ensure_ascii=False), updated_by),
        )
        save_target_values(conn, year, payload, updated_by)
        conn.commit()
    return payload
