import os
import sys
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))
from database import init_db, get_db, clear_year_data
from aggregator import (
    parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel,
    aggregate_performance, aggregate_jingdai, aggregate_hr, aggregate_value
)

app = FastAPI(title="经营分析看板API")

# CORS - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    jd_rows = []
    hr_rows = []
    value_rows = []

    if performance and performance.filename:
        try:
            df = parse_performance_excel(await performance.read())
            perf_rows = aggregate_performance(df)
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
            df = parse_value_excel(await value.read())
            value_rows = aggregate_value(df)
            results["uploaded"].append(f"价值数据: {len(value_rows)}条")
        except Exception as e:
            results["errors"].append(f"价值数据: {str(e)}")

    # 收集所有实际年份
    for rows in [perf_rows, jd_rows, hr_rows, value_rows]:
        for r in rows:
            if 'year' in r and r['year']:
                results["data_years"].add(int(r['year']))

    # 如果没有检测到年份，使用传入的year参数
    years_to_clear = list(results["data_years"]) if results["data_years"] else [year]
    results["data_years"] = sorted(list(results["data_years"])) if results["data_years"] else [year]

    # 清除这些年份的旧数据
    for y in years_to_clear:
        clear_year_data(y)

    # 写入数据库
    with get_db() as conn:
        c = conn.cursor()

        for r in perf_rows:
            c.execute('''
                INSERT INTO performance (year, month, channel, qj_premium, gm_premium, zs_premium)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (r['year'], r['month'], r['channel'], r['qj_premium'], r['gm_premium'], r['zs_premium']))

        for r in jd_rows:
            c.execute('''
                INSERT INTO jingdai (year, month, qj_premium, gm_premium, zs_premium)
                VALUES (?, ?, ?, ?, ?)
            ''', (r['year'], r['month'], r['qj_premium'], r['gm_premium'], r['zs_premium']))

        for r in hr_rows:
            c.execute('''
                INSERT INTO hr_data (year, month, channel, start_headcount, end_headcount, active_headcount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (r['year'], r['month'], r['channel'], r['start_headcount'], r['end_headcount'], r['active_headcount']))

        for r in value_rows:
            c.execute('''
                INSERT INTO value_data (year, month, channel, value_premium)
                VALUES (?, ?, ?, ?)
            ''', (r['year'], r['month'], r['channel'], r['value_premium']))

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
    from database import get_db

    with get_db() as conn:
        c = conn.cursor()

        # 期交保费累计
        c.execute('''
            SELECT channel, SUM(qj_premium) as total
            FROM performance WHERE year = ? GROUP BY channel
        ''', (year,))
        perf = {r['channel']: r['total'] for r in c.fetchall()}

        c.execute('''
            SELECT SUM(qj_premium) as total FROM jingdai WHERE year = ?
        ''', (year,))
        jingdai_qj = c.fetchone()['total'] or 0

        # 人力数据（最新月份）
        c.execute('''
            SELECT channel, MAX(month) as max_month FROM hr_data WHERE year = ? GROUP BY channel
        ''', (year,))
        latest_months = {r['channel']: r['max_month'] for r in c.fetchall()}

        hr = {}
        for channel, max_month in latest_months.items():
            c.execute('''
                SELECT start_headcount, end_headcount, active_headcount
                FROM hr_data WHERE year = ? AND channel = ? AND month = ?
            ''', (year, channel, max_month))
            row = c.fetchone()
            if row:
                hr[channel] = {
                    'start': row['start_headcount'],
                    'end': row['end_headcount'],
                    'active': row['active_headcount'],
                    'avg': (row['start_headcount'] + row['end_headcount']) / 2
                }

        # 价值数据累计
        c.execute('''
            SELECT channel, SUM(value_premium) as total
            FROM value_data WHERE year = ? GROUP BY channel
        ''', (year,))
        value = {r['channel']: r['total'] for r in c.fetchall()}

        return {
            'year': year,
            'qj_premium': {
                'jingdai': round(jingdai_qj, 2),
                'oto': round(perf.get('OTO', 0), 2),
                'zhengbao': round(perf.get('证保', 0), 2),
                'yiqiao': round(perf.get('蚁桥', 0), 2),
                'total_transform': round(perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0), 2),
                'total': round(jingdai_qj + perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0), 2),
            },
            'hr': hr,
            'value': value,
        }


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
