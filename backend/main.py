import hashlib
import json
import os
import sys
from fastapi import Depends, FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import logging
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))
from api.kpi import router as kpi_router
from api.legacy import router as legacy_router
from api.org import router as org_router
from api.product import router as product_router
from api.targets import router as targets_router
from api.payment_period import router as payment_period_router
from api.team import router as team_router
from api.trend import router as trend_router
from api.config import router as config_router
from api.product_config import router as product_config_router
from api.diagnostics import router as diagnostics_router
from auth import require_admin
from config.business_lines import DEFAULT_YEAR
from db import (
    init_db, get_db, replace_rows_incremental,
)
from etl import (
    parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel,
    aggregate_performance, aggregate_jingdai, aggregate_jingdai_daily, aggregate_hr, aggregate_value,
    aggregate_product_structure, aggregate_active_headcount,
    aggregate_org_performance, aggregate_org_value,
    aggregate_daily_performance, aggregate_org_daily_performance,
    aggregate_payment_period, aggregate_jingdai_payment_period,
    aggregate_transform_longterm, aggregate_jingdai_longterm,
    aggregate_org_hr, aggregate_org_active_headcount,
)

from validators.data_validator import validate_rows
from services.import_safety import RawIncrementalWriteError, write_raw_table_incremental
from services.product_config_service import extract_jingdai_products_to_config, extract_products_to_config


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_skip(conn, file_name: str, file_hash: str) -> bool:
    """检查相同哈希的文件是否已导入过。返回 True 表示可跳过。"""
    row = conn.execute(
        'SELECT id FROM data_imports WHERE file_hash = ? AND status = ? ORDER BY id DESC LIMIT 1',
        (file_hash, 'success'),
    ).fetchone()
    return row is not None


