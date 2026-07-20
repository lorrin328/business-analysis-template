"""KPI repository queries."""
import re
import sqlite3
from db.connection import get_db
from services.cutoff_policy import (
    build_period_context,
    build_source_cutoff_policy,
    cutoff_min,
    Cutoff,
    date_range_filter_sql,
    latest_daily_cutoff,
)


_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _sql_identifier(value: str) -> str:
    if not _SQL_IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid SQL identifier: {value}")
    return value


def _sum_daily_columns(
    cursor: sqlite3.Cursor,
    table: str,
    year: int,
    start_cutoff: Cutoff,
    end_cutoff: Cutoff,
    columns: dict[str, str],
) -> dict[str, float]:
    """Sum daily aggregate columns within an inclusive month/day range."""
    date_sql, date_params = date_range_filter_sql(start_cutoff, end_cutoff)
    table = _sql_identifier(table)
    select_sql = ", ".join(
        [
            f"SUM({_sql_identifier(column)}) AS {_sql_identifier(alias)}"
            for alias, column in columns.items()
        ]
    )
    cursor.execute(
        f"""
        SELECT {select_sql}
        FROM {table}
        WHERE year = ?
          AND {date_sql}
        """,
        [year, *date_params],
    )
    row = cursor.fetchone()
    return {
        alias: round((row[alias] if row else 0) or 0, 2)
        for alias in columns
    }


def _sum_daily_column_by_channel(
    cursor: sqlite3.Cursor,
    table: str,
    year: int,
    start_cutoff: Cutoff,
    end_cutoff: Cutoff,
    column: str,
) -> dict[str, float]:
    """Sum one daily aggregate column by channel within a range."""
    date_sql, date_params = date_range_filter_sql(start_cutoff, end_cutoff)
    table = _sql_identifier(table)
    column = _sql_identifier(column)
    cursor.execute(
        f"""
        SELECT channel, SUM({column}) AS total
        FROM {table}
        WHERE year = ?
          AND {date_sql}
        GROUP BY channel
        """,
        [year, *date_params],
    )
    return {
        r["channel"]: round(r["total"] or 0, 2)
        for r in cursor.fetchall()
    }


