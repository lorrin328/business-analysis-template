import hashlib
import json
import os
import sys
from fastapi import Depends, FastAPI, File, Query, Request, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
from api.export import router as export_router
from api.auth_routes import admin_router, router as auth_router
from api.honor import router as honor_router
from api.scheme import router as scheme_router
from api.ai import router as ai_router
from auth import get_current_user, require_permission
from config.business_lines import DEFAULT_YEAR
from db import (
    init_db, get_db,
)

from services.excel_pipeline import (
    ExcelSource,
    ExcelPipelineResult,
    append_excel_source,
    finalize_excel_pipeline_result,
    validate_daily_cutoff_alignment as _validate_daily_cutoff_alignment,
    write_excel_pipeline_result,
)
from services.import_safety import RawIncrementalWriteError
from services.health_check import run_health_check
from services.operation_lock import OperationLockError, operation_lock
from services.product_config_service import purge_non_jingdai_product_config
from services.audit_log import log_operation


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


def _skip_duplicate_upload(file_name: str, file_hash: str, label: str, results: dict, *, force: bool = False) -> bool:
    """Return True when the same successful file hash has already been imported."""
    if force:
        logger.info("import duplicate check bypassed by force=true file=%s hash=%s", file_name, file_hash)
        return False
    with get_db() as conn:
        if not _check_skip(conn, file_name, file_hash):
            return False
    results["skipped"].append(f"{label}: duplicate file, skipped")
    logger.info("import skipped duplicate file=%s hash=%s", file_name, file_hash)
    return True


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

for router in [auth_router, admin_router, kpi_router, trend_router, org_router, team_router, product_router, targets_router, payment_period_router, config_router, product_config_router, diagnostics_router, export_router, honor_router, scheme_router, ai_router, legacy_router]:
    app.include_router(router)


