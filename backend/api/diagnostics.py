"""诊断端点 — 对比期交保费与长险期交差异，辅助排查数据口径问题。"""
from fastapi import APIRouter, Depends

from auth import require_permission
from config.business_lines import DEFAULT_YEAR
from db import DB_PATH, get_db
from services.data_quality_audit import run_data_quality_audit

router = APIRouter(prefix="/api", tags=["diagnostics"])


@router.get("/diagnostics/import-status")
def get_import_status(year: int = DEFAULT_YEAR, _user=Depends(require_permission("permission_admin"))):
    """Return database freshness details for Excel import troubleshooting."""
    with get_db() as conn:
        c = conn.cursor()

        def one(sql: str, params=()):
            row = c.execute(sql, params).fetchone()
            return dict(row) if row else {}

        def all_rows(sql: str, params=()):
            return [dict(r) for r in c.execute(sql, params).fetchall()]

        latest_imports = all_rows(
            """
            SELECT id, imported_at, file_name, file_size, data_years, table_counts, status, error_message
            FROM data_imports
            ORDER BY id DESC
            LIMIT 8
            """
        )
        transform_cutoff = one(
            """
            SELECT month, MAX(day) AS day
            FROM agg_daily_performance
            WHERE year = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
            """,
            (year,),
        )
        transform_channel_cutoffs = all_rows(
            """
            SELECT channel, month, MAX(day) AS day
            FROM agg_daily_performance
            WHERE year = ?
              AND month = (SELECT MAX(month) FROM agg_daily_performance WHERE year = ?)
            GROUP BY channel, month
            ORDER BY channel
            """,
            (year, year),
        )
        jingdai_cutoff = one(
            """
            SELECT month, MAX(day) AS day
            FROM agg_jingdai_daily
            WHERE year = ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT 1
            """,
            (year,),
        )
        transform_monthly_ytd = one(
            "SELECT ROUND(SUM(qj_premium), 4) AS qj FROM agg_performance WHERE year = ?",
            (year,),
        ).get("qj") or 0
        transform_daily_ytd = one(
            "SELECT ROUND(SUM(qj_premium), 4) AS qj FROM agg_daily_performance WHERE year = ?",
            (year,),
        ).get("qj") or 0
        transform_org_daily_ytd = one(
            "SELECT ROUND(SUM(qj_premium), 4) AS qj FROM agg_org_daily_performance WHERE year = ?",
            (year,),
        ).get("qj") or 0
        transform_by_channel = all_rows(
            """
            SELECT channel, ROUND(SUM(qj_premium), 4) AS qj
            FROM agg_daily_performance
            WHERE year = ?
            GROUP BY channel
            ORDER BY channel
            """,
            (year,),
        )
        org_by_cutoff = {}
        for day in [26, 27, 28, 29, 30, 31]:
            row = one(
                """
                SELECT ROUND(SUM(qj_premium), 4) AS qj
                FROM agg_org_daily_performance
                WHERE year = ?
                  AND (month < 5 OR (month = 5 AND day <= ?))
                """,
                (year, day),
            )
            org_by_cutoff[f"through_05_{day:02d}"] = row.get("qj") or 0

    return {
        "year": year,
        "database_path": DB_PATH,
        "latest_imports": latest_imports,
        "cutoffs": {
            "transform": transform_cutoff,
            "transform_by_channel": transform_channel_cutoffs,
            "jingdai": jingdai_cutoff,
        },
        "transform_ytd": {
            "monthly": transform_monthly_ytd,
            "daily": transform_daily_ytd,
            "org_daily": transform_org_daily_ytd,
            "org_daily_by_cutoff": org_by_cutoff,
            "by_channel": transform_by_channel,
        },
    }


@router.get("/diagnostics")
def get_diagnostics(_user=Depends(require_permission("permission_admin"))):
    """对比 agg_performance 与 agg_longterm_qj 的总保费。"""
    with get_db() as conn:
        c = conn.cursor()

        # agg_performance 按 channel 汇总
        c.execute('''
            SELECT channel, SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_performance WHERE year >= ?
            GROUP BY channel ORDER BY total DESC
        ''', (DEFAULT_YEAR,))
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
            FROM agg_longterm_qj WHERE year >= ? AND business_type = '转型'
            GROUP BY channel ORDER BY total DESC
        ''', (DEFAULT_YEAR,))
        lt_channels = [
            {"channel": r["channel"], "total_qj": round(r["total"] or 0, 2),
             "latest_period": r["latest"]}
            for r in c.fetchall()
        ]

        lt_total_qj = sum(p["total_qj"] for p in lt_channels)

        # 经代对比
        c.execute('''
            SELECT SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_jingdai WHERE year >= ?
        ''', (DEFAULT_YEAR,))
        jd_row = c.fetchone()
        jd_perf_total = round(jd_row["total"] or 0, 2) if jd_row else 0
        jd_perf_latest = jd_row["latest"] if jd_row else None

        c.execute('''
            SELECT SUM(qj_premium) AS total, MAX(year*100+month) AS latest
            FROM agg_longterm_qj WHERE year >= ? AND business_type = '经代'
        ''', (DEFAULT_YEAR,))
        jd_lt_row = c.fetchone()
        jd_lt_total = round(jd_lt_row["total"] or 0, 2) if jd_lt_row else 0
        jd_lt_latest = jd_lt_row["latest"] if jd_lt_row else None

        # 日级 cutoff（期交保费实际使用的口径）
        c.execute('''
            SELECT month, MAX(day) AS max_day
            FROM agg_daily_performance WHERE year >= ?
            GROUP BY month ORDER BY month DESC LIMIT 1
        ''', (DEFAULT_YEAR,))
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


@router.get("/diagnostics/data-quality")
def get_data_quality_diagnostics(year: int = DEFAULT_YEAR, _user=Depends(require_permission("permission_admin"))):
    return run_data_quality_audit(year)
