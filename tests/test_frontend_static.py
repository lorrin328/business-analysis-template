import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = os.path.join(ROOT, "经营分析模板.html")
API_CLIENT_PATH = os.path.join(ROOT, "js", "api-client.js")


def read_html() -> str:
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def read_api_client() -> str:
    with open(API_CLIENT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_activity_yoy_uses_percentage_point_gap():
    html = read_html()
    assert "活动率 / 活动率Prev - 1" not in html
    assert "活动率 - 活动率Prev" in html
    assert "pp</span>" in html


def test_frontend_has_no_production_console_log():
    assert "console.log" not in read_html()


def test_unsupported_metrics_render_empty_state():
    html = read_html()
    assert "口径待完善" in html
    assert "暂无长险期交数据" in html
    assert "kpi-protection-rate');\n        if (el) el.textContent = '0%'" not in html


def test_default_target_source_is_explicit():
    html = read_html()
    assert "服务端尚未配置正式目标" in html
    assert "targetSourceLabel" in html


def test_frontend_centralizes_read_api_fetches():
    html = read_html()
    api_client = read_api_client()
    assert '<script src="js/api-client.js"></script>' in html
    assert "function apiUrl(path)" not in html
    assert "async function fetchJson(path" not in html
    assert "function apiUrl(path)" in api_client
    assert "async function fetchJson(path" in api_client
    assert "window.adminFetch = adminFetch" in api_client
    assert "fetch(`${API_BASE}/api/data/" not in html
    assert "fetch(`${API_BASE}/api/kpi/" not in html
    assert "fetch(`${API_BASE}/api/product/" not in html
    assert "fetch(`${API_BASE}/api/org-kpi/" not in html
    assert "/api/platform-data?year=" in html
    assert "/api/kpi?year=" in html
    assert "/api/product-analysis?" in html
    assert "/api/org-analysis?year=" in html
    assert "/api/targets?year=" in html
