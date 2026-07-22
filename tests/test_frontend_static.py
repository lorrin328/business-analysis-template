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
    assert "allowLocalTargetCache" in target
    assert "本机开发缓存目标" in target


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
    assert '<script src="js/api-client.js?v=1.0.107"></script>' in html
    assert '<script src="js/auth-ui.js?v=1.0.107"></script>' in html
    assert '<script src="js/export-excel.js?v=1.0.107"></script>' in html
    assert '<script src="js/upload.js?v=1.0.107"></script>' in html
    assert '<script src="js/target-modal.js?v=1.0.107"></script>' in html
    assert '<script src="js/kpi-cards.js?v=1.0.107"></script>' in html
    assert '<script src="js/platform-trend.js?v=1.0.107"></script>' in html
    assert '<script src="js/team-analysis.js?v=1.0.107"></script>' in html
    # api-client centralizes fetchJson / adminFetch / apiUrl
    assert "function apiUrl(path)" not in html
    assert "async function fetchJson(path" not in html
    assert "function apiUrl(path)" in api_client
    assert "async function fetchJson(path" in api_client
    assert "window.adminFetch = authFetch" in api_client
    assert "function withRefreshNonce" in api_client
    assert "fetchOptions.cache = 'no-store'" in api_client
    assert "'Cache-Control': 'no-cache'" in api_client
    # No raw fetch with template literals in HTML
    assert "fetch(`${API_BASE}/api/data/" not in html
    assert "fetch(`${API_BASE}/api/kpi/" not in html
    assert "fetch(`${API_BASE}/api/product/" not in html
    assert "fetch(`${API_BASE}/api/org-kpi/" not in html
    # API URLs are only expected in the active runtime boundary plus the current HTML shell.
    js_files = ["platform-trend.js", "kpi-cards.js", "dashboard-config.js", "dashboard-actions.js", "export-excel.js", "product-config-modal.js",
                "kpi-modal-content.js", "org-analysis.js", "seed-data.js", "data-integration.js",
                "product-analysis.js", "payperiod-chart.js", "team-analysis.js", "target-modal.js"]
    all_js = read_html() + " ".join(read_js(f) for f in js_files if os.path.exists(os.path.join(JS_DIR, f)))
    assert "/api/platform-data?year=" in all_js
    assert "/api/kpi?year=" in all_js
    assert "/api/product-analysis?" in all_js
    assert "/api/org-analysis?" in all_js
    assert "/api/targets?year=" in all_js


def test_permission_admin_can_manage_admin_role_with_batch_save_and_delete():
    html = read_html()
    auth_ui = read_js("auth-ui.js")
    assert "team_enhanced: '队伍结构与产能分析'" in auth_ui
    assert "personnel_management: '人员管理'" in auth_ui
    assert "scheme_calculation: '方案计算'" in auth_ui
    assert "scheme_upload: '方案上传'" in auth_ui
    assert "const ROLE_OPTIONS = ['normal', 'senior', 'admin']" in auth_ui
    assert "ROLE_OPTIONS.map(role" in auth_ui
    assert "user.role === 'admin' ? 'disabled'" not in auth_ui
    assert "permission-action-cell" in auth_ui
    assert "permission-delete-btn" in auth_ui
    assert "permission-save-all-btn" in auth_ui
    assert "saveAllUserPermissions" in auth_ui
    assert "deletePermissionUser" in auth_ui
    assert "onclick=\"saveUserPermission" not in auth_ui
    assert "onclick=\"saveAllUserPermissions()\"" not in auth_ui
    assert "onclick=\"deletePermissionUser" not in auth_ui
    assert 'data-action="save-all-users"' in auth_ui
    assert 'data-action="delete-user"' in auth_ui
    assert "bindPermissionAdminActions" in auth_ui
    assert ".permission-action-cell" in html
    assert ".permission-delete-btn" in html
    assert ".permission-save-all-btn" in html
    assert "position: sticky; right: 0" in html
    assert ".permission-table { width: 100%; min-width: 0; table-layout: fixed; }" in html


def test_local_seed_data_is_development_only_when_api_is_slow_or_unavailable():
    html = read_html()
    upload = read_js("upload.js")
    seed = read_js("seed-data.js")
    data_integration = read_js("data-integration.js")
    combined = html + "\n" + upload + "\n" + seed + "\n" + data_integration
    assert "const productData =" not in html
    assert "const teamMock =" not in html
    assert "const productData =" in seed
    assert "const teamMock =" in seed
    assert "const productFallbackData = {};" in seed
    assert "const teamMock = {};" in seed
    assert "ALLOW_LOCAL_FALLBACK" in data_integration
    assert "window.ALLOW_LOCAL_FALLBACK = ALLOW_LOCAL_FALLBACK" in data_integration
    assert "window.location.hostname" in data_integration
    assert "localFallback') === '1'" in data_integration
    assert "服务端数据加载失败" in data_integration
    assert "开发环境：本地兜底数据" in data_integration
    assert "Object.keys(productFallbackData).forEach(key => delete productFallbackData[key])" in data_integration
    assert "Object.keys(teamMock).forEach(key => delete teamMock[key])" in data_integration
    assert "clearRuntimeFallbackYear" in data_integration
    assert "已重新写入并刷新看板数据" in combined
    assert "await fetchTargetData(DEFAULT_DASHBOARD_YEAR_NUM);\n      const ok = await loadYearFromApi" in html


def test_frontend_seed_files_do_not_publish_business_values():
    seed = read_js("seed-data.js")
    platform_seed = read_js("platform-seed-data.js")

    assert "const platformMock = {};" in platform_seed
    assert "const productFallbackData = {};" in seed
    assert "const teamMock = {};" in seed
    assert '"2026"' not in seed
    assert '"2026"' not in platform_seed


