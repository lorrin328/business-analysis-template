import os
import sys

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from etl.aggregates.longterm import aggregate_transform_longterm
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
    assert rows[0]["qj_premium"] == 1.2


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
