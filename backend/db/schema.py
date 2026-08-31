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
    'agg_org_daily_activity',
    'agg_org_performance',
    'agg_org_value',
    'agg_payment_period',
    'agg_payment_period_daily',
    'agg_longterm_qj',
    'agg_staff_month_performance',
    'agg_product_daily',
    'agg_zhituo_performance',
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
        _migrate(c, "ALTER TABLE agg_jingdai ADD COLUMN product_annuity REAL NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE agg_jingdai ADD COLUMN product_protection REAL NOT NULL DEFAULT 0")

        c.execute('''CREATE TABLE IF NOT EXISTS agg_jingdai_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, ymd TEXT, qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0, zs_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, day))''')
        _migrate(c, "ALTER TABLE agg_jingdai_daily ADD COLUMN ymd TEXT")
        _migrate(c, "ALTER TABLE agg_jingdai_daily ADD COLUMN product_annuity REAL NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE agg_jingdai_daily ADD COLUMN product_protection REAL NOT NULL DEFAULT 0")

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

        c.execute('''CREATE TABLE IF NOT EXISTS agg_staff_month_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL, month INTEGER NOT NULL,
            channel TEXT NOT NULL, org TEXT NOT NULL DEFAULT '', staff_id TEXT NOT NULL,
            qj_premium REAL NOT NULL DEFAULT 0,
            standard_premium REAL NOT NULL DEFAULT 0,
            policy_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, channel, org, staff_id))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_product_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL DEFAULT 1,
            business_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '',
            product_category TEXT NOT NULL DEFAULT '未分类',
            product_name TEXT NOT NULL DEFAULT '未分类',
            qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, business_type, channel, org, product_category, product_name))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_zhituo_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL DEFAULT 1,
            channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '',
            staff_id TEXT NOT NULL DEFAULT '人员待确认',
            product_name TEXT NOT NULL DEFAULT '产品待确认',
            product_type TEXT NOT NULL DEFAULT '产品类型待确认',
            payment_period TEXT NOT NULL DEFAULT '交期待确认',
            qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0,
            policy_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, channel, org, staff_id, product_name, product_type, payment_period))''')

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

        c.execute('''CREATE TABLE IF NOT EXISTS agg_payment_period_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, business_type TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '', category TEXT NOT NULL,
            qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, business_type, channel, org, category))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_longterm_qj (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1,
            business_type TEXT NOT NULL, channel TEXT NOT NULL DEFAULT '', org TEXT NOT NULL DEFAULT '',
            qj_premium REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, business_type, channel, org))''')
        _migrate_longterm_qj_daily(c)

        c.execute('''CREATE TABLE IF NOT EXISTS agg_daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, channel TEXT NOT NULL, qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0, zs_premium REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(year, month, day, channel))''')

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_daily_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, month INTEGER NOT NULL,
            day INTEGER NOT NULL DEFAULT 1, org TEXT NOT NULL, channel TEXT NOT NULL,
            qj_premium REAL NOT NULL DEFAULT 0, gm_premium REAL NOT NULL DEFAULT 0,
            zs_premium REAL NOT NULL DEFAULT 0,
            product_10year REAL NOT NULL DEFAULT 0, product_annuity REAL NOT NULL DEFAULT 0,
            product_protection REAL NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, day, org, channel))''')
        _migrate(c, "ALTER TABLE agg_org_daily_performance ADD COLUMN product_10year REAL NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE agg_org_daily_performance ADD COLUMN product_annuity REAL NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE agg_org_daily_performance ADD COLUMN product_protection REAL NOT NULL DEFAULT 0")

        c.execute('''CREATE TABLE IF NOT EXISTS agg_org_daily_activity (
            year INTEGER NOT NULL, month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 31), org TEXT NOT NULL, channel TEXT NOT NULL,
            has_positive_qj INTEGER NOT NULL DEFAULT 0 CHECK(has_positive_qj IN (0, 1)),
            uncertain INTEGER NOT NULL DEFAULT 0 CHECK(uncertain IN (0, 1)),
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

        c.execute('''CREATE TABLE IF NOT EXISTS product_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            product_name TEXT,
            business_type TEXT,
            is_annuity TEXT NOT NULL DEFAULT 'N',
            is_protection TEXT NOT NULL DEFAULT 'N',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(business_type, product_code))''')
        _migrate_product_config_unique(c)

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

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'normal',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            revoked_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS user_module_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module_key TEXT NOT NULL,
            allowed INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, module_key),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL DEFAULT 'system',
            action TEXT NOT NULL,
            target_user_id INTEGER,
            target_username TEXT,
            status TEXT NOT NULL DEFAULT 'success',
            detail TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            requires_aggregate_rebuild INTEGER NOT NULL DEFAULT 0,
            note TEXT DEFAULT ''
        )''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260524_aggregate_rebuild_from_raw', 1, 'Adds raw SQLite aggregate rebuild path')
        ''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER,
            rule_version TEXT NOT NULL,
            source_cutoff TEXT,
            data_source_mode TEXT NOT NULL DEFAULT 'existing_data',
            source_tables TEXT DEFAULT '{}',
            source_files TEXT DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'success',
            exception_count INTEGER NOT NULL DEFAULT 0,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_field_audit_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            table_name TEXT NOT NULL,
            required_field TEXT NOT NULL,
            matched_column TEXT,
            required_level TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 0,
            impact TEXT,
            fallback_strategy TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_source_staff_month (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            org TEXT,
            business_line TEXT,
            staff_code TEXT NOT NULL,
            staff_name TEXT,
            rank_name TEXT,
            role_type TEXT,
            staff_category TEXT,
            entry_year INTEGER,
            entry_month INTEGER,
            is_employed_end_month INTEGER DEFAULT 0,
            group_code TEXT,
            department_code TEXT,
            raw_payload TEXT DEFAULT '{}',
            UNIQUE(batch_id, year, month, staff_code, business_line, role_type)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_source_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            org TEXT,
            business_line TEXT,
            staff_code TEXT,
            policy_no TEXT,
            is_longterm INTEGER DEFAULT 0,
            payment_years REAL,
            standard_premium REAL DEFAULT 0,
            annualized_premium REAL DEFAULT 0,
            qj_premium REAL DEFAULT 0,
            premium_source TEXT,
            issue_date TEXT,
            callback_date TEXT,
            account_date TEXT,
            raw_payload TEXT DEFAULT '{}'
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_person_month (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            org TEXT,
            business_line TEXT,
            staff_code TEXT NOT NULL,
            staff_name TEXT,
            role_type TEXT,
            is_employed_end_month INTEGER DEFAULT 0,
            standard_premium REAL DEFAULT 0,
            longterm_policy_count INTEGER DEFAULT 0,
            monthly_qualified INTEGER DEFAULT 0,
            protected_month INTEGER DEFAULT 0,
            diamond_delta INTEGER DEFAULT 0,
            diamond_balance INTEGER DEFAULT 0,
            membership_level TEXT DEFAULT '未入会',
            is_new_star INTEGER DEFAULT 0,
            exception_flags TEXT DEFAULT '[]',
            UNIQUE(batch_id, year, month, staff_code, business_line, role_type)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_person_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            latest_month INTEGER NOT NULL,
            org TEXT,
            business_line TEXT,
            staff_code TEXT NOT NULL,
            staff_name TEXT,
            role_type TEXT,
            diamond_balance INTEGER DEFAULT 0,
            membership_level TEXT DEFAULT '未入会',
            total_gain INTEGER DEFAULT 0,
            total_deduct INTEGER DEFAULT 0,
            qualified_months INTEGER DEFAULT 0,
            is_new_star INTEGER DEFAULT 0,
            warning_tags TEXT DEFAULT '[]',
            UNIQUE(batch_id, year, staff_code, business_line, role_type)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_org_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            org TEXT NOT NULL,
            business_line TEXT,
            tracked_headcount INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            senior_plus_count INTEGER DEFAULT 0,
            monthly_gain_count INTEGER DEFAULT 0,
            monthly_deduct_count INTEGER DEFAULT 0,
            total_diamond INTEGER DEFAULT 0,
            member_rate REAL DEFAULT 0,
            avg_diamond REAL DEFAULT 0,
            estimated_reward REAL DEFAULT 0,
            UNIQUE(batch_id, year, month, org, business_line)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_quarter_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            org TEXT NOT NULL,
            staff_code TEXT,
            staff_name TEXT,
            membership_level TEXT,
            reward_amount REAL DEFAULT 0,
            reward_label TEXT,
            is_estimated INTEGER DEFAULT 1
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS honor_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            severity TEXT NOT NULL,
            exception_type TEXT NOT NULL,
            org TEXT,
            staff_code TEXT,
            policy_no TEXT,
            message TEXT NOT NULL,
            suggested_action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        _migrate_honor_identity_tracks(c)
        _migrate_honor_staff_category(c)

        c.execute('''CREATE TABLE IF NOT EXISTS scheme_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL,
            scheme_name TEXT NOT NULL,
            rule_version TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            summary_json TEXT NOT NULL DEFAULT '{}',
            detail_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            imported_by TEXT DEFAULT 'system',
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS branch_reference_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            regular_count INTEGER NOT NULL,
            referral_count INTEGER NOT NULL,
            imported_by TEXT DEFAULT 'system',
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS branch_reference (
            reference_id TEXT PRIMARY KEY,
            batch_id INTEGER NOT NULL,
            branch_type TEXT NOT NULL,
            branch_name TEXT NOT NULL UNIQUE,
            parent_name TEXT DEFAULT '',
            province TEXT DEFAULT '',
            city TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            project TEXT DEFAULT '',
            subproject TEXT DEFAULT '',
            locality TEXT DEFAULT '',
            include_in_regular_count INTEGER NOT NULL DEFAULT 0,
            source_row INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES branch_reference_batches(id)
        )''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260729_branch_reference_domain', 0, 'Adds protected branch reference master data')
        ''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260527_honor_domain', 0, 'Adds honor alliance tables and field audit foundation')
        ''')

        c.execute('''CREATE TABLE IF NOT EXISTS history_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_directory TEXT NOT NULL,
            source_cutoff TEXT,
            performance_rows INTEGER NOT NULL DEFAULT 0,
            customer_source_rows INTEGER NOT NULL DEFAULT 0,
            customer_policy_rows INTEGER NOT NULL DEFAULT 0,
            source_text_issue_rows INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            reconciliation_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT,
            imported_by TEXT NOT NULL DEFAULT 'system',
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS history_import_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            source_kind TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            min_period TEXT,
            max_period TEXT,
            text_issue_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(batch_id, file_name),
            FOREIGN KEY(batch_id) REFERENCES history_import_batches(id)
        )''')
        _migrate(c, "ALTER TABLE history_import_batches ADD COLUMN source_text_issue_rows INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE history_import_files ADD COLUMN text_issue_count INTEGER NOT NULL DEFAULT 0")
        c.execute('''CREATE TABLE IF NOT EXISTS history_reconciliation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            period TEXT NOT NULL,
            business_line TEXT NOT NULL,
            existing_rows INTEGER NOT NULL DEFAULT 0,
            source_rows INTEGER NOT NULL DEFAULT 0,
            existing_qj_premium REAL NOT NULL DEFAULT 0,
            source_qj_premium REAL NOT NULL DEFAULT 0,
            existing_policy_count INTEGER NOT NULL DEFAULT 0,
            source_policy_count INTEGER NOT NULL DEFAULT 0,
            matched_policy_count INTEGER NOT NULL DEFAULT 0,
            decision TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(batch_id, period, business_line),
            FOREIGN KEY(batch_id) REFERENCES history_import_batches(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS customer_policy_snapshot (
            policy_no TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            application_time TEXT,
            import_time TEXT,
            callback_time TEXT,
            underwriting_time TEXT NOT NULL,
            first_account_time TEXT,
            latest_account_time TEXT,
            hesitation_surrender_time TEXT,
            policy_status TEXT NOT NULL,
            termination_reason TEXT,
            status_group TEXT NOT NULL,
            raw_row_count INTEGER NOT NULL DEFAULT 1,
            batch_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES history_import_batches(id)
        )''')
        _migrate(c, "ALTER TABLE customer_policy_snapshot ADD COLUMN customer_import_batch_id INTEGER")
        c.execute('''CREATE TABLE IF NOT EXISTS customer_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_by TEXT NOT NULL DEFAULT 'system',
            manifest_hash TEXT NOT NULL,
            file_count INTEGER NOT NULL DEFAULT 0,
            source_rows INTEGER NOT NULL DEFAULT 0,
            normalized_policy_rows INTEGER NOT NULL DEFAULT 0,
            inserted_policies INTEGER NOT NULL DEFAULT 0,
            updated_policies INTEGER NOT NULL DEFAULT 0,
            unchanged_policies INTEGER NOT NULL DEFAULT 0,
            skipped_older_policies INTEGER NOT NULL DEFAULT 0,
            conflict_policies INTEGER NOT NULL DEFAULT 0,
            linked_performance_policies INTEGER NOT NULL DEFAULT 0,
            source_cutoff TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            error_message TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )''')
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN upload_id TEXT")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN total_bytes INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN received_bytes INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN processed_rows INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN invalid_rows INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN duplicate_rows INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_batches ADD COLUMN updated_at TIMESTAMP")
        c.execute('''CREATE TABLE IF NOT EXISTS customer_import_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES customer_import_batches(id)
        )''')
        _migrate(c, "ALTER TABLE customer_import_files ADD COLUMN file_index INTEGER NOT NULL DEFAULT 0")
        _migrate(c, "ALTER TABLE customer_import_files ADD COLUMN received_bytes INTEGER NOT NULL DEFAULT 0")
        c.execute('''CREATE TABLE IF NOT EXISTS customer_master (
            customer_id TEXT PRIMARY KEY,
            first_underwriting_time TEXT NOT NULL,
            first_policy_no TEXT NOT NULL,
            total_policy_count INTEGER NOT NULL DEFAULT 0,
            active_policy_count INTEGER NOT NULL DEFAULT 0,
            suspended_policy_count INTEGER NOT NULL DEFAULT 0,
            terminated_policy_count INTEGER NOT NULL DEFAULT 0,
            batch_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES history_import_batches(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS customer_policy_month_fact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            transaction_date TEXT,
            business_line TEXT NOT NULL,
            org TEXT NOT NULL DEFAULT '',
            policy_no TEXT NOT NULL,
            customer_id TEXT,
            underwriting_time TEXT,
            first_customer_underwriting_time TEXT,
            is_longterm INTEGER NOT NULL DEFAULT 0,
            qj_premium REAL NOT NULL DEFAULT 0,
            gm_premium REAL NOT NULL DEFAULT 0,
            zs_premium REAL NOT NULL DEFAULT 0,
            value_premium REAL NOT NULL DEFAULT 0,
            accepted_count REAL NOT NULL DEFAULT 0,
            policy_status TEXT,
            termination_reason TEXT,
            status_group TEXT NOT NULL DEFAULT 'unmatched',
            customer_match INTEGER NOT NULL DEFAULT 0,
            batch_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month, business_line, org, policy_no),
            FOREIGN KEY(batch_id) REFERENCES history_import_batches(id)
        )''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260801_customer_history_domain', 0, 'Adds full history import audit and customer policy analysis facts')
        ''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260802_dashboard_query_aggregates', 1, 'Adds bounded staff-month and product-day dashboard aggregates')
        ''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260802_customer_incremental_import', 0, 'Adds governed customer snapshot CSV/XLSX import audit')
        ''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260826_zhituo_analysis', 1, 'Adds dedicated zhituo aggregate and analysis page')
        ''')
        c.execute('''
            INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
            VALUES ('20260831_org_zero_streak', 1, 'Adds daily positive QJ acceptance evidence by business attribution date')
        ''')

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
            'CREATE INDEX IF NOT EXISTS ix_staff_perf_year_month ON agg_staff_month_performance(year, month, channel, org)',
            'CREATE INDEX IF NOT EXISTS ix_staff_perf_staff ON agg_staff_month_performance(year, staff_id, month)',
            'CREATE INDEX IF NOT EXISTS ix_product_daily_filter ON agg_product_daily(year, month, day, business_type, channel, org)',
            'CREATE INDEX IF NOT EXISTS ix_product_daily_name ON agg_product_daily(year, business_type, channel, product_name)',
            'CREATE INDEX IF NOT EXISTS ix_zhituo_filter ON agg_zhituo_performance(year, month, org)',
            'CREATE INDEX IF NOT EXISTS ix_zhituo_staff ON agg_zhituo_performance(year, staff_id, month)',
            'CREATE INDEX IF NOT EXISTS ix_zhituo_product ON agg_zhituo_performance(year, product_name, month)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_year_period ON target_values(year, period_type, period_value)',
            'CREATE INDEX IF NOT EXISTS ix_target_values_line_org_metric ON target_values(business_line, org, metric_code)',
            'CREATE INDEX IF NOT EXISTS ix_pay_period_year_month_type ON agg_payment_period(year, month, business_type)',
            'CREATE INDEX IF NOT EXISTS ix_pay_period_daily_range ON agg_payment_period_daily(year, month, day, business_type)',
            'CREATE INDEX IF NOT EXISTS ix_longterm_qj_year_month ON agg_longterm_qj(year, month, business_type)',
            'CREATE INDEX IF NOT EXISTS ix_data_imports_hash ON data_imports(file_hash)',
            'CREATE INDEX IF NOT EXISTS ix_users_role ON users(role)',
            'CREATE INDEX IF NOT EXISTS ix_user_sessions_user ON user_sessions(user_id)',
            'CREATE INDEX IF NOT EXISTS ix_user_permissions_user ON user_module_permissions(user_id)',
            'CREATE INDEX IF NOT EXISTS ix_raw_performance_ym_line ON performance("年月", "业务模式")',
            'CREATE INDEX IF NOT EXISTS ix_raw_jingdai_time_org ON jingdai("时间", "经代机构")',
            'CREATE INDEX IF NOT EXISTS ix_history_files_batch ON history_import_files(batch_id, source_kind)',
            'CREATE INDEX IF NOT EXISTS ix_history_reconciliation_batch ON history_reconciliation(batch_id, period, business_line)',
            'CREATE INDEX IF NOT EXISTS ix_customer_policy_customer ON customer_policy_snapshot(customer_id, underwriting_time)',
            'CREATE INDEX IF NOT EXISTS ix_customer_policy_status ON customer_policy_snapshot(status_group, underwriting_time)',
            'CREATE INDEX IF NOT EXISTS ix_customer_master_first_date ON customer_master(first_underwriting_time)',
            'CREATE INDEX IF NOT EXISTS ix_customer_fact_period_line ON customer_policy_month_fact(year, month, business_line)',
            'CREATE INDEX IF NOT EXISTS ix_customer_fact_org_period ON customer_policy_month_fact(org, year, month, business_line)',
            'CREATE INDEX IF NOT EXISTS ix_customer_fact_customer ON customer_policy_month_fact(customer_id, year, month)',
            'CREATE INDEX IF NOT EXISTS ix_customer_fact_policy ON customer_policy_month_fact(policy_no)',
            'CREATE INDEX IF NOT EXISTS ix_customer_fact_status ON customer_policy_month_fact(status_group, year, month)',
            'CREATE INDEX IF NOT EXISTS ix_customer_import_batches_status ON customer_import_batches(status, id)',
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_customer_import_batches_upload ON customer_import_batches(upload_id)',
            'CREATE INDEX IF NOT EXISTS ix_customer_import_files_batch ON customer_import_files(batch_id)',
        ]:
            c.execute(sql)

        for sql in [
            'CREATE INDEX IF NOT EXISTS ix_operation_logs_created ON operation_logs(created_at)',
            'CREATE INDEX IF NOT EXISTS ix_operation_logs_action ON operation_logs(action)',
            'CREATE INDEX IF NOT EXISTS ix_operation_logs_username ON operation_logs(username)',
        ]:
            c.execute(sql)

        for sql in [
            'CREATE INDEX IF NOT EXISTS ix_honor_batches_year_month ON honor_import_batches(year, month)',
            'CREATE INDEX IF NOT EXISTS ix_honor_person_month_batch ON honor_person_month(batch_id, year, month)',
            'CREATE INDEX IF NOT EXISTS ix_honor_person_summary_batch ON honor_person_summary(batch_id, year)',
            'CREATE INDEX IF NOT EXISTS ix_honor_org_summary_batch ON honor_org_summary(batch_id, year, month)',
            'CREATE INDEX IF NOT EXISTS ix_honor_exceptions_batch ON honor_exceptions(batch_id, severity)',
            'CREATE INDEX IF NOT EXISTS ix_scheme_batches_scheme ON scheme_import_batches(scheme_id, imported_at)',
            'CREATE INDEX IF NOT EXISTS ix_scheme_batches_hash ON scheme_import_batches(file_hash)',
            'CREATE INDEX IF NOT EXISTS ix_branch_reference_type ON branch_reference(branch_type, include_in_regular_count)',
            'CREATE INDEX IF NOT EXISTS ix_branch_reference_project ON branch_reference(project, grade)',
        ]:
            c.execute(sql)

        conn.commit()

    from auth import ensure_default_admin
    ensure_default_admin()