def test_upload_js_no_duplicate_vars():
    upload = read_js("upload.js")
    import re
    declarations = re.findall(r'(?:const|let|var)\s+_uploading', upload)
    assert len(declarations) <= 1, f"Duplicate _uploading: {declarations}"
    assert "/api/upload?force=' + force" in upload
    assert "forceUploadRewrite" in upload
    assert "已重新写入并刷新看板数据" in upload
    assert "未写入数据" in upload
    assert "var uploadYear = _pickRefreshYear(years)" in upload
    assert "years.length > 0 ? years[0]" not in upload
    assert "normalized[normalized.length - 1]" in upload
    assert "window.__apiRefreshNonce = Date.now()" in upload
    assert "window._pickUploadRefreshYear = _pickRefreshYear" in upload


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
        "js/dashboard-actions.js",
        "js/kpi-cards.js",
        "js/platform-trend.js",
        "js/product-config-modal.js",
        "js/kpi-modal-content.js",
        "js/org-analysis.js",
        "js/seed-data.js",
        "js/platform-seed-data.js",
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

    assert '<script src="js/dashboard-config.js?v=1.0.107"></script>' in html
    assert html.index('js/dashboard-config.js') < html.index('js/kpi-cards.js')
    assert "await loadDashboardConfig();" in html
    assert "/api/config/metrics" in config
    assert "dashboardKpiCards" in config
    assert ".kpi-card[data-kpi-modal]" in config
    assert '[onclick="openModal(' not in config


def test_product_config_modal_is_outside_html_shell():
    html = read_html()
    modal = read_js("product-config-modal.js")

    assert '<script src="js/product-config-modal.js?v=1.0.107"></script>' in html
    assert "async function openProductConfigModal()" not in html
    assert "async function saveProductConfig()" not in html
    assert "async function openProductConfigModal()" in modal
    assert "async function saveProductConfig()" in modal
    assert 'onclick="closeModal()"' not in modal
    assert 'onclick="saveProductConfig()"' not in modal
    assert 'data-product-config-action="cancel"' in modal
    assert 'data-product-config-action="save"' in modal
    assert "function bindProductConfigActions()" in modal


def test_modal_close_controls_are_bound_by_modal_script():
    html = read_html()
    modal_shell = html.split('<!-- Modal -->', 1)[1].split('<!-- Product config modal lives', 1)[0]

    assert 'id="modalOverlay" onclick=' not in modal_shell
    assert 'onclick="event.stopPropagation()"' not in modal_shell
    assert 'onclick="closeModal()"' not in modal_shell
    assert 'data-modal-action="close"' in modal_shell
    assert "function closeModal(e)" in modal_shell
    assert "function bindModalControls()" in modal_shell
    assert "modalOverlay.addEventListener('click', closeModal)" in modal_shell
    assert "button.addEventListener('click', () => closeModal())" in modal_shell
    assert "modalOverlay.classList.remove('modal-target')" in modal_shell
    assert "modalOverlay.classList.remove('modal-product-config')" in modal_shell


def test_dashboard_toolbar_actions_are_bound_by_runtime_module():
    html = read_html()
    actions = read_js("dashboard-actions.js")
    header = html.split('<div class="container">', 1)[0]

    assert '<script src="js/dashboard-actions.js?v=1.0.107"></script>' in html
    assert html.index('js/target-modal.js') < html.index('js/dashboard-actions.js') < html.index('js/kpi-cards.js')
    assert 'data-dashboard-action="open-permission-admin"' in header
    assert 'data-dashboard-action="open-operation-logs"' in header
    assert 'data-dashboard-action="navigate" data-dashboard-href="/personnel-management.html"' in header
    assert 'data-dashboard-action="navigate" data-dashboard-href="/honor"' in header
    assert 'data-dashboard-action="navigate" data-dashboard-href="/scheme-calculator.html"' in header
    assert 'data-dashboard-action="export-excel"' in header
    assert 'data-dashboard-action="open-product-config"' in header
    assert 'data-dashboard-action="open-targets"' in header
    assert 'data-dashboard-action="recalculate"' in header
    assert 'data-dashboard-action="logout"' in header
    assert 'onclick="openPermissionAdmin()"' not in header
    assert 'onclick="openOperationLogs()"' not in header
    assert 'onclick="exportDashboardExcel()"' not in header
    assert 'onclick="openProductConfigModal()"' not in header
    assert 'onclick="openTargetModal()"' not in header
    assert 'onclick="recalculateDashboard()"' not in header
    assert 'onclick="logout()"' not in header
    assert "const ACTIONS =" in actions
    assert "'open-product-config': () => invokeGlobal('openProductConfigModal')" in actions
    assert "document.querySelector('.header-right')?.addEventListener('click', handleDashboardAction)" in actions


def test_excel_export_is_runtime_module():
    html = read_html()
    exporter = read_js("export-excel.js")

    assert '<script src="js/export-excel.js?v=1.0.107"></script>' in html
    assert 'id="exportExcelBtn"' in html
    assert "function exportDashboardExcel()" not in html
    assert "function exportDashboardExcel()" in exporter
    assert "/api/export/excel?${params.toString()}" in exporter
    assert "appendDashboardRange(params)" in exporter
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
    assert 'data-permission="personnel_management"' in html
    assert 'data-dashboard-action="navigate" data-dashboard-href="/personnel-management.html"' in html
    assert 'data-permission="honor_view"' in html
    assert 'data-dashboard-action="navigate" data-dashboard-href="/honor"' in html
    assert 'data-permission="scheme_calculation"' in html
    assert 'data-dashboard-action="navigate" data-dashboard-href="/scheme-calculator.html"' in html
    assert 'data-permission="upload"' in html
    assert 'data-permission="excel_export"' in html
    assert "/api/auth/${mode}" in auth_ui
    assert "/api/auth/config" in auth_ui
    assert "allowPublicRegistration" in auth_ui
    assert "switchAuthMode('register')" in auth_ui
    assert "authConfirmPassword" in auth_ui
    assert "authSubmitRegisterBtn" in auth_ui
    assert "新注册账号默认为普通用户" in auth_ui
    assert "honor_view: '星钻联盟查看'" in auth_ui
    assert "honor_recalculate: '星钻重算'" in auth_ui
    assert "scheme_upload: '方案上传'" in auth_ui
    assert "/api/admin/users" in auth_ui
    assert "function ensureAuthClient()" in auth_ui
    assert "window.setAuthSession = function" in auth_ui


