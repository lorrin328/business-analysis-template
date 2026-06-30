from honor.summary import build_org_summary, build_quarter_rewards


def test_honor_build_org_summary_uses_current_employed_members():
    summaries = [
        {
            "org": "上海",
            "business_line": "OTO",
            "staff_code": "1001",
            "staff_name": "张三",
            "membership_level": "资深会员",
            "diamond_balance": 12,
        },
        {
            "org": "上海",
            "business_line": "OTO",
            "staff_code": "2001",
            "staff_name": "李四",
            "membership_level": "未入会",
            "diamond_balance": 0,
        },
    ]
    months = [
        {"year": 2026, "month": 5, "staff_code": "1001", "business_line": "OTO", "is_employed_end_month": 1, "diamond_delta": 1},
        {"year": 2026, "month": 5, "staff_code": "2001", "business_line": "OTO", "is_employed_end_month": 0, "diamond_delta": -1},
    ]

    rows = build_org_summary(7, 2026, 5, summaries, months)

    row = rows[0]
    assert row["tracked_headcount"] == 1
    assert row["member_count"] == 1
    assert row["senior_plus_count"] == 1
    assert row["monthly_gain_count"] == 1
    assert row["monthly_deduct_count"] == 1
    assert row["member_rate"] == 1
    assert row["estimated_reward"] == 100


def test_honor_build_quarter_rewards_uses_calendar_quarter():
    rows = build_quarter_rewards(
        7,
        2026,
        5,
        [
            {
                "org": "上海",
                "staff_code": "1001",
                "staff_name": "张三",
                "membership_level": "钻石会员",
            }
        ],
    )

    assert rows == [
        {
            "batch_id": 7,
            "year": 2026,
            "quarter": 2,
            "org": "上海",
            "staff_code": "1001",
            "staff_name": "张三",
            "membership_level": "钻石会员",
            "reward_amount": 200,
            "reward_label": "黄金至至尊测算奖励",
            "is_estimated": 1,
        }
    ]
