"""Lossless schema expansion for existing Jingdai sources.

Historical aggregate rows retain source counts and never acquire invented policy
numbers. The caller owns the transaction and the one-time migration record.
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path
import sqlite3

from etl.normalize import _to_number, NumericSourceError
from services.raw_table_reader import quote_identifier


JINGDAI_SOURCE_COLUMNS = {
    '统计时间_年月日': 'TEXT', '销售平台': 'TEXT', '投保单号': 'TEXT',
    '产品代码': 'TEXT', '产品名称': 'TEXT', '产品销售名称': 'TEXT',
    '长短险': 'TEXT', '缴别': 'TEXT', '缴费年限': 'REAL',
    '是否社会保障类产品': 'TEXT', '是否商保年金产品': 'TEXT',
    '是否个人养老金': 'TEXT', '期交保费': 'REAL', '年化规保': 'REAL',
    '承保件数': 'INTEGER', '件数来源': 'TEXT', '经代源格式': 'TEXT',
    '时间': 'TEXT', '经代机构': 'TEXT', '承保年化规保': 'REAL',
}


def _present(column):
    return f"NULLIF(TRIM(CAST({quote_identifier(column)} AS TEXT)), '') IS NOT NULL"


def migrate_jingdai_history(conn):
    """Add missing fields, copy only proven aliases, preserve all source events."""
    existing = {r[1] for r in conn.execute('PRAGMA table_info(jingdai)')}
    if not existing:
        return {'rows': 0, 'legacyRows': 0, 'addedColumns': []}
    count_aliases = [c for c in ('承保件数', '承保保单件数', '承保产品件数') if c in existing]
    # Validate old source counts before any schema/data mutation. Source values
    # never appear in the exception or migration report.
    if count_aliases:
        projection = ','.join(map(quote_identifier, count_aliases))
        for frame in pd.read_sql_query(f'SELECT {projection} FROM jingdai', conn, chunksize=50000):
            parsed, present = [], []
            for column in count_aliases:
                values = _to_number(frame[column])
                if (values % 1 != 0).any():
                    raise NumericSourceError('历史经代承保件数存在非整数，已停止迁移。')
                parsed.append(values)
                present.append(frame[column].notna() & frame[column].astype('string').str.strip().ne(''))
            for i in range(len(count_aliases)):
                for j in range(i):
                    if (present[i] & present[j] & parsed[i].ne(parsed[j])).any():
                        raise NumericSourceError('历史经代件数别名存在冲突，已停止迁移。')

    before = conn.execute('SELECT COUNT(*) FROM jingdai').fetchone()[0]
    added = []
    for column, kind in JINGDAI_SOURCE_COLUMNS.items():
        if column not in existing:
            conn.execute(f'ALTER TABLE jingdai ADD COLUMN {quote_identifier(column)} {kind}')
            added.append(column)
    conn.execute("UPDATE jingdai SET 经代源格式='legacy_aggregate' WHERE NULLIF(TRIM(经代源格式),'') IS NULL")
    # Map both directions so the canonical source and legacy ETL aliases can be
    # read together, without changing any non-empty original source field.
    for target, source in (
        ('统计时间_年月日', '时间'), ('时间', '统计时间_年月日'),
        ('销售平台', '经代机构'), ('经代机构', '销售平台'),
        ('年化规保', '承保年化规保'), ('承保年化规保', '年化规保'),
    ):
        conn.execute(f'UPDATE jingdai SET {quote_identifier(target)}={quote_identifier(source)} '
                     f'WHERE NOT ({_present(target)}) AND {_present(source)}')
    if '当前缴别小类' in existing:
        # These are frequency labels from the original source, not pay years.
        conn.execute(f'UPDATE jingdai SET 缴别="当前缴别小类" WHERE NOT ({_present("缴别")}) AND {_present("当前缴别小类")}')
    for alias in count_aliases:
        if alias != '承保件数':
            conn.execute(f'UPDATE jingdai SET 承保件数={quote_identifier(alias)} '
                         f'WHERE 经代源格式=\'legacy_aggregate\' AND NOT ({_present("承保件数")}) AND {_present(alias)}')
    conn.execute("UPDATE jingdai SET 件数来源='source_net' WHERE 经代源格式='legacy_aggregate' AND NULLIF(TRIM(件数来源),'') IS NULL")
    after = conn.execute('SELECT COUNT(*) FROM jingdai').fetchone()[0]
    if before != after:
        raise RuntimeError('历史经代迁移行数不一致，已停止。')
    legacy = conn.execute("SELECT COUNT(*) FROM jingdai WHERE 经代源格式='legacy_aggregate'").fetchone()[0]
    return {'rows': after, 'legacyRows': legacy, 'addedColumns': added}


def restore_jingdai_history(conn, baseline, *, last_year=2024):
    """Restore only the authorized JD history partition from a known snapshot.

    The caller must first back up the current database and own the transaction.
    Original business values and existing aggregate rows are kept exactly; no
    policy identities or source rows are reconstructed from aggregate totals.
    """
    if last_year != 2024:
        raise ValueError('本次历史恢复范围固定为2020—2024年。')
    tables = ('jingdai', 'agg_jingdai', 'agg_jingdai_daily', 'agg_jingdai_policy_daily',
              'agg_product_daily', 'agg_payment_period', 'agg_payment_period_daily', 'agg_longterm_qj')
    counts = {}
    with sqlite3.connect(Path(baseline).resolve().as_uri() + '?mode=ro', uri=True) as original:
        for table in tables:
            current_cols = {r[1] for r in conn.execute(f'PRAGMA table_info({quote_identifier(table)})')}
            if not current_cols:
                continue
            period = 'CAST(substr("时间",1,4) AS INTEGER)' if table == 'jingdai' else 'year'
            where = f'{period} BETWEEN 2020 AND 2024'
            if 'business_type' in current_cols:
                where += " AND business_type='经代'"
            source_cols = [r[1] for r in original.execute(f'PRAGMA table_info({quote_identifier(table)})')]
            missing = set(source_cols) - current_cols
            if missing:
                raise RuntimeError('恢复副本存在目标库未识别的历史字段，已停止。')
            conn.execute(f'DELETE FROM {quote_identifier(table)} WHERE {where}')
            if not source_cols:
                counts[table] = 0
                continue
            names = ','.join(map(quote_identifier, source_cols))
            marks = ','.join('?' for _ in source_cols)
            records = original.execute(f'SELECT {names} FROM {quote_identifier(table)} WHERE {where} ORDER BY rowid')
            conn.executemany(f'INSERT INTO {quote_identifier(table)} ({names}) VALUES ({marks})', records)
            counts[table] = conn.execute(f'SELECT COUNT(*) FROM {quote_identifier(table)} WHERE {where}').fetchone()[0]
            if counts[table] != original.execute(f'SELECT COUNT(*) FROM {quote_identifier(table)} WHERE {where}').fetchone()[0]:
                raise RuntimeError('历史恢复行数未对齐，已停止。')
        migrate_jingdai_history(conn)
    return counts