@app.middleware("http")
async def require_login_for_api(request: Request, call_next):
    public_prefixes = ("/api/auth/", "/api/health", "/api/ai/")
    if request.url.path.startswith("/api/") and not request.url.path.startswith(public_prefixes):
        try:
            get_current_user(request.headers.get("authorization"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/api/health")
def health():
    return run_health_check()


@app.post("/api/upload")
async def upload_files(
    performance: UploadFile = File(None),
    jingdai: UploadFile = File(None),
    hr: UploadFile = File(None),
    value: UploadFile = File(None),
    year: int = DEFAULT_YEAR,
    allow_partial: bool = Query(False),
    force: bool = Query(False),
    _user=Depends(require_permission("upload")),
):
    """上传Excel文件并聚合到SQLite"""
    try:
        with operation_lock("excel-import", timeout=1.0):
            result = await _upload_files_locked(performance, jingdai, hr, value, year, allow_partial, force)
    except OperationLockError as exc:
        log_operation("import_report", user=_user, status="failed", detail={"reason": "operation_locked"})
        raise HTTPException(status_code=409, detail="已有导入或重建任务正在执行，请稍后再试。") from exc
    except HTTPException as exc:
        log_operation("import_report", user=_user, status="failed", detail={"year": year, "detail": exc.detail})
        raise

    log_operation(
        "import_report",
        user=_user,
        status=result.get("status", "success"),
        detail={
            "year": year,
            "force": result.get("force"),
            "import_id": result.get("import_id"),
            "uploaded": result.get("uploaded", []),
            "errors": result.get("errors", []),
            "skipped": result.get("skipped", []),
            "data_years": result.get("data_years", []),
        },
    )
    return result


async def _upload_files_locked(
    performance: UploadFile = File(None),
    jingdai: UploadFile = File(None),
    hr: UploadFile = File(None),
    value: UploadFile = File(None),
    year: int = DEFAULT_YEAR,
    allow_partial: bool = Query(False),
    force: bool = Query(False),
):
    """上传Excel文件并聚合到SQLite。调用方必须先获得 operation_lock。"""
    # 单文件最大 20MB
    max_size = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    for f in [performance, jingdai, hr, value]:
        if f and f.size and f.size > max_size:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 {MAX_UPLOAD_SIZE_MB}MB 限制")
    results = {"uploaded": [], "errors": [], "skipped": [], "data_years": set()}
    results["force"] = bool(force)
    file_hashes = {}  # file_name -> hash
    file_sizes = {}   # file_name -> size
    pipeline_result = ExcelPipelineResult()
    logger.info("import started year=%s force=%s", year, force)
    with get_db() as conn:
        purged = purge_non_jingdai_product_config(conn)
        conn.commit()
        if purged:
            logger.info("purged %s non-jingdai product_config rows before import", purged)

    upload_specs = [
        ("performance", "转型业务业绩", performance),
        ("jingdai", "经代业务业绩", jingdai),
        ("hr", "人力数据", hr),
        ("value", "价值数据", value),
    ]
    upload_labels = {kind: label for kind, label, _ in upload_specs}
    for kind, label, upload in upload_specs:
        if not upload or not upload.filename:
            continue
        try:
            content = await upload.read()
            file_hash = _hash_bytes(content)
            if _skip_duplicate_upload(upload.filename, file_hash, kind, results, force=force):
                continue
            source = ExcelSource(kind=kind, filename=upload.filename, content=content)
            append_excel_source(pipeline_result, source)
            file_hashes[upload.filename] = file_hash
            file_sizes[upload.filename] = len(content)
        except Exception as e:
            results["errors"].append(f"{label}: {str(e)}")
            logger.exception("%s import failed", kind)

    if file_hashes:
        try:
            finalize_excel_pipeline_result(pipeline_result)
            results["uploaded"].extend(pipeline_result.source_summaries)
            results["data_years"] = pipeline_result.data_years or [year]
            if pipeline_result.cutoff_warnings:
                results["cutoff_warnings"] = pipeline_result.cutoff_warnings
                logger.info("daily cutoff alignment warnings: %s", pipeline_result.cutoff_warnings)
        except Exception as e:
            for kind in upload_labels:
                if any(summary.startswith(f"{kind}:") for summary in pipeline_result.source_summaries):
                    results["errors"].append(f"{upload_labels[kind]}: {str(e)}")
            logger.exception("excel pipeline build failed")
    else:
        results["data_years"] = [year]

    if not file_hashes and not results["errors"]:
        logger.info("import finished with duplicates only skipped=%s years=%s", len(results["skipped"]), results["data_years"])
        results["import_id"] = None
        return _set_import_status(results, has_written_rows=False)

    if results["errors"] and not file_hashes:
        _set_import_status(results, has_written_rows=False)
        raise HTTPException(status_code=400, detail=results)

    if results["errors"] and file_hashes and not allow_partial:
        results["message"] = "导入已取消：部分文件解析失败。请修正失败文件后重新上传，或显式设置 allow_partial=true。"
        _set_import_status(results, has_written_rows=False)
        logger.warning("import aborted because partial import is disabled errors=%s", results["errors"])
        raise HTTPException(status_code=400, detail=results)

    if not file_hashes:
        _set_import_status(results, has_written_rows=False)
        raise HTTPException(status_code=400, detail=results)

    # 写入数据库（增量：按月删除再插入，未涉及月份保持不动）
    import_id = None
    table_row_counts = {}
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            table_row_counts = write_excel_pipeline_result(conn, pipeline_result, incremental=True)

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
    force: bool = Query(False),
    _user=Depends(require_permission("upload")),
):
    return await upload_files(performance=performance, jingdai=jingdai, hr=hr, value=value, year=year, force=force, _user=_user)


# 静态文件服务 - 生产HTML
static_dir = os.path.join(os.path.dirname(__file__), '..')
if os.path.exists(os.path.join(static_dir, '经营分析模板.html')):
    js_dir = os.path.join(static_dir, 'js')
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, '经营分析模板.html'))

    @app.get("/honor")
    def honor_page():
        return FileResponse(os.path.join(static_dir, "honor.html"))

    @app.get("/scheme-calculator")
    @app.get("/scheme-calculator.html")
    def scheme_calculator_page():
        return FileResponse(os.path.join(static_dir, "scheme-calculator.html"))

    @app.get("/personnel-management")
    @app.get("/personnel-management.html")
    def personnel_management_page():
        return FileResponse(os.path.join(static_dir, "personnel-management.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "45679")))
