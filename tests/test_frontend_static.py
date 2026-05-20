import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = os.path.join(ROOT, "经营分析模板.html")
JS_DIR = os.path.join(ROOT, "js")


def read_html() -> str:
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def read_js(filename: str) -> str:
    with open(os.path.join(JS_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


def test_activity_yoy_uses_percentage_point_gap():
    kpi = read_js("kpi-cards.js")
    assert "活动率 / 活动率Prev - 1" not in kpi
    assert "活动率 - 活动率Prev" in kpi
    assert "pp</span>" in kpi


def test_frontend_has_no_production_console_log():
    html = read_html()
    assert "console.log" not in html


def test_unsupported_metrics_render_empty_state():
    kpi = read_js("kpi-cards.js")
    target = read_js("target-modal.js")
    combined = kpi + target
    assert "口径待完善" in combined
    assert "暂无长险期交数据" in combined
    assert "kpi-protection-rate');\n        if (el) el.textContent = '0%'" not in combined


def test_default_target_source_is_explicit():
    target = read_js("target-modal.js")
    assert "服务端尚未配置正式目标" in target
    assert "targetSourceLabel" in target


def test_frontend_centralizes_read_api_fetches():
    html = read_html()
    api_client = read_js("api-client.js")
    # api-client.js loaded in HTML head
    assert '<script src="js/api-client.js"></script>' in html
    # api-client centralizes fetchJson / adminFetch / apiUrl
    assert "function apiUrl(path)" not in html
    assert "async function fetchJson(path" not in html
    assert "function apiUrl(path)" in api_client
    assert "async function fetchJson(path" in api_client
    assert "window.adminFetch = adminFetch" in api_client
    # No raw fetch with template literals in HTML
    assert "fetch(`${API_BASE}/api/data/" not in html
    assert "fetch(`${API_BASE}/api/kpi/" not in html
    assert "fetch(`${API_BASE}/api/product/" not in html
    assert "fetch(`${API_BASE}/api/org-kpi/" not in html
    # API URLs are in JS modules (mock-data.js, platform-trend.js, org-analysis.js, etc.)
    js_files = ["mock-data.js", "platform-trend.js", "org-analysis.js", "kpi-cards.js",
                 "product-analysis.js", "payperiod-chart.js", "team-analysis.js", "target-modal.js"]
    all_js = " ".join(read_js(f) for f in js_files if os.path.exists(os.path.join(JS_DIR, f)))
    assert "/api/platform-data?year=" in all_js
    assert "/api/kpi?year=" in all_js
    assert "/api/product-analysis?" in all_js
    assert "/api/org-analysis?year=" in all_js
    assert "/api/targets?year=" in all_js
