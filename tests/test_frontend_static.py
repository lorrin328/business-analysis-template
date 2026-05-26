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
    assert "暂无长险期交数据" in combined
    assert "未配置保障类目标" in combined
    assert "kpi-protection-rate');\n        if (el) el.textContent = '0%'" not in combined


def test_default_target_source_is_explicit():
    target = read_js("target-modal.js")
    assert "服务端尚未配置正式目标" in target
    assert "targetSourceLabel" in target


def test_product_config_does_not_embed_admin_token_and_uses_protection_kpi():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    combined = html + "\n" + kpi
    api_client = read_js("api-client.js")
    assert "Aaaaa8888%" not in api_client
    assert "DEFAULT_ADMIN_TOKEN" not in api_client
    assert "kpi.protection_total" in combined
    assert "未配置保障类目标" in combined


def test_protection_modal_shows_jingdai_transform_and_sub_modes():
    modal_content = read_js("kpi-modal-content.js")
    assert "case 'protection'" in modal_content
    assert "保障类产品达成率" in modal_content
    assert "年度累计达成" in modal_content
    assert "mainRow('经代', jdActual, targetJd)" in modal_content
    assert "mainRow('转型', tfActual, targetTf)" in modal_content
    assert "转型业务分模式" in modal_content
    assert "item.year?.product_protection" in modal_content


def test_annuity_modal_shows_jingdai_transform_and_sub_modes():
    modal_content = read_js("kpi-modal-content.js")
    assert "case 'annuity'" in modal_content
    assert "商保年金达成率" in modal_content
    assert "mainRow('经代', jdActual, targetJd)" in modal_content
    assert "mainRow('转型', tfActual, targetTf)" in modal_content
    assert "转型业务分模式" in modal_content
    assert "item.year?.product_annuity" in modal_content
    assert "经代业务</td><td>--" not in modal_content


def test_kpi_year_comparison_accepts_numeric_api_year():
    kpi = read_js("kpi-cards.js")
    assert "String(kpi.year) === year" in kpi
    assert "kpi.year === year" not in kpi


def test_tenyear_kpi_includes_jingdai_in_card_and_modal():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    modal_content = read_js("kpi-modal-content.js")
    combined = html + "\n" + kpi + "\n" + modal_content
    assert "kpi.tenyear_jd" in combined
    assert "kpi.tenyear_tf" in combined
    assert "未配置10年期产品目标" in combined
    assert "Math.round(kpiData.tenyear_jd || 0)" in combined
    assert "targetCategory = is10y ? 'tenYear' : 'qjPremium'" in combined


def test_frontend_centralizes_read_api_fetches():
    html = read_html()
    api_client = read_js("api-client.js")
    # Shared runtime modules are loaded in HTML head
    assert '<script src="js/constants.js"></script>' in html
    assert '<script src="js/format-utils.js"></script>' in html
    assert '<script src="js/api-client.js?v=1.0.68"></script>' in html
    assert '<script src="js/auth-ui.js?v=1.0.68"></script>' in html
    assert '<script src="js/export-excel.js"></script>' in html
    assert '<script src="js/upload.js"></script>' in html
    assert '<script src="js/target-modal.js"></script>' in html
    assert '<script src="js/kpi-cards.js?v=1.0.57"></script>' in html
    assert '<script src="js/platform-trend.js"></script>' in html
    assert '<script src="js/team-analysis.js?v=1.0.68"></script>' in html
    # api-client centralizes fetchJson / adminFetch / apiUrl
    assert "function apiUrl(path)" not in html
    assert "async function fetchJson(path" not in html
    assert "function apiUrl(path)" in api_client
    assert "async function fetchJson(path" in api_client
    assert "window.adminFetch = authFetch" in api_client
    # No raw fetch with template literals in HTML
    assert "fetch(`${API_BASE}/api/data/" not in html
    assert "fetch(`${API_BASE}/api/kpi/" not in html
    assert "fetch(`${API_BASE}/api/product/" not in html
    assert "fetch(`${API_BASE}/api/org-kpi/" not in html
    # API URLs are only expected in the active runtime boundary plus the current HTML shell.
    js_files = ["platform-trend.js", "kpi-cards.js", "dashboard-config.js", "export-excel.js", "product-config-modal.js",
                "kpi-modal-content.js", "org-analysis.js", "seed-data.js", "data-integration.js",
                "product-analysis.js", "payperiod-chart.js", "team-analysis.js", "target-modal.js"]
    all_js = read_html() + " ".join(read_js(f) for f in js_files if os.path.exists(os.path.join(JS_DIR, f)))
    assert "/api/platform-data?year=" in all_js
    assert "/api/kpi?year=" in all_js
    assert "/api/product-analysis?" in all_js
    assert "/api/org-analysis?year=" in all_js
    assert "/api/targets?year=" in all_js