def test_deploy_preserves_runtime_environment_files():
    with open(os.path.join(ROOT, "deploy", "deploy.sh"), "r", encoding="utf-8") as f:
        deploy = f.read()
    assert "--exclude='deploy/.admin_env'" in deploy
    assert "--exclude='deploy/.ai_env'" in deploy
    assert "--exclude='deploy/.webhook_env'" in deploy
    assert 'REBUILD_DATABASE="${REBUILD_DATABASE:-auto}"' in deploy
    assert 'DB_EXISTED_BEFORE=1' in deploy
    assert "默认不从 Excel 全量重建" in deploy
    assert "REBUILD_DATABASE=1" in deploy
    assert "systemctl disable --now webhook-deploy" in deploy
    assert "rm -f /etc/sudoers.d/webhook-deploy" in deploy
    assert "cp \"$APP_DIR/deploy/webhook.service\" /etc/systemd/system/webhook-deploy.service" not in deploy
    assert "systemctl enable webhook-deploy" not in deploy
    assert 'DATA_DIR="${DATA_DIR:-/var/lib/business-analysis}"' in deploy
    assert 'python3 "$SRC_DIR/backend/backup_database.py"' in deploy
    assert 'chown -R root:root "$APP_DIR"' in deploy
    assert 'chown -R "$RUN_USER:$RUN_USER" "$DATA_DIR" "$LOG_DIR"' in deploy
    assert "SQLite 原始表重建失败，部署已中止" in deploy


def test_personnel_management_page_is_admin_only_calculator_runtime():
    html = read_html()
    page_path = os.path.join(ROOT, "personnel-management.html")
    with open(page_path, "r", encoding="utf-8") as f:
        page = f.read()
    js = read_js("personnel-management.js")
    auth = open(os.path.join(ROOT, "backend", "auth.py"), "r", encoding="utf-8").read()

    assert "人员管理</button>" in html
    assert 'data-permission="personnel_management"' in html
    assert '<script src="/js/personnel-management.js?v=1.0.107"></script>' in page
    assert "OTO 基本法测算" in page
    assert "证保基本法测算" in page
    assert "OTO 参数设置" in page
    assert "证保参数设置" in page
    assert "整体基本法成本" in page
    assert "专员成本明细" in page
    assert "管理职成本明细" in page
    assert 'id="otoOverallTable"' in page
    assert 'id="otoSpecialistTable"' in page
    assert 'id="otoManagementTable"' in page
    assert 'id="zbOverallTable"' in page
    assert 'id="zbSpecialistTable"' in page
    assert 'id="zbManagementTable"' in page
    assert 'data-export="oto"' in page
    assert 'data-export="zhengbao"' in page
    assert "requirePersonnelAccess" in js
    assert "hasPermission('personnel_management')" in js
    assert "function calculateOto()" in js
    assert "function calculateZhengbao()" in js
    assert "function calculateOtoScenario" in js
    assert "function calculateZhengbaoScenario" in js
    assert "function renderOtoTables" in js
    assert "function renderZhengbaoTables" in js
    assert "function exportRows" in js
    assert "DEFAULT_SCENARIOS" in js
    assert "ZB_RATE_DICT" in js
    assert '"personnel_management"' in auth
    assert '{"permission_admin", "personnel_management", "honor_admin", "honor_upload", "scheme_upload"}' in auth
    assert '"personnel_management": False' in auth


def test_honor_page_is_separate_runtime():
    html = read_html()
    honor_path = os.path.join(ROOT, "honor.html")
    with open(honor_path, "r", encoding="utf-8") as f:
        honor_html = f.read()
    honor_js = read_js("honor.js")

    assert 'data-permission="honor_view" data-dashboard-action="navigate" data-dashboard-href="/honor">荣誉体系</button>' in html
    assert "????" not in html
    assert "星钻联盟荣誉体系" in honor_html
    assert '<script src="/js/honor.js?v=1.0.107"></script>' in honor_html
    assert "数据适配检查" in honor_html
    assert "数据审计" in honor_html
    assert "荣誉追踪" in honor_html
    assert "总览驾驶舱" in honor_html
    assert "机构追踪" in honor_html
    assert "项目分析" in honor_html
    assert "专员级" in honor_html
    assert "管理职" in honor_html
    assert "月度预警" in honor_html
    assert "/api/honor/dashboard" in honor_js
    assert "/api/honor/field-audit" in honor_js
    assert "/api/honor/recalculate" in honor_js
    assert "/api/honor/export?batchId=" in honor_js
    assert 'data-permission="honor_recalculate"' in honor_html
    assert 'id="honorAsOf" type="date"' in honor_html
    assert "function renderTracking()" in honor_js
    assert "function renderTopContributors" in honor_js
    assert "tracking.topContributors" in honor_js
    assert "asOf" in honor_js
    assert "function renderOverview()" in honor_js
    assert "function renderProjects()" in honor_js
    assert "function renderSpecialists()" in honor_js
    assert "function renderManagers()" in honor_js
    assert "function renderSpecialistHistory()" in honor_js
    assert "function renderManagerHistory()" in honor_js
    assert "function renderWarnings()" in honor_js
    assert "staff_name: '人员姓名'" in honor_js
    assert "manager_code: '主管/经理代码'" in honor_js
    assert "star_manpower_count: '团队会员人数'" in honor_js
    assert "qualified_months: '累计获钻次数'" in honor_js
    assert "tracking_policy_count: '当月件数'" in honor_js
    assert 'id="honorMonth" type="number" min="1" max="12" value="6"' in honor_html
    assert "avg_diamond: '人均钻石'" in honor_js
    assert "return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%`" in honor_js