def get_kpi_data(
    year: int,
    as_of: str | None = None,
    *,
    range_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """获取 KPI 概览数据。

    期交保费 YTD 优先使用日累计表（agg_daily_performance / agg_jingdai_daily），
    按「统计日」口径截取去年同期，即截至上一年的同一日。
    人力、价值等无日维度的指标仍按月级精度计算。
    """
    with get_db() as conn:
        c = conn.cursor()
        period_context = build_period_context(
            conn,
            year,
            range_type=range_type,
            start_date=start_date,
            end_date=end_date,
            as_of=as_of,
        )
        as_of_context = period_context["asOf"]
        selected_start = period_context["startCutoff"]
        selected_cutoff = period_context["endCutoff"]

        # Use the smallest available source cutoff to avoid mixing data through different months.
        def _max_month(table: str):
            c.execute(f'SELECT MAX(month) FROM {table} WHERE year = ?', (year,))
            value = c.fetchone()[0]
            return int(value) if value else None

        data_cutoff = {
            'performance': _max_month('agg_performance'),
            'hr': _max_month('agg_hr_data'),
            'jingdai': _max_month('agg_jingdai'),
            'value': _max_month('agg_value_data'),
        }
        available_cutoffs = [month for month in data_cutoff.values() if month]
        query_month = min(available_cutoffs) if available_cutoffs else 1
        if selected_cutoff:
            query_month = min(query_month, int(selected_cutoff["month"]))
        query_start_month = int(selected_start["month"]) if selected_start else 1

        # ── 日级统计截止日（用于期交保费同比同口径截取） ──
        # 转型业务与经代业务来自不同报表：转型更新到拉取当天，经代截至前一日。
        # KPI 按各自真实截止日取数；共同截止日仅暴露给需要同日对比的展示。
        transform_source_cutoff = latest_daily_cutoff(conn, 'agg_daily_performance', year)
        jingdai_source_cutoff = latest_daily_cutoff(conn, 'agg_jingdai_daily', year)
        transform_daily_cutoff = cutoff_min(transform_source_cutoff, selected_cutoff) if transform_source_cutoff else None
        jingdai_daily_cutoff = cutoff_min(jingdai_source_cutoff, selected_cutoff) if jingdai_source_cutoff else None
        daily_policy = build_source_cutoff_policy(transform_daily_cutoff, jingdai_daily_cutoff)
        use_daily = daily_policy['use_daily']
        common_daily_cutoff = daily_policy['common']
        latest_cutoff = daily_policy['latest']
        if use_daily and latest_cutoff:
            ytd_end_month = latest_cutoff['month']
            ytd_end_day = latest_cutoff['day']
        elif daily_policy.get('partial_daily') and latest_cutoff:
            # Avoid mixing a partial daily source with another source's full-month table.
            query_month = min(query_month, max(int(latest_cutoff['month']) - 1, 0))
            daily_policy['fallback_month'] = query_month
            ytd_end_month = query_month
            ytd_end_day = 31
        else:
            ytd_end_month = query_month
            ytd_end_day = 31

        def _period_premiums_daily(query_year: int) -> dict:
            """从日表取所选范围期交保费，按 channel 汇总。"""
            if not use_daily or not transform_daily_cutoff:
                return {}
            return _sum_daily_column_by_channel(
                c, 'agg_daily_performance', query_year, selected_start, transform_daily_cutoff, 'qj_premium'
            )

        def _period_jingdai_daily(query_year: int) -> float:
            """从经代日表取所选范围期交保费。"""
            if not use_daily or not jingdai_daily_cutoff:
                return 0.0
            return _sum_daily_columns(
                c, 'agg_jingdai_daily', query_year, selected_start, jingdai_daily_cutoff, {'total': 'qj_premium'}
            )['total']

        def _ytd_transform_products_daily(query_year: int) -> dict:
            """从转型机构日表取截至统计日的产品指标。"""
            if not use_daily or not transform_daily_cutoff:
                return {'annuity': 0.0, 'protection': 0.0, 'tenyear': 0.0}
            return _sum_daily_columns(
                c,
                'agg_org_daily_performance',
                query_year,
                selected_start,
                transform_daily_cutoff,
                {
                    'annuity': 'product_annuity',
                    'protection': 'product_protection',
                    'tenyear': 'product_10year',
                },
            )

        def _ytd_jingdai_products_daily(query_year: int) -> dict:
            """从经代日表取截至统计日的商保年金 / 保障类指标。"""
            if not use_daily or not jingdai_daily_cutoff:
                return {'annuity': 0.0, 'protection': 0.0}
            return _sum_daily_columns(
                c,
                'agg_jingdai_daily',
                query_year,
                selected_start,
                jingdai_daily_cutoff,
                {
                    'annuity': 'product_annuity',
                    'protection': 'product_protection',
                },
            )

        # ── YTD 保费（有日数据时用日累计，否则回退月表） ──
        daily_perf = _period_premiums_daily(year)
        daily_jd = _period_jingdai_daily(year)

        if use_daily:
            perf = daily_perf
            jingdai_qj = daily_jd
        else:
            c.execute('''
                SELECT channel, SUM(qj_premium) AS total
                FROM agg_performance WHERE year = ? AND month BETWEEN ? AND ? GROUP BY channel
            ''', (year, query_start_month, query_month))
            perf = {r['channel']: r['total'] or 0 for r in c.fetchall()}
            c.execute('''
                SELECT SUM(qj_premium) AS total FROM agg_jingdai WHERE year = ? AND month BETWEEN ? AND ?
            ''', (year, query_start_month, query_month))
            jingdai_qj = c.fetchone()['total'] or 0

        # HR（月级精度）
        c.execute('''
            SELECT channel, month, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? AND month BETWEEN ? AND ?
            ORDER BY channel, month
        ''', (year, query_start_month, query_month))
        hr = {}
        hr_latest = {}
        for r in c.fetchall():
            ch = r['channel']
            avg_hc = ((r['start_headcount'] or 0) + (r['end_headcount'] or 0)) / 2.0
            info = hr.setdefault(ch, {'avg_sum': 0.0, 'months': 0, 'month': query_month})
            info['avg_sum'] += avg_hc
            info['months'] += 1
            if r['month'] == query_month:
                hr_latest[ch] = {
                    'start': r['start_headcount'] or 0,
                    'end': r['end_headcount'] or 0,
                    'active': r['active_headcount'] or 0,
                    'avg': avg_hc,
                }
        for ch, info in hr.items():
            info.update(hr_latest.get(ch, {}))
            if not info.get('avg'):
                info['avg'] = 0
            if info['months'] > 1:
                info['avg_sum'] = round(info['avg_sum'], 2)

        # 去年同期 HR（月级精度，人力基表无日维度）
        c.execute('''
            SELECT channel, month, start_headcount, end_headcount, active_headcount
            FROM agg_hr_data WHERE year = ? AND month BETWEEN ? AND ?
            ORDER BY channel, month
        ''', (year - 1, query_start_month, query_month))
        hr_prev = {}; hr_prev_latest = {}
        for r in c.fetchall():
            ch = r['channel']
            avg_hc = ((r['start_headcount'] or 0) + (r['end_headcount'] or 0)) / 2.0
            info = hr_prev.setdefault(ch, {'avg_sum': 0.0, 'months': 0, 'month': query_month})
            info['avg_sum'] += avg_hc
            info['months'] += 1
            if r['month'] == query_month:
                hr_prev_latest[ch] = {
                    'start': r['start_headcount'] or 0, 'end': r['end_headcount'] or 0,
                    'active': r['active_headcount'] or 0, 'avg': avg_hc,
                }
        for ch, info in hr_prev.items():
            info.update(hr_prev_latest.get(ch, {}))
            if not info.get('avg'): info['avg'] = 0

        def _longterm_where_params(query_year: int) -> tuple[str, list[int]]:
            where = 'year = ? AND month BETWEEN ? AND ?'
            params: list[int] = [query_year, query_start_month, ytd_end_month]
            if use_daily and transform_daily_cutoff and jingdai_daily_cutoff:
                transform_sql, transform_params = date_range_filter_sql(selected_start, transform_daily_cutoff)
                jingdai_sql, jingdai_params = date_range_filter_sql(selected_start, jingdai_daily_cutoff)
                where = f'''year = ? AND (
                    (business_type = '转型' AND {transform_sql})
                    OR (business_type = '经代' AND {jingdai_sql})
                )'''
                params = [query_year, *transform_params, *jingdai_params]
            return where, params

        # 长险期交（YTD）。按业务线各自日级截止日，与期交保费保持同源同口径。
        longterm_where, longterm_params = _longterm_where_params(year)
        c.execute(f'''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE {longterm_where} GROUP BY business_type, channel
        ''', longterm_params)
        lt_qj = {}; lt_tf = 0.0; lt_jd = 0.0
        for r in c.fetchall():
            v = round(r['total'] or 0, 2)
            key = f"{r['business_type']}|{r['channel']}" if r['channel'] else r['business_type']
            lt_qj[key] = v
            if r['business_type'] == '转型': lt_tf += v
            else: lt_jd += v
        lt_total = lt_tf + lt_jd

        prev_longterm_where, prev_longterm_params = _longterm_where_params(year - 1)
        c.execute(f'''
            SELECT business_type, channel, SUM(qj_premium) AS total
            FROM agg_longterm_qj WHERE {prev_longterm_where} GROUP BY business_type, channel
        ''', prev_longterm_params)
        lt_qj_prev = {}; lt_tf_prev = 0.0; lt_jd_prev = 0.0
        for r in c.fetchall():
            v = round(r['total'] or 0, 2)
            lt_qj_prev[f"{r['business_type']}|{r['channel']}" if r['channel'] else r['business_type']] = v
            if r['business_type'] == '转型': lt_tf_prev += v
            else: lt_jd_prev += v
        lt_total_prev = lt_tf_prev + lt_jd_prev

        # 价值（YTD，月级精度）
        c.execute('''
            SELECT channel, SUM(value_premium) AS total
            FROM agg_value_data WHERE year = ? AND month BETWEEN ? AND ? GROUP BY channel
        ''', (year, query_start_month, query_month))
        value = {r['channel']: r['total'] or 0 for r in c.fetchall()}
        # 经代当前没有独立价值数据表，但业务口径要求纳入价值达成率。
        # 在经代价值数据接入前显式返回 0，前端据此展示“经代”行并纳入整体目标口径。
        value.setdefault('经代', 0.0)

        # 商保年金 / 保障类 / 10年期（有日表时按 asOf 日级截断）
        if use_daily:
            transform_products = _ytd_transform_products_daily(year)
            jingdai_products = _ytd_jingdai_products_daily(year)
            annuity_tf = transform_products['annuity']
            protection_tf = transform_products['protection']
            tenyear_tf = transform_products['tenyear']
            annuity_jd = jingdai_products['annuity']
            protection_jd = jingdai_products['protection']
        else:
            c.execute('''
                SELECT channel, SUM(product_annuity) AS a, SUM(product_protection) AS p, SUM(product_10year) AS t
                FROM agg_org_performance WHERE year = ? AND month BETWEEN ? AND ? GROUP BY channel
            ''', (year, query_start_month, query_month))
            org_product_rows = c.fetchall()
            annuity_tf = sum((r['a'] or 0) for r in org_product_rows)
            protection_tf = sum((r['p'] or 0) for r in org_product_rows)
            tenyear_tf = sum((r['t'] or 0) for r in org_product_rows)
            c.execute('''
                SELECT SUM(product_annuity) AS a, SUM(product_protection) AS p
                FROM agg_jingdai WHERE year = ? AND month BETWEEN ? AND ?
            ''', (year, query_start_month, query_month))
            jd_product_row = c.fetchone()
            annuity_jd = (jd_product_row['a'] or 0) if jd_product_row else 0.0
            protection_jd = (jd_product_row['p'] or 0) if jd_product_row else 0.0
        daily_payment_table_exists = bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agg_payment_period_daily'"
        ).fetchone())
        daily_payment_available = daily_payment_table_exists and bool(c.execute(
            "SELECT 1 FROM agg_payment_period_daily WHERE year = ? LIMIT 1", (year,)
        ).fetchone())
        if use_daily and daily_payment_available:
            payment_sql, payment_params = date_range_filter_sql(selected_start, jingdai_daily_cutoff)
            c.execute(f'''
                SELECT SUM(qj_premium) AS t
                FROM agg_payment_period_daily
                WHERE year = ? AND {payment_sql}
                  AND business_type = '经代'
                  AND category = '10年及以上'
            ''', [year, *payment_params])
        else:
            c.execute('''
                SELECT SUM(qj_premium) AS t
                FROM agg_payment_period
                WHERE year = ? AND month BETWEEN ? AND ?
                  AND business_type = '经代'
                  AND category = '10年及以上'
            ''', (year, query_start_month, query_month))
        row = c.fetchone()
        tenyear_jd = (row['t'] or 0) if row else 0.0

        total_transform = perf.get('OTO', 0) + perf.get('证保', 0) + perf.get('蚁桥', 0)

        # 去年同期期交保费（日级口径）
        prev_perf = _period_premiums_daily(year - 1) if use_daily else {}
        prev_jingdai_qj = _period_jingdai_daily(year - 1) if use_daily else 0.0

        return {
            'year': year,
            'month': query_month,
            'data_cutoff': data_cutoff,
            'daily_cutoff': {
                'month': ytd_end_month,
                'day': ytd_end_day,
                'use_daily': use_daily,
                'common': common_daily_cutoff,
                'transform': transform_daily_cutoff,
                'jingdai': jingdai_daily_cutoff,
                'policy': daily_policy,
            },
            'as_of': as_of_context,
            'period': period_context,
            'qj_premium': {
                'jingdai': round(jingdai_qj, 2),
                'oto': round(perf.get('OTO', 0), 2),
                'zhengbao': round(perf.get('证保', 0), 2),
                'yiqiao': round(perf.get('蚁桥', 0), 2),
                'total_transform': round(total_transform, 2),
                'total': round(jingdai_qj + total_transform, 2),
            },
            'qj_premium_prev': {
                'jingdai': round(prev_jingdai_qj, 2),
                'oto': round(prev_perf.get('OTO', 0), 2),
                'zhengbao': round(prev_perf.get('证保', 0), 2),
                'yiqiao': round(prev_perf.get('蚁桥', 0), 2),
                'total_transform': round(
                    prev_perf.get('OTO', 0) + prev_perf.get('证保', 0) + prev_perf.get('蚁桥', 0), 2
                ),
                'total': round(prev_jingdai_qj + prev_perf.get('OTO', 0) + prev_perf.get('证保', 0) + prev_perf.get('蚁桥', 0), 2),
            } if use_daily else None,
            'longterm_qj': lt_total,
            'longterm_qj_tf': lt_tf,
            'longterm_qj_jd': lt_jd,
            'longterm_qj_prev': lt_total_prev,
            'longterm_qj_tf_prev': lt_tf_prev,
            'longterm_qj_jd_prev': lt_jd_prev,
            'annuity_total': round(annuity_tf + annuity_jd, 2),
            'annuity_tf': round(annuity_tf, 2),
            'annuity_jd': round(annuity_jd, 2),
            'protection_total': round(protection_tf + protection_jd, 2),
            'protection_tf': round(protection_tf, 2),
            'protection_jd': round(protection_jd, 2),
            'tenyear_total': round(tenyear_tf + tenyear_jd, 2),
            'tenyear_tf': round(tenyear_tf, 2),
            'tenyear_jd': round(tenyear_jd, 2),
            'hr': hr,
            'hr_prev': hr_prev,
            'value': value,
        }
