"""Stage a Jingdai-only source refresh while preserving every other data table.

The default command only prints a file manifest. --apply writes a validated
candidate beside an online backup in a caller-selected, non-repository folder.
Publishing that candidate is a separate explicit operation.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def manifest(directory):
    files = sorted(p for p in Path(directory).glob('*.xlsx') if not p.name.startswith('~$') and 'sync-conflict' not in p.name)
    if not files:
        raise ValueError('经代来源目录没有可导入的xlsx文件。')
    return [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': file_sha256(p)} for p in files]


def table_fingerprints(conn, *, exclude=()):
    """Diagnostics contain only table names, row counts and hashes, never rows."""
    result = {}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        if table in exclude:
            continue
        q = '"' + table.replace('"', '""') + '"'
        h, n = hashlib.sha256(), 0
        for row in conn.execute(f'SELECT * FROM {q} ORDER BY rowid'):
            h.update(json.dumps(tuple(row), ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8'))
            h.update(b'\n')
            n += 1
        result[table] = {'rows': n, 'sha256': h.hexdigest()}
    return result


JINGDAI_MUTABLE = {
    'jingdai', 'agg_jingdai', 'agg_jingdai_daily', 'agg_jingdai_policy_daily',
    'agg_product_daily', 'agg_payment_period', 'agg_payment_period_daily',
    'agg_longterm_qj', 'product_config', 'data_imports', 'schema_migrations',
}
SHARED_TABLES = ('agg_product_daily', 'agg_payment_period', 'agg_payment_period_daily', 'agg_longterm_qj')


def retained_fingerprints(conn):
    result = table_fingerprints(conn, exclude=JINGDAI_MUTABLE)
    for table in SHARED_TABLES:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        h, n = hashlib.sha256(), 0
        for row in conn.execute(f'SELECT * FROM "{table}" WHERE business_type!=\'经代\' ORDER BY rowid'):
            h.update(json.dumps(tuple(row), ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8') + b'\n')
            n += 1
        result[table + ':non_jingdai'] = {'rows': n, 'sha256': h.hexdigest()}
    return result


def stage_refresh(database, directory, backup_directory):
    database, directory, output = Path(database).resolve(), Path(directory).resolve(), Path(backup_directory).resolve()
    repo = Path(__file__).resolve().parent.parent
    if output == repo or repo in output.parents:
        raise ValueError('数据库恢复材料必须保存在代码目录之外。')
    if not database.is_file():
        raise ValueError('待迁移数据库不存在。')
    files = manifest(directory)
    output.mkdir(parents=True, exist_ok=False)
    baseline, candidate = output / 'before.db', output / 'candidate.db'
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(baseline) as dest:
        source.backup(dest)
    with sqlite3.connect(baseline) as source, sqlite3.connect(candidate) as dest:
        source.backup(dest)
    os.environ['BUSINESS_ANALYSIS_DB'] = str(candidate)
    # This executable must run in its own process, before the DB modules load.
    from db import connection, get_db, init_db
    if Path(connection.DB_PATH).resolve() != candidate.resolve():
        raise RuntimeError(f'数据库模块绑定路径不匹配：{Path(connection.DB_PATH).resolve()}；候选路径：{candidate.resolve()}。')
    from services.excel_pipeline import ExcelSource, ExcelPipelineResult, build_excel_pipeline_result, replace_aggregate_rows, write_excel_pipeline_result
    from services.aggregate_rebuilder import _read_raw_table_year, _raw_years, build_aggregate_rows_from_raw
    from etl.aggregates.jingdai import _load_jingdai_product_config
    from etl.parser import parse_jingdai_excel
    from services.import_safety import validate_jingdai_detail_years
    from etl.normalize import _year_month_day_from_series, validate_source_numbers
    from services.excel_pipeline import finalize_excel_pipeline_result
    with sqlite3.connect(baseline) as old:
        retained = retained_fingerprints(old)
        old_years = old.execute('SELECT substr("时间",1,4),COUNT(*) FROM jingdai GROUP BY 1').fetchall()
    init_db()
    # Refresh only JD-derived history. Full application rebuilds are unnecessary
    # for the local import and would broaden this source replacement's scope.
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for year in _raw_years(conn, 'jingdai'):
            frame = _read_raw_table_year(conn, 'jingdai', year)
            if frame is not None and not frame.empty:
                rows = build_aggregate_rows_from_raw({'jingdai': frame}, jingdai_config_map=_load_jingdai_product_config(conn))
                replace_aggregate_rows(conn, ExcelPipelineResult(raw_tables={'jingdai': frame}, rows_by_table=rows), incremental=True)
            del frame
        conn.commit()
    imported = []
    excluded_history = []
    # Each non-overlapping file is a complete source partition. A later file
    # containing an already selected month must instead be combined in the Web
    # batch importer; this CLI refuses that ambiguity.
    selected_months = set()
    for item in files:
        path = directory / item['file']
        if file_sha256(path) != item['sha256']:
            raise RuntimeError('源文件在预检后发生变化，已停止候选导入。')
        print(json.dumps({'phase': 'parse', 'file': item['file']}, ensure_ascii=False), flush=True)
        frame = parse_jingdai_excel(path.read_bytes())
        if frame['经代源格式'].eq('policy_detail').all():
            years, _, _ = _year_month_day_from_series(frame['时间'].drop_duplicates())
            if years.notna().all() and years.between(2020, 2024).all():
                excluded_history.append(dict(item, reason='2020—2024年使用原有历史，本次新明细不导入'))
                print(json.dumps({'phase': 'preserve_history_skip', 'file': item['file']}, ensure_ascii=False), flush=True)
                del frame
                gc.collect()
                continue
        validate_jingdai_detail_years(frame)
        validate_source_numbers('jingdai', frame)
        result = finalize_excel_pipeline_result(ExcelPipelineResult(raw_tables={'jingdai': frame}, source_warnings=frame.attrs.get('source_warnings', [])))
        months = {(r['year'], r['month']) for r in result.rows_by_table['agg_jingdai']}
        if selected_months & months:
            raise RuntimeError('本命令的分文件月份有重叠；请用网页同时选择同月全部日期分片。')
        selected_months.update(months)
        with get_db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            counts = write_excel_pipeline_result(conn, result, incremental=True)
            conn.execute("INSERT INTO data_imports(file_name,file_hash,file_size,status,data_years,table_counts) VALUES(?,?,?,'success',?,?)",
                         (item['file'], item['sha256'], item['bytes'], json.dumps(result.data_years), json.dumps(counts)))
            conn.commit()
        imported.append(dict(item, rows=len(frame), periods=sorted(f'{y:04d}-{m:02d}' for y, m in months), warnings=result.cutoff_warnings))
        print(json.dumps({'phase': 'written', 'file': item['file'], 'rows': len(frame)}, ensure_ascii=False), flush=True)
        del result, frame
        gc.collect()
    with get_db() as conn:
        after = retained_fingerprints(conn)
        if retained != {key: after[key] for key in retained}:
            raise RuntimeError('非经代数据摘要发生变化，候选库不得使用。')
        checks = {name: conn.execute('PRAGMA ' + name).fetchone()[0] for name in ('quick_check', 'integrity_check')}
        if any(value != 'ok' for value in checks.values()):
            raise RuntimeError('候选库完整性校验未通过。')
    report = {'baseline': str(baseline), 'candidate': str(candidate), 'database': str(database),
              'baselineSha256': file_sha256(baseline), 'oldYears': old_years,
              'sourceFiles': imported, 'excludedHistoricalFiles': excluded_history, 'retainedTables': retained, 'checks': checks,
              'status': 'candidate_only_not_published'}
    (output / 'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--source-dir', required=True)
    parser.add_argument('--backup-dir')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'files': manifest(args.source_dir), 'status': 'preview_only',
                          'historicalPolicy': '2020—2024年仅保留原数据并转换结构，新投保单号明细仅从2025年起使用'}, ensure_ascii=False, indent=2))
        return
    if not args.backup_dir:
        parser.error('--apply requires --backup-dir outside the repository')
    report = stage_refresh(args.database, args.source_dir, args.backup_dir)
    print(json.dumps({k: v for k, v in report.items() if k not in {'retainedTables', 'sourceFiles'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