def test_permission_admin_can_manage_admin_role_and_save_column_is_fixed():
    html = read_html()
    auth_ui = read_js("auth-ui.js")
    assert "team_enhanced: '队伍结构与产能分析'" in auth_ui
    assert "const ROLE_OPTIONS = ['normal', 'senior', 'admin']" in auth_ui
    assert "ROLE_OPTIONS.map(role" in auth_ui
    assert "user.role === 'admin' ? 'disabled'" not in auth_ui
    assert "permission-action-cell" in auth_ui
    assert "permission-save-btn" in auth_ui
    assert ".permission-action-cell" in html
    assert ".permission-save-btn" in html
    assert "position: sticky; right: 0" in html
    assert ".permission-table { width: 100%; min-width: 0; table-layout: fixed; }" in html


def test_local_seed_data_remains_available_when_api_is_slow_or_unavailable():
    html = read_html()
    upload = read_js("upload.js")
    seed = read_js("seed-data.js")
    data_integration = read_js("data-integration.js")
    combined = html + "\n" + upload + "\n" + seed + "\n" + data_integration
    assert "const productData =" not in html
    assert "const teamMock =" not in html
    assert "const productData =" in seed
    assert "const teamMock =" in seed
    assert "ALLOW_LOCAL_FALLBACK" in data_integration
    assert "clearRuntimeFallbackYear" in data_integration
    assert "暂保留本地兜底数据" in combined
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
        path = ref.split("?", 1)[0]
        assert os.path.exists(os.path.join(ROOT, path)), f"Missing: {ref}"


def test_runtime_js_boundary_is_explicit():
    import re
    html = read_html()
    refs = [ref.split("?", 1)[0] for ref in re.findall(r'src="(js/[^"]+)"', html)]
    assert refs == [
        "js/constants.js",
        "js/format-utils.js",
        "js/api-client.js",
        "js/auth-ui.js",
        "js/export-excel.js",
        "js/dashboard-config.js",
        "js/upload.js",
        "js/target-modal.js",
        "js/kpi-cards.js",
        "js/platform-trend.js",
        "js/product-config-modal.js",
        "js/kpi-modal-content.js",
        "js/org-analysis.js",
        "js/seed-data.js",
        "js/data-integration.js",
        "js/platform-trend-main.js",
        "js/product-analysis.js",
        "js/payperiod-chart.js",
        "js/team-analysis.js",
    ]
    with open(os.path.join(JS_DIR, "README.md"), "r", encoding="utf-8") as f:
        note = f.read()
    assert "Current production runtime" in note
    assert "archived under `bak/20260524_stability_archive/js_unused/`" in note


def test_dashboard_config_is_loaded_before_kpi_cards():
    html = read_html()
    config = read_js("dashboard-config.js")

    assert '<script src="js/dashboard-config.js"></script>' in html
    assert html.index('js/dashboard-config.js') < html.index('js/kpi-cards.js')
    assert "await loadDashboardConfig();" in html
    assert "/api/config/metrics" in config
    assert "dashboardKpiCards" in config


def test_product_config_modal_is_outside_html_shell():
    html = read_html()
    modal = read_js("product-config-modal.js")

    assert '<script src="js/product-config-modal.js"></script>' in html
    assert "async function openProductConfigModal()" not in html
    assert "async function saveProductConfig()" not in html
    assert "async function openProductConfigModal()" in modal
    assert "async function saveProductConfig()" in modal


def test_excel_export_is_runtime_module():
    html = read_html()
    exporter = read_js("export-excel.js")

    assert '<script src="js/export-excel.js"></script>' in html
    assert 'id="exportExcelBtn"' in html
    assert "function exportDashboardExcel()" not in html
    assert "function exportDashboardExcel()" in exporter
    assert "/api/export/excel?year=" in exporter
    assert "window.exportDashboardExcel = exportDashboardExcel" in exporter


def test_account_auth_replaces_admin_token_prompt():
    html = read_html()
    api_client = read_js("api-client.js")
    auth_ui = read_js("auth-ui.js")
    upload = read_js("upload.js")
    combined = html + "\n" + api_client + "\n" + auth_ui + "\n" + upload

    assert "business_admin_token" not in combined
    assert "X-Admin-Token" not in combined
    assert "Admin Token" not in combined
    assert "requireAuthenticatedUser" in html
    assert "权限管理" in html
    assert 'data-permission="permission_admin"' in html
    assert 'data-permission="upload"' in html
    assert 'data-permission="excel_export"' in html
    assert "/api/auth/${mode}" in auth_ui
    assert "/api/admin/users" in auth_ui
    assert "function ensureAuthClient()" in auth_ui
    assert "window.setAuthSession = function" in auth_ui


