import csv
import io
from pathlib import Path

import pytest
from openpyxl import Workbook

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
    assert client.get("/api/customer-analysis/new-customer-cohort", headers=_headers(normal["token"])).status_code == 403
    assert ROLE_DEFAULT_PERMISSIONS["admin"]["customer_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["customer_analysis"] is True
    assert ROLE_DEFAULT_PERMISSIONS["normal"]["customer_analysis"] is False


def _seed_new_customer_cohort():
    import db.connection as connection

    policies = [
        ("P-C1-1", "C1", "2026-01-10", "OTO", "上海", 10000, "产品A"),
        ("P-C1-2", "C1", "2026-01-20", "OTO", "上海", 20000, "产品B"),
        ("P-C1-3", "C1", "2026-03-10", "证保", "北京", 30000, "产品C"),
        ("P-C1-4", "C1", "2027-01-09", "蚁桥", "上海", 40000, "产品B"),
        ("P-C1-5", "C1", "2027-01-10", "OTO", "上海", 50000, "产品D"),
        ("P-C2-1", "C2", "2026-02-01", "OTO", "上海", 60000, "产品A"),
        ("P-C3-1", "C3", "2026-12-15", "证保", "北京", 70000, "产品A"),
        ("P-C3-2", "C3", "2026-12-20", "证保", "北京", 80000, "产品B"),
        ("P-C3-3", "C3", "2027-01-15", "证保", "北京", 90000, "产品C"),
    ]
    with connection.get_db() as conn:
        batch_id = conn.execute(
            """INSERT INTO history_import_batches
               (source_directory, source_cutoff, performance_rows, customer_source_rows,
                customer_policy_rows, source_text_issue_rows, status, completed_at)
               VALUES ('cohort-fixture', '2027-06-30 23:59:59', 9, 9, 9, 0, 'success', CURRENT_TIMESTAMP)"""
        ).lastrowid
        conn.executemany(
            """INSERT INTO customer_master
               (customer_id, first_underwriting_time, first_policy_no, total_policy_count,
                active_policy_count, suspended_policy_count, terminated_policy_count, batch_id)
               VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
            [
                ("C1", "2026-01-10", "P-C1-1", 5, 5, batch_id),
                ("C2", "2026-02-01", "P-C2-1", 1, 1, batch_id),
                ("C3", "2026-12-15", "P-C3-1", 3, 3, batch_id),
            ],
        )
        conn.executemany(
            """INSERT INTO customer_policy_snapshot
               (policy_no, customer_id, underwriting_time, policy_status, termination_reason,
                status_group, raw_row_count, batch_id)
               VALUES (?, ?, ?, '有效', '', 'active', 1, ?)""",
            [(policy_no, customer_id, underwriting_date, batch_id)
             for policy_no, customer_id, underwriting_date, *_ in policies],
        )
        conn.executemany(
            """INSERT INTO customer_policy_month_fact
               (year, month, transaction_date, business_line, org, policy_no, customer_id,
                underwriting_time, first_customer_underwriting_time, is_longterm, qj_premium,
                gm_premium, zs_premium, value_premium, accepted_count, policy_status,
                termination_reason, status_group, customer_match, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, 0, 0, 1, '有效', '', 'active', 1, ?)""",
            [
                (int(underwriting_date[:4]), int(underwriting_date[5:7]), underwriting_date,
                 business_line, org, policy_no, customer_id, underwriting_date,
                 next(item[1] for item in [("C1", "2026-01-10"), ("C2", "2026-02-01"), ("C3", "2026-12-15")] if item[0] == customer_id),
                 qj, batch_id)
                for policy_no, customer_id, underwriting_date, business_line, org, qj, _product in policies
            ],
        )
        conn.execute('ALTER TABLE performance ADD COLUMN "投保单号" TEXT')
        conn.execute('ALTER TABLE performance ADD COLUMN "产品名称" TEXT')
        conn.execute('ALTER TABLE performance ADD COLUMN "产品代码" TEXT')
        conn.executemany(
            """INSERT INTO performance
               ("年月", "业务模式", "销售机构名称", "期交保费", "投保单号", "产品名称", "产品代码")
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (underwriting_date[:7], business_line, org, qj, policy_no, product, f"CODE-{index}")
                for index, (policy_no, _customer_id, underwriting_date, business_line, org, qj, product)
                in enumerate(policies, 1)
            ],
        )
        conn.execute('CREATE INDEX ix_test_performance_policy ON performance("投保单号")')
        conn.commit()