def _migrate(c, sql):
    """执行迁移 SQL。如果列/表已存在则静默跳过。"""
    try:
        c.execute(sql)
    except Exception as exc:
        message = str(exc).lower()
        if 'duplicate column' in message or 'already exists' in message:
            return
        raise


def _migrate_product_config_unique(c):
    indexes = c.execute("PRAGMA index_list(product_config)").fetchall()
    has_pair_unique = False
    has_code_only_unique = False
    for idx in indexes:
        if not idx[2]:
            continue
        cols = [row[2] for row in c.execute(f"PRAGMA index_info({idx[1]})").fetchall()]
        if cols == ["business_type", "product_code"]:
            has_pair_unique = True
        if cols == ["product_code"]:
            has_code_only_unique = True
    if has_pair_unique or not has_code_only_unique:
        return

    c.execute("ALTER TABLE product_config RENAME TO product_config_old")
    c.execute('''CREATE TABLE product_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL,
        product_name TEXT,
        business_type TEXT,
        is_annuity TEXT NOT NULL DEFAULT 'N',
        is_protection TEXT NOT NULL DEFAULT 'N',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(business_type, product_code))''')
    c.execute('''
        INSERT OR IGNORE INTO product_config
            (id, product_code, product_name, business_type, is_annuity, is_protection, created_at, updated_at)
        SELECT id, product_code, product_name, COALESCE(business_type, ''),
               is_annuity, is_protection, created_at, updated_at
        FROM product_config_old
    ''')
    c.execute("DROP TABLE product_config_old")


