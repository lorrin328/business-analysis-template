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
);