def test_scheme_calculator_page_is_separate_runtime():
    html = read_html()
    page_path = os.path.join(ROOT, "scheme-calculator.html")
    with open(page_path, "r", encoding="utf-8") as f:
        page = f.read()
    js = read_js("scheme-calculator.js")
    auth = open(os.path.join(ROOT, "backend", "auth.py"), "r", encoding="utf-8").read()
    api = open(os.path.join(ROOT, "backend", "api", "scheme.py"), "r", encoding="utf-8").read()

    assert 'data-permission="scheme_calculation" data-dashboard-action="navigate" data-dashboard-href="/scheme-calculator.html">方案复核</button>' in html
    assert '<script src="/js/scheme-calculator.js?v=1.0.107"></script>' in page
    assert "方案计算" in page
    assert "2026年组发政策" in page
    assert "方案专用上传" in page
    assert "本模块上传独立于经营数据导入" in page
    assert 'id="schemeSelector"' in page
    assert 'id="schemeTrackingFile" data-scheme-upload-input type="file" accept=".xlsx"' in page
    assert 'data-upload-input' not in page
    assert '<script src="/js/upload.js' not in page
    assert "/api/scheme/options" in js
    assert "/api/scheme/latest?schemeId=" in js
    assert "/api/scheme/upload" in js
    assert "hasPermission('scheme_calculation')" in js
    assert "hasPermission('scheme_upload')" in js
    assert "function uploadWorkbook()" in js
    assert "function renderSchemeChoices()" in js
    assert "schemeTrackingFile" in js
    assert '"scheme_calculation"' in auth
    assert '"scheme_upload"' in auth
    assert "require_permission(\"scheme_calculation\")" in api
    assert "require_permission(\"scheme_upload\")" in api


def test_static_cutoff_starts_empty_until_server_data_arrives():
    html = read_html()
    data_integration = read_js("data-integration.js")
    assert 'id="dataCutoff">统计范围：--</span>' in html
    assert 'id="dashboardRangeType"' in html
    assert 'id="dashboardRangeStart"' in html
    assert 'id="dashboardRangeEnd"' in html
    assert 'id="dashboardRangeApply"' in html
    assert 'id="dataCutoffNote"' in html
    assert "switchDashboardAsOf(this.value)" not in html
    assert "function switchDashboardAsOf(value)" in data_integration
    assert "function bindDashboardAsOfControl()" in data_integration
    assert "addEventListener('click', applyDashboardRange)" in data_integration
    assert "function appendDashboardRange(params)" in data_integration
    assert "warningText" in data_integration
    assert '统计范围：2026年5月</span>' not in html


def test_dashboard_cache_reloads_after_server_normalizes_date_range():
    trend = read_js("platform-trend-main.js")
    load_fn = trend.split("async function loadYearFromApi", 1)[1].split("async function switchYear", 1)[0]
    assert "let cacheKey" in load_fn
    assert load_fn.count("cacheKey = typeof dashboardCacheKey") >= 2
    assert load_fn.index("await fetchAPIData(yearNum)") < load_fn.rindex("cacheKey = typeof dashboardCacheKey")


def test_per_capita_calculates_custom_date_ranges_by_covered_months():
    cards = read_js("kpi-cards.js")
    assert "completeMonthRange" not in cards
    assert "当前范围非完整月，人力按月统计，暂不计算" not in cards
    assert "区间保费按${统计月数}个覆盖月折算" in cards
    assert "const 月均保费 = 统计月数 > 0 ? 总保费 / 统计月数 : 总保费;" in cards
    assert "window.ALLOW_LOCAL_FALLBACK && tm" in cards


def test_incomplete_server_targets_are_not_marked_official():
    targets = read_js("target-modal.js")
    assert "function hasCompleteServerTarget(data)" in targets
    assert "targetDataSource = completeServerTarget ? 'server'" in targets
    assert "服务端目标不完整，暂不参与达成率" in targets


def test_raw_table_runtime_reads_are_explicit_column_lists():
    paths = [
        os.path.join(ROOT, "backend", "api", "product_config.py"),
        os.path.join(ROOT, "backend", "db", "repositories", "team_enhanced.py"),
        os.path.join(ROOT, "backend", "services", "aggregate_rebuilder.py"),
    ]
    combined = ""
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            combined += f.read()
    assert "SELECT * FROM performance" not in combined
    assert "SELECT * FROM jingdai" not in combined
    assert "SELECT * FROM hr_data" not in combined


def test_kpi_modal_content_is_outside_html_shell():
    html = read_html()
    modal_content = read_js("kpi-modal-content.js")

    assert '<script src="js/kpi-modal-content.js?v=1.0.107"></script>' in html
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

    assert 'src="js/org-analysis.js?v=1.0.107"' in html
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


def test_org_filter_controls_are_bound_by_org_analysis_js():
    html = read_html()
    org = read_js("org-analysis.js")
    org_section = html.split('<!-- Business Platform Trend -->', 1)[0].split('<!-- 机构维度 -->', 1)[1]

    assert 'onclick="toggleOrgFilter' not in org_section
    assert 'onclick="switchOrgDim' not in org_section
    assert 'onchange="renderOrgTable()"' not in org_section
    assert 'data-org-filter="all"' in org_section
    assert 'data-org-filter="上海"' in org_section
    assert 'data-org-dim="year"' in org_section
    assert 'data-org-dim="quarter"' in org_section
    assert 'data-org-dim="month"' in org_section
    assert "function bindOrgFilterControls()" in org
    assert "function bindOrgDimControls()" in org
    assert "function bindOrgPeriodControls()" in org
    assert "label[data-org-filter]" in org
    assert "button[data-org-dim]" in org
    assert "switchOrgDim(button.dataset.orgDim, button)" in org
    assert "orgSubPeriod = parseInt(qSelect.value, 10)" in org
    assert "orgSubMonth = parseInt(mSelect.value, 10)" in org
    assert "event.target.classList.add('active')" not in org


def test_org_analysis_includes_annual_longterm_qj_metric():
    org = read_js("org-analysis.js")

    assert "function getOrgLongtermMetric(source, org, channel)" in org
    assert "'longterm': 'qjPremium'" in org
    assert "if (metric === 'longterm') return item.year || 0;" in org
    assert "longtermTarget" in org
    assert "longtermActual" in org
    assert "longtermRate" in org
    assert "长险期交${globalRangeActive ? '' : '（年度）'}" in org


