"""数据库连接管理。"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'business_data.db')


@contextmanager
def get_db():
    """获取数据库连接，自动关闭，行结果以 sqlite3.Row 返回。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
