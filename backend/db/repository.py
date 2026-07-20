"""通用数据仓库操作：行替换、清空、增量写入。"""
from db.connection import get_db
from db.schema import AGG_TABLES, init_db

_ALLOWED_TABLES = set(AGG_TABLES) | {'performance', 'jingdai', 'hr_data', 'value_data', 'data_imports', 'target_config', 'target_values'}


def _check_table(table: str):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table}")


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def replace_rows(conn, table, rows):
    """INSERT OR REPLACE 批量写入。"""
    if not rows:
        return
    _check_table(table)
    keys = list(rows[0].keys())
    placeholders = ', '.join(['?'] * len(keys))
    columns = ', '.join(_quote_identifier(k) for k in keys)
    sql = f'INSERT OR REPLACE INTO {_quote_identifier(table)} ({columns}) VALUES ({placeholders})'
    conn.executemany(sql, [[row.get(k) for k in keys] for row in rows])


def replace_rows_incremental(conn, table, rows):
    """按月增量写入：先删除本次涉及 (year, month) 的数据，再 INSERT OR REPLACE。

    与 replace_rows 的区别：只删除本次数据覆盖的月份，其他月份不动。
    对同时承载转型/经代的聚合表，按 business_type 缩小删除范围，避免单独重建经代时误删同月转型数据。
    """
    if not rows:
        return
    _check_table(table)
    scoped_tables = {'agg_payment_period', 'agg_payment_period_daily', 'agg_longterm_qj'}
    if table in scoped_tables and all('business_type' in r for r in rows):
        scopes = {
            (int(r['year']), int(r['month']), str(r.get('business_type') or ''))
            for r in rows if 'year' in r and 'month' in r
        }
        for year, month, business_type in scopes:
            conn.execute(
                f'DELETE FROM {_quote_identifier(table)} WHERE year = ? AND month = ? AND business_type = ?',
                (year, month, business_type),
            )
    else:
        months = {(int(r['year']), int(r['month'])) for r in rows if 'year' in r and 'month' in r}
        for year, month in months:
            conn.execute(f'DELETE FROM {_quote_identifier(table)} WHERE year = ? AND month = ?', (year, month))
    replace_rows(conn, table, rows)


def clear_year_data(year: int):
    """删除指定年度在所有聚合表中的数据。"""
    init_db()
    with get_db() as conn:
        c = conn.cursor()
        for table in AGG_TABLES:
            c.execute(f'DELETE FROM {table} WHERE year = ?', (year,))
        conn.commit()


def clear_table_year_data(conn, table: str, year: int):
    """删除指定表指定年度的数据（不提交，由调用方管理事务）。"""
    _check_table(table)
    conn.execute(f'DELETE FROM {_quote_identifier(table)} WHERE year = ?', (year,))