def test_upload_js_exposes_handle_file():
    html = read_html()
    upload = read_js("upload.js")
    upload_section = html.split('<!-- Modal -->', 1)[0].split('<!-- Upload Module -->', 1)[1]

    assert "async function handleFile(input, infoId)" not in html
    assert 'onclick="document.getElementById(' not in upload_section
    assert 'onchange="handleFile' not in upload_section
    assert 'data-upload-input="file1"' in upload_section
    assert 'data-upload-input="file2"' in upload_section
    assert 'data-upload-input="file3"' in upload_section
    assert 'data-upload-input="file4"' in upload_section
    assert 'data-upload-info="info1"' in upload_section
    assert 'data-upload-info="info2"' in upload_section
    assert 'data-upload-info="info3"' in upload_section
    assert 'data-upload-info="info4"' in upload_section
    assert "function bindUploadControls()" in upload
    assert ".upload-card[data-upload-input]" in upload
    assert "document.querySelectorAll('input[type=\"file\"][data-upload-info]')" in upload
    assert "handleFile(input, input.dataset.uploadInfo)" in upload
    assert "window.handleFile = handleFile" in upload
    assert "window.bindUploadControls = bindUploadControls" in upload
    assert "async function _readUploadError(resp)" in upload
    assert "Array.isArray(detail.errors)" in upload
    assert "导入失败: " in upload
    assert "resp.status === 400" in upload
    assert "服务器拒绝本次导入，请检查文件类型、字段和后端日志" in upload
    assert "window._readUploadError = _readUploadError" in upload
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
    assert "function bindTargetModalControls()" in target
    assert 'onchange="changeTargetYear' not in target
    assert 'onclick="exportTargetJSON' not in target
    assert 'onclick="document.getElementById' not in target
    assert 'onchange="importTargetJSON' not in target
    assert 'onclick="saveTargetData' not in target
    assert 'onchange="updateTargetValue' not in target
    assert 'onclick="switchOrgTargetDim' not in target
    assert 'onchange="updateOrgTargetValue' not in target
    assert 'data-target-year' in target
    assert 'data-target-action="export"' in target
    assert 'data-target-action="import"' in target
    assert 'data-target-action="distribute"' in target
    assert 'data-target-action="save"' in target
    assert 'data-target-section="business"' in target
    assert 'data-target-section="org"' in target
    assert 'data-target-period="${dim}"' in target
    assert 'data-target-import-file' in target
    assert 'data-target-value' in target
    assert 'target-save-state' in target
    assert 'target-balance' in target
    assert 'data-org-target-dim="year"' in target
    assert 'data-org-target-dim="quarter"' in target
    assert 'data-org-target-dim="month1"' in target
    assert 'data-org-target-dim="month2"' in target
    assert 'data-org-target-value' in target
    assert "button[data-target-action]" in target
    assert "body.querySelector('input[data-target-import-file]')?.click()" in target
    assert "button[data-target-section]" in target
    assert "switchTargetSection(sectionButton.dataset.targetSection)" in target
    assert "button[data-target-period]" in target
    assert "switchTargetPeriod(periodButton.dataset.targetPeriod)" in target
    assert "distributeTargetData()" in target
    assert "button[data-org-target-dim]" in target
    assert "switchOrgTargetDim(dimButton.dataset.orgTargetDim)" in target
    assert "select[data-target-year]" in target
    assert "changeTargetYear(yearSelect.value)" in target
    assert "input[data-target-value]" in target
    assert "updateTargetValue(targetInput)" in target
    assert "input[data-org-target-value]" in target
    assert "updateOrgTargetValue(orgTargetInput)" in target
    assert "body.addEventListener('input'" in target
    assert "window.fetchTargetData = fetchTargetData" in target
    assert "window.openTargetModal = openTargetModal" in target
    assert "closeModal();" not in target
    assert "function updateKPICards()" not in target


def test_kpi_cards_js_is_runtime_owner_for_kpi_cards():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    kpi_section = html.split('<!-- 机构维度 -->', 1)[0]

    assert "function updateKPICards()" not in html
    assert 'src="js/kpi-cards.js?v=1.0.107"' in html
    assert 'onclick="openModal(' not in kpi_section
    for modal_type in ["overall", "value", "activity", "annuity", "protection", "10year", "longterm", "percapita"]:
        assert f'data-kpi-modal="{modal_type}"' in kpi_section
    assert "function updateKPICards()" in kpi
    assert "function bindKPICardActions()" in kpi
    assert ".kpi-card[data-kpi-modal]" in kpi
    assert "window.openModal(modalType)" in kpi
    assert "window.updateKPICards = updateKPICards" in kpi
    assert "window.bindKPICardActions = bindKPICardActions" in kpi
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


def test_kpi_insight_panel_uses_current_kpi_context():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    combined = html + "\n" + kpi

    assert 'id="kpiInsightPanel"' in html
    assert "经营研判" not in html
    assert ".kpi-insight-panel" in html
    assert "function renderKpiInsight" in kpi
    assert "整体期交" in kpi
    assert "时间进度" in kpi
    assert "targetSourceLabel()" in kpi
    assert "kpi?.as_of?.selectedDate" in kpi
    assert "KPI 按" in kpi
    assert "经代贡献" in kpi
    assert "转型贡献" in kpi
    assert "window.ALLOW_LOCAL_FALLBACK" in kpi
    assert "renderKpiInsight({" in kpi
    assert ".kpi-insight-panel { grid-template-columns: 1fr; }" in combined


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


def test_product_structure_controls_are_bound_by_product_module():
    html = read_html()
    product = read_js("product-analysis.js")
    data_integration = read_js("data-integration.js")
    product_section = html.split('<div class="chart-card" data-permission="payment_period">', 1)[0].split('<div class="chart-card" data-permission="product_structure">', 1)[1]

    assert 'onclick="switchPie' not in product_section
    assert 'onchange="toggleProductSource' not in product_section
    assert 'onchange="toggleProductTransform' not in product_section
    assert 'onchange="toggleProductOrg' not in product_section
    assert 'onclick="switchProductDim' not in product_section
    assert 'onchange="switchProductSub' not in product_section
    assert 'onclick="switchProductMetric' not in product_section
    assert 'id="productPieTypeBtns"' in product_section
    assert 'data-product-pie-type="premium"' in product_section
    assert 'data-product-pie-type="count"' in product_section
    assert 'id="productSourceChecks"' in product_section
    assert 'data-product-source="transform"' in product_section
    assert 'data-product-transform="OTO"' in product_section
    assert 'data-product-org="all"' in product_section
    assert 'id="productDimBtns"' in product_section
    assert 'data-product-dim="year"' in product_section
    assert 'id="productMetricBtns"' in product_section
    assert 'data-product-metric="qj"' in product_section
    assert "function bindProductStructureControls()" in product
    assert "button[data-product-pie-type]" in product
    assert "input[data-product-source]" in product
    assert "input[data-product-transform]" in product
    assert "input[data-product-jingdai-org]" in product
    assert "input[data-product-org]" in product
    assert "button[data-product-dim]" in product
    assert "subSelect.addEventListener('change', () => switchProductSub(subSelect.value))" in product
    assert "button[data-product-metric]" in product
    assert "input.dataset[datasetKey] = String(labelText || '')" in data_integration
    assert "'productJingdaiOrg'" in data_integration
    assert "input.addEventListener('change'" not in data_integration


