"""Import safety helpers for raw detail table writes."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from etl.columns import _pick_col
from etl.normalize import _normalize_channel, _period_year_month
from services.customer_fact_refresh import policy_key
from services.raw_table_reader import compact_period_expr, quote_identifier

KNOWN_RAW_TABLES = {'performance', 'jingdai', 'hr_data', 'value_data'}
IMPORT_MODES = {'replace_months', 'supplement'}
BUSINESS_FIELDS = {
    'performance': {'投保单号', '投保人id', '是否职拓', '职拓标识', '是否职域', '承保件数',
                    '年月日', '入账时间', '业务模式', '销售机构名称', '人员工号', '产品代码',
                    '产品名称', '产品类型', '长短险', '缴费年限', '期交保费', '年化规保',
                    '折算保费', '价值规保', '是否商保年金产品', '是否社会保障型产品',
                    '是否个人养老金', '证券方营业网点名称', '证券方销售人员工号',
                    '主管工号', '经理工号', '营业组', '营业部', '自保件标记', '是否企划口径',
                    '承保时间', '回销时间', '犹豫期退保时间'},
    'jingdai': {'时间', '年月日', '产品名称', '期交保费', '承保年化规保', '年化规保', '缴费年限'},
    'hr_data': {'统计日期', '人员工号', '业务模式名称', '销售机构名称', '月初在职人力', '月末在职人力'},
    'value_data': {'年月', '业务模式名称', '销售机构名称', '价值', '价值保费'},
}


class RawIncrementalWriteError(ValueError):
    """Raised when a raw table cannot be updated safely by period."""


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


def ensure_table_columns(conn, table: str, columns: list[str]):
    """Add missing raw-table columns before appending newer Excel layouts.

    Raw Excel files occasionally add columns. These columns are not used by the
    aggregate formulas immediately, but aborting the whole import leaves the
    dashboard on stale data. Adding them as TEXT preserves old raw history and
    lets the current import refresh aggregates safely.
    """
    existing = table_columns(conn, table)
    for column in columns:
        if column in existing:
            continue
        conn.execute(
            f'ALTER TABLE {quote_identifier(table)} ADD COLUMN {quote_identifier(column)} TEXT'
        )
        existing.add(column)


def delete_raw_period(conn, table: str, year: int, month: int, cols: tuple[str | None, str | None, str | None]):
    where, params = raw_period_predicate(year, month, cols)
    conn.execute(f'DELETE FROM {quote_identifier(table)} WHERE {where}', params)


def raw_period_predicate(year: int, month: int, cols: tuple[str | None, str | None, str | None]):
    year_col, month_col, date_col = cols
    if date_col:
        compact = f"{year:04d}{month:02d}"
        expr = compact_period_expr(date_col)
        return f'substr({expr}, 1, 6) = ?', (compact,)
    if year_col and month_col:
        month_expr = compact_period_expr(month_col)
        return (f'''CAST({quote_identifier(year_col)} AS INTEGER) = ?
              AND (
                CAST({quote_identifier(month_col)} AS INTEGER) = ?
                OR substr({month_expr}, 1, 6) = ?
              )''', (year, month, f"{year:04d}{month:02d}"))
    if month_col:
        compact = f"{year:04d}{month:02d}"
        expr = compact_period_expr(month_col)
        return f'substr({expr}, 1, 6) = ?', (compact,)
    raise RawIncrementalWriteError('现有数据没有可识别的期间字段，不能安全替换历史')


def read_raw_periods(conn, table: str, periods: set[tuple[int, int]]) -> pd.DataFrame:
    columns = table_columns(conn, table)
    if not columns or not periods:
        return pd.DataFrame(columns=sorted(columns))
    config = raw_period_config(table, pd.DataFrame(columns=sorted(columns)))
    clauses, params = [], []
    for year, month in sorted(periods):
        clause, values = raw_period_predicate(year, month, config)
        clauses.append(f'({clause})')
        params.extend(values)
    select = ','.join(quote_identifier(column) for column in sorted(columns))
    return pd.read_sql_query(f'SELECT {select} FROM {quote_identifier(table)} WHERE {" OR ".join(clauses)}', conn, params=params)


def validate_replacement_fields(conn, table: str, df) -> None:
    """Fail before any writes when a complete monthly extract loses enabled fields."""
    existing = table_columns(conn, table)
    missing = sorted((BUSINESS_FIELDS.get(table, set()) & existing) - set(df.columns))
    if not missing or df.empty:
        return
    periods, _ = extract_raw_periods(table, df)
    config = raw_period_config(table, pd.DataFrame(columns=sorted(existing)))
    for year, month in sorted(periods):
        where, params = raw_period_predicate(year, month, config)
        for column in missing:
            enabled = conn.execute(
                f'SELECT 1 FROM {quote_identifier(table)} WHERE ({where}) AND '
                f'TRIM(COALESCE(CAST({quote_identifier(column)} AS TEXT),\'\'))<>\'\' LIMIT 1', params,
            ).fetchone()
            if enabled:
                raise RawIncrementalWriteError(
                    f'{year}年{month}月完整替换缺少已有业务字段“{column}”，已停止导入并保留原数据。'
                    '请使用字段完整的月度源；仅补充缺失保单时，请明确选择补充模式。'
                )


def _db_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    return value.item() if hasattr(value, 'item') else value


def append_raw_frame(conn, table: str, df) -> None:
    """Native SQLite writes keep the caller's transaction (pandas.to_sql commits)."""
    columns = list(map(str, df.columns))
    existing = table_columns(conn, table)
    if not existing:
        definitions = []
        for column in columns:
            dtype = df[column].dtype
            kind = 'INTEGER' if pd.api.types.is_integer_dtype(dtype) else 'REAL' if pd.api.types.is_numeric_dtype(dtype) else 'TEXT'
            definitions.append(f'{quote_identifier(column)} {kind}')
        conn.execute(f'CREATE TABLE {quote_identifier(table)} ({",".join(definitions)})')
    else:
        ensure_table_columns(conn, table, columns)
    # Missing source fields must stay unknown instead of acquiring DEFAULT 0.
    # Real source zeroes still remain protected by replacement validation.
    missing = sorted(existing - set(columns))
    columns.extend(missing)
    names = ','.join(map(quote_identifier, columns))
    placeholders = ','.join('?' for _ in columns)
    conn.executemany(f'INSERT INTO {quote_identifier(table)} ({names}) VALUES ({placeholders})',
                     (tuple(_db_value(value) for value in row) + (None,) * len(missing)
                      for row in df.itertuples(index=False, name=None)))


