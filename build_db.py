#!/usr/bin/env python3
"""
build_db.py — 把日明细 Excel/CSV 预生成为 SQLite (data.db)，供前端 sql.js 加载。

用法：
    python build_db.py --input 日明细.xlsx [--sheet Sheet1] [--output data.db] [--force]

要求源文件包含：
  必需：日期(或投保日期/签单日期), 年, 月, 季, 月标签
  维度：销售机构名称, 业务模式, 是否在运营项目, 分红产品, 创新or传统, 长短险,
        是否商保年金产品, 缴费年限, 保障年限, 产品设计分类
  指标：期交保费, 年化规保, 折算保费 (单位为元)

设计要点：
  1. 金额按"分"乘 100 转 INTEGER 入库，避免 IEEE754 浮点尾噪
  2. 维度列空白填 '未知'；负数严格保留（撤单/退保）
  3. 年统一存 str（与 HTML 既有约定一致）
  4. 建立常用查询索引；末尾 ANALYZE + VACUUM
"""
from __future__ import annotations

import argparse
import difflib
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd


REQUIRED_TIME_COLS = ["年", "月", "季", "月标签"]
DATE_COL_CANDIDATES = ["日期", "投保日期", "签单日期", "成交日期"]
DIM_COLS = [
    "销售机构名称", "业务模式", "是否在运营项目", "分红产品", "创新or传统",
    "长短险", "是否商保年金产品", "缴费年限", "保障年限", "产品设计分类",
]
METRIC_COLS = ["期交保费", "年化规保", "折算保费"]