def test_pay_period_controls_are_bound_by_payperiod_module():
    html = read_html()
    payperiod = read_js("payperiod-chart.js")
    payperiod_section = html.split('<!-- Charts Row 2: Team Trend + YoY -->', 1)[0].split('<div class="chart-card" data-permission="payment_period">', 1)[1]

    assert 'onclick="switchPayPeriodPie' not in payperiod_section
    assert 'onchange="switchPayPeriodYear' not in payperiod_section
    assert 'onclick="switchPayPeriodDim' not in payperiod_section
    assert 'onchange="switchPayPeriodSub' not in payperiod_section
    assert 'onchange="togglePayPeriodBiz' not in payperiod_section
    assert 'onchange="togglePayPeriodChannel' not in payperiod_section
    assert 'onchange="togglePayPeriodOrg' not in payperiod_section
    assert 'onclick="switchPayPeriodMetric' not in payperiod_section
    assert 'id="payPeriodPieTypeBtns"' in payperiod_section
    assert 'data-pay-period-pie-type="premium"' in payperiod_section
    assert 'id="payPeriodDimBtns"' in payperiod_section
    assert 'data-pay-period-dim="year"' in payperiod_section
    assert 'id="payPeriodBizChecks"' in payperiod_section
    assert 'data-pay-period-biz="转型"' in payperiod_section
    assert 'data-pay-period-channel="OTO"' in payperiod_section
    assert 'data-pay-period-org="all"' in payperiod_section
    assert 'id="payPeriodMetricBtns"' in payperiod_section
    assert 'data-pay-period-metric="qj"' in payperiod_section
    assert "function bindPayPeriodControls()" in payperiod
    assert "button[data-pay-period-pie-type]" in payperiod
    assert "yearSelect.addEventListener('change', () => switchPayPeriodYear(yearSelect.value))" in payperiod
    assert "button[data-pay-period-dim]" in payperiod
    assert "subSelect.addEventListener('change', () => switchPayPeriodSub(subSelect.value))" in payperiod
    assert "input[data-pay-period-biz]" in payperiod
    assert "input[data-pay-period-channel]" in payperiod
    assert "input[data-pay-period-org]" in payperiod
    assert "input[data-pay-period-jingdai-org]" in payperiod
    assert "button[data-pay-period-metric]" in payperiod
    assert "createCheckboxLabel(org, true, 'payPeriodOrg')" in payperiod
    assert "createCheckboxLabel(org, true, 'productOrg')" in payperiod
    assert "createCheckboxLabel(org, checked, 'payPeriodJingdaiOrg')" in payperiod
    assert "createCheckboxLabel(org, true, togglePayPeriodOrg)" not in payperiod
    assert "createCheckboxLabel(org, true, toggleProductOrg)" not in payperiod


