import os
import sys
from fastapi import Body, FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))
from database import (
    init_db, get_db, replace_rows,
    get_kpi_data, get_product_structure, get_target_config, save_target_config,
    get_org_kpi_data,
)
from aggregator import (
    parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel,
    aggregate_performance, aggregate_jingdai, aggregate_hr, aggregate_value,
    aggregate_product_structure, aggregate_active_headcount,
    aggregate_org_performance, aggregate_org_value,
    aggregate_daily_performance, aggregate_org_daily_performance,
)

app = FastAPI(title="经营分析看板API")

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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_files(
    performance: UploadFile = File(None),
    jingdai: UploadFile = File(None),
    hr: UploadFile = File(None),
    value: UploadFile = File(None),
    year: int = 2026,
):
    """上传Excel文件并聚合到SQLite"""
    results = {"uploaded": [], "errors": [], "data_years": set()}

    # 第一步：解析所有Excel文件，收集实际年份
    perf_rows = []
    daily_rows = []
    org_daily_rows = []
    jd_rows = []
    hr_rows = []
    value_rows = []
    product_rows = []
    active_rows = []
    org_perf_rows = []
    org_value_rows = []

    if performance and performance.filename:
        try:
            perf_bytes = await performance.read()
            df = parse_performance_excel(perf_bytes)
            perf_rows = aggregate_performance(df)
            daily_rows = aggregate_daily_performance(df)
            org_daily_rows = aggregate_org_daily_performance(df)
            product_rows = aggregate_product_structure(df)
            active_rows = aggregate_active_headcount(df)
            org_perf_rows = aggregate_org_performance(df)
            results["uploaded"].append(f"转型业务业绩: {len(perf_rows)}条")
        except Exception as e:
            results["errors"].append(f"转型业务业绩: {str(e)}")

    if jingdai and jingdai.filename:
        try:
            df = parse_jingdai_excel(await jingdai.read())
            jd_rows = aggregate_jingdai(df)
            results["uploaded"].append(f"经代业务业绩: {len(jd_rows)}条")
        except Exception as e:
            results["errors"].append(f"经代业务业绩: {str(e)}")

    if hr and hr.filename:
        try:
            df = parse_hr_excel(await hr.read())
            hr_rows = aggregate_hr(df)
            results["uploaded"].append(f"人力数据: {len(hr_rows)}条")
        except Exception as e:
            results["errors"].append(f"人力数据: {str(e)}")

    if value and value.filename:
        try:
            val_bytes = await value.read()
            df = parse_value_excel(val_bytes)
            value_rows = aggregate_value(df)
            org_value_rows = aggregate_org_value(df)
            results["uploaded"].append(f"价值数据: {len(value_rows)}条")
        except Exception as e:
            results["errors"].append(f"价值数据: {str(e)}")

    if hr_rows and active_rows:
        active_index = {
            (r['year'], r['month'], r['channel']): r['active_headcount']
            for r in active_rows
        }
        for row in hr_rows:
            row['active_headcount'] = active_index.get((row['year'], row['month'], row['channel']), 0)

    # 收集所有实际年份
    for rows in [perf_rows, daily_rows, org_daily_rows, jd_rows, hr_rows, value_rows, product_rows, org_perf_rows, org_value_rows]:
        for r in rows:
            if 'year' in r and r['year']:
                results["data_years"].add(int(r['year']))

    # 如果没有检测到年份，使用传入的year参数
    results["data_years"] = sorted(list(results["data_years"])) if results["data_years"] else [year]

    # 写入数据库
    with get_db() as conn:
        c = conn.cursor()

        table_rows = [
            ('agg_performance', perf_rows),
            ('agg_daily_performance', daily_rows),
            ('agg_org_daily_performance', org_daily_rows),
            ('agg_product_structure', product_rows),
            ('agg_jingdai', jd_rows),
            ('agg_hr_data', hr_rows),
            ('agg_value_data', value_rows),
            ('agg_org_performance', org_perf_rows),
            ('agg_org_value', org_value_rows),
        ]
        for table, rows in table_rows:
            for y in sorted({int(r['year']) for r in rows if 'year' in r and r['year']}):
                c.execute(f'DELETE FROM {table} WHERE year = ?', (y,))

        replace_rows(conn, 'agg_performance', perf_rows)
        replace_rows(conn, 'agg_daily_performance', daily_rows)
        replace_rows(conn, 'agg_org_daily_performance', org_daily_rows)
        replace_rows(conn, 'agg_jingdai', jd_rows)
        replace_rows(conn, 'agg_hr_data', hr_rows)
        replace_rows(conn, 'agg_value_data', value_rows)
        replace_rows(conn, 'agg_product_structure', product_rows)
        replace_rows(conn, 'agg_org_performance', org_perf_rows)
        replace_rows(conn, 'agg_org_value', org_value_rows)

        conn.commit()

    return results


@app.get("/api/data/{year}")
def get_data(year: int):
    """获取指定年份的所有聚合数据"""
    from database import get_platform_data
    return get_platform_data(year)


@app.get("/api/kpi/{year}")
def get_kpi(year: int):
    """获取KPI概览数据"""
    return get_kpi_data(year)


@app.get("/api/product/{year}")
def get_product(year: int, dimension: str = "design_cat"):
    """获取产品结构数据"""
    return get_product_structure(year, dimension)


@app.get("/api/org-kpi/{year}")
def get_org_kpi(year: int):
    """获取机构维度KPI数据"""
    return get_org_kpi_data(year)


@app.get("/api/targets/{year}")
def get_targets(year: int):
    """获取服务器端统一目标配置"""
    saved = get_target_config(year)
    return saved or {"year": year, "categories": None}


@app.put("/api/targets/{year}")
def put_targets(year: int, payload: dict = Body(...)):
    """保存服务器端统一目标配置"""
    if not isinstance(payload, dict) or "categories" not in payload:
        raise HTTPException(status_code=400, detail="invalid target payload")
    return save_target_config(year, payload)


# 静态文件服务 - 生产HTML
static_dir = os.path.join(os.path.dirname(__file__), '..')
if os.path.exists(os.path.join(static_dir, '经营分析模板.html')):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, '经营分析模板.html'))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
