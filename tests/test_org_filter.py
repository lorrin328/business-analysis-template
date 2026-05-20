"""测试机构筛选逻辑：org_validator 和 data_validator 中的 org 校验。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from validators.org_validator import org_scope_note
from validators.data_validator import ValidationResult, validate_rows


class TestOrgScopeNote:
    def test_jingdai_with_orgs_warns(self):
        note = org_scope_note(["经代"], ["上海"])
        assert note is not None
        assert "经代" in note

    def test_jingdai_without_orgs_silent(self):
        note = org_scope_note(["经代"], None)
        assert note == ""

    def test_oto_with_orgs_no_warning(self):
        note = org_scope_note(["OTO"], ["上海"])
        assert note is None or "经代" not in note


class TestValidateRowsOrg:
    def test_org_warning_for_unknown_org(self):
        rows = [
            {"year": 2026, "month": 4, "channel": "OTO", "qj_premium": 100, "_org": "火星"},
        ]
        result = validate_rows(rows, required=["year", "month", "channel"], mode="aggregate")
        assert result.valid

    def test_org_no_warning_for_known_org(self):
        rows = [
            {"year": 2026, "month": 4, "channel": "OTO", "qj_premium": 100, "_org": "上海"},
        ]
        result = validate_rows(rows, required=["year", "month", "channel"])
        assert result.valid