def test_team_trend_controls_are_bound_by_team_module():
    html = read_html()
    team = read_js("team-analysis.js")
    team_trend_section = html.split('<div class="chart-card" data-permission="team_enhanced">', 1)[0].split('<!-- Charts Row 2: Team Trend + YoY -->', 1)[1]

    assert 'onchange="switchTeamYear' not in team_trend_section
    assert 'onclick="switchTeamMetric' not in team_trend_section
    assert 'onclick="switchTeamDim' not in team_trend_section
    assert 'onchange="switchTeamQuarter' not in team_trend_section
    assert 'onchange="toggleTeamSeries' not in team_trend_section
    assert 'onchange="toggleTeamOrg' not in team_trend_section
    assert 'id="teamMetricBtns"' in team_trend_section
    assert 'data-team-metric="headcount"' in team_trend_section
    assert 'id="teamDimBtns"' in team_trend_section
    assert 'data-team-dim="year"' in team_trend_section
    assert 'data-team-series="OTO"' in team_trend_section
    assert 'data-team-org="all"' in team_trend_section
    assert 'data-team-org="上海"' in team_trend_section
    assert "function bindTeamTrendControls()" in team
    assert "yearSelect.addEventListener('change', () => switchTeamYear(yearSelect.value))" in team
    assert "button[data-team-metric]" in team
    assert "switchTeamMetric(button, button.dataset.teamMetric)" in team
    assert "button[data-team-dim]" in team
    assert "switchTeamDim(button, button.dataset.teamDim)" in team
    assert "quarterSelect.addEventListener('change', () => switchTeamQuarter(quarterSelect.value))" in team
    assert "input[data-team-series]" in team
    assert "toggleTeamSeries(input.dataset.teamSeries, input.checked)" in team
    assert "input[data-team-org]" in team
    assert "toggleTeamOrg(input.dataset.teamOrg, input.checked)" in team
    assert "document.querySelectorAll('#teamOrgChecks input[data-team-org]:not([data-team-org=\"all\"])')" in team
    assert "if (!data && !useOrgData) return Array(12).fill(null);" in team


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
    assert "async function fetchTeamEnhancedData(requestSerial)" in team
    assert "/api/team-enhanced-analysis" in team
    assert "window.fetchJson(`/api/team-enhanced-analysis?" in team
    assert "let teamEnhancedRequestSerial = 0;" in team
    assert "const requestSerial = ++teamEnhancedRequestSerial;" in team
    assert "if (requestSerial !== teamEnhancedRequestSerial) return false;" in team
    assert "if (teamEnhancedLoading) return;" not in team
    assert "function renderTeamEnhancedPanel()" in team
    assert "teamTenureStructureTable" in team
    assert "teamProductivityBandTable" in team
    assert "teamPercentileTable" in team
    assert "teamProductivityTrendTable" in team
    assert "teamOrgPercentileTable" in team
    assert "teamStandardManpowerSummaryTable" in team
    assert "teamStandardManpowerTrendTable" in team
    assert "teamStandardManpowerOrgTable" in team
    assert "teamStandardManpowerOrgLineTable" in team
    assert "标准人力贡献分析" in team
    assert "OTO 为月末在职且当月折算保费/标准保费≥2万元" in team
    assert "证保为月末在职且当月折算保费/标准保费≥3万元" in team
    assert "2026年产品4281按10年及以上交期处理" in team
    assert "switchTeamEnhancedPeriodType" in team
    assert "switchTeamEnhancedPeriodValue" in team
    assert "selectedTeamEnhancedBusinessLines = { OTO: true, '证保': true, '蚁桥': true }" in team
    assert "toggleTeamEnhancedBusinessLine" in team
    assert "getSelectedTeamEnhancedBusinessLines" in team
    assert "params.set('businessLines', selectedLines.join(','))" in team
    assert "params.set('businessLines', '__none__')" in team
    assert "let selectedTeamEnhancedBusinessLine =" not in team
    assert "switchTeamEnhancedBusinessLine" not in team
    assert "team-enhanced-controls" in team
    assert "team-enhanced-control-label" in team
    assert "team-enhanced-check" in team
    assert "function bindTeamEnhancedControls()" in team
    assert "bindTeamEnhancedControls();" in team
    assert 'onchange="switchTeamEnhancedPeriodValue' not in team
    assert 'onclick="switchTeamEnhancedPeriodType' not in team
    assert 'onchange="toggleTeamEnhancedBusinessLine' not in team
    assert 'data-team-enhanced-period-value' in team
    assert 'data-team-enhanced-period-type="year"' in team
    assert 'data-team-enhanced-period-type="quarter"' in team
    assert 'data-team-enhanced-period-type="month"' in team
    assert 'data-team-enhanced-line="全部"' in team
    assert 'data-team-enhanced-line="${escapeTeamText(line)}"' in team
    assert "button[data-team-enhanced-period-type]" in team
    assert "switchTeamEnhancedPeriodType(button.dataset.teamEnhancedPeriodType)" in team
    assert "select[data-team-enhanced-period-value]" in team
    assert "switchTeamEnhancedPeriodValue(select.value)" in team
    assert "input[data-team-enhanced-line]" in team
    assert "toggleTeamEnhancedBusinessLine(input.dataset.teamEnhancedLine, input.checked)" in team
    assert ".team-enhanced-check" in html
    assert "<span>全选</span>" in team
    assert "业务模式" in team
    assert "Object.keys(selectedTeamEnhancedBusinessLines).map(line" in team
    assert "periodType" in team
    assert "periodValue" in team
    assert "≥P25人数" in team
    assert "≥P50人数" in team
    assert "≥P75人数" in team
    assert "零/负产能占比" in team
    assert "P50 中位数" in team
    assert "P75 骨干门槛" in team
    assert "月末在职样本" in team
    assert "诊断矩阵" not in team
    assert "接入人级底座" not in team
    assert "待接入人级月度底座" not in team
    assert "需完善人员月度明细统计" not in team
    assert "需完善人员产能分布统计" not in team
    assert "月度仅纳入当月月末在职人员" in team
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
    assert "window.getDashboardAsOf" not in platform
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
    assert '<script src="js/platform-trend-main.js?v=1.0.107"></script>' in html
    assert "Object.keys(platformMock).forEach(year => delete platformMock[year])" in platform_main
    assert "function refreshPlatformChart()" in platform_main
    assert "function switchYear(value)" in platform_main
    assert "let selectedMonth = String(new Date().getMonth() + 1)" in platform_main
    assert "value === defaultMonth ? ' selected' : ''" in platform_main
    assert 'value="4" selected' not in platform_main
    assert "params.set('asOf', asOf)" not in platform_main
    assert "let cacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(yearNum) : yearLabel" in platform_main
    assert "await fetchProductData(yearLabel)" in platform_main
    assert "convertApiToPlatformMock(cached.platform, yearLabel)" in platform_main
    assert "fetchProductData(yearKey)" not in platform_main
    assert "convertApiToPlatformMock(cached.platform, yearKey)" not in platform_main


def test_platform_trend_controls_are_bound_by_platform_module():
    html = read_html()
    platform_main = read_js("platform-trend-main.js")
    platform_section = html.split('<!-- Product and Payment Period Structure -->', 1)[0].split('<!-- Business Platform Trend -->', 1)[1]

    assert 'onchange="switchYear' not in platform_section
    assert 'onclick="switchTimeDim' not in platform_section
    assert 'onchange="switchSubPeriod' not in platform_section
    assert 'onchange="toggleSeries' not in platform_section
    assert 'onchange="toggleOrg' not in platform_section
    assert 'onclick="switchPremiumType' not in platform_section
    assert 'id="platformTimeDimBtns"' in platform_section
    assert 'data-platform-time-dim="year"' in platform_section
    assert 'data-platform-time-dim="quarter"' in platform_section
    assert 'data-platform-time-dim="month"' in platform_section
    assert 'data-platform-series="经代"' in platform_section
    assert 'data-platform-org="上海"' in platform_section
    assert 'id="platformPremiumTypeBtns"' in platform_section
    assert 'data-platform-premium-type="qj"' in platform_section
    assert "function bindPlatformTrendControls()" in platform_main
    assert "yearSelect.addEventListener('change', () => switchYear(yearSelect.value))" in platform_main
    assert "button[data-platform-time-dim]" in platform_main
    assert "switchTimeDim(button, button.dataset.platformTimeDim)" in platform_main
    assert "subPeriodSelect.addEventListener('change', () => switchSubPeriod(subPeriodSelect.value))" in platform_main
    assert "input[data-platform-series]" in platform_main
    assert "toggleSeries(input.dataset.platformSeries, input.checked)" in platform_main
    assert "input[data-platform-org]" in platform_main
    assert "toggleOrg(input.dataset.platformOrg, input.checked)" in platform_main
    assert "button[data-platform-premium-type]" in platform_main
    assert "switchPremiumType(button, button.dataset.platformPremiumType)" in platform_main


