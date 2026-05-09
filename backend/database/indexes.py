INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_perf_year_month_channel ON agg_performance(year, month, channel)",
    "CREATE INDEX IF NOT EXISTS ix_jd_year_month ON agg_jingdai(year, month)",
    "CREATE INDEX IF NOT EXISTS ix_daily_year_month_day_channel ON agg_daily_performance(year, month, day, channel)",
    "CREATE INDEX IF NOT EXISTS ix_org_perf_year_month_org_channel ON agg_org_performance(year, month, org, channel)",
    "CREATE INDEX IF NOT EXISTS ix_target_values_year_period ON target_values(year, period_type, period_value)",
    "CREATE INDEX IF NOT EXISTS ix_target_values_line_org_metric ON target_values(business_line, org, metric_code)",
]


def ensure_indexes(conn) -> None:
    for sql in INDEX_SQL:
        conn.execute(sql)
