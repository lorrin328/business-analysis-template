import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def test_honor_export_builds_workbook(auth_db):
    from honor.repository import create_batch, replace_calculation_results
    from honor.exporter import build_honor_export_workbook

    batch_id = create_batch(year=2026, month=5, rule_version="2026-v1", created_by="pytest")
    replace_calculation_results(
        batch_id,
        {
            "org_summary": [{"batch_id": batch_id, "year": 2026, "month": 5, "org": "上海", "business_line": "OTO", "tracked_headcount": 1}],
            "person_summary": [{"batch_id": batch_id, "year": 2026, "latest_month": 5, "org": "上海", "business_line": "OTO", "staff_code": "1001", "membership_level": "初级会员"}],
            "person_month": [{"batch_id": batch_id, "year": 2026, "month": 5, "org": "上海", "business_line": "OTO", "staff_code": "1001", "membership_level": "初级会员"}],
            "quarter_rewards": [],
            "exceptions": [],
            "source_staff_month": [],
            "source_policy": [],
        },
        0,
    )
    content = build_honor_export_workbook(batch_id)
    assert content.startswith(b"PK")
    assert len(content) > 1000
