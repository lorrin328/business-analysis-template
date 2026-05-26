"""Helpers for explicit raw table reads.

Raw Excel tables have Chinese column names that can change by source file. These
helpers keep direct reads defensive and avoid unbounded SELECT * usage in API
paths while preserving the original column names required by ETL functions.
"""
from __future__ import annotations

import pandas as pd


def quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def raw_table_columns(conn, table: str) -> list[str]:
    table_name = quote_identifier(table)
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def read_raw_table_dataframe(conn, table: str) -> pd.DataFrame:
    columns = raw_table_columns(conn, table)
    if not columns:
        return pd.DataFrame()
    select_list = ", ".join(quote_identifier(col) for col in columns)
    return pd.read_sql_query(f"SELECT {select_list} FROM {quote_identifier(table)}", conn)


def read_raw_table_rows(conn, table: str):
    columns = raw_table_columns(conn, table)
    if not columns:
        return []
    select_list = ", ".join(quote_identifier(col) for col in columns)
    return conn.execute(f"SELECT {select_list} FROM {quote_identifier(table)}").fetchall()
