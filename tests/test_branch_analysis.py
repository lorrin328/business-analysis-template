import csv
import hashlib
import re
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


def _seed_non_branch_cutoff_data():
    import db.connection as connection

    with connection.get_db() as conn:
        conn.executemany(
            '''
            INSERT INTO performance (
                "年月", "年月日", "业务模式", "销售机构名称", "人员工号",
                "投保单号", "证券方营业网点名称", "证券方销售人员工号", "期交保费"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                ("2026-08", "2026-08-17", "OTO", "广东", "A999", "P-OTO-2026", "", "", 999999),
                ("2025-08", "2025-08-16", "证券", "广东", "A007", "P-2025-08", "测试证券一号营业部", "S007", 10000),
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
    assert data["regularBranches"][0]["externalSellers"] == 1
    assert data["regularBranches"][0]["internalAgents"] == 1
    assert data["regularBranches"][1]["status"] == "新增/恢复"
    assert len(data["referralBranches"]) == 1


def test_branch_cutoff_uses_full_performance_coverage_not_last_branch_sale(auth_db):
    _seed_branch_data()
    _seed_non_branch_cutoff_data()
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])

    annual = client.get(
        "/api/branch-analysis/overview?year=2026&periodType=year",
        headers=headers,
    )
    assert annual.status_code == 200
    annual_data = annual.json()["data"]
    assert annual_data["meta"]["performanceCutoff"] == "2026-08-17"
    assert annual_data["meta"]["asOf"] == "2026-08-17"
    assert annual_data["meta"]["lastBranchBusinessDate"] == "2026-07-28"
    assert annual_data["meta"]["previousAsOf"] == "2025-08-17"
    assert annual_data["summary"]["premiumWan"] == 14
    assert annual_data["summary"]["previousPremiumWan"] == 8

    august = client.get(
        "/api/branch-analysis/overview?year=2026&periodType=month&periodValue=8",
        headers=headers,
    )
    assert august.status_code == 200
    august_data = august.json()["data"]
    assert august_data["meta"]["asOf"] == "2026-08-17"
    assert august_data["meta"]["lastBranchBusinessDate"] is None
    assert august_data["summary"]["premiumWan"] == 0
    assert august_data["summary"]["previousPremiumWan"] == 1
    assert august_data["summary"]["activeRegular"] == 0


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


def test_branch_page_permission_and_static_runtime(auth_db, approved_user):
    client = TestClient(app)
    page = client.get("/branch-analysis")
    assert page.status_code == 200
    assert 'id="scopeNotice"' in page.text
    assert 'data-tab="followup"' in page.text
    assert 'id="periodType"' in page.text
    assert 'id="periodValue"' in page.text
    assert "/js/branch-analysis.js" in page.text
    script = client.get("/js/branch-analysis.js")
    assert script.status_code == 200
    assert "query.set('periodType', periodType)" in script.text
    assert "query.set('periodValue', periodValue)" in script.text
    assert "数据截至 ${state.data.meta.performanceCutoff}" in script.text
    assert "lastBranchBusinessDate" in script.text
    assert "integer(item.internalAgents)" in script.text
    assert "regularStock" in script.text
    assert "出单天数" in script.text
    assert "待匹配" in script.text
    assert "券商及太平人员均按出单工号去重" in script.text
    branch_tag = re.search(r'/js/branch-analysis\.js\?v=\d+\.\d+\.\d+-([0-9a-f]{12})', page.text)
    assert branch_tag, "网点分析脚本必须携带内容哈希以刷新代理和浏览器缓存"
    normalized_script = script.text.replace("\r\n", "\n")
    assert branch_tag.group(1) == hashlib.sha256(normalized_script.encode("utf-8")).hexdigest()[:12]
    assert ROLE_DEFAULT_PERMISSIONS["admin"]["branch_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["branch_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["normal"]["branch_analysis"] is False

    user = approved_user(client, "branch_normal", "normal-pass-123")
    assert user["user"]["permissions"]["branch_analysis"] is False
    assert client.get(
        "/api/branch-analysis/overview",
        headers=_headers(user["token"]),
    ).status_code == 403


def test_branch_large_policy_and_structure_indicators(auth_db):
    _seed_branch_data()
    import db.connection as connection
    with connection.get_db() as conn:
        existing = {row["name"] for row in conn.execute('PRAGMA table_info("performance")')}
        if "缴费年限" not in existing:
            conn.execute('ALTER TABLE performance ADD COLUMN "缴费年限" INTEGER')
        conn.execute(
            """
            INSERT INTO performance (
                "年月", "年月日", "业务模式", "销售机构名称", "人员工号",
                "投保单号", "证券方营业网点名称", "证券方销售人员工号", "期交保费", "缴费年限"
            ) VALUES ('2026-07', '2026-07-28', '证券', '广东', 'A009', 'P-LARGE-1', '测试证券一号营业部', 'S009', 1200000, 10)
            """
        )
        conn.commit()

    client = TestClient(app)
    login = _login(client)
    res = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28",
        headers=_headers(login["token"]),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    s = data["summary"]
    assert s["premiumWan"] == 134.0
    assert s["largePremiumWan"] == 120.0
    assert s["largePolicies"] == 1
    assert s["regularPlatformWan"] == 14.0
    assert s["largeShare"] == pytest.approx(120.0 / 134.0)
    assert s["longTerm10yPremiumWan"] == 120.0
    assert s["longTerm10yShare"] == 1
    assert s["termCoverage"] == pytest.approx(120.0 / 134.0)
    assert s["unknownTermPositivePremiumWan"] == 14.0


def test_branch_tiers_pareto_and_brokers(auth_db):
    _seed_branch_data()
    client = TestClient(app)
    login = _login(client)
    res = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28",
        headers=_headers(login["token"]),
    )
    assert res.status_code == 200
    data = res.json()["data"]

    # Tiers check
    assert len(data["tiers"]) == 5
    tier_counts = sum(t["count"] for t in data["tiers"])
    assert tier_counts == data["summary"]["regularStock"]

    # Pareto check
    assert "top5Share" in data["pareto"]
    assert "top10Share" in data["pareto"]
    assert "pareto20PercentShare" in data["pareto"]
    assert len(data["pareto"]["series"]) > 0

    # Brokers check
    assert len(data["brokers"]) > 0
    broker_names = {b["broker"] for b in data["brokers"]}
    assert "测试证券" in broker_names or "广发证券股份有限公司" in broker_names


def test_branch_quadrant_and_insights(auth_db):
    _seed_branch_data()
    client = TestClient(app)
    login = _login(client)
    res = client.get(
        "/api/branch-analysis/overview?year=2026&asOf=2026-07-28",
        headers=_headers(login["token"]),
    )
    assert res.status_code == 200
    data = res.json()["data"]

    # Quadrant
    assert len(data["quadrant"]) == data["summary"]["regularStock"]
    assert "quadrant" in data["quadrant"][0]
    assert "quadrantLabel" in data["quadrant"][0]

    # Monthly Trend
    assert isinstance(data["monthlyTrend"], list)

    # Insights
    ins = data["insights"]
    assert "platformDiagnosis" in ins
    assert "level" in ins["platformDiagnosis"]
    assert "dormantAlerts" in ins
    assert "localityComparison" in ins
    assert "local" in ins["localityComparison"]
    assert "remote" in ins["localityComparison"]

def _insert_branch_rows(rows):
    import db.connection as connection

    with connection.get_db() as conn:
        columns = {row["name"] for row in conn.execute('PRAGMA table_info("performance")')}
        if "缴费年限" not in columns:
            conn.execute('ALTER TABLE performance ADD COLUMN "缴费年限" TEXT')
        conn.executemany(
            """
            INSERT INTO performance (
                "年月", "年月日", "业务模式", "销售机构名称", "人员工号", "投保单号",
                "证券方营业网点名称", "证券方销售人员工号", "期交保费", "缴费年限"
            ) VALUES (?, ?, '证保', ?, 'A001', ?, ?, 'S001', ?, ?)
            """,
            [(day[:7], day, org, policy, branch, premium, term)
             for day, org, policy, branch, premium, term in rows],
        )
        conn.commit()


def test_branch_monthly_and_period_netting_reconcile_signed_and_unknown_premiums(auth_db):
    from datetime import date
    from branch_analysis.analyzer import analyze_branch_network

    _seed_branch_data()
    regular = "测试证券一号营业部"
    parent = "广发证券股份有限公司"
    _insert_branch_rows([
        ("2026-06-10", "广东", "SPLIT", regular, 600000, "10.0"),
        ("2026-06-21", "广东", "SPLIT", regular, 500000, "10.0"),
        ("2026-07-03", "广东", "SPLIT", regular, -150000, None),
        ("2026-06-17", "山东", "REVERSAL", parent, 200000, "5"),
        ("2026-07-09", "山东", "REVERSAL", parent, -200000, "5"),
        ("2026-07-11", "广东", "ZERO", regular, 15000, "3"),
        ("2026-07-11", "广东", "ZERO", regular, -15000, "3"),
        ("2026-07-15", "山东", "NEG", parent, -50000, None),
        ("2026-07-19", "北京", "UNMATCHED-NEG", "", -20000, None),
        ("2026-07-20", "广东", None, regular, 1200000, "10"),
        ("2026-07-21", "广东", "CONFLICT", regular, 8000, "5"),
        ("2026-07-22", "广东", "CONFLICT", regular, 2000, "10"),
    ])
    annual = analyze_branch_network(year=2026, as_of=date(2026, 7, 28))
    s = annual["summary"]
    assert s["premiumWan"] == 223
    assert s["policies"] == 5
    assert s["largePremiumWan"] == 0 and s["largeShare"] == 0
    assert s["regularPlatformWan"] == 110
    assert s["netNegativePremiumWan"] == -7
    assert s["unclassifiedPositivePremiumWan"] == 120
    assert s["premiumWan"] == s["regularPlatformWan"] + s["largePremiumWan"] + s["netNegativePremiumWan"] + s["unclassifiedPositivePremiumWan"]
    assert s["termCoverage"] == pytest.approx(95 / 110)
    assert s["longTerm10yShare"] == 1
    assert annual["quality"]["missingPolicyRows"] == 1
    assert s["referralOverlapPremiumWan"] == s["referralPremiumWan"] == -2
    assert s["unmatchedPremiumWan"] == -1
    assert s["matchedPremiumRate"] <= 1

    months = {item["month"]: item for item in annual["monthlyTrend"]}
    assert len(months) == 7 and months["2026-05"]["totalWan"] == 0
    assert months["2026-06"]["policies"] == 2 and months["2026-06"]["largePolicies"] == 1
    assert months["2026-07"]["policies"] == 4 and months["2026-07"]["netNegativeWan"] == -42
    assert months["2026-07"]["activeBranches"] == 2
    assert sum(item["totalWan"] for item in months.values()) == s["premiumWan"]
    assert sum(item["policies"] for item in months.values()) == 6

    july = analyze_branch_network(year=2026, as_of=date(2026, 7, 28), period_type="month", period_value=7)
    assert july["quadrant"] == [] and july["meta"]["matrixWindow"] is None
    assert july["summary"]["policies"] == months["2026-07"]["policies"]
    by_name = {item["branch"]: item for item in july["regularBranches"]}
    assert by_name[regular]["activeDays"] == 3
    assert by_name[parent]["premiumWan"] == -22 and by_name[parent]["policies"] == 1
    assert by_name[parent]["tierName"] == "净期交≤0"
    assert july["summary"]["activeRegular"] == 2


def test_branch_matrix_uses_complete_months_and_dormant_uses_policy_status(auth_db):
    from datetime import date
    from branch_analysis.analyzer import analyze_branch_network

    _seed_branch_data()
    regular = "测试证券一号营业部"
    parent = "广发证券股份有限公司"
    _insert_branch_rows([
        ("2026-04-09", "广东", "APR", regular, 100000, "3"),
        ("2026-05-09", "广东", "MAY", regular, 100000, "3"),
        ("2026-06-20", "广东", "APR", regular, -10000, "3"),
        ("2026-07-29", "广东", "LATER", regular, 900000, "3"),
        ("2025-06-18", "山东", "PRIOR", parent, 30000, "5"),
        ("2026-06-18", "北京", "ONLY-REV", parent, -10000, "5"),
        ("2026-06-18", "北京", "NO-NUMBER", "未识别网点", 30000, "5"),
    ])
    annual = analyze_branch_network(year=2026, as_of=date(2026, 7, 28))
    window = annual["meta"]["matrixWindow"]
    assert (window["start"], window["end"]) == ("2026-04-01", "2026-06-30")
    assert window["available"]
    points = {point["branch"]: point for point in annual["quadrant"]}
    assert points[regular]["premiumWan"] == 19
    assert points[regular]["activeMonths"] == 2
    assert points[regular]["quadrant"] == "III"
    assert annual["summary"]["continuedRegular"] == 2
    second_quarter = analyze_branch_network(year=2026, as_of=date(2026, 7, 28), period_type="quarter", period_value=2)
    dormant = second_quarter["insights"]["dormantAlerts"]
    assert any(item["branch"] == parent and item["premiumWan"] == -1 and item["previousOrgs"] == ["山东"] for item in dormant)
    assert second_quarter["quality"]["unmatchedBranches"][0]["orgs"] == ["北京"]


def test_branch_matrix_without_three_covered_months_reports_unavailable(auth_db):
    from datetime import date
    from branch_analysis.analyzer import analyze_branch_network

    _seed_branch_data()
    result = analyze_branch_network(year=2025, as_of=date(2025, 7, 28))
    assert result["meta"]["matrixWindow"]["available"] is False
    assert result["quadrant"] == []