# 中文 → SQLite 列名映射
COL_MAP = {
    "销售机构名称": "org",
    "业务模式": "biz_mode",
    "是否在运营项目": "is_operating",
    "分红产品": "is_dividend",
    "创新or传统": "innovate",
    "长短险": "term_type",
    "是否商保年金产品": "is_annuity",
    "缴费年限": "pay_years",
    "保障年限": "cov_years",
    "产品设计分类": "design_cat",
}
METRIC_MAP = {
    "期交保费": "qj_cents",
    "年化规保": "ghgb_cents",
    "折算保费": "zhsf_cents",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build data.db from daily premium Excel/CSV")
    p.add_argument("--input", "-i", required=True, help="源 Excel/CSV 文件路径")
    p.add_argument("--sheet", default=0, help="Excel sheet 名或索引（默认第一个）")
    p.add_argument("--output", "-o", default="data.db", help="输出 SQLite 文件（默认 data.db）")
    p.add_argument("--force", "-f", action="store_true", help="若输出已存在则覆盖")
    p.add_argument("--date-col", help="指定日期列名（默认自动从候选名中识别）")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def read_source(path: str, sheet) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        sys.exit(f"❌ 输入文件不存在：{path}")
    suffix = p.suffix.lower()
    if suffix in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(p, sheet_name=sheet, dtype={"年": str})
    elif suffix == ".csv":
        df = pd.read_csv(p, dtype={"年": str})
    else:
        sys.exit(f"❌ 不支持的文件类型：{suffix}（仅支持 .xlsx/.xls/.xlsm/.csv）")
    return df


def find_date_col(df: pd.DataFrame, override: str | None) -> str | None:
    if override:
        if override not in df.columns:
            suggest = difflib.get_close_matches(override, df.columns, n=3, cutoff=0.4)
            sys.exit(f"❌ 找不到指定的日期列 '{override}'。相近列：{suggest or '无'}")
        return override
    for c in DATE_COL_CANDIDATES:
        if c in df.columns:
            return c
    return None


def validate_columns(df: pd.DataFrame) -> None:
    expected = set(REQUIRED_TIME_COLS + DIM_COLS + METRIC_COLS)
    actual = set(df.columns)
    missing = expected - actual
    if missing:
        msg = ["❌ 源文件缺失以下必要列："]
        for col in sorted(missing):
            sug = difflib.get_close_matches(col, df.columns, n=3, cutoff=0.4)
            msg.append(f"   • {col}    最相近：{sug or '无'}")
        msg.append(f"\n实际列名共 {len(df.columns)} 列：{list(df.columns)}")
        sys.exit("\n".join(msg))


def to_cents(s: pd.Series) -> pd.Series:
    """元 → 分 (int64)。容忍字符串型数字、千分位、空值。"""
    cleaned = s.astype(str).str.replace(",", "", regex=False).str.strip()
    nums = pd.to_numeric(cleaned, errors="coerce").fillna(0.0)
    return (nums * 100).round().astype("int64")


def normalize(df: pd.DataFrame, date_col: str | None) -> pd.DataFrame:
    out = pd.DataFrame()

    # 时间字段
    out["year"] = df["年"].astype(str).str.strip()
    out["month"] = pd.to_numeric(df["月"], errors="coerce").fillna(0).astype("int64")
    out["quarter"] = pd.to_numeric(df["季"], errors="coerce").fillna(0).astype("int64")
    out["month_label"] = df["月标签"].astype(str).str.strip()

    if date_col is not None:
        parsed = pd.to_datetime(df[date_col], errors="coerce")
        out["date"] = parsed.dt.strftime("%Y-%m-%d")
        out["day"] = parsed.dt.day.astype("Int64")  # 可空整数
    else:
        out["date"] = None
        out["day"] = pd.Series([pd.NA] * len(df), dtype="Int64")

    # 维度列
    for zh, en in COL_MAP.items():
        col = df[zh].astype(str).str.strip()
        col = col.replace({"": "未知", "nan": "未知", "None": "未知"})
        out[en] = col

    # 金额列（元 → 分）
    for zh, en in METRIC_MAP.items():
        out[en] = to_cents(df[zh])

    return out


def write_db(df: pd.DataFrame, out_path: Path) -> None:
    if out_path.exists():
        out_path.unlink()
    conn = sqlite3.connect(out_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE fact_premium (
                id            INTEGER PRIMARY KEY,
                date          TEXT,
                year          TEXT NOT NULL,
                quarter       INTEGER NOT NULL,
                month         INTEGER NOT NULL,
                day           INTEGER,
                month_label   TEXT NOT NULL,
                org           TEXT,
                biz_mode      TEXT,
                is_operating  TEXT,
                is_dividend   TEXT,
                innovate      TEXT,
                term_type     TEXT,
                is_annuity    TEXT,
                pay_years     TEXT,
                cov_years     TEXT,
                design_cat    TEXT,
                qj_cents      INTEGER NOT NULL DEFAULT 0,
                ghgb_cents    INTEGER NOT NULL DEFAULT 0,
                zhsf_cents    INTEGER NOT NULL DEFAULT 0
            )
        """)

        cols = [
            "date", "year", "quarter", "month", "day", "month_label",
            "org", "biz_mode", "is_operating", "is_dividend", "innovate",
            "term_type", "is_annuity", "pay_years", "cov_years", "design_cat",
            "qj_cents", "ghgb_cents", "zhsf_cents",
        ]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO fact_premium ({','.join(cols)}) VALUES ({placeholders})"

        rows = []
        for r in df.itertuples(index=False):
            rec = []
            for c in cols:
                v = getattr(r, c)
                if pd.isna(v):
                    rec.append(None)
                else:
                    rec.append(v.item() if hasattr(v, "item") else v)
            rows.append(rec)

        cur.executemany(sql, rows)

        cur.execute("CREATE INDEX ix_ym   ON fact_premium(year, month)")
        cur.execute("CREATE INDEX ix_yq   ON fact_premium(year, quarter)")
        cur.execute("CREATE INDEX ix_ymd  ON fact_premium(year, month, day)")
        cur.execute("CREATE INDEX ix_org  ON fact_premium(org)")
        cur.execute("CREATE INDEX ix_mode ON fact_premium(biz_mode)")
        cur.execute("CREATE INDEX ix_dsg  ON fact_premium(design_cat)")

        conn.commit()
        cur.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()

    # VACUUM 必须在自动事务外执行
    conn = sqlite3.connect(out_path)
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()


def report(df: pd.DataFrame, out_path: Path) -> None:
    by_year = df["year"].value_counts().sort_index().to_dict()
    neg_rows = int(((df["qj_cents"] < 0) | (df["ghgb_cents"] < 0) | (df["zhsf_cents"] < 0)).sum())
    null_date = int(df["date"].isna().sum()) if "date" in df else len(df)
    sums_yuan = {
        "期交保费": df["qj_cents"].sum() / 100.0,
        "年化规保": df["ghgb_cents"].sum() / 100.0,
        "折算保费": df["zhsf_cents"].sum() / 100.0,
    }
    size_kb = out_path.stat().st_size / 1024

    print("\n✅ 构建完成")
    print(f"   输出文件      : {out_path}  ({size_kb:.1f} KB)")
    print(f"   总行数        : {len(df):,}")
    print(f"   按年分布      : {by_year}")
    print(f"   负数行（任一指标）: {neg_rows:,}")
    print(f"   日期空缺行    : {null_date:,}")
    print(f"   金额合计（元）:")
    for k, v in sums_yuan.items():
        print(f"     {k:8s} = {v:>20,.2f}")


def main() -> None:
    args = parse_args()

    out_path = Path(args.output)
    if out_path.exists() and not args.force:
        sys.exit(f"❌ {out_path} 已存在。使用 --force 覆盖，或手动删除后重试。")

    print(f"📖 读取 {args.input} ...")
    df_raw = read_source(args.input, args.sheet)
    print(f"   原始行数：{len(df_raw):,}，列数：{len(df_raw.columns)}")

    validate_columns(df_raw)
    date_col = find_date_col(df_raw, args.date_col)
    if date_col is None:
        print("⚠️  源文件未找到日期列，将以月级粒度入库（无日级 tooltip 数据）")
    else:
        print(f"   使用日期列：{date_col}")

    print("🔧 规整数据 ...")
    df = normalize(df_raw, date_col)

    print(f"💾 写入 {out_path} ...")
    write_db(df, out_path)

    report(df, out_path)


if __name__ == "__main__":
    main()
