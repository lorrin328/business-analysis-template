"""Import safety helpers for raw detail table writes."""
from __future__ import annotations

from etl.columns import _pick_col
from etl.normalize import _period_year_month

KNOWN_RAW_TABLES = {'performance', 'jingdai', 'hr_data', 'value_data'}


class RawIncrementalWriteError(ValueError):
    """Raised when a raw table cannot be updated safely by period."""


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def raw_period_config(table: str, df):
    if table == 'performance':
        return (
            _pick_col(df, ['年']),
            _pick_col(df, ['年月', '月', '月份']),
            _pick_col(df, ['年月日', '入账时间', '日期', '出单日期', '投保日期', '承保日期']),
        )
    if table == 'jingdai':
        return (
            None,
            _pick_col(df, ['时间', '年月']),
            _pick_col(df, ['年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期']),
        )
    if table == 'hr_data':
        return (
            _pick_col(df, ['统计年', '年']),
            _pick_col(df, ['统计日期', '年月', '统计月', '月']),
            None,
        )
    if table == 'value_data':
        return None, _pick_col(df, ['年月', '时间']), None
    return None, None, None


def extract_raw_periods(table: str, df) -> tuple[set[tuple[int, int]], tuple[str | None, str | None, str | None]]:
    year_col, month_col, date_col = raw_period_config(table, df)
    if not (month_col or date_col):
        return set(), (year_col, month_col, date_col)
    work = _period_year_month(df, year_col, month_col if not date_col else None, date_col)
    periods = {
        (int(row['_year']), int(row['_month']))
        for _, row in work[['_year', '_month']].dropna().drop_duplicates().iterrows()
    }
    return periods, (year_col, month_col, date_col)


def table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info({quote_identifier(table)})').fetchall()
    return {row[1] for row in rows}


def delete_raw_period(conn, table: str, year: int, month: int, cols: tuple[str | None, str | None, str | None]):
    year_col, month_col, date_col = cols
    if date_col:
        compact = f"{year:04d}{month:02d}"
        col = quote_identifier(date_col)
        conn.execute(
            f'''
            DELETE FROM {quote_identifier(table)}
            WHERE substr(replace(replace(CAST({col} AS TEXT), '-', ''), '/', ''), 1, 6) = ?
            ''',
            (compact,),
        )
        return
    if year_col and month_col:
        conn.execute(
            f'''
            DELETE FROM {quote_identifier(table)}
            WHERE CAST({quote_identifier(year_col)} AS INTEGER) = ?
              AND (
                CAST({quote_identifier(month_col)} AS INTEGER) = ?
                OR substr(replace(replace(CAST({quote_identifier(month_col)} AS TEXT), '-', ''), '/', ''), 1, 6) = ?
              )
            ''',
            (year, month, f"{year:04d}{month:02d}"),
        )
        return
    if month_col:
        compact = f"{year:04d}{month:02d}"
        conn.execute(
            f'''
            DELETE FROM {quote_identifier(table)}
            WHERE substr(replace(replace(CAST({quote_identifier(month_col)} AS TEXT), '-', ''), '/', ''), 1, 6) = ?
            ''',
            (compact,),
        )


def write_raw_table_incremental(conn, table: str, df):
    """Append raw rows after deleting the same periods when the existing schema matches."""
    if df is None or df.empty:
        return
    existing_cols = table_columns(conn, table)
    df_cols = set(map(str, df.columns))
    periods, period_cols = extract_raw_periods(table, df)
    if not existing_cols:
        df.to_sql(table, conn, if_exists='replace', index=False)
        return
    if not df_cols.issubset(existing_cols):
        missing = sorted(df_cols - existing_cols)
        raise RawIncrementalWriteError(
            f"raw table {table} schema mismatch; new columns require an explicit full rebuild: {missing}"
        )
    if table in KNOWN_RAW_TABLES and not periods:
        raise RawIncrementalWriteError(
            f"raw table {table} has no recognizable year/month period; import aborted to avoid replacing history"
        )
    if not periods:
        raise RawIncrementalWriteError(
            f"raw table {table} has no recognizable year/month period"
        )
    for year, month in periods:
        delete_raw_period(conn, table, year, month, period_cols)
    df.to_sql(table, conn, if_exists='append', index=False)
