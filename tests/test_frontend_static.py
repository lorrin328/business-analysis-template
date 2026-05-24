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


def test_product_config_does_not_embed_admin_token_and_uses_protection_kpi():
    html = read_html()
    api_client = read_js("api-client.js")
    assert "Aaaaa8888%" not in api_client
    assert "DEFAULT_ADMIN_TOKEN" not in api_client
    assert "kpi.protection_total" in html
    assert "未配置保障类目标" in html


def test_protection_modal_shows_jingdai_transform_and_sub_modes():
    html = read_html()
    assert "case 'protection'" in html
    assert "保障类产品达成率" in html
    assert "年度累计达成" in html
    assert "mainRow('经代', jdActual, targetJd)" in html
    assert "mainRow('转型', tfActual, targetTf)" in html
    assert "转型业务分模式" in html
    assert "item.year?.product_protection" in html


def test_annuity_modal_shows_jingdai_transform_and_sub_modes():
    html = read_html()
    assert "case 'annuity'" in html
    assert "商保年金达成率" in html
    assert "mainRow('经代', jdActual, targetJd)" in html
    assert "mainRow('转型', tfActual, targetTf)" in html
    assert "转型业务分模式" in html
    assert "item.year?.product_annuity" in html
    assert "经代业务</td><td>--" not in html


def test_kpi_year_comparison_accepts_numeric_api_year():
    html = read_html()
    assert "String(kpi.year) === year" in html
    assert "kpi.year === year" not in html


def test_tenyear_kpi_includes_jingdai_in_card_and_modal():
    html = read_html()
    assert "kpi.tenyear_jd" in html
    assert "kpi.tenyear_tf" in html
    assert "未配置10年期产品目标" in html
    assert "Math.round(kpiData.tenyear_jd || 0)" in html
    assert "targetCategory = is10y ? 'tenYear' : 'qjPremium'" in html


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


def test_local_seed_data_remains_available_when_api_is_slow_or_unavailable():
    html = read_html()
    assert "ALLOW_LOCAL_FALLBACK" in html
    assert "clearRuntimeFallbackYear" in html
    assert "暂保留本地兜底数据" in html
    assert "updateKPICards();\n      await fetchTargetData" in html


def test_upload_js_no_duplicate_vars():
    upload = read_js("upload.js")
    import re
    declarations = re.findall(r'(?:const|let|var)\s+_uploading', upload)
    assert len(declarations) <= 1, f"Duplicate _uploading: {declarations}"


def test_all_js_brackets_balanced():
    for f in sorted(os.listdir(JS_DIR)):
        if not f.endswith('.js'):
            continue
        content = read_js(f)
        assert content.count('{') == content.count('}'), f"{f}: {{={content.count('{')} }}={content.count('}')}"
        assert content.count('(') == content.count(')'), f"{f}: (={content.count('(')} )={content.count(')')}"


def test_html_js_references_exist():
    import re
    html = read_html()
    refs = re.findall(r'src="(js/[^"]+)"', html)
    for ref in refs:
        assert os.path.exists(os.path.join(ROOT, ref)), f"Missing: {ref}"


def test_runtime_js_boundary_is_explicit():
    import re
    html = read_html()
    refs = re.findall(r'src="(js/[^"]+)"', html)
    assert refs == ["js/api-client.js"]
    with open(os.path.join(JS_DIR, "README.md"), "r", encoding="utf-8") as f:
        note = f.read()
    assert "not active runtime code" in note


def test_dynamic_org_controls_do_not_inline_unescaped_orgs():
    html = read_html()
    combined = html + "\n" + read_js("mock-data.js") + "\n" + read_js("product-analysis.js") + "\n" + read_js("payperiod-chart.js")
    assert "onchange=\"togglePayPeriodOrg('${org}'" not in combined
    assert "onchange=\"toggleProductOrg('${org}'" not in combined
    assert "wrapper.innerHTML = orgs.map" not in combined
    assert "container.innerHTML = orgs.map" not in combined


def test_upload_js_exposes_handle_file():
    upload = read_js("upload.js")
    assert "window.handleFile = handleFile" in upload
    assert "try {" in upload
    assert "} catch" in upload
    assert "} finally" in upload


def test_platform_trend_uses_calendar_days_for_daily_series():
    html = read_html()
    assert "function daysInMonth(year, month)" in html
    assert "function dailyDisplayEndDay(year, month)" in html
    assert "new Date(Number(year), Number(month), 0).getDate()" in html
    assert "m === now.getMonth() + 1" in html
    assert "daysInMonthArr" not in html
    assert "function trimDailySeries" not in html
    assert "function completeDailySeries" in html


def test_per_capita_metrics_use_average_headcount_denominators():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    target_modal = read_js("target-modal.js")
    combined = html + "\n" + kpi + "\n" + target_modal

    assert "avgSum / months" in combined
    assert "avgArr(tm.headcount['OTO'])" in combined
    assert "sumArr(tm.headcount['OTO']) + sumArr(tm.headcount['证保'])" not in combined
    assert "res.totalPrem += p; res.totalAvg += a;" in combined
    assert "res.totalAvg = Math.round(res.totalAvg * 10) / 10;" in combined
    assert "res.ch[ch] = { prem: p, avg: a, pc: calcPC(p, a) }" in combined
    assert "res.ch[ch] = { prem: p, avg: aSum, pc: calcPC(p, aSum) }" not in combined
