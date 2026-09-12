import base64
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from main import app
from db import get_db
from services.ai_raw_data import DATASETS
from services.import_safety import append_raw_frame


def _headers(username="admin", password="Test-only-admin-2026!"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def raw_db(auth_db):
    with get_db() as conn:
        for table in DATASETS:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
            append_raw_frame(conn, table, pd.DataFrame({
                "业务模式": ["OTO", "OTO", "证券"],
                "投保单号": ["001", "002", "003"],
                "期交保费": [12000.5, 0, None],
                '新增"字段': ["保留", None, "保留"],
            }))
        conn.commit()


@pytest.mark.parametrize("table", DATASETS)
def test_all_columns_and_rows_survive_pagination(raw_db, table):
    client = TestClient(app)
    first = client.get(f"/api/ai/raw-data/{table}", params={"limit": 2}, headers=_headers())
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["rows"][0]["投保单号"] == "001"
    assert data["rows"][0]["期交保费"] == 12000.5
    assert data["rows"][1]["期交保费"] == 0
    assert data["rows"][1]['新增"字段'] is None
    assert data["hasMore"] is True
    second = client.get(f"/api/ai/raw-data/{table}", params={
        "limit": 2, "afterRowId": data["nextAfterRowId"], "expectedImportId": data["latestImportId"],
    }, headers=_headers()).json()["data"]
    assert second["hasMore"] is False
    assert second["nextAfterRowId"] is None
    assert second["rows"][0]["期交保费"] is None
    with get_db() as conn:
        expected = [dict(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
    assert data["rows"] + second["rows"] == expected


def test_catalog_matches_current_schema_and_new_import_column(raw_db):
    with get_db() as conn:
        append_raw_frame(conn, "performance", pd.DataFrame({"未来新增列": ["新值"]}))
        conn.commit()
    client = TestClient(app)
    catalog = client.get("/api/ai/raw-datasets", headers=_headers()).json()["data"]
    assert {item["dataset"] for item in catalog["datasets"]} == set(DATASETS)
    perf = next(item for item in catalog["datasets"] if item["dataset"] == "performance")
    assert "未来新增列" in [column["name"] for column in perf["columns"]]
    page = client.get("/api/ai/raw-data/performance", headers=_headers()).json()["data"]
    assert page["rows"][-1]["未来新增列"] == "新值"
    assert page["rows"][0]["未来新增列"] is None


def test_column_selection_filters_null_and_sql_payload(raw_db):
    client = TestClient(app)
    response = client.get("/api/ai/raw-data/performance", headers={**_headers(),
        "X-AI-Filters": json.dumps({"期交保费": 0, '新增"字段': None}),
    }, params=[
        ("columns", "投保单号"), ("columns", '新增"字段'),
    ])
    assert response.status_code == 200
    assert response.json()["data"]["rows"] == [{"投保单号": "002", '新增"字段': None}]
    injection = client.get("/api/ai/raw-data/performance", headers={**_headers(),
        "X-AI-Filters": json.dumps({"业务模式": "' OR 1=1 --"}),
    })
    assert injection.status_code == 200
    assert injection.json()["data"]["rows"] == []


@pytest.mark.parametrize("params,status", [
    ({"limit": 0}, 422), ({"limit": 1001}, 422), ({"afterRowId": -1}, 422),
    ({"afterRowId": 2**63}, 422), ({"columns": "password_hash"}, 400),
    ({"columns": ["投保单号", "投保单号"]}, 400),
    ({"filters": "[]"}, 400), ({"filters": "bad json"}, 400),
    ({"filters": '{"业务模式": ["OTO"]}'}, 400),
    ({"filters": '{"期交保费": NaN}'}, 400),
    ({"filters": '{"期交保费": 9999999999999999999999999}'}, 400),
    ({"filters": '{"不存在": "值"}'}, 400),
    ({"filters": '{"业务模式": true}'}, 400),
])
def test_invalid_queries_are_rejected(raw_db, params, status):
    params = dict(params)
    headers = _headers()
    if "filters" in params:
        headers["X-AI-Filters"] = params.pop("filters").encode("ascii", "backslashreplace").decode("ascii")
    response = TestClient(app).get("/api/ai/raw-data/performance", headers=headers, params=params)
    assert response.status_code == status


def test_unknown_missing_and_empty_datasets(raw_db):
    client = TestClient(app)
    assert client.get("/api/ai/raw-data/users", headers=_headers()).status_code == 404
    with get_db() as conn:
        conn.execute("DROP TABLE value_data")
        conn.execute("DELETE FROM hr_data")
        conn.commit()
    assert client.get("/api/ai/raw-data/value_data", headers=_headers()).status_code == 404
    catalog = client.get("/api/ai/raw-datasets", headers=_headers()).json()["data"]["datasets"]
    assert next(item for item in catalog if item["dataset"] == "value_data")["available"] is False
    page = client.get("/api/ai/raw-data/hr_data", headers=_headers()).json()["data"]
    assert page["rows"] == [] and page["hasMore"] is False


@pytest.mark.parametrize("status", ["success", "partial"])
def test_import_change_invalidates_expected_id(raw_db, status):
    client = TestClient(app)
    page = client.get("/api/ai/raw-data/performance", headers=_headers()).json()["data"]
    with get_db() as conn:
        conn.execute("""INSERT INTO data_imports (file_name,file_hash,file_size,data_years,table_counts,status)
                        VALUES ('synthetic.xlsx','synthetic',1,'[]','{}',?)""", (status,))
        conn.commit()
    response = client.get("/api/ai/raw-data/performance", headers=_headers(), params={
        "expectedImportId": page["latestImportId"],
    })
    assert response.status_code == 409


def test_raw_permission_is_explicit_and_audited(raw_db, monkeypatch):
    monkeypatch.setenv("AI_READONLY_TOKEN", "aggregate-test-token")
    client = TestClient(app)
    for path in ("/api/ai/raw-datasets", "/api/ai/raw-data/performance"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer aggregate-test-token"}).status_code == 403
    registered = client.post("/api/auth/register", json={"username": "rawreader", "password": "test-pass-123"})
    user_id = registered.json()["data"]["user"]["id"]
    headers = _headers("rawreader", "test-pass-123")
    assert client.get("/api/ai/raw-data/performance", headers=headers).status_code == 403
    with get_db() as conn:
        conn.execute("UPDATE users SET role='senior' WHERE id=?", (user_id,))
        conn.execute("DELETE FROM user_module_permissions WHERE user_id=? AND module_key='ai_raw_data'", (user_id,))
        conn.commit()
    assert client.get("/api/ai/raw-data/performance", headers=headers).status_code == 403
    admin = client.post("/api/auth/login", json={"username": "admin", "password": "Test-only-admin-2026!"}).json()["data"]
    granted = client.patch(f"/api/admin/users/{user_id}",
                           headers={"Authorization": f"Bearer {admin['token']}"},
                           json={"permissions": {"ai_raw_data": True}})
    assert granted.status_code == 200
    assert client.get("/api/ai/raw-data/performance", headers={**headers,
        "X-AI-Filters": json.dumps({"投保单号": "PRIVATE-FILTER-VALUE"}),
    }).status_code == 200
    assert client.get("/api/ai/raw-datasets", headers=headers).status_code == 200
    login = client.post("/api/auth/login", json={"username": "rawreader", "password": "test-pass-123"}).json()["data"]
    assert client.get("/api/ai/raw-data/performance", headers={"Authorization": f"Bearer {login['token']}"}).status_code == 200
    for method in (client.post, client.put, client.delete):
        assert method("/api/ai/raw-data/performance", headers=headers).status_code == 405
    with get_db() as conn:
        log = conn.execute("SELECT * FROM operation_logs WHERE action='ai_raw_data_read'").fetchall()
        assert log and "PRIVATE-FILTER-VALUE" not in str([tuple(row) for row in log])


def test_openapi_documents_actual_raw_parameters(raw_db):
    paths = TestClient(app).get("/api/ai/openapi.json").json()["paths"]
    assert "/api/ai/raw-datasets" in paths
    params = paths["/api/ai/raw-data/{dataset}"]["get"]["parameters"]
    assert {p["name"] for p in params} == {"dataset", "limit", "afterRowId", "columns", "X-AI-Filters", "expectedImportId"}
    assert next(p for p in params if p["name"] == "X-AI-Filters")["in"] == "header"
    assert all(set(path) == {"get"} for path in paths.values())


@pytest.mark.parametrize("kind,headers", [
    ("performance", ["业务模式", "期交保费"]),
    ("jingdai", ["时间", "承保年化规保", "期交保费"]),
    ("hr_data", ["业务模式名称", "统计日期", "月初在职人力", "月末在职人力"]),
    ("value_data", ["业务模式名称", "价值"]),
])
def test_excel_parser_to_sqlite_to_api_preserves_unused_columns(auth_db, kind, headers):
    from etl import parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel
    parsers = dict(zip(DATASETS, [parse_performance_excel, parse_jingdai_excel, parse_hr_excel, parse_value_excel]))
    workbook = Workbook()
    workbook.active.append(headers + ["额外业务字段", "空字段"])
    workbook.active.append(["OTO"] + [1] * (len(headers) - 1) + ["没有用于汇总的内容", None])
    stream = io.BytesIO()
    workbook.save(stream)
    frame = parsers[kind](stream.getvalue())
    with get_db() as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{kind}"')
        append_raw_frame(conn, kind, frame)
        conn.commit()
    response = TestClient(app).get(f"/api/ai/raw-data/{kind}", headers=_headers())
    assert response.status_code == 200
    row = response.json()["data"]["rows"][0]
    assert set(row) == set(headers + ["额外业务字段", "空字段"])
    assert row["额外业务字段"] == "没有用于汇总的内容"
    assert row["空字段"] is None