def _migrate_honor_identity_tracks(c):
    applied = c.execute(
        "SELECT 1 FROM schema_migrations WHERE version = '20260702_honor_identity_tracks'"
    ).fetchone()
    if applied:
        return

    c.execute("ALTER TABLE honor_person_month RENAME TO honor_person_month_old")
    c.execute('''CREATE TABLE honor_person_month (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        org TEXT,
        business_line TEXT,
        staff_code TEXT NOT NULL,
        staff_name TEXT,
        role_type TEXT,
        is_employed_end_month INTEGER DEFAULT 0,
        standard_premium REAL DEFAULT 0,
        longterm_policy_count INTEGER DEFAULT 0,
        monthly_qualified INTEGER DEFAULT 0,
        protected_month INTEGER DEFAULT 0,
        diamond_delta INTEGER DEFAULT 0,
        diamond_balance INTEGER DEFAULT 0,
        membership_level TEXT DEFAULT '未入会',
        is_new_star INTEGER DEFAULT 0,
        exception_flags TEXT DEFAULT '[]',
        UNIQUE(batch_id, year, month, staff_code, business_line, role_type)
    )''')
    c.execute('''
        INSERT OR IGNORE INTO honor_person_month
            (id, batch_id, year, month, org, business_line, staff_code, staff_name,
             role_type, is_employed_end_month, standard_premium, longterm_policy_count,
             monthly_qualified, protected_month, diamond_delta, diamond_balance,
             membership_level, is_new_star, exception_flags)
        SELECT id, batch_id, year, month, org, business_line, staff_code, staff_name,
               role_type, is_employed_end_month, standard_premium, longterm_policy_count,
               monthly_qualified, protected_month, diamond_delta, diamond_balance,
               membership_level, is_new_star, exception_flags
        FROM honor_person_month_old
    ''')
    c.execute("DROP TABLE honor_person_month_old")

    c.execute("ALTER TABLE honor_person_summary RENAME TO honor_person_summary_old")
    c.execute('''CREATE TABLE honor_person_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        latest_month INTEGER NOT NULL,
        org TEXT,
        business_line TEXT,
        staff_code TEXT NOT NULL,
        staff_name TEXT,
        role_type TEXT,
        diamond_balance INTEGER DEFAULT 0,
        membership_level TEXT DEFAULT '未入会',
        total_gain INTEGER DEFAULT 0,
        total_deduct INTEGER DEFAULT 0,
        qualified_months INTEGER DEFAULT 0,
        is_new_star INTEGER DEFAULT 0,
        warning_tags TEXT DEFAULT '[]',
        UNIQUE(batch_id, year, staff_code, business_line, role_type)
    )''')
    c.execute('''
        INSERT OR IGNORE INTO honor_person_summary
            (id, batch_id, year, latest_month, org, business_line, staff_code,
             staff_name, role_type, diamond_balance, membership_level, total_gain,
             total_deduct, qualified_months, is_new_star, warning_tags)
        SELECT id, batch_id, year, latest_month, org, business_line, staff_code,
               staff_name, role_type, diamond_balance, membership_level, total_gain,
               total_deduct, qualified_months, is_new_star, warning_tags
        FROM honor_person_summary_old
    ''')
    c.execute("DROP TABLE honor_person_summary_old")
    c.execute('''
        INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
        VALUES ('20260702_honor_identity_tracks', 0, 'Allows separate personal and management honor tracks')
    ''')