def _comparison(value, column):
    if pd.isna(value):
        return ''
    text = str(_db_value(value)).strip()
    if column in {'期交保费', '年化规保', '折算保费', '价值规保', '承保件数', '缴费年限', '年'}:
        try:
            return str(Decimal(text).normalize())
        except InvalidOperation:
            pass
    return text


def _supplement_groups(frame, compare_columns):
    year_col, month_col, date_col = raw_period_config('performance', frame)
    if not {'投保单号', '业务模式'}.issubset(frame.columns):
        raise RawIncrementalWriteError('补充模式要求业绩期间、业务模式和投保单号作为稳定业务键')
    work = _period_year_month(frame, year_col, month_col if not date_col else None, date_col)
    if len(work) != len(frame):
        raise RawIncrementalWriteError('补充模式存在不可识别的业绩期间，已停止导入')
    groups = {}
    raw_identifiers = {}
    for index, row in work.iterrows():
        if pd.isna(row['投保单号']) or pd.isna(row['业务模式']):
            raise RawIncrementalWriteError('补充模式存在空保单号或业务模式，已停止导入')
        key = (int(row['_year']), int(row['_month']), _normalize_channel(row['业务模式']), policy_key(row['投保单号']))
        if not key[2] or not key[3]:
            raise RawIncrementalWriteError('补充模式存在空保单号或业务模式，已停止导入')
        identifiers = raw_identifiers.setdefault(key[3], set())
        identifiers.add(str(row['投保单号']).strip())
        if len(identifiers) > 1:
            raise RawIncrementalWriteError('补充模式存在一对多保单编号映射，已停止导入；请核对保单编号')
        values = []
        for column in compare_columns:
            if column == '投保单号':
                value = key[3]
            elif column == '业务模式':
                value = key[2]
            elif column in {'年月', '年'}:
                value = str(key[:2])
            else:
                value = _comparison(row.get(column), column)
            values.append(value)
        indexes, counter = groups.setdefault(key, ([], Counter()))
        indexes.append(index)
        counter[tuple(values)] += 1
    return groups


def prepare_supplement(conn, table: str, df) -> pd.DataFrame:
    if table != 'performance':
        raise RawIncrementalWriteError('补充模式仅用于具有稳定保单业务键的业绩源，其他源请使用完整月替换')
    periods, _ = extract_raw_periods(table, df)
    old = read_raw_periods(conn, table, periods)
    compare_columns = list(map(str, df.columns))
    incoming = _supplement_groups(df, compare_columns)
    existing = _supplement_groups(old, compare_columns) if not old.empty else {}
    indexes = []
    for key, (row_indexes, rows) in incoming.items():
        if key in existing:
            if rows != existing[key][1]:
                raise RawIncrementalWriteError('补充模式发现已存在业务键的内容或记录数不一致，已停止整批导入；请核对后使用完整月替换')
        else:
            indexes.extend(row_indexes)
    return df.loc[indexes].copy()


def write_raw_table_incremental(conn, table: str, df, *, mode: str = 'replace_months'):
    """Append raw rows after deleting the same periods when the existing schema matches."""
    if mode not in IMPORT_MODES:
        raise RawIncrementalWriteError('导入模式仅支持完整月替换或明确的补充模式')
    if df is None or df.empty:
        return 0
    existing_cols = table_columns(conn, table)
    periods, period_cols = extract_raw_periods(table, df)
    if table in KNOWN_RAW_TABLES and not periods:
        raise RawIncrementalWriteError(
            f"raw table {table} has no recognizable year/month period; import aborted to avoid replacing history"
        )
    if not periods:
        raise RawIncrementalWriteError(
            f"raw table {table} has no recognizable year/month period"
        )
    if mode == 'replace_months':
        validate_replacement_fields(conn, table, df)
        selected = df
    else:
        selected = prepare_supplement(conn, table, df)
    if not conn.in_transaction:
        conn.execute('BEGIN')
    conn.execute('SAVEPOINT raw_incremental_write')
    try:
        if mode == 'replace_months' and existing_cols:
            existing_period_cols = raw_period_config(table, pd.DataFrame(columns=sorted(existing_cols)))
            for year, month in periods:
                delete_raw_period(conn, table, year, month, existing_period_cols)
        append_raw_frame(conn, table, selected)
        conn.execute('RELEASE SAVEPOINT raw_incremental_write')
        return len(selected)
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT raw_incremental_write')
        conn.execute('RELEASE SAVEPOINT raw_incremental_write')
        raise
