import csv
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from auth import ROLE_DEFAULT_PERMISSIONS
from branch_analysis.repository import import_reference_csv
from main import app


def _login(client: TestClient, username="admin", password="Test-only-admin-2026!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]


def _headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def _seed_branch_data():
    import db.connection as connection

    with connection.get_db() as conn:
        existing = {row["name"] for row in conn.execute('PRAGMA table_info("performance")')}
        for column, kind in [
            ("年月日", "TEXT"),
            ("人员工号", "TEXT"),
            ("投保单号", "TEXT"),
            ("证券方营业网点名称", "TEXT"),
            ("证券方销售人员工号", "TEXT"),
        ]:
            if column not in existing:
                conn.execute(f'ALTER TABLE performance ADD COLUMN "{column}" {kind}')
        batch = conn.execute(
            """
            INSERT INTO branch_reference_batches
                (file_name, file_hash, regular_count, referral_count, imported_by)
            VALUES ('branch-reference.csv', 'test-hash', 2, 1, 'pytest')
            """
        ).lastrowid
        conn.executemany(
            """
            INSERT INTO branch_reference (
                reference_id, batch_id, branch_type, branch_name, parent_name,
                province, city, grade, project, subproject, locality,
                include_in_regular_count, source_row
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("REG-001", batch, "常规网点", "测试证券一号营业部", "测试证券", "广东省", "广州市", "A", "广东项目", "广东项目", "本地", 1, 2),
                ("REG-002", batch, "常规网点", "广发证券股份有限公司", "广发证券股份有限公司", "广东省", "深圳市", "B", "广东项目", "广东项目", "异地", 1, 3),
                ("REF-001", batch, "转介绍网点", "广发转介绍测试网点", "广发证券股份有限公司", "广东省", "广州市", "", "广发转介绍", "广发转介绍", "本地", 0, 151),
            ],
        )
        conn.executemany(
            """
            INSERT INTO performance (
                "年月", "年月日", "业务模式", "销售机构名称", "人员工号",
                "投保单号", "证券方营业网点名称", "证券方销售人员工号", "期交保费"
            ) VALUES (?, ?, '证券', ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-07", "2026-07-28", "广东", "A001", "P-2026-1", "测试证券一号营业部", "S001", 100000),
                ("2026-07", "2026-07-28", "广东", "A002", "P-2026-2", "广发证券股份有限公司", "S002", 30000),
                ("2026-07", "2026-07-28", "广东", "A003", "P-2026-3", "待匹配网点", "S003", 10000),
                ("2025-07", "2025-07-28", "广东", "A001", "P-2025-1", "测试证券一号营业部", "S001", 50000),
                ("2025-07", "2025-07-28", "广东", "A004", "P-2025-2", "测试证券二号营业部", "S004", 20000),
            ],
        )
        conn.commit()


def _seed_first_quarter_data():
    import db.connection as connection

    with connection.get_db() as conn:
        conn.executemany(
            """
            INSERT INTO performance (
                "年月", "年月日", "业务模式", "销售机构名称", "人员工号",
                "投保单号", "证券方营业网点名称", "证券方销售人员工号", "期交保费"
            ) VALUES (?, ?, '证券', ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-01", "2026-01-15", "广东", "A005", "P-2026-01", "测试证券一号营业部", "S005", 20000),
                ("2025-01", "2025-01-15", "广东", "A006", "P-2025-01", "测试证券一号营业部", "S006", 10000),
            ],
        )
        conn.commit()


def test_branch_overview_separates_regular_and_referral_counts(auth_db):
    _seed_branch_data()
    client = TestClient(app)
    login = _login(client)
    response = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28",
        headers=_headers(login["token"]),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["premiumWan"] == 14
    assert data["summary"]["regularStock"] == 2
    assert data["summary"]["activeRegular"] == 2
    assert data["summary"]["regularActivityRate"] == 1
    assert data["summary"]["referralStockExcluded"] == 1
    assert data["summary"]["referralPremiumWan"] == 3
    assert data["summary"]["unmatchedPremiumWan"] == 1
    assert data["summary"]["matchedPremiumRate"] == pytest.approx(13 / 14)
    assert len(data["regularBranches"]) == 2
    assert data["regularBranches"][0]["status"] == "持续经营"
    assert data["regularBranches"][1]["status"] == "新增/恢复"
    assert len(data["referralBranches"]) == 1


def test_branch_period_filters_recalculate_month_quarter_and_year(auth_db):
    _seed_branch_data()
    _seed_first_quarter_data()
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])

    annual = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=year",
        headers=headers,
    )
    assert annual.status_code == 200
    annual_data = annual.json()["data"]
    assert annual_data["summary"]["premiumWan"] == 16
    assert annual_data["summary"]["previousPremiumWan"] == 8
    assert annual_data["meta"]["periodLabel"] == "2026年度累计"
    assert annual_data["meta"]["periodStart"] == "2026-01-01"
    assert annual_data["meta"]["asOf"] == "2026-07-28"

    july = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=month&periodValue=7",
        headers=headers,
    )
    assert july.status_code == 200
    july_data = july.json()["data"]
    assert july_data["summary"]["premiumWan"] == 14
    assert july_data["summary"]["previousPremiumWan"] == 7
    assert july_data["meta"]["periodLabel"] == "2026年7月"
    assert july_data["meta"]["periodStart"] == "2026-07-01"
    assert july_data["meta"]["previousPeriodStart"] == "2025-07-01"

    first_quarter = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=quarter&periodValue=1",
        headers=headers,
    )
    assert first_quarter.status_code == 200
    quarter_data = first_quarter.json()["data"]
    assert quarter_data["summary"]["premiumWan"] == 2
    assert quarter_data["summary"]["previousPremiumWan"] == 1
    assert quarter_data["meta"]["periodLabel"] == "2026年Q1"
    assert quarter_data["meta"]["asOf"] == "2026-03-31"
    assert quarter_data["meta"]["previousAsOf"] == "2025-03-31"

    third_quarter = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=quarter&periodValue=3",
        headers=headers,
    )
    assert third_quarter.status_code == 200
    assert third_quarter.json()["data"]["summary"]["premiumWan"] == 14
    assert third_quarter.json()["data"]["meta"]["asOf"] == "2026-07-28"


def test_branch_period_filters_reject_missing_invalid_and_future_periods(auth_db):
    _seed_branch_data()
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])

    missing = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=quarter",
        headers=headers,
    )
    assert missing.status_code == 422
    assert "1至4季度" in missing.json()["detail"]

    invalid = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=quarter&periodValue=5",
        headers=headers,
    )
    assert invalid.status_code == 422
    assert "1至4季度" in invalid.json()["detail"]

    future = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28&periodType=quarter&periodValue=4",
        headers=headers,
    )
    assert future.status_code == 422
    assert "尚未到达统计截止日" in future.json()["detail"]


def test_reference_import_is_transactional_and_count_guarded(auth_db, tmp_path: Path):
    source = tmp_path / "证保网点参考表.csv"
    fields = [
        "参考编号", "网点类型", "证券网点", "归属主体", "所在省", "所在市",
        "网点等级", "机构类项目", "机构类项目细分", "本地异地", "纳入常规网点数", "源表行号",
    ]
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "参考编号": "REG-001", "网点类型": "常规网点", "证券网点": "常规测试网点",
                    "归属主体": "测试证券", "所在省": "浙江省", "所在市": "杭州市", "网点等级": "A",
                    "机构类项目": "浙江项目", "机构类项目细分": "浙江项目", "本地异地": "本地",
                    "纳入常规网点数": "是", "源表行号": "2",
                },
                {
                    "参考编号": "REF-001", "网点类型": "转介绍网点", "证券网点": "转介绍测试网点",
                    "归属主体": "广发证券股份有限公司", "所在省": "广东省", "所在市": "广州市", "网点等级": "",
                    "机构类项目": "广发转介绍", "机构类项目细分": "广发转介绍", "本地异地": "异地",
                    "纳入常规网点数": "否", "源表行号": "151",
                },
            ]
        )
    result = import_reference_csv(source, imported_by="pytest", expected_regular=1, expected_referral=1)
    assert result["regularCount"] == 1
    assert result["referralCount"] == 1
    with pytest.raises(ValueError, match="确认口径"):
        import_reference_csv(source)


def test_branch_page_permission_and_static_runtime(auth_db):
    client = TestClient(app)
    page = client.get("/branch-analysis")
    assert page.status_code == 200
    assert "常规网点147个" in page.text
    assert 'id="periodType"' in page.text
    assert 'id="periodValue"' in page.text
    assert "/js/branch-analysis.js" in page.text
    script = client.get("/js/branch-analysis.js")
    assert script.status_code == 200
    assert "query.set('periodType', periodType)" in script.text
    assert "query.set('periodValue', periodValue)" in script.text
    assert ROLE_DEFAULT_PERMISSIONS["admin"]["branch_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["branch_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["normal"]["branch_analysis"] is False

    registered = client.post("/api/auth/register", json={"username": "branch_normal", "password": "normal-pass-123"})
    assert registered.status_code == 200
    user = registered.json()["data"]
    assert user["user"]["permissions"]["branch_analysis"] is False
    assert client.get(
        "/api/branch-analysis/overview",
        headers=_headers(user["token"]),
    ).status_code == 403
