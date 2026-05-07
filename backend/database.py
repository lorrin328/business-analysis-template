import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'business_data.db')


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # 转型业务业绩
        c.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                channel TEXT,
                qj_premium REAL,
                gm_premium REAL,
                zs_premium REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 经代业务业绩
        c.execute('''
            CREATE TABLE IF NOT EXISTS jingdai (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                qj_premium REAL,
                gm_premium REAL,
                zs_premium REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 人力数据
        c.execute('''
            CREATE TABLE IF NOT EXISTS hr_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                channel TEXT,
                start_headcount INTEGER,
                end_headcount INTEGER,
                active_headcount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 价值数据
        c.execute('''
            CREATE TABLE IF NOT EXISTS value_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                month INTEGER,
                channel TEXT,
                value_premium REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()


def clear_year_data(year: int):
    with get_db() as conn:
        c = conn.cursor()
        for table in ['performance', 'jingdai', 'hr_data', 'value_data']:
            c.execute(f'DELETE FROM {table} WHERE year = ?', (year,))
        conn.commit()


def get_platform_data(year: int):
    with get_db() as conn:
        c = conn.cursor()

        # 转型业务数据
        c.execute('''
            SELECT month, channel, qj_premium, gm_premium, zs_premium
            FROM performance WHERE year = ? ORDER BY month, channel
        ''', (year,))
        perf_rows = c.fetchall()

        # 经代数据
        c.execute('''
            SELECT month, qj_premium, gm_premium, zs_premium
            FROM jingdai WHERE year = ? ORDER BY month
        ''', (year,))
        jingdai_rows = c.fetchall()

        # 人力数据
        c.execute('''
            SELECT month, channel, start_headcount, end_headcount, active_headcount
            FROM hr_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        hr_rows = c.fetchall()

        # 价值数据
        c.execute('''
            SELECT month, channel, value_premium
            FROM value_data WHERE year = ? ORDER BY month, channel
        ''', (year,))
        value_rows = c.fetchall()

        return {
            'performance': [dict(r) for r in perf_rows],
            'jingdai': [dict(r) for r in jingdai_rows],
            'hr': [dict(r) for r in hr_rows],
            'value': [dict(r) for r in value_rows],
        }
