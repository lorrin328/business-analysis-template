"""诊断端点 — 对比期交保费与长险期交差异，辅助排查数据口径问题。"""
from fastapi import APIRouter
from db import get_db

router = APIRouter(prefix="/api", tags=["diagnostics"])


@router.get("/diagnostics")
def get_diagnostics():
    """对比 agg_performance 与 agg_longterm_qj 的总保费。"""
    with get_db() as conn:
        c = conn.cursor()

        # agg_performance 按 channel 汇总
        c.execute('''
            SELECT channel, SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_performance WHERE year >= 2026
            GROUP BY channel ORDER BY total DESC
        ''')
        perf_channels = [
            {"channel": r["channel"], "total_qj": round(r["total"] or 0, 2),
             "latest_period": r["latest"]}
            for r in c.fetchall()
        ]

        # 转型总期交（长期条件过滤前）
        perf_total_qj = sum(p["total_qj"] for p in perf_channels)

        # agg_longterm_qj 按 channel 汇总（转型）
        c.execute('''
            SELECT channel, SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_longterm_qj WHERE year >= 2026 AND business_type = '转型'
            GROUP BY channel ORDER BY total DESC
        ''')
        lt_channels = [
            {"channel": r["channel"], "total_qj": round(r["total"] or 0, 2),
             "latest_period": r["latest"]}
            for r in c.fetchall()
        ]

        lt_total_qj = sum(p["total_qj"] for p in lt_channels)

        # 经代对比
        c.execute('''
            SELECT SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_jingdai WHERE year >= 2026
        ''')
        jd_row = c.fetchone()
        jd_perf_total = round(jd_row["total"] or 0, 2) if jd_row else 0
        jd_perf_latest = jd_row["latest"] if jd_row else None

        c.execute('''
            SELECT SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_longterm_qj WHERE year >= 2026 AND business_type = '经代'
        ''')
        jd_lt_row = c.fetchone()
        jd_lt_total = round(jd_lt_row["total"] or 0, 2) if jd_lt_row else 0
        jd_lt_latest = jd_lt_row["latest"] if jd_lt_row else None

        # 日级 cutoff（期交保费实际使用的口径）
        c.execute('''
            SELECT month, MAX(day) AS max_day
            FROM agg_daily_performance WHERE year >= 2026
            GROUP BY month ORDER BY month DESC LIMIT 1
        ''')
        daily_cutoff = c.fetchone()
        daily_info = {
            "month": daily_cutoff["month"],
            "max_day": daily_cutoff["max_day"],
            "use_daily": daily_cutoff["month"] is not None,
        } if daily_cutoff else {"use_daily": False}

    ratio = round(lt_total_qj / perf_total_qj * 100, 1) if perf_total_qj else 0
    jd_ratio = round(jd_lt_total / jd_perf_total * 100, 1) if jd_perf_total else 0

    return {
        "summary": {
            "transform": {
                "qj_premium_total": perf_total_qj,
                "longterm_qj_total": lt_total_qj,
                "ratio_pct": ratio,
                "gap": round(perf_total_qj - lt_total_qj, 2),
                "status": "OK" if ratio > 85 else ("WARN" if ratio > 50 else "CRITICAL"),
            },
            "jingdai": {
                "qj_premium_total": jd_perf_total,
                "longterm_qj_total": jd_lt_total,
                "ratio_pct": jd_ratio,
                "gap": round(jd_perf_total - jd_lt_total, 2),
            },
        },
        "perf_channels": perf_channels,
        "longterm_channels": lt_channels,
        "data_periods": {
            "perf_transform_latest": max((p["latest_period"] or 0) for p in perf_channels) if perf_channels else None,
            "longterm_transform_latest": max((p["latest_period"] or 0) for p in lt_channels) if lt_channels else None,
            "perf_jingdai_latest": jd_perf_latest,
            "longterm_jingdai_latest": jd_lt_latest,
        },
        "daily_cutoff": daily_info,
        "note": "ratio=长险期交/期交保费×100。ratio>95正常，80-95需关注，<80异常。",
    }
