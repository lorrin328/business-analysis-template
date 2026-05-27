import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def _patch_db(monkeypatch, path):
    import db.connection as connection

    monkeypatch.setattr(connection, "DB_PATH", str(path))


def test_field_audit_reports_missing_raw_tables(tmp_path, monkeypatch):
    _patch_db(monkeypatch, tmp_path / "missing.db")
    from honor.field_audit import audit_fields

    result = audit_fields()

    assert result["rawTables"]["performance"]["exists"] is False
    assert result["rawTables"]["hr_data"]["exists"] is False
    assert result["canReuseExistingData"] is False


def test_field_audit_matches_synonyms_and_grades_team_gap(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE hr_data ("统计年" INTEGER, "统计月" INTEGER, "机构" TEXT, "业务线" TEXT, "工号" TEXT, "人员姓名" TEXT, "入职年" INTEGER, "入职月" INTEGER, "在职状态" INTEGER)')
    conn.execute('CREATE TABLE performance ("业务线" TEXT, "工号" TEXT, "保单号" TEXT, "长短险" TEXT, "标保" REAL, "年月" TEXT)')
    conn.commit()
    conn.close()
    _patch_db(monkeypatch, db_path)

    from honor.field_audit import audit_fields

    result = audit_fields()
    hr_fields = {row["requiredField"]: row for row in result["rawTables"]["hr_data"]["fields"]}
    perf_fields = {row["requiredField"]: row for row in result["rawTables"]["performance"]["fields"]}

    assert hr_fields["销售机构名称"]["matchedColumn"] == "机构"
    assert hr_fields["业务模式名称"]["matchedColumn"] == "业务线"
    assert hr_fields["人员代码"]["matchedColumn"] == "工号"
    assert perf_fields["折算保费"]["matchedColumn"] == "标保"
    team_rule = next(row for row in result["ruleAssessment"] if row["rule"] == "主管团队星钻")
    assert team_rule["grade"] == "C"