def _migrate_honor_staff_category(c):
    """Separate a person's external position from the personal/management honor track."""
    _migrate(c, "ALTER TABLE honor_source_staff_month ADD COLUMN staff_category TEXT")
    _migrate(c, "ALTER TABLE honor_person_month ADD COLUMN staff_category TEXT")
    _migrate(c, "ALTER TABLE honor_person_summary ADD COLUMN staff_category TEXT")

    c.execute('''
        UPDATE honor_source_staff_month
        SET staff_category = CASE
            WHEN role_type IN ('主管', '经理') THEN '外勤管理职'
            ELSE '专员'
        END
        WHERE staff_category IS NULL OR TRIM(staff_category) = ''
    ''')
    c.execute('''
        UPDATE honor_person_month AS person
        SET staff_category = COALESCE(
            (
                SELECT source.staff_category
                FROM honor_source_staff_month AS source
                WHERE source.batch_id = person.batch_id
                  AND source.year = person.year
                  AND source.month = person.month
                  AND source.staff_code = person.staff_code
                  AND source.business_line = person.business_line
                LIMIT 1
            ),
            CASE WHEN person.role_type IN ('主管', '经理') THEN '外勤管理职' ELSE '专员' END
        )
        WHERE staff_category IS NULL OR TRIM(staff_category) = ''
    ''')
    c.execute('''
        UPDATE honor_person_summary AS person
        SET staff_category = COALESCE(
            (
                SELECT source.staff_category
                FROM honor_source_staff_month AS source
                WHERE source.batch_id = person.batch_id
                  AND source.year = person.year
                  AND source.month = person.latest_month
                  AND source.staff_code = person.staff_code
                  AND source.business_line = person.business_line
                LIMIT 1
            ),
            CASE WHEN person.role_type IN ('主管', '经理') THEN '外勤管理职' ELSE '专员' END
        )
        WHERE staff_category IS NULL OR TRIM(staff_category) = ''
    ''')
    c.execute('''
        INSERT OR IGNORE INTO schema_migrations (version, requires_aggregate_rebuild, note)
        VALUES ('20260817_honor_staff_category', 0, 'Separates external management and specialist positions from honor identity tracks')
    ''')


