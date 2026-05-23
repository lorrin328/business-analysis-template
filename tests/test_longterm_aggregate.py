import os
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from etl.aggregates.longterm import aggregate_jingdai_longterm, aggregate_transform_longterm
from etl.aggregates.hr import aggregate_active_headcount
from etl.classify import _classify_payment_period


def test_transform_longterm_accepts_one_year_above_term_label():
    rows = aggregate_transform_longterm(
        pd.DataFrame(
            [
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "销售机构名称": "上海",
                    "长短险": "一年期以上",
                    "产品代码": "4188",
                    "缴费年限": 5,
                    "期交保费": 10000,
                },
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "销售机构名称": "上海",
                    "长短险": "一年期",
                    "产品代码": "4122",
                    "缴费年限": 1,
                    "期交保费": 3000,
                },
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "销售机构名称": "上海",
                    "长短险": "一年期",
                    "产品代码": "4281",
                    "缴费年限": 1,
                    "期交保费": 2000,
                },
            ]
        )
    )

    assert len(rows) == 1
    assert rows[0]["business_type"] == "转型"
    assert rows[0]["channel"] == "OTO"
    assert rows[0]["day"] == 1
    assert rows[0]["qj_premium"] == 1.2


def test_transform_longterm_keeps_daily_dimension():
    rows = aggregate_transform_longterm(
        pd.DataFrame(
            [
                {
                    "年": 2026,
                    "年月日": "2026-05-22",
                    "业务模式": "OTO",
                    "销售机构名称": "上海",
                    "长短险": "长期",
                    "产品代码": "4188",
                    "缴费年限": 5,
                    "期交保费": 10000,
                },
                {
                    "年": 2026,
                    "年月日": "2026-05-23",
                    "业务模式": "OTO",
                    "销售机构名称": "上海",
                    "长短险": "长期",
                    "产品代码": "4188",
                    "缴费年限": 5,
                    "期交保费": 20000,
                },
            ]
        )
    )

    by_day = {row["day"]: row["qj_premium"] for row in rows}
    assert by_day == {22: 1.0, 23: 2.0}


def test_jingdai_longterm_keeps_daily_dimension():
    rows = aggregate_jingdai_longterm(
        pd.DataFrame(
            [
                {"时间": "2026-05-21", "经代机构": "支付宝", "当前缴别大类": "期交", "缴费年限": 10, "期交保费": 10000},
                {"时间": "2026-05-22", "经代机构": "支付宝", "当前缴别大类": "期交", "缴费年限": 10, "期交保费": 20000},
                {"时间": "2026-05-23", "经代机构": "支付宝", "当前缴别大类": "期交", "缴费年限": 1, "期交保费": 99999},
            ]
        )
    )

    by_day = {row["day"]: row["qj_premium"] for row in rows}
    assert by_day == {21: 1.0, 22: 2.0}


def test_payment_period_treats_one_year_terms_as_shortterm():
    assert _classify_payment_period(1, "一年期") == "短期险"
    assert _classify_payment_period(1, "一年期以下") == "短期险"
    assert _classify_payment_period(3, "一年期以上") == "3年交"


def test_active_headcount_uses_longterm_terms_only():
    rows = aggregate_active_headcount(
        pd.DataFrame(
            [
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "长短险": "一年期以上",
                    "产品代码": "4188",
                    "缴费年限": 5,
                    "人员工号": "A001",
                    "期交保费": 10000,
                },
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "长短险": "一年期",
                    "产品代码": "4122",
                    "缴费年限": 1,
                    "人员工号": "A002",
                    "期交保费": 10000,
                },
                {
                    "年": 2026,
                    "年月": "202605",
                    "业务模式": "OTO",
                    "长短险": "一年期",
                    "产品代码": "4281",
                    "缴费年限": 1,
                    "人员工号": "A003",
                    "期交保费": 10000,
                },
            ]
        )
    )

    assert len(rows) == 1
    assert rows[0]["active_headcount"] == 2
