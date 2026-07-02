import json

from honor.dashboard import build_honor_dashboard_payload


def test_honor_dashboard_builder_derives_tracking_sections():
    payload = build_honor_dashboard_payload(
        summary={"batch": {"year": 2026, "month": 5}, "overview": {"tracked_headcount": 1}},
        org_rows=[
            {
                "org": "上海",
                "business_line": "OTO",
                "tracked_headcount": 2,
                "member_count": 1,
                "member_rate": 0.5,
                "avg_diamond": 1.5,
                "monthly_gain_count": 1,
                "monthly_deduct_count": 1,
                "total_diamond": 3,
                "estimated_reward": 100,
            }
        ],
        person_summary=[
            {
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "1001",
                "staff_name": "张三",
                "role_type": "个人",
                "diamond_balance": 3,
                "membership_level": "初级会员",
                "warning_tags": "[]",
            },
            {
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "2001",
                "staff_name": "李四",
                "role_type": "主管",
                "diamond_balance": 0,
                "membership_level": "未入会",
                "warning_tags": "[]",
            },
        ],
        person_month=[
            {
                "month": 4,
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "2001",
                "staff_name": "李四",
                "role_type": "主管",
                "is_employed_end_month": 1,
                "diamond_delta": 1,
                "diamond_balance": 1,
                "membership_level": "初级会员",
                "standard_premium": 20000,
                "longterm_policy_count": 1,
                "monthly_qualified": 1,
            },
            {
                "month": 5,
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "1001",
                "staff_name": "张三",
                "role_type": "个人",
                "is_employed_end_month": 1,
                "diamond_delta": 1,
                "diamond_balance": 3,
                "membership_level": "初级会员",
                "standard_premium": 20000,
                "longterm_policy_count": 1,
                "monthly_qualified": 1,
            },
            {
                "month": 5,
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "2001",
                "staff_name": "李四",
                "role_type": "主管",
                "is_employed_end_month": 1,
                "diamond_delta": -1,
                "diamond_balance": 0,
                "membership_level": "未入会",
                "standard_premium": 0,
                "longterm_policy_count": 0,
                "monthly_qualified": 0,
            },
        ],
        source_staff=[
            {
                "month": 5,
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "1001",
                "staff_name": "张三",
                "role_type": "个人",
                "group_code": "G1",
                "department_code": "D1",
            },
            {
                "month": 5,
                "org": "上海",
                "business_line": "OTO",
                "staff_code": "2001",
                "staff_name": "李四",
                "role_type": "主管",
                "group_code": "G1",
                "department_code": "D1",
            },
        ],
        source_policy=[
            {"month": 5, "business_line": "OTO", "staff_code": "1001", "qj_premium": 20000, "standard_premium": 20000},
            {"month": 5, "business_line": "OTO", "staff_code": "2001", "qj_premium": 10000, "standard_premium": 10000},
        ],
        exceptions=[],
    )

    assert payload["projects"][0]["dimension"] == "OTO"
    assert payload["orgMemberStructure"][0]["specialist_member_count"] == 1
    assert payload["tracking"]["overview"]["total_members"] == 1
    assert payload["tracking"]["overview"]["personal_members"] == 1
    assert payload["tracking"]["orgMembers"][0]["org"] == "上海"
    assert payload["tracking"]["newMembers"][0]["staff_name"] == "张三"
    assert payload["tracking"]["topContributors"][0]["staff_code"] == "1001"
    assert payload["tracking"]["memberRoster"][0]["membership_level"] == "初级会员"
    assert payload["levels"] == [{"level": "初级会员", "count": 1, "share": 1.0}]
    assert payload["specialistHistory"][0]["qj_premium"] == 20000
    assert payload["managerHistory"][0]["team_qj_premium"] == 30000
    assert payload["warnings"][0]["warning_type"] == "等级下降"
    assert payload["trend"][-1]["month"] == 5


def test_honor_tracking_policy_count_excludes_one_year_medical_policy():
    payload = build_honor_dashboard_payload(
        summary={"batch": {"year": 2026, "month": 6}, "overview": {}},
        org_rows=[],
        person_summary=[
            {
                "org": "福建",
                "business_line": "OTO",
                "staff_code": "1001",
                "staff_name": "张三",
                "role_type": "个人",
                "diamond_balance": 6,
                "membership_level": "中级会员",
                "warning_tags": "[]",
            }
        ],
        person_month=[
            {
                "month": 6,
                "org": "福建",
                "business_line": "OTO",
                "staff_code": "1001",
                "staff_name": "张三",
                "role_type": "个人",
                "is_employed_end_month": 1,
                "diamond_delta": 1,
                "diamond_balance": 6,
                "membership_level": "中级会员",
                "standard_premium": 30000,
                "longterm_policy_count": 2,
                "monthly_qualified": 1,
            }
        ],
        source_staff=[],
        source_policy=[
            {
                "month": 6,
                "business_line": "OTO",
                "staff_code": "1001",
                "policy_no": "P_LONG",
                "is_longterm": 1,
                "standard_premium": 30000,
                "raw_payload": json.dumps({"长短险": "一年期以上", "产品名称": "长期产品"}, ensure_ascii=False),
            },
            {
                "month": 6,
                "business_line": "OTO",
                "staff_code": "1001",
                "policy_no": "P_MEDICAL",
                "is_longterm": 1,
                "standard_premium": 180,
                "raw_payload": json.dumps({"长短险": "一年期", "产品名称": "医疗保险"}, ensure_ascii=False),
            },
        ],
        exceptions=[],
    )

    top = payload["tracking"]["topContributors"][0]
    assert top["longterm_policy_count"] == 2
    assert top["tracking_policy_count"] == 1