def test_new_customer_cohort_windows_repeat_and_product_metrics(auth_db):
    _seed_new_customer_cohort()
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])

    response = client.get(
        "/api/customer-analysis/new-customer-cohort",
        params={"year": 2026, "observationWindow": "twelve_months"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    summary = data["summary"]
    assert summary["systemNewCustomers"] == 3
    assert summary["trackedNewCustomers"] == 3
    assert summary["repeatCustomers"] == 2
    assert summary["repeatCustomerRate"] == pytest.approx(2 / 3)
    assert summary["trackedPolicies"] == 8
    assert summary["repeatPolicies"] == 5
    assert summary["averageRepeatPolicies"] == pytest.approx(5 / 3)
    assert summary["firstQjPremiumWan"] == 14
    assert summary["repeatQjPremiumWan"] == 26
    assert summary["qjPremiumWan"] == 40
    assert summary["repeatPremiumShare"] == pytest.approx(26 / 40)
    assert summary["completedObservationCustomers"] == 2
    assert summary["incompleteObservationCustomers"] == 1
    assert summary["observationCompletenessRate"] == pytest.approx(2 / 3)
    assert len(data["timeline"]) == 12
    assert "满12个月当日不计入" in data["quality"]["definitions"]["twelveMonthWindow"]
    product_b = next(item for item in data["products"] if item["product"] == "产品B")
    assert product_b["repeatCustomers"] == 2
    assert product_b["repeatPolicies"] == 3
    assert product_b["repeatQjPremiumWan"] == 14

    first_month = client.get(
        "/api/customer-analysis/new-customer-cohort",
        params={"year": 2026, "observationWindow": "first_month"}, headers=headers,
    ).json()["data"]
    assert first_month["summary"]["trackedPolicies"] == 5
    assert first_month["summary"]["repeatPolicies"] == 2
    assert first_month["summary"]["repeatQjPremiumWan"] == 10
    assert len(first_month["timeline"]) == 1

    calendar_year = client.get(
        "/api/customer-analysis/new-customer-cohort",
        params={"year": 2026, "observationWindow": "calendar_year"}, headers=headers,
    ).json()["data"]
    assert calendar_year["summary"]["trackedPolicies"] == 6
    assert calendar_year["summary"]["repeatPolicies"] == 3
    assert calendar_year["summary"]["repeatQjPremiumWan"] == 13


def test_new_customer_cohort_dimension_filters(auth_db):
    _seed_new_customer_cohort()
    client = TestClient(app)
    token = _login(client)["token"]
    response = client.get(
        "/api/customer-analysis/new-customer-cohort",
        params={"year": 2026, "observationWindow": "twelve_months", "product": "产品B"},
        headers=_headers(token),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["trackedNewCustomers"] == 2
    assert data["summary"]["repeatCustomers"] == 2
    assert data["summary"]["repeatCustomerRate"] == 1
    assert data["summary"]["repeatPolicies"] == 3
    assert data["summary"]["repeatQjPremiumWan"] == 14
    assert "产品A" in data["meta"]["availableProducts"]

    oto = client.get(
        "/api/customer-analysis/new-customer-cohort",
        params={"year": 2026, "observationWindow": "twelve_months", "businessLine": "OTO", "org": "上海"},
        headers=_headers(token),
    ).json()["data"]
    assert oto["summary"]["trackedNewCustomers"] == 2
    assert oto["summary"]["repeatCustomers"] == 1
    assert oto["summary"]["repeatPolicies"] == 1
    assert {item["businessLine"] for item in oto["lines"]} == {"OTO"}


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
    assert "获客、复购与保单状态" in page.text
    assert "不作为13个月或25个月继续率" in page.text
    assert "/js/customer-analysis.js" in page.text
    script = client.get("/js/customer-analysis.js")
    assert script.status_code == 200
    assert "新客贡献" in script.text
    assert "退保终止" in script.text
    assert "持单与间隔" in page.text
    assert "新客经营" in page.text
    assert "首现后12个月" in page.text
    assert "首次复购间隔" in script.text
    assert "再次承保客户" in script.text
    assert "新客购买产品" in script.text
    assert "数据导入" in page.text
    assert "后台流式处理" in script.text
    assert "不设置固定文件大小、文件数和行数上限" in script.text
    assert "AI建议" not in page.text + script.text


def _customer_csv_bytes(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CUSTOMER_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _customer_xlsx_bytes(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "客户清单"
    sheet.append(CUSTOMER_COLUMNS)
    for row in rows:
        sheet.append([row.get(column, "") for column in CUSTOMER_COLUMNS])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _seed_customer_incremental_import():
    import db.connection as connection

    with connection.get_db() as conn:
        batch_id = conn.execute(
            """INSERT INTO history_import_batches
               (source_directory, source_cutoff, performance_rows, customer_source_rows,
                customer_policy_rows, status, imported_by, completed_at)
               VALUES ('fixture', '2026-07-01 12:00:00', 2, 1, 1, 'success', 'pytest', CURRENT_TIMESTAMP)"""
        ).lastrowid
        conn.execute(
            """INSERT INTO customer_policy_snapshot
               (policy_no, customer_id, import_time, underwriting_time, policy_status,
                termination_reason, status_group, raw_row_count, batch_id)
               VALUES ('P-OLD', 'C-OLD', '2026-07-01 12:00:00', '2025-01-10 10:00:00',
                       '有效', '', 'active', 1, ?)""", (batch_id,),
        )
        conn.execute(
            """INSERT INTO customer_master
               (customer_id, first_underwriting_time, first_policy_no, total_policy_count,
                active_policy_count, suspended_policy_count, terminated_policy_count, batch_id)
               VALUES ('C-OLD', '2025-01-10 10:00:00', 'P-OLD', 1, 1, 0, 0, ?)""", (batch_id,),
        )
        conn.executemany(
            """INSERT INTO customer_policy_month_fact
               (year, month, transaction_date, business_line, org, policy_no, customer_id,
                underwriting_time, first_customer_underwriting_time, is_longterm, qj_premium,
                gm_premium, zs_premium, value_premium, accepted_count, policy_status,
                termination_reason, status_group, customer_match, batch_id)
               VALUES (2026, 7, '2026-07-10', 'OTO', '上海', ?, ?, ?, ?, 1, ?, 0, 0, 0, 1, ?, ?, ?, ?, ?)""",
            [
                ("P-OLD", "C-OLD", "2025-01-10 10:00:00", "2025-01-10 10:00:00", 10000, "有效", "", "active", 1, batch_id),
                ("P-NEW", None, None, None, 20000, None, None, "unmatched", 0, batch_id),
            ],
        )
        conn.commit()


def _upload_customer_job(client: TestClient, headers: dict, name: str, content: bytes) -> dict:
    session_response = client.post(
        "/api/customer-analysis/import/uploads", headers=headers,
        json={"files": [{"name": name, "size": len(content)}]},
    )
    assert session_response.status_code == 200
    session = session_response.json()["data"]
    offset = 0
    chunk_size = session["chunkBytes"]
    while offset < len(content):
        chunk = content[offset:offset + chunk_size]
        response = client.post(
            f"/api/customer-analysis/import/uploads/{session['uploadId']}/files/0/chunks",
            params={"offset": offset}, headers={**headers, "Content-Type": "application/octet-stream"},
            content=chunk,
        )
        assert response.status_code == 200
        offset += len(chunk)
    process = client.post(
        f"/api/customer-analysis/import/uploads/{session['uploadId']}/process", headers=headers,
    )
    assert process.status_code == 202
    status = client.get(
        f"/api/customer-analysis/import/uploads/{session['uploadId']}", headers=headers,
    )
    assert status.status_code == 200
    return status.json()["data"]


def test_customer_csv_preview_commit_refreshes_customer_domains(auth_db):
    import db.connection as connection

    _seed_customer_incremental_import()
    client = TestClient(app)
    token = _login(client)["token"]
    headers = _headers(token)
    rows = [
        {
            "投保单号": "P-OLD", "投保人id": "C-OLD", "投保时间": "2025-01-09 09:00:00",
            "导入时间": "2026-08-01 09:00:00", "回销时间": "2025-01-09 10:00:00",
            "承保时间": "2025-01-10 10:00:00", "入账时间": "2025-01-10 10:01:00",
            "犹豫期退保时间": "", "保单状态名称": "终止", "保单终止原因": "退保终止",
        },
        {
            "投保单号": "P-NEW", "投保人id": "C-NEW", "投保时间": "2026-07-09 09:00:00",
            "导入时间": "2026-08-01 09:00:00", "回销时间": "2026-07-09 10:00:00",
            "承保时间": "2026-07-10 10:00:00", "入账时间": "2026-07-10 10:01:00",
            "犹豫期退保时间": "", "保单状态名称": "有效", "保单终止原因": "",
        },
    ]
    content = _customer_csv_bytes(rows)
    preview = _upload_customer_job(client, headers, "客户清单_增量.csv", content)
    assert preview["canImport"] is True
    assert preview["sourceRows"] == 2
    assert preview["insertPolicies"] == 1
    assert preview["updatePolicies"] == 1
    assert "policy_no" not in str(preview)
    commit = client.post(
        f"/api/customer-analysis/import/uploads/{preview['uploadId']}/commit", headers=headers,
    )
    assert commit.status_code == 202
    result = client.get(
        f"/api/customer-analysis/import/uploads/{preview['uploadId']}", headers=headers,
    ).json()["data"]
    assert result["status"] == "success"
    assert result["linkedPerformancePolicies"] == 2
    with connection.get_db() as conn:
        old = conn.execute("SELECT status_group, customer_import_batch_id FROM customer_policy_snapshot WHERE policy_no='P-OLD'").fetchone()
        assert old["status_group"] == "surrender"
        assert old["customer_import_batch_id"] == result["batchId"]
        new_fact = conn.execute("SELECT customer_id, customer_match, status_group FROM customer_policy_month_fact WHERE policy_no='P-NEW'").fetchone()
        assert dict(new_fact) == {"customer_id": "C-NEW", "customer_match": 1, "status_group": "active"}
        assert conn.execute("SELECT COUNT(*) FROM customer_master WHERE customer_id='C-NEW'").fetchone()[0] == 1
        audit_text = " ".join(row[0] for row in conn.execute("SELECT detail FROM operation_logs").fetchall())
        assert "C-NEW" not in audit_text and "P-NEW" not in audit_text
        staging = Path(connection.DB_PATH).resolve().parent / "customer-import-staging" / preview["uploadId"]
        assert not staging.exists()
    overview = client.get("/api/customer-analysis/overview?year=2026", headers=headers).json()["data"]
    assert overview["meta"]["sourceCutoff"].startswith("2026-08-01")
    batches = client.get("/api/customer-analysis/import/batches", headers=headers).json()["data"]["batches"]
    assert batches[0]["batchId"] == result["batchId"]


def test_customer_import_blocks_identity_conflict_and_template_is_downloadable(auth_db):
    _seed_customer_incremental_import()
    client = TestClient(app)
    headers = _headers(_login(client)["token"])
    conflict = [{
        "投保单号": "P-OLD", "投保人id": "C-DIFFERENT", "投保时间": "2025-01-09",
        "导入时间": "2026-08-01", "回销时间": "", "承保时间": "2025-01-10",
        "入账时间": "", "犹豫期退保时间": "", "保单状态名称": "有效", "保单终止原因": "",
    }]
    preview = _upload_customer_job(client, headers, "conflict.csv", _customer_csv_bytes(conflict))
    assert preview["canImport"] is False
    assert preview["conflictPolicies"] == 1
    commit = client.post(
        f"/api/customer-analysis/import/uploads/{preview['uploadId']}/commit", headers=headers,
    )
    assert commit.status_code == 422
    csv_template = client.get("/api/customer-analysis/import/template?format=csv", headers=headers)
    assert csv_template.status_code == 200
    assert csv_template.content.startswith(b"\xef\xbb\xbf")
    xlsx_template = client.get("/api/customer-analysis/import/template?format=xlsx", headers=headers)
    assert xlsx_template.status_code == 200
    assert xlsx_template.content.startswith(b"PK")


def test_customer_xlsx_is_streamed_and_prepared_in_background(auth_db):
    _seed_customer_incremental_import()
    client = TestClient(app)
    headers = _headers(_login(client)["token"])
    row = _customer_row("P-XLSX", 2026)
    preview = _upload_customer_job(client, headers, "customer.xlsx", _customer_xlsx_bytes([row]))
    assert preview["status"] == "ready"
    assert preview["insertPolicies"] == 1
    assert preview["sourceRows"] == 1


def test_customer_import_requires_upload_permission(auth_db):
    client = TestClient(app)
    admin = _login(client)
    registered = client.post("/api/auth/register", json={"username": "customer_reader", "password": "normal-pass-123"})
    user_id = registered.json()["data"]["user"]["id"]
    update = client.patch(
        f"/api/admin/users/{user_id}", headers=_headers(admin["token"]),
        json={"username": "customer_reader", "role": "normal", "permissions": {"customer_analysis": True}},
    )
    assert update.status_code == 200
    reader = _login(client, "customer_reader", "normal-pass-123")
    row = _customer_row("P-1", 2026)
    content = _customer_csv_bytes([row])
    response = client.post(
        "/api/customer-analysis/import/uploads", headers=_headers(reader["token"]),
        json={"files": [{"name": "customer.csv", "size": len(content)}]},
    )
    assert response.status_code == 403


def test_customer_upload_session_has_no_fixed_file_count_or_total_size_limit(auth_db):
    client = TestClient(app)
    headers = _headers(_login(client)["token"])
    declared_size = 6 * 1024 * 1024
    files = [{"name": f"customer_{index:02d}.csv", "size": declared_size} for index in range(25)]
    response = client.post("/api/customer-analysis/import/uploads", headers=headers, json={"files": files})
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["files"]) == 25
    assert data["totalBytes"] == declared_size * 25  # 150MB，超过旧50MB门槛
    assert data["chunkBytes"] == 8 * 1024 * 1024
