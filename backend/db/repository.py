"""通用数据仓库操作：行替换、清空、增量写入。"""
from db.connection import get_db
from db.schema import AGG_TABLES, init_db


def replace_rows(conn, table, rows):
    """INSERT OR REPLACE 批量写入。"""
    if not rows:
        return
    keys = list(rows[0].keys())
    placeholders = ', '.join(['?'] * len(keys))
    columns = ', '.join(keys)
    sql = f'INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})'
    conn.executemany(sql, [[row.get(k) for k in keys] for row in rows])


def replace_rows_incremental(conn, table, rows):
    """按月增量写入：先删除本次涉及 (year, month) 的数据，再 INSERT OR REPLACE。

    与 replace_rows 的区别：只删除本次数据覆盖的月份，其他月份不动。
    """
    if not rows:
        return
    months = {(int(r['year']), int(r['month'])) for r in rows if 'year' in r and 'month' in r}
    for year, month in months:
        conn.execute(f'DELETE FROM {table} WHERE year = ? AND month = ?', (year, month))
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
    conn.execute(f'DELETE FROM {table} WHERE year = ?', (year,))
