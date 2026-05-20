"""数据库表定义与初始化。

所有 CREATE TABLE / CREATE INDEX / ALTER TABLE 迁移集中在此文件。
"""
from db.connection import get_db

AGG_TABLES = [
    'agg_performance',
    'agg_jingdai',
    'agg_jingdai_daily',
    'agg_hr_data',
    'agg_org_hr_data',
    'agg_value_data',
    'agg_product_structure',
    'agg_daily_performance',
    'agg_org_daily_performance',
    'agg_org_performance',
    'agg_org_value',
    'agg_payment_period',
    'agg_longterm_qj',
]


def init_db():
    """建表、建索引、执行存量迁移。幂等，可重复调用。"""
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS agg_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            channel TEXT NOT NULL, qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            zs_premium REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_jingdai (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            zs_premium REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_jingdai_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, ymd TEXT, qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0, zs_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, day))''')
        _migrate(c, "ALTER TABLE agg_jingdai_daily ADD COLUMN ymd TEXT")

        c.execute('''CREATE TABLE IF NOT EXISTS agg_hr_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            channel TEXT NOT NULL, start_headcount INTEGER NOT NULL DEFAULT 0,
            end_headcount INTEGER NOT NULL DEFAULT 0, active_headcount INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_hr_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            org TEXT NOT NULL, channel TEXT NOT NULL, start_headcount INTEGER NOT NULL DEFAULT 0,
            end_headcount INTEGER NOT NULL DEFAULT 0, active_headcount INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, org, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_value_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            channel TEXT NOT NULL, value_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_product_structure (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL,
            dimension TEXT NOT NULL, label TEXT NOT NULL, premium REAL NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, dimension, label))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            org TEXT NOT NULL, channel TEXT NOT NULL, qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0, zs_premium REAL NOT NULL DEFAULT 0,
            product_10year REAL NOT NULL DEFAULT 0, product_annuity REAL NOT NULL DEFAULT 0,
            product_protection REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, org, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_value (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            org TEXT NOT NULL, channel TEXT NOT NULL, value_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, org, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_payment_period (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            business_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL, qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, business_type, channel, org, category))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_longterm_qj (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            business_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '',
            qj_premium REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, business_type, channel, org))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, channel TEXT NOT NULL, qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0, zs_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, day, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, org TEXT NOT NULL, channel TEXT NOT NULL,
            qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            zs_premium REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, org, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS target_config (
            year INTEGER PRIMARY KEY, payload TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT DEFAULT 'system')''')
        _migrate(c, "ALTER TABLE target_config ADD COLUMN updated_by TEXT DEFAULT 'system'")

        c.execute('''CREATE TABLE IF NOT EXISTS target_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, period_type TEXT NOT NULL,
            period_value INTEGER NOT NULL DEFAULT 0, business_line TEXT NOT NULL, org TEXT,
            metric_code TEXT NOT NULL, target_value REAL NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_by TEXT DEFAULT 'system',
            role_scope TEXT DEFAULT 'admin')''')

        c.execute('''CREATE TABLE IF NOT EXISTS data_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            data_years TEXT NOT NULL,
            table_counts TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            imported_by TEXT DEFAULT 'web')''')

        c.execute('''CREATE TABLE IF NOT EXISTS performance (
            "年月" TEXT, "业务模式" TEXT, "销售机构名称" TEXT, "产品类型" TEXT,
            "期交保费" REAL DEFAULT 0, "年化规保" REAL DEFAULT 0,
            "规模保费" REAL DEFAULT 0, "承保件数" INTEGER DEFAULT 0
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS jingdai (
            "时间" TEXT, "经代机构" TEXT, "产品名称" TEXT,
            "期交保费" REAL DEFAULT 0, "承保年化规保" REAL DEFAULT 0
        )''')

        for sql in [
            'CREATE INDEX IF NOT EXISTS ix_perf_year_month_channel ON agg_performance(year, month, channel)',
            'CREATE INDEX IF NOT EXISTS ix_jd_year_month ON agg_jingdai(year, month)',
            'CREATE INDEX IF NOT EXISTS ix_daily_year_month_day_channel ON agg_daily_performance(year, month, day, channel)',
            'CREATE INDEX IF NOT EXISTS ix_org_perf_year_month_org_channel ON agg_org_performance(year, month, org, channel)',
            'CREATE INDEX IF NOT EXISTS ix_org_value_year_month_org_channel ON agg_org_value(year, month, org, channel)',
            'CREATE INDEX IF NOT EXISTS ix_product_year_dimension ON agg_product_structure(year, dimension)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_year_period ON target_values(year, period_type, period_value)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_line_org_metric ON target_values(business_line, org, metric_code)',
            'CREATE INDEX IF NOT EXISTS ix_pay_period_year_month_type ON agg_payment_period(year, month, business_type)',
            'CREATE INDEX IF NOT EXISTS ix_longterm_qj_year_month ON agg_longterm_qj(year, month, business_type)',
            'CREATE INDEX IF NOT EXISTS ix_data_imports_hash ON data_imports(file_hash)',
            'CREATE INDEX IF NOT EXISTS ix_raw_performance_ym_line ON performance("年月", "业务模式")',
            'CREATE INDEX IF NOT EXISTS ix_raw_jingdai_time_org ON jingdai("时间", "经代机构")',
        ]:
            c.execute(sql)

        conn.commit()


def _migrate(c, sql):
    """执行迁移 SQL。如果列/表已存在则静默跳过。"""
    try:
        c.execute(sql)
    except Exception as exc:
        message = str(exc).lower()
        if 'duplicate column' in message or 'already exists' in message:
            return
        raise