def test_dashboard_asof_only_drives_precise_kpi_and_org_yoy_not_trend_series():
    integration = read_js("data-integration.js")
    platform_main = read_js("platform-trend-main.js")
    org = read_js("org-analysis.js")

    assert "`/api/kpi?year=${year}${dashboardAsOfQuery()}`" in integration
    assert "`/api/platform-data?year=${year}`" in integration
    assert "`/api/platform-data?year=${year}${dashboardAsOfQuery()}`" not in integration
    assert "const asOfContext = apiData?.kpi?.as_of;" in integration
    assert "const asOfContext = apiData?.kpi?.as_of || apiData?.platform?.as_of" not in integration
    assert "window.appendDashboardRange(params)" in org
    assert "platformTrendCacheKey(year, premiumType, selectedKeys, periodType, periodValue)" in platform_main
    assert "params.set('asOf', asOf)" not in platform_main
    assert "window.getDashboardAsOf" not in platform_main


def test_per_capita_metrics_use_average_headcount_denominators():
    html = read_html()
    kpi = read_js("kpi-cards.js")
    target_modal = read_js("target-modal.js")
    modal_content = read_js("kpi-modal-content.js")
    combined = html + "\n" + kpi + "\n" + target_modal + "\n" + modal_content

    assert "所选区间转型期交保费" in combined
    assert "const 月均保费 = 统计月数 > 0 ? 总保费 / 统计月数 : 总保费;" in combined
    assert "avgSum / months" in combined
    assert "avgArr(tm.headcount['OTO'])" in combined
    assert "sumArr(tm.headcount['OTO']) + sumArr(tm.headcount['证保'])" not in combined
    assert "res.totalPrem += p; res.totalAvg += a;" in combined
    assert "res.totalAvg = Math.round(res.totalAvg * 10) / 10;" in combined
    assert "res.ch[ch] = { prem: p, avg: a, pc: calcPC(p, a, periodMonths) }" in combined
    assert "res.totalPc = calcPC(res.totalPrem, res.totalAvg, periodMonths);" in combined
    assert "res.ch[ch] = { prem: p, avg: aSum, pc: calcPC(p, aSum) }" not in combined


def test_dashboard_navigation_and_kpis_are_responsive_and_keyboard_accessible():
    html = read_html()
    actions = read_js("dashboard-actions.js")
    kpi = read_js("kpi-cards.js")

    assert 'class="primary-nav" aria-label="主要页面"' in html
    assert '<summary class="chart-btn">管理与工具</summary>' in html
    assert 'class="header-tools"' in html
    header = html.split('<div class="container">', 1)[0]
    tools = header.split('<div class="header-tools">', 1)[1].split('</div>', 1)[0]
    assert 'class="chart-btn header-recalculate"' in header
    assert header.index('id="recalcBtn"') < header.index('<details class="header-menu">')
    assert 'data-dashboard-action="recalculate"' not in tools
    assert 'class="kpi-card target-dependent"' in html
    assert 'role="button" tabindex="0"' in html
    assert "event.key !== 'Enter' && event.key !== ' '" in kpi
    assert "button.closest('details')?.removeAttribute('open')" in actions
    assert '.header-main { display: block; }' in html
    assert 'width: calc(100vw - 24px)' in html


def test_unverified_targets_do_not_render_as_formal_achievement_judgement():
    html = read_html()
    kpi = read_js("kpi-cards.js")

    assert 'id="targetTrustBanner"' in html
    assert '正式目标尚未配置' in html
    assert "const targetsOfficial = targetLabel === '服务端目标'" in kpi
    assert "value.textContent = '目标待配置'" in kpi
    assert "const targetsComparable = targetsOfficial && targetMode !== 'none'" in kpi
    assert '当前日期区间无可直接对应的正式目标' in kpi


def test_login_and_honor_tabs_expose_accessible_semantics():
    auth_ui = read_js("auth-ui.js")
    honor_page = open(os.path.join(ROOT, "honor.html"), "r", encoding="utf-8").read()
    honor_js = read_js("honor.js")

    assert 'for="authUsername"' in auth_ui
    assert 'for="authPassword"' in auth_ui
    assert 'id="authMessage" role="status" aria-live="polite"' in auth_ui
    assert 'role="tablist"' in honor_page
    assert 'role="tab" aria-selected="true"' in honor_page
    assert 'role="tabpanel" aria-labelledby="tab-tracking"' in honor_page
    assert "event.key === 'ArrowRight'" in honor_js
    assert "item.setAttribute('aria-selected', String(selected))" in honor_js


def test_honor_metrics_and_scheme_page_expose_decision_hierarchy_and_boundary():
    honor_page = open(os.path.join(ROOT, "honor.html"), "r", encoding="utf-8").read()
    honor_js = read_js("honor.js")
    scheme_page = open(os.path.join(ROOT, "scheme-calculator.html"), "r", encoding="utf-8").read()
    scheme_js = read_js("scheme-calculator.js")

    assert 'class="metric-groups"' in honor_page
    assert "title: '核心结果'" in honor_js
    assert "title: '风险关注'" in honor_js
    assert "title: '追踪基础'" in honor_js
    assert '<title>方案底稿复核</title>' in scheme_page
    assert '非最终发放结果' in scheme_page
    assert '底稿导入、规则测算和结果复核' in scheme_page
    assert '请先选择方案，并通过“方案专用上传”导入对应底稿' in scheme_js


def test_production_static_serving_does_not_expose_repository_root():
    main_py = open(os.path.join(ROOT, "backend", "main.py"), "r", encoding="utf-8").read()
    nginx = open(os.path.join(ROOT, "deploy", "nginx.conf"), "r", encoding="utf-8").read()

    assert 'app.mount("/static", StaticFiles(directory=static_dir)' not in main_py
    assert 'app.mount("/js", StaticFiles(directory=js_dir)' in main_py
    assert 'location /api/' in nginx
    assert 'location ^~ /js/' in nginx
    assert 'location = / {' in nginx
    assert 'location = /webhook/deploy' in nginx
    assert 'return 404;' in nginx
    assert 'try_files $uri =404;' in nginx
    assert 'try_files $uri $uri/ =404;' not in nginx
    assert 'root /opt/business-analysis;' in nginx