def test_kpi_modal_content_is_outside_html_shell():
    html = read_html()
    modal_content = read_js("kpi-modal-content.js")

    assert '<script src="js/kpi-modal-content.js?v=1.0.57"></script>' in html
    assert "function getModalContent(type)" not in html
    assert "function getModalContent(type)" in modal_content


def test_dynamic_org_controls_do_not_inline_unescaped_orgs():
    html = read_html()
    combined = html + "\n" + read_js("org-analysis.js") + "\n" + read_js("product-analysis.js") + "\n" + read_js("payperiod-chart.js")
    assert "onchange=\"togglePayPeriodOrg('${org}'" not in combined
    assert "onchange=\"toggleProductOrg('${org}'" not in combined
    assert "wrapper.innerHTML = orgs.map" not in combined
    assert "container.innerHTML = orgs.map" not in combined


def test_org_analysis_has_expand_mode_and_colored_indicators():
    html = read_html()
    org = read_js("org-analysis.js")
    combined = html + "\n" + org

    assert 'src="js/org-analysis.js?v=1.0.53"' in html
    assert 'id="orgExpandBtn"' in html
    assert 'id="orgExpandBtn" type="button" aria-expanded="false"' in html
    assert 'id="orgExpandBtn" onclick=' not in html
    assert "function toggleOrgExpand(event)" in org
    assert "let orgExpanded = false" in org
    assert "btn.addEventListener('click', toggleOrgExpand)" in org
    assert "window.toggleOrgExpand = toggleOrgExpand" in org
    assert "window.renderOrgTable = renderOrgTable" in org
    assert "aria-expanded" in org
    assert "qjPrev === 0 && valuePrev === 0" in org
    assert "都要进入同比分母" in org
    assert "机构汇总" in org
    assert "aggregateOrgRows" in org
    assert "calcOrgTimeProgressPercent" in org
    assert "rate >= 100 ? 'org-ind-red' : rate >= progress ? 'org-ind-light-red' : 'org-ind-green'" in org
    assert "yoy >= 10 ? 'org-ind-red' : yoy >= 0 ? 'org-ind-light-red' : 'org-ind-green'" in org
    assert 'return `<td class="${cls}">${fmtOrgPct(rate)}</td>`' in org
    assert 'return `<td class="${cls}">${fmtOrgPct(yoy, true)}</td>`' in org
    assert "toFixed(1)" in org
    assert ".org-table .org-ind-green" in combined
    assert ".org-table .org-ind-light-red" in combined
    assert ".org-table .org-ind-red" in combined


def test_org_analysis_includes_annual_longterm_qj_metric():
    org = read_js("org-analysis.js")

    assert "function getOrgLongtermMetric(source, org, channel)" in org
    assert "'longterm': 'qjPremium'" in org
    assert "if (metric === 'longterm') return item.year || 0;" in org
    assert "longtermTarget" in org
    assert "longtermActual" in org
    assert "longtermRate" in org
    assert "\u957f\u9669\u671f\u4ea4\uff08\u5e74\u5ea6\uff09" in org


def test_upload_js_exposes_handle_file():
    html = read_html()
    upload = read_js("upload.js")
    assert "async function handleFile(input, infoId)" not in html
    assert "window.handleFile = handleFile" in upload
    assert "try {" in upload
    assert "} catch" in upload
    assert "} finally" in upload


def test_target_modal_js_is_runtime_owner_for_target_settings():
    html = read_html()
    target = read_js("target-modal.js")

    assert "async function openTargetModal()" not in html
    assert "async function openTargetModal()" in target
    assert "function createDefaultTargetData(year)" in target
    assert "function saveTargetData(evt)" in target
    assert "function updateKPICards()" not in target


def test_kpi_cards_js_is_runtime_owner_for_kpi_cards():
    html = read_html()
    kpi = read_js("kpi-cards.js")

    assert "function updateKPICards()" not in html
    assert 'src="js/kpi-cards.js?v=1.0.57"' in html
    assert "function updateKPICards()" in kpi
    assert "window.updateKPICards = updateKPICards" in kpi
    assert "KPI card rendering lives in js/kpi-cards.js" in html


