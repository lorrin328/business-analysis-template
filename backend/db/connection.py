"""数据库连接管理。"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv(
    "BUSINESS_ANALYSIS_DB",
    os.path.join(os.path.dirname(__file__), '..', 'business_data.db'),
)


@contextmanager
def get_db():
    """获取数据库连接，自动关闭，行结果以 sqlite3.Row 返回。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    try:
        yield conn
    finally:
        conn.close()
