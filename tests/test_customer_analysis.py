import csv
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from auth import ROLE_DEFAULT_PERMISSIONS
from history_import.importer import CUSTOMER_COLUMNS, PERFORMANCE_COLUMNS, FullHistoryImporter, _normalize_source_text
from main import app


def _login(client: TestClient, username="admin", password="Test-only-admin-2026!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]


def _headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def _seed_customer_analysis():
    import db.connection as connection

    with connection.get_db() as conn:
        batch_id = conn.execute(
            """INSERT INTO history_import_batches
               (source_directory, source_cutoff, performance_rows, customer_source_rows,
                customer_policy_rows, source_text_issue_rows, status, completed_at)
               VALUES ('fixture', '2026-07-31 12:21:12', 4, 3, 3, 0, 'success', CURRENT_TIMESTAMP)"""
        ).lastrowid
        conn.executemany(
            """INSERT INTO customer_master
               (customer_id, first_underwriting_time, first_policy_no, total_policy_count,
                active_policy_count, suspended_policy_count, terminated_policy_count, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("C-NEW-1", "2026-01-10 10:00:00", "P-1", 1, 1, 0, 0, batch_id),
                ("C-OLD-1", "2025-06-01 10:00:00", "P-OLD", 2, 1, 0, 1, batch_id),
                ("C-NEW-2", "2026-02-03 10:00:00", "P-3", 1, 0, 0, 1, batch_id),
            ],
        )
        conn.executemany(
            """INSERT INTO customer_policy_snapshot
               (policy_no, customer_id, underwriting_time, policy_status, termination_reason,
                status_group, raw_row_count, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            [
                ("P-1", "C-NEW-1", "2026-01-10", "有效", "", "active", batch_id),
                ("P-OLD", "C-OLD-1", "2025-06-01", "有效", "", "active", batch_id),
                ("P-2", "C-OLD-1", "2026-02-05", "终止", "退保终止", "surrender", batch_id),
                ("P-3", "C-NEW-2", "2026-02-03", "终止", "契撤终止", "cooling_off", batch_id),
            ],
        )
        conn.executemany(
            """INSERT INTO customer_policy_month_fact
               (year, month, transaction_date, business_line, org, policy_no, customer_id,
                underwriting_time, first_customer_underwriting_time, is_longterm, qj_premium,
                gm_premium, zs_premium, value_premium, accepted_count, policy_status,
                termination_reason, status_group, customer_match, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 1, ?, ?, ?, ?, ?)""",
            [
                (2026, 1, "2026-01-10", "OTO", "上海", "P-1", "C-NEW-1", "2026-01-10", "2026-01-10", 1, 100000, "有效", "", "active", 1, batch_id),
                (2026, 2, "2026-02-05", "OTO", "上海", "P-2", "C-OLD-1", "2026-02-05", "2025-06-01", 1, 50000, "终止", "退保终止", "surrender", 1, batch_id),
                (2026, 2, "2026-02-03", "证保", "北京", "P-3", "C-NEW-2", "2026-02-03", "2026-02-03", 1, 30000, "终止", "契撤终止", "cooling_off", 1, batch_id),
                (2026, 3, "2026-03-01", "蚁桥", "广东", "P-4", None, None, None, 0, 20000, None, None, "unmatched", 0, batch_id),
            ],
        )
        conn.commit()


def test_customer_analysis_business_metrics_and_status_boundary(auth_db):
    _seed_customer_analysis()
    client = TestClient(app)
    login = _login(client)
    response = client.get("/api/customer-analysis/overview?year=2026", headers=_headers(login["token"]))
    assert response.status_code == 200
    data = response.json()["data"]
    summary = data["summary"]
    assert summary["customers"] == 3
    assert summary["policies"] == 4
    assert summary["qjPremiumWan"] == 20
    assert summary["newCustomers"] == 2
    assert summary["existingCustomers"] == 1
    assert summary["newQjPremiumWan"] == 13
    assert summary["existingQjPremiumWan"] == 5
    assert summary["unknownQjPremiumWan"] == 2
    assert summary["newPremiumShare"] == pytest.approx(13 / 18)
    assert summary["activePolicies"] == 1
    assert summary["surrenderPolicies"] == 1
    assert summary["coolingOffPolicies"] == 1
    assert summary["policyMatchRate"] == pytest.approx(3 / 4)
    assert sum(item["policies"] for item in data["statusDistribution"]) == 4
    assert data["quality"]["definitions"]["policyStatus"].endswith("不等同于13个月或25个月继续率。")
    holdings = data["holdings"]
    assert holdings["summary"]["coveredCustomers"] == 3
    assert holdings["summary"]["multiPolicyCustomers"] == 1
    assert holdings["summary"]["multiPolicyRate"] == pytest.approx(1 / 3)
    assert holdings["summary"]["customersWithActivePolicy"] == 2
    assert holdings["summary"]["zeroActiveCustomers"] == 1
    assert holdings["summary"]["firstRepeatEligibleCustomers"] == 1
    assert sum(item["customers"] for item in holdings["policyCountBands"]) == 3
    assert sum(item["customers"] for item in holdings["activePolicyCountBands"]) == 3


def test_customer_analysis_month_segment_and_permission(auth_db):
    _seed_customer_analysis()
    client = TestClient(app)
    admin = _login(client)
    february = client.get(
        "/api/customer-analysis/overview?year=2026&periodType=month&periodValue=2",
        headers=_headers(admin["token"]),
    )
    assert february.status_code == 200
    data = february.json()["data"]
    assert data["summary"]["newCustomers"] == 1
    assert data["summary"]["existingCustomers"] == 1
    assert data["summary"]["newQjPremiumWan"] == 3
    assert data["summary"]["existingQjPremiumWan"] == 5

    registered = client.post("/api/auth/register", json={"username": "customer_normal", "password": "normal-pass-123"})
    assert registered.status_code == 200
    normal = registered.json()["data"]
    assert normal["user"]["permissions"]["customer_analysis"] is False
    assert client.get("/api/customer-analysis/overview", headers=_headers(normal["token"])).status_code == 403
    assert ROLE_DEFAULT_PERMISSIONS["admin"]["customer_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["customer_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["normal"]["customer_analysis"] is False


def _performance_row(year: int, policy_no: str, staff_code: str):
    row = {column: "" for column in PERFORMANCE_COLUMNS}
    row.update({
        "年": str(year), "年季": f"{year}Q1", "年月": f"{year}-01-01", "年月日": f"{year}-01-15",
        "销售机构名称": "上海", "业务模式": "OTO", "人员工号": staff_code,
        "投保单号": policy_no, "投保时间": f"{year}-01-10 09:00:00",
        "承保时间": f"{year}-01-15 10:00:00", "入账时间": f"{year}-01-15 10:01:00",
        "长短险": "长险", "缴费年限": "10", "投保人id": f"C-{policy_no}",
        "期交保费": "10000", "折算保费": "10000", "年化规保": "10000",
        "价值规保": "8000", "承保件数": "1",
    })
    return row


def _customer_row(policy_no: str, year: int):
    return {
        "投保单号": policy_no, "投保人id": f"C-{policy_no}", "投保时间": f"{year}-01-10 09:00:00",
        "导入时间": "2026-07-31 12:00:00", "回销时间": f"{year}-01-12 09:00:00",
        "承保时间": f"{year}-01-15 10:00:00", "入账时间": f"{year}-01-15 10:01:00",
        "犹豫期退保时间": "", "保单状态名称": "有效", "保单终止原因": "",
    }


def test_full_history_import_is_chunked_audited_and_policy_grained(auth_db, tmp_path: Path):
    import db.connection as connection

    source = tmp_path / "full"
    source.mkdir()
    policies = []
    for index in range(12):
        year = 2015 + index
        policy = f"99{index + 1:013d}"
        policies.append((policy, year))
        path = source / f"AI-电商业绩_fixture_{index:02d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PERFORMANCE_COLUMNS)
            writer.writeheader()
            row = _performance_row(year, policy, "A�01" if index == 0 else f"A{index:03d}")
            if index == 0:
                row["产品名称"] = "产�品"
            writer.writerow(row)
    for index in range(5):
        path = source / f"AI-客户清单_fixture_{index:02d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CUSTOMER_COLUMNS)
            writer.writeheader()
            writer.writerow(_customer_row(*policies[index]))

    importer = FullHistoryImporter(connection.DB_PATH, source, imported_by="pytest")
    try:
        result = importer.run()
    finally:
        importer.close()
    assert result.performance_rows == 12
    assert result.customer_source_rows == 5
    assert result.customer_policy_rows == 5
    assert result.fact_rows == 12
    assert result.source_text_issue_rows == 1
    assert result.quick_check == "ok"

    with connection.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM performance").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_snapshot").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM customer_policy_month_fact WHERE is_longterm=1").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM history_import_files").fetchone()[0] == 17
        assert conn.execute("SELECT source_text_issue_rows FROM history_import_batches").fetchone()[0] == 1


def test_customer_page_uses_direct_business_language(auth_db):
    client = TestClient(app)
    page = client.get("/customer-analysis")
    assert page.status_code == 200
    assert "新客、老客与保单状态" in page.text
    assert "不作为13个月或25个月继续率" in page.text
    assert "/js/customer-analysis.js" in page.text
    script = client.get("/js/customer-analysis.js")
    assert script.status_code == 200
    assert "新客贡献" in script.text
    assert "退保终止" in script.text
    assert "持单与间隔" in page.text
    assert "首次复购间隔" in script.text
    assert "AI建议" not in page.text + script.text
