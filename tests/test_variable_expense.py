from io import BytesIO

import pytest

pytest.importorskip("fastapi")
openpyxl = pytest.importorskip("openpyxl")
from fastapi.testclient import TestClient

from main import app
from auth import ROLE_DEFAULT_PERMISSIONS
from variable_expense.analyzer import analyze_variable_expense_workbook


def _workbook_bytes(*, invalid_total: bool = False) -> bytes:
    wb = openpyxl.Workbook()
    report = wb.active
    report.title = "报告数据"

    report["AG41"], report["AH41"] = 100, 80
    report["AG42"], report["AH42"] = 50, 10
    report["AG43"], report["AH43"] = (151 if invalid_total else 150), 90
    report["C6"], report["D6"] = 120, 70
    report["C5"], report["D5"] = 140, 90
    for row, available, actual in [(47, 60, 45), (48, 25, 20), (49, 15, 15), (50, 0, 5)]:
        report[f"AP{row}"], report[f"AS{row}"] = available, actual
    report["BQ81"], report["BR81"], report["BS81"], report["BT81"], report["BU81"] = 20, 20, 15, 20, 80

    one = wb.create_sheet("一对一沟通会")
    one["D5"], one["F5"], one["G5"], one["H5"] = "测试机构", 300, 10, 5
    one["I5"], one["J5"], one["M5"], one["N5"] = 100, 80, 40, 20
    one["D6"], one["F6"], one["G6"], one["H6"] = "全系统合计", 300, 10, 5
    one["I6"], one["J6"], one["M6"], one["N6"] = 100, 80, 40, 20

    policy = wb.create_sheet("【机构可用】费用政策")
    policy.append([])
    for _ in range(7):
        policy.append([])
    policy.append([None, None, "测试机构", "测试项目", "OTO", "P1", "测试产品", 5, None, None, 0.1, 10000000, 1000000])

    support1 = wb.create_sheet("【机构可用】总部支援1—方案下拨")
    support1.append(["年月", "销售机构名称", "业务模式", "项目名称", "方案下拨可用费用"])
    support1.append([])

    support2 = wb.create_sheet("【机构可用】总部支援2—总部DU号等费用")
    for _ in range(8):
        support2.append([])

    direct = wb.create_sheet("【财务动支】首年直接变费")
    for _ in range(4):
        direct.append([])
    direct.append(["测试机构", "OTO", "测试项目", "业务推动费用", 80, "Y", "业推费"])

    product = wb.create_sheet("【条线可用】变费可用（含证保结转）")
    for _ in range(3):
        product.append([])
    product.append(["测试机构", "OTO", "P1", "测试产品", 5, 0.1, 10000000, 100, 0, 100, "OTO"])

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def _login(client: TestClient, username="admin", password="Test-only-admin-2026!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]


def _headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_parser_keeps_zero_denominator_null_and_validates_totals():
    result = analyze_variable_expense_workbook(
        _workbook_bytes(),
        "2026年财务指标统计（截至6月）.xlsx",
        "2026-06",
    )
    assert result["quality"]["status"] == "passed"
    assert result["reportComparison"] is None
    assert all(item["passed"] for item in result["quality"]["checks"])
    public = next(item for item in result["details"]["modes"] if item["mode"] == "公共")
    assert public["available"] == 0
    assert public["actual"] == 5
    assert public["rate"] is None
    assert public["status"] == "not_calculable"
    project = result["details"]["projects"][0]
    assert project["comparisonStatus"] == "matched"
    assert project["rate"] == 0.8
    with pytest.raises(ValueError, match="不一致"):
        analyze_variable_expense_workbook(_workbook_bytes(), "【月报】26年财务指标统计（截至6月）.xlsx", "2026-07")


def test_upload_is_isolated_duplicate_safe_and_latest_readable(auth_db):
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])
    content = _workbook_bytes()

    before = client.get("/api/variable-expense/latest", headers=headers)
    assert before.status_code == 200
    assert before.json()["data"]["batch"] is None

    response = client.post(
        "/api/variable-expense/upload",
        headers=headers,
        data={"period": "2026-06"},
        files={"workbook": ("2026年财务指标统计（截至6月）.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    batch_id = response.json()["data"]["batch"]["id"]
    assert response.json()["data"]["summary"]["transformation"]["actual"] == 90

    duplicate = client.post(
        "/api/variable-expense/upload",
        headers=headers,
        data={"period": "2026-06"},
        files={"workbook": ("2026年财务指标统计（截至6月）.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    assert duplicate.json()["data"]["batch"]["id"] == batch_id

    import db.connection as connection
    with connection.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM variable_expense_batches").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0] == 0

    latest = client.get("/api/variable-expense/latest?period=2026-06", headers=headers)
    assert latest.status_code == 200
    assert latest.json()["data"]["batch"]["id"] == batch_id


def test_blocking_validation_does_not_replace_latest(auth_db):
    client = TestClient(app)
    login = _login(client)
    headers = _headers(login["token"])
    valid = _workbook_bytes()
    invalid = _workbook_bytes(invalid_total=True)

    created = client.post(
        "/api/variable-expense/upload",
        headers=headers,
        data={"period": "2026-06"},
        files={"workbook": ("2026年财务指标统计（截至6月）.xlsx", valid)},
    )
    batch_id = created.json()["data"]["batch"]["id"]
    rejected = client.post(
        "/api/variable-expense/upload",
        headers=headers,
        data={"period": "2026-07"},
        files={"workbook": ("2026年财务指标统计（截至7月）.xlsx", invalid)},
    )
    assert rejected.status_code == 422
    latest = client.get("/api/variable-expense/latest", headers=headers)
    assert latest.json()["data"]["batch"]["id"] == batch_id


def test_normal_user_has_no_financial_module_access(auth_db):
    client = TestClient(app)
    registered = client.post("/api/auth/register", json={"username": "expense_normal", "password": "normal-pass-123"})
    assert registered.status_code == 200
    user = registered.json()["data"]
    assert user["user"]["permissions"]["variable_expense_view"] is False
    assert user["user"]["permissions"]["variable_expense_upload"] is False
    headers = _headers(user["token"])
    assert client.get("/api/variable-expense/latest", headers=headers).status_code == 403
    assert client.post("/api/variable-expense/upload", headers=headers).status_code == 403


def test_static_page_and_role_defaults_are_isolated():
    client = TestClient(app)
    page = client.get("/variable-expense")
    assert page.status_code == 200
    assert "独立统计模块" in page.text
    assert "/js/variable-expense.js" in page.text
    assert ROLE_DEFAULT_PERMISSIONS["admin"]["variable_expense_upload"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["variable_expense_view"] is True
    assert ROLE_DEFAULT_PERMISSIONS["senior"]["variable_expense_upload"] is False
    assert ROLE_DEFAULT_PERMISSIONS["normal"]["variable_expense_view"] is False
