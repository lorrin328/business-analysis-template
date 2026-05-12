"""Repository queries — auto-split from database.py."""
import json
import sqlite3
from datetime import datetime
from db.connection import get_db
from db.schema import init_db


def get_target_config(year: int):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT payload FROM target_config WHERE year = ?', (year,))
        row = c.fetchone()
        if not row:
            return None
        try:
            return json.loads(row['payload'])
        except json.JSONDecodeError:
            return None


def _flatten_target_payload(year: int, payload: dict, updated_by: str = 'system') -> list[dict]:
    rows = []

    def append_row(period_type, period_value, business_line, metric_code, target_value, org=None):
        if target_value is None:
            return
        try:
            value = float(target_value or 0)
        except (TypeError, ValueError):
            value = 0
        rows.append({
            'year': int(year),
            'period_type': period_type,
            'period_value': int(period_value),
            'business_line': business_line,
            'org': org,
            'metric_code': metric_code,
            'target_value': value,
            'updated_by': updated_by,
        })

    categories = (payload or {}).get('categories') or {}
    for metric_code, category in categories.items():
        metrics = (category or {}).get('metrics') or {}
        for business_line, metric in metrics.items():
            append_row('year', 0, business_line, metric_code, metric.get('year') if isinstance(metric, dict) else 0)
            for idx, value in enumerate((metric or {}).get('quarter') or [], start=1):
                append_row('quarter', idx, business_line, metric_code, value)
            for idx, value in enumerate((metric or {}).get('month') or [], start=1):
                append_row('month', idx, business_line, metric_code, value)

    org_targets = (payload or {}).get('orgTargets') or {}
    for org_line_key, metrics in org_targets.items():
        org, business_line = (org_line_key.split('|', 1) + [''])[:2] if '|' in org_line_key else (org_line_key, '')
        for metric_code, metric in (metrics or {}).items():
            append_row('year', 0, business_line, metric_code, metric.get('year') if isinstance(metric, dict) else 0, org)
            for idx, value in enumerate((metric or {}).get('quarter') or [], start=1):
                append_row('quarter', idx, business_line, metric_code, value, org)
            for idx, value in enumerate((metric or {}).get('month') or [], start=1):
                append_row('month', idx, business_line, metric_code, value, org)

    return rows


def save_target_values(conn: sqlite3.Connection, year: int, payload: dict, updated_by: str = 'system'):
    rows = _flatten_target_payload(year, payload, updated_by)
    conn.execute('DELETE FROM target_values WHERE year = ?', (year,))
    if not rows:
        return
    conn.executemany(
        '''
        INSERT INTO target_values (
            year, period_type, period_value, business_line, org, metric_code,
            target_value, updated_by, updated_at
        ) VALUES (
            :year, :period_type, :period_value, :business_line, :org, :metric_code,
            :target_value, :updated_by, CURRENT_TIMESTAMP
        )
        ''',
        rows,
    )


def get_target_values(year: int, period_type: str | None = None, period_value: int | None = None):
    with get_db() as conn:
        sql = 'SELECT * FROM target_values WHERE year = ?'
        params = [year]
        if period_type:
            sql += ' AND period_type = ?'
            params.append(period_type)
        if period_value is not None:
            sql += ' AND period_value = ?'
            params.append(period_value)
        sql += ' ORDER BY metric_code, business_line, org, period_type, period_value'
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def save_target_config(year: int, payload: dict, updated_by: str = 'system'):
    init_db()
    payload = dict(payload)
    payload['year'] = year
    payload['updated_at'] = datetime.now().isoformat(timespec='seconds')
    payload['updated_by'] = updated_by
    with get_db() as conn:
        conn.execute(
            '''
            INSERT INTO target_config (year, payload, updated_at, updated_by)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(year) DO UPDATE SET
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = excluded.updated_by
            ''',
            (year, json.dumps(payload, ensure_ascii=False), updated_by),
        )
        save_target_values(conn, year, payload, updated_by)
        conn.commit()
    return payload