def test_qj_kpi_card_shows_business_line_yoy():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    combined = html + "\n" + kpi

    assert "kpi.qj_premium_prev || {}" in kpi
    assert "calcYoy(整体实际, qjPrev.total)" in kpi
    assert "calcYoy(经代实际, qjPrev.jingdai)" in kpi
    assert "calcYoy(转型实际, qjPrev.total_transform)" in kpi
    assert "整体 <span" in kpi
    assert "同比 ${yoyText(整体同比)}" in kpi
    assert "同比 ${yoyText(经代同比)}" in kpi
    assert "同比 ${yoyText(转型同比)}" in kpi
    assert ".kpi-bottom-meta .kpi-yoy-negative" in combined
    assert ".kpi-bottom-meta .kpi-yoy-mid" in combined
    assert ".kpi-bottom-meta .kpi-yoy-strong" in combined


def test_qj_modal_shows_yoy_column():
    modal = read_js("kpi-modal-content.js")
    assert "qj_premium_prev" in modal
    assert "<th>同比</th>" in modal
    assert "function qjRow(label, target, actual, prev" in modal
    assert "yoy(actual, prev)" in modal
    assert "qjRow('整体', ztT, ztA, prevZtA" in modal
    assert "qjRow('经代', jdT, jdA, prevJdA)" in modal
    assert "qjRow('转型业务', zxT, zxA, prevZxA)" in modal


def test_value_kpi_includes_jingdai_placeholder():
    kpi = read_js("kpi-cards.js")
    modal = read_js("kpi-modal-content.js")
    exporter = open(os.path.join(ROOT, "backend", "services", "excel_exporter.py"), "r", encoding="utf-8").read()
    backend_kpi = open(os.path.join(ROOT, "backend", "db", "repositories", "kpi.py"), "r", encoding="utf-8").read()
    combined = kpi + "\n" + modal + "\n" + exporter + "\n" + backend_kpi
    assert "value.setdefault('经代', 0.0)" in backend_kpi
    assert "const jingdai = value['经代'] || 0" in kpi
    assert "channels: ['经代', 'OTO', '证保', '蚁桥']" in modal
    assert "价值达成率口径包含经代" in modal
    assert "经代价值数据表尚未接入，经代实绩暂按 0 展示" in modal
    assert "经代+OTO+证保+蚁桥" in exporter


def test_structure_modules_are_same_level_with_tables():
    html = read_html()
    product = read_js("product-analysis.js")
    payperiod = read_js("payperiod-chart.js")
    data_integration = read_js("data-integration.js")
    backend_product = open(os.path.join(ROOT, "backend", "db", "repositories", "product.py"), "r", encoding="utf-8").read()
    combined = html + "\n" + product + "\n" + payperiod + "\n" + data_integration + "\n" + backend_product

    assert 'id="structureSection"' in html
    assert "产品与交期结构" in html
    assert 'id="productTopTableWrapper"' in html
    assert 'id="payPeriodTableWrapper"' in html
    assert html.index('<span class="chart-title">业务平台趋势</span>') < html.index("产品与交期结构")
    assert html.index("产品与交期结构") < html.index('<span class="chart-title">产品结构</span>')
    assert html.index("产品与交期结构") < html.index('<span class="chart-title">交期结构</span>')
    assert "function renderProductTopTable(rows)" in product
    assert "前三名产品" in product
    assert "rank" in product
    assert "期交保费" in product
    assert "模式内占比" in product
    assert "function renderPayPeriodTable()" in payperiod
    assert "保费占比" in payperiod
    assert "件数占比" in payperiod
    assert "topProducts" in combined
    assert "renderProductTopTable(product.topProducts || [])" in data_integration
    assert "def _query_top_products_by_business_line" in backend_product