def _migrate_longterm_qj_daily(c):
    columns = [row[1] for row in c.execute("PRAGMA table_info(agg_longterm_qj)").fetchall()]
    indexes = c.execute("PRAGMA index_list(agg_longterm_qj)").fetchall()
    has_daily_unique = False
    has_monthly_unique = False
    for idx in indexes:
        if not idx[2]:
            continue
        idx_cols = [row[2] for row in c.execute(f"PRAGMA index_info({idx[1]})").fetchall()]
        if idx_cols == ["year", "month", "day", "business_type", "channel", "org"]:
            has_daily_unique = True
        if idx_cols == ["year", "month", "business_type", "channel", "org"]:
            has_monthly_unique = True
    if "day" in columns and has_daily_unique:
        return

    c.execute("ALTER TABLE agg_longterm_qj RENAME TO agg_longterm_qj_old")
    c.execute('''CREATE TABLE agg_longterm_qj (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day INTEGER NOT NULL DEFAULT 1,
        business_type TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT '',
        org TEXT NOT NULL DEFAULT '',
        qj_premium REAL NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(year, month, day, business_type, channel, org))''')
    old_day_expr = "day" if "day" in columns else "1"
    c.execute(f'''
        INSERT OR IGNORE INTO agg_longterm_qj
            (id, year, month, day, business_type, channel, org, qj_premium, created_at)
        SELECT id, year, month, COALESCE({old_day_expr}, 1), business_type,
               COALESCE(channel, ''), COALESCE(org, ''), qj_premium, created_at
        FROM agg_longterm_qj_old
    ''')
    c.execute("DROP TABLE agg_longterm_qj_old")