def _record_import(conn, file_name: str, file_hash: str, file_size: int,
                   data_years: list, table_counts: dict, status: str = 'success',
                   error_message: str | None = None):
    conn.execute('''
        INSERT INTO data_imports (file_name, file_hash, file_size, data_years, table_counts, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (file_name, file_hash, file_size, json.dumps(data_years or []),
          json.dumps(table_counts or {}), status, error_message))
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def _skip_duplicate_upload(file_name: str, file_hash: str, label: str, results: dict) -> bool:
    """Return True when the same successful file hash has already been imported."""
    with get_db() as conn:
        if not _check_skip(conn, file_name, file_hash):
            return False
    results["skipped"].append(f"{label}: duplicate file, skipped")
    logger.info("import skipped duplicate file=%s hash=%s", file_name, file_hash)
    return True


class _DuplicateUpload(Exception):
    pass



MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))


def _set_import_status(results: dict, *, has_written_rows: bool):
    has_errors = len(results.get("errors", [])) > 0
    if has_errors and has_written_rows:
        status = "partial"
        message = "Partial import completed; some files failed and current dashboard data may be incomplete."
    elif has_errors:
        status = "failed"
        message = "Import failed; no file was written."
    elif results.get("skipped") and not has_written_rows:
        status = "skipped"
        message = "All selected files were duplicates and no data was written."
    else:
        status = "success"
        message = "Import completed."
    results["status"] = status
    results["data_integrity"] = {
        "complete": status in {"success", "skipped"},
        "status": status,
        "message": message,
        "uploadedCount": len(results.get("uploaded", [])),
        "errorCount": len(results.get("errors", [])),
        "skippedCount": len(results.get("skipped", [])),
    }
    return results

app = FastAPI(title="经营分析看板API")

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("business-analysis")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(os.path.join(LOG_DIR, "app.log"), maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)

# CORS：生产环境不需要（HTML从同一服务提供），开发环境按需配置
# 如需跨域，设置环境变量 CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
_cors_origins = os.getenv("CORS_ORIGINS", "").strip()
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 初始化数据库
init_db()

for router in [kpi_router, trend_router, org_router, team_router, product_router, targets_router, payment_period_router, config_router, product_config_router, diagnostics_router, legacy_router]:
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_files(
    performance: UploadFile = File(None),
    jingdai: UploadFile = File(None),
    hr: UploadFile = File(None),
    value: UploadFile = File(None),
    year: int = DEFAULT_YEAR,
    _admin=Depends(require_admin),
):
    """上传Excel文件并聚合到SQLite"""
    # 单文件最大 20MB
    max_size = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    for f in [performance, jingdai, hr, value]:
        if f and f.size and f.size > max_size:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 {MAX_UPLOAD_SIZE_MB}MB 限制")
    results = {"uploaded": [], "errors": [], "skipped": [], "data_years": set()}
    file_hashes = {}  # file_name -> hash
    file_sizes = {}   # file_name -> size
    table_row_counts = {}  # table -> count
    logger.info("import started year=%s", year)

    # 第一步：解析所有Excel文件，收集实际年份
    perf_rows = []
    daily_rows = []
    org_daily_rows = []
    jd_rows = []
    jd_daily_rows = []
    hr_rows = []
    org_hr_rows = []
    value_rows = []
    product_rows = []
    active_rows = []
    org_active_rows = []
    org_perf_rows = []
    org_value_rows = []
    pay_period_rows = []
    jd_pay_period_rows = []
    longterm_rows = []
    jd_longterm_rows = []
    raw_tables = {}

    if performance and performance.filename:
        try:
            perf_bytes = await performance.read()
            h = _hash_bytes(perf_bytes)
            if _skip_duplicate_upload(performance.filename, h, "performance", results):
                raise _DuplicateUpload()
            file_hashes[performance.filename] = h
            file_sizes[performance.filename] = len(perf_bytes)
            df = parse_performance_excel(perf_bytes)
            raw_tables['performance'] = df
            _extract_products_to_config(df)
            perf_rows = aggregate_performance(df)
            daily_rows = aggregate_daily_performance(df)
            org_daily_rows = aggregate_org_daily_performance(df)
            product_rows = aggregate_product_structure(df)
            active_rows = aggregate_active_headcount(df)
            org_active_rows = aggregate_org_active_headcount(df)
            org_perf_rows = aggregate_org_performance(df)
            pay_period_rows = aggregate_payment_period(df)
            longterm_rows = aggregate_transform_longterm(df)
            validation = validate_rows(perf_rows, required=["year", "month", "channel"], unique_keys=["year", "month", "channel"])
            if not validation.valid:
                raise ValueError(validation.to_dict())
            results["uploaded"].append(f"转型业务业绩: {len(perf_rows)}条")
        except _DuplicateUpload:
            pass
        except Exception as e:
            results["errors"].append(f"转型业务业绩: {str(e)}")
            logger.exception("performance import failed")

    if jingdai and jingdai.filename:
        try:
            jd_bytes = await jingdai.read()
            h = _hash_bytes(jd_bytes)
            if _skip_duplicate_upload(jingdai.filename, h, "jingdai", results):
                raise _DuplicateUpload()
            file_hashes[jingdai.filename] = h
            file_sizes[jingdai.filename] = len(jd_bytes)
            df = parse_jingdai_excel(jd_bytes)
            raw_tables['jingdai'] = df
            extract_jingdai_products_to_config(df)
            jd_rows = aggregate_jingdai(df)
            jd_daily_rows = aggregate_jingdai_daily(df)
            jd_pay_period_rows = aggregate_jingdai_payment_period(df)
            jd_longterm_rows = aggregate_jingdai_longterm(df)
            validation = validate_rows(jd_rows, required=["year", "month"], unique_keys=["year", "month"])
            if not validation.valid:
                raise ValueError(validation.to_dict())
            results["uploaded"].append(f"经代业务业绩: {len(jd_rows)}条")
        except _DuplicateUpload:
            pass
        except Exception as e:
            results["errors"].append(f"经代业务业绩: {str(e)}")
            logger.exception("jingdai import failed")

    if hr and hr.filename:
        try:
            hr_bytes = await hr.read()
            h = _hash_bytes(hr_bytes)
            if _skip_duplicate_upload(hr.filename, h, "hr", results):
                raise _DuplicateUpload()
            file_hashes[hr.filename] = h
            file_sizes[hr.filename] = len(hr_bytes)
            df = parse_hr_excel(hr_bytes)
            raw_tables['hr_data'] = df
            hr_rows = aggregate_hr(df)
            org_hr_rows = aggregate_org_hr(df)
            results["uploaded"].append(f"人力数据: {len(hr_rows)}条")
        except _DuplicateUpload:
            pass
        except Exception as e:
            results["errors"].append(f"人力数据: {str(e)}")
            logger.exception("hr import failed")

    if value and value.filename:
        try:
            val_bytes = await value.read()
            h = _hash_bytes(val_bytes)
            if _skip_duplicate_upload(value.filename, h, "value", results):
                raise _DuplicateUpload()
            file_hashes[value.filename] = h
            file_sizes[value.filename] = len(val_bytes)
            df = parse_value_excel(val_bytes)
            raw_tables['value_data'] = df
            value_rows = aggregate_value(df)
            org_value_rows = aggregate_org_value(df)
            results["uploaded"].append(f"价值数据: {len(value_rows)}条")
        except _DuplicateUpload:
            pass
        except Exception as e:
            results["errors"].append(f"价值数据: {str(e)}")
            logger.exception("value import failed")

    if hr_rows and active_rows:
        active_index = {
            (r['year'], r['month'], r['channel']): r['active_headcount']
            for r in active_rows
        }
        for row in hr_rows:
            row['active_headcount'] = active_index.get((row['year'], row['month'], row['channel']), 0)

    if org_hr_rows and org_active_rows:
        org_active_index = {
            (r['year'], r['month'], r['org'], r['channel']): r['active_headcount']
            for r in org_active_rows
        }
        for row in org_hr_rows:
            row['active_headcount'] = org_active_index.get((row['year'], row['month'], row['org'], row['channel']), 0)

    # 收集所有实际年份
    for rows in [perf_rows, daily_rows, org_daily_rows, jd_rows, jd_daily_rows, hr_rows, value_rows, product_rows, org_perf_rows, org_value_rows, org_hr_rows]:
        for r in rows:
            if 'year' in r and r['year']:
                results["data_years"].add(int(r['year']))

    # 如果没有检测到年份，使用传入的year参数
    results["data_years"] = sorted(list(results["data_years"])) if results["data_years"] else [year]

    if not file_hashes and not results["errors"]:
        logger.info("import finished with duplicates only skipped=%s years=%s", len(results["skipped"]), results["data_years"])
        results["import_id"] = None
        return _set_import_status(results, has_written_rows=False)

    if results["errors"] and not file_hashes:
        _set_import_status(results, has_written_rows=False)
        raise HTTPException(status_code=400, detail=results)

    # 写入数据库（增量：按月删除再插入，未涉及月份保持不动）
    import_id = None
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            table_rows = [
                ('agg_performance', perf_rows),
                ('agg_daily_performance', daily_rows),
                ('agg_org_daily_performance', org_daily_rows),
                ('agg_product_structure', product_rows),
                ('agg_jingdai', jd_rows),
                ('agg_jingdai_daily', jd_daily_rows),
                ('agg_hr_data', hr_rows),
                ('agg_org_hr_data', org_hr_rows),
                ('agg_value_data', value_rows),
                ('agg_org_performance', org_perf_rows),
                ('agg_org_value', org_value_rows),
                ('agg_payment_period', pay_period_rows + jd_pay_period_rows),
                ('agg_longterm_qj', longterm_rows + jd_longterm_rows),
            ]
            for table, rows in table_rows:
                if rows:
                    replace_rows_incremental(conn, table, rows)
                    table_row_counts[table] = len(rows)
            for table, df in raw_tables.items():
                write_raw_table_incremental(conn, table, df)
                table_row_counts[table] = len(df)

            # 记录导入历史
            has_errors = len(results["errors"]) > 0
            for fname, h in file_hashes.items():
                _record_import(conn, fname, h, file_sizes.get(fname, 0),
                               results["data_years"], table_row_counts,
                               status='partial' if has_errors else 'success')
            import_id = conn.execute('SELECT MAX(id) FROM data_imports').fetchone()[0]

            conn.commit()
        except RawIncrementalWriteError as e:
            conn.rollback()
            results["errors"].append(str(e))
            _set_import_status(results, has_written_rows=False)
            raise HTTPException(status_code=400, detail=results) from e
        except Exception:
            conn.rollback()
            raise

    logger.info("import finished uploaded=%s errors=%s skipped=%s years=%s import_id=%s",
                len(results["uploaded"]), len(results["errors"]), len(results["skipped"]),
                results["data_years"], import_id)
    results["import_id"] = import_id
    results["data_years"] = sorted(list(results["data_years"])) if results["data_years"] else [year]
    return _set_import_status(results, has_written_rows=bool(file_hashes))


@app.post("/api/import")
async def import_files(
    performance: UploadFile = File(None),
    jingdai: UploadFile = File(None),
    hr: UploadFile = File(None),
    value: UploadFile = File(None),
    year: int = DEFAULT_YEAR,
    _admin=Depends(require_admin),
):
    return await upload_files(performance=performance, jingdai=jingdai, hr=hr, value=value, year=year)


# 静态文件服务 - 生产HTML
static_dir = os.path.join(os.path.dirname(__file__), '..')
if os.path.exists(os.path.join(static_dir, '经营分析模板.html')):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    js_dir = os.path.join(static_dir, 'js')
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, '经营分析模板.html'))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "45679")))