def test_team_enhanced_panel_is_added_without_replacing_team_trend():
    html = read_html()
    team = read_js("team-analysis.js")
    data_integration = read_js("data-integration.js")
    combined = html + "\n" + team + "\n" + data_integration

    assert 'id="teamChart"' in html
    assert 'id="teamEnhancedPanel"' in html
    assert "队伍结构与产能分析（试运行）" not in html
    assert "队伍结构与产能分析" in html
    assert 'data-permission="team_enhanced"' in html
    assert "async function fetchTeamEnhancedData()" in team
    assert "/api/team-enhanced-analysis" in team
    assert "window.fetchJson(`/api/team-enhanced-analysis?" in team
    assert "function renderTeamEnhancedPanel()" in team
    assert "teamTenureStructureTable" in team
    assert "teamProductivityBandTable" in team
    assert "teamPercentileTable" in team
    assert "teamProductivityTrendTable" in team
    assert "teamOrgPercentileTable" in team
    assert "switchTeamEnhancedPeriodType" in team
    assert "switchTeamEnhancedPeriodValue" in team
    assert "selectedTeamEnhancedBusinessLine" in team
    assert "switchTeamEnhancedBusinessLine" in team
    assert "team-enhanced-controls" in team
    assert "team-enhanced-control-label" in team
    assert "业务模式" in team
    assert "['全部', 'OTO', '证保', '蚁桥']" in team
    assert "periodType" in team
    assert "periodValue" in team
    assert "≥P25人数" in team
    assert "≥P50人数" in team
    assert "≥P75人数" in team
    assert "零/负产能占比" in team
    assert "P50 中位数" in team
    assert "P75 骨干门槛" in team
    assert "诊断矩阵" not in team
    assert "接入人级底座" not in team
    assert "待接入人级月度底座" not in team
    assert "需完善人员月度明细统计" not in team
    assert "需完善人员产能分布统计" not in team
    assert "月度按当月个人期交保费计算" in team
    assert "P 值人数为达到该分位阈值及以上的人数" in team
    assert "#teamEnhancedPanel .team-insight-grid { grid-template-columns: repeat(2, minmax(0, 1fr));" in html
    assert "#teamEnhancedPanel .team-insight-grid {\n        grid-template-columns: 1fr;" in html
    assert "#teamEnhancedPanel .structure-table {\n        min-width: 680px;" in html
    assert "#teamEnhancedPanel #teamTenureStructureTable" in html
    assert "if (typeof refreshTeamEnhancedPanel === 'function') refreshTeamEnhancedPanel();" in combined


def test_metric_calculation_review_report_exists():
    report_path = os.path.join(ROOT, "docs", "指标计算口径核对报告_v1.0.55.md")
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        report = f.read()
    assert "期交保费达成率" in report
    assert "长险活动率同比不是相对增速" in report
    assert "target_config" in report
    assert "当前 KPI 实绩按各来源自身日级截止日" in report
    assert "机构维度不纳入未归属机构业绩" in report
    assert "整体同比 = 本年整体期交保费累计 / 去年整体同截止日累计 - 1" in report


def test_platform_trend_uses_calendar_days_for_daily_series():
    html = read_html()
    platform = read_js("platform-trend.js")
    platform_main = read_js("platform-trend-main.js")
    combined = html + "\n" + platform + "\n" + platform_main
    assert "function daysInMonth(year, month)" not in html
    assert "function dailyDisplayEndDay(year, month)" not in html
    assert "function completeDailySeries(values, year, month)" not in html
    assert "function daysInMonth(year, month)" in platform
    assert "function dailyDisplayEndDay(year, month)" in platform
    assert "function completeDailySeries(values, year, month)" in platform
    assert "new Date(Number(year), Number(month), 0).getDate()" in platform
    assert "m === now.getMonth() + 1" in platform
    assert "window.completeDailySeries = completeDailySeries" in platform
    assert "daysInMonthArr" not in html
    assert "function trimDailySeries" not in html
    assert "completeDailySeries(monthData[key], year, month)" in combined


def test_platform_trend_main_is_loaded_at_runtime_boundary():
    html = read_html()
    platform_main = read_js("platform-trend-main.js")

    assert "const platformChart = echarts.init(document.getElementById('platformChart'))" not in html
    assert "const platformChart = echarts.init(document.getElementById('platformChart'))" in platform_main
    assert '<script src="js/platform-trend-main.js"></script>' in html
    assert "function refreshPlatformChart()" in platform_main
    assert "function switchYear(value)" in platform_main


def test_per_capita_metrics_use_average_headcount_denominators():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    target_modal = read_js("target-modal.js")
    modal_content = read_js("kpi-modal-content.js")
    combined = html + "\n" + kpi + "\n" + target_modal + "\n" + modal_content

    assert "月均新单保费 / 月均在职人力" in combined
    assert "const 月均保费 = 统计月数 > 0 ? 总保费 / 统计月数 : 总保费;" in combined
    assert "avgSum / months" in combined
    assert "avgArr(tm.headcount['OTO'])" in combined
    assert "sumArr(tm.headcount['OTO']) + sumArr(tm.headcount['证保'])" not in combined
    assert "res.totalPrem += p; res.totalAvg += a;" in combined
    assert "res.totalAvg = Math.round(res.totalAvg * 10) / 10;" in combined
    assert "res.ch[ch] = { prem: p, avg: a, pc: calcPC(p, a, periodMonths) }" in combined
    assert "res.totalPc = calcPC(res.totalPrem, res.totalAvg, periodMonths);" in combined
    assert "res.ch[ch] = { prem: p, avg: aSum, pc: calcPC(p, aSum) }" not in combined
