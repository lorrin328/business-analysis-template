# 工作日志

## 2026-06-30 GitHub 同步与 192.168.50.6 手工部署

- 任务：将维护性重构成果同步到 GitHub，并部署到 `192.168.50.6` 生产服务器。
- GitHub：本地 `master` 已提交 `5688acf refactor: improve dashboard maintainability`，并推送到 `origin/master`。
- 部署：因服务器 `/opt/business-analysis` Git 工作区存在大量本地改动，未直接 `git pull`；改为在服务器 `/tmp` 临时克隆 GitHub 最新提交 `5688acf`，通过 `deploy/deploy.sh` 同步代码到 `/opt/business-analysis`。
- 数据保护：部署脚本已备份生产数据库到 `/opt/business-analysis-backups/business_data.db.20260630_173301`。
- 数据重建：服务器检测到 8 个 Excel 文件并重建数据库，导入后年份覆盖 `[2022, 2023, 2024, 2025, 2026]`。
- 验证：`business-analysis` 与 `nginx` 均为 `active`；`/api/health` 返回 `status=ok`、`app_version=v1.0.98`、`page_version=v1.0.98`、`latest_period=202606`；首页 HTTP 状态 `200`。
- 验证：生产文件已包含 `data-dashboard-as-of` 和 `bindTargetModalControls()`；服务器数据质量审计 `status=ok`、`issue_count=0`。
- 日志：`journalctl -u business-analysis -n 40` 显示服务在 `2026-06-30 17:33:56` 正常停止并重启，新进程启动后健康检查 `200 OK`。
- 风险：服务器仍未配置 `/opt/business-analysis/deploy/.webhook_env`，部署脚本提示自动部署功能不可用；本次为 SSH 手工部署。

## 2026-06-30 目标弹窗与截止日期内联事件清理

- 任务：继续提升前端可维护性，完成主页面和 `js` 目录可见 `onclick` / `onchange` 内联事件清理。
- 调整：`经营分析模板.html` 中数据截止日期下拉框移除 `onchange="switchDashboardAsOf(this.value)"`，改为 `data-dashboard-as-of`。
- 调整：`js/data-integration.js` 新增 `bindDashboardAsOfControl()`，统一绑定数据截止日期切换事件。
- 调整：`js/target-modal.js` 中目标年份、导出/导入/保存、目标值输入、机构目标维度和机构目标值输入均移除内联事件。
- 调整：目标弹窗改为 `data-target-*`、`data-org-target-*` 声明式属性，并新增 `bindTargetModalControls()` 在 `modalBody` 上统一事件代理。
- 测试：`tests/test_frontend_static.py` 增加截止日期和目标弹窗不得回退到内联事件的静态约束。
- 验证：前端静态测试 `49 passed`；全局搜索确认 `经营分析模板.html` 和 `js` 目录已无 `onclick=` / `onchange=` 命中。

## 2026-06-30 队伍增强动态控件事件绑定收敛

- 任务：继续提升队伍增强面板可维护性，降低运行时 HTML 模板中统计期间和业务模式控件的内联事件耦合。
- 调整：`js/team-analysis.js` 中 `renderTeamEnhancedControls()` 移除 `switchTeamEnhancedPeriodType`、`switchTeamEnhancedPeriodValue`、`toggleTeamEnhancedBusinessLine` 内联事件。
- 调整：队伍增强控件改为 `data-team-enhanced-period-type`、`data-team-enhanced-period-value`、`data-team-enhanced-line` 声明式属性。
- 调整：新增 `bindTeamEnhancedControls()`，在 `teamEnhancedPanel` 容器上通过事件代理统一处理期间切换、期间值变化和业务模式勾选。
- 测试：`tests/test_frontend_static.py` 增加队伍增强动态控件不得回退到内联事件、必须使用 `data-team-enhanced-*` 事件代理的静态约束。
- 验证：前端静态测试 `49 passed`；搜索确认队伍增强旧内联事件已无命中。

## 2026-06-30 通用弹窗关闭事件绑定收敛

- 任务：继续提升通用弹窗系统可维护性，降低详情弹窗、目标弹窗、产品配置弹窗等共享 overlay 的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中 `modalOverlay` 移除 `onclick="closeModal(event)"`，弹窗主体移除 `onclick="event.stopPropagation()"`，关闭按钮改为 `data-modal-action="close"`。
- 调整：通用弹窗脚本新增 `bindModalControls()`，统一绑定 overlay 点击关闭和关闭按钮点击关闭。
- 保持：`closeModal()` 仍保留仅点击 overlay 背景关闭的判断，并继续清理 `modal-target`、`modal-product-config` 类名。
- 测试：`tests/test_frontend_static.py` 增加通用弹窗关闭控件不得回退到内联 `closeModal` / `stopPropagation` 的静态约束。
- 验证：前端静态测试 `49 passed`；搜索确认通用弹窗旧内联关闭事件已无命中。

## 2026-06-30 上传区域事件绑定收敛

- 任务：继续提升数据上传入口可维护性，降低后续新增、调整、删减上传文件类型时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中 4 张上传卡片移除 `onclick="document.getElementById(...).click()"`，改为 `data-upload-input` 声明目标文件输入。
- 调整：4 个文件输入移除 `onchange="handleFile(...)"`，改为 `data-upload-info` 声明对应提示区域。
- 调整：`js/upload.js` 新增 `bindUploadControls()`，集中绑定上传卡片点击和文件输入 change 事件；保留 `handleFile()` 上传业务流程不变。
- 测试：`tests/test_frontend_static.py` 增加上传区域不得回退到卡片点击和文件选择内联事件的静态约束。
- 验证：前端静态测试 `48 passed`；搜索确认上传区域已无旧内联事件。

## 2026-06-30 队伍趋势控件事件绑定收敛

- 任务：继续提升队伍分析模块可维护性，降低后续新增队伍指标、时间维度、业务系列或机构筛选时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中队伍趋势年份、指标类型、时间维度、季度、业务系列和机构控件移除内联 `onchange` / `onclick`。
- 调整：队伍趋势控件改为 `data-team-metric`、`data-team-dim`、`data-team-series`、`data-team-org` 等声明式属性。
- 调整：`js/team-analysis.js` 新增 `bindTeamTrendControls()`，集中绑定队伍趋势主控件事件；`switchTeamMetric()`、`switchTeamDim()` 增加按钮参数判空。
- 调整：队伍机构全选同步改为使用 `data-team-org` 选择器，不再依赖 checkbox 顺序。
- 测试：`tests/test_frontend_static.py` 增加队伍趋势主控件不得回退到 `switchTeam*` / `toggleTeam*` 内联事件的静态约束。
- 验证：前端静态测试 `48 passed`；搜索确认队伍趋势主控件已无旧内联事件。

## 2026-06-30 交期结构控件事件绑定收敛

- 任务：继续提升产品与交期结构区域可维护性，降低后续新增交期维度、业务系列、渠道、机构筛选和保费口径时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中交期结构图表切换、年份、时间维度、季度/月度、业务系列、转型渠道、转型机构和保费类型控件移除内联 `onclick` / `onchange`。
- 调整：交期结构控件改为 `data-pay-period-pie-type`、`data-pay-period-dim`、`data-pay-period-biz`、`data-pay-period-channel`、`data-pay-period-org`、`data-pay-period-metric` 等声明式属性。
- 调整：`js/payperiod-chart.js` 新增 `bindPayPeriodControls()`，集中绑定交期结构控制区事件；按钮切换函数增加显式判空，便于模块内调用。
- 修正：动态生成的转型机构、经代机构复选框改为 `data-pay-period-org` / `data-pay-period-jingdai-org`；动态生成的产品转型机构复选框改为 `data-product-org`，避免上一轮 `createCheckboxLabel()` 改造后仍传业务回调的隐患。
- 测试：`tests/test_frontend_static.py` 增加交期结构控件不得回退到 `switchPayPeriod*` / `togglePayPeriod*` 内联事件的静态约束，并约束动态复选框不再传回调函数。
- 验证：前端静态测试 `47 passed`；搜索确认交期结构区已无旧内联控制调用。

## 2026-06-30 产品结构控件事件绑定收敛

- 任务：继续提升产品结构模块可维护性，降低后续新增业务来源、转型渠道、经代机构、转型机构、时间维度和保费口径时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中产品结构图表切换、业务来源、转型业务、转型机构、时间维度、季度/月度和保费类型控件移除内联 `onclick` / `onchange`。
- 调整：产品结构控件改为 `data-product-pie-type`、`data-product-source`、`data-product-transform`、`data-product-org`、`data-product-dim`、`data-product-metric` 等声明式属性。
- 调整：`js/product-analysis.js` 新增 `bindProductStructureControls()`，集中绑定产品结构控制区事件；按钮切换函数增加显式判空，便于模块内调用。
- 调整：`js/data-integration.js` 动态生成的经代机构复选框改为 `data-product-jingdai-org`，由产品结构模块事件代理处理。
- 测试：`tests/test_frontend_static.py` 增加产品结构控件不得回退到 `switchPie`、`toggleProductSource`、`toggleProductTransform`、`toggleProductOrg`、`switchProductDim`、`switchProductSub`、`switchProductMetric` 内联事件的静态约束。
- 验证：前端静态测试 `46 passed`；搜索确认产品结构区已无旧内联控制调用。

## 2026-06-30 平台趋势控件事件绑定收敛

- 任务：继续提升业务平台趋势模块可维护性，降低后续新增趋势维度、保费类型、业务系列或机构筛选时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中平台趋势年份、时间维度、季度/月度、业务系列、机构和保费类型控件移除内联 `onchange` / `onclick`。
- 调整：平台趋势控件改为 `data-platform-time-dim`、`data-platform-series`、`data-platform-org`、`data-platform-premium-type` 等声明式属性。
- 调整：`js/platform-trend-main.js` 新增 `bindPlatformTrendControls()`，集中绑定平台趋势控制区事件。
- 调整：`switchTimeDim()` 和 `switchPremiumType()` 对按钮参数增加显式判空，便于模块内调用和后续测试。
- 测试：`tests/test_frontend_static.py` 增加平台趋势控件不得回退到 `switchYear`、`switchTimeDim`、`switchSubPeriod`、`toggleSeries`、`toggleOrg`、`switchPremiumType` 内联事件的静态约束。
- 验证：前端静态测试 `45 passed`；搜索确认平台趋势区已无旧内联控制调用。

## 2026-06-30 机构维度筛选控件事件绑定收敛

- 任务：继续提升机构维度模块可维护性，降低后续新增机构、调整时间维度和筛选逻辑时的 HTML 内联事件耦合。
- 调整：`经营分析模板.html` 中机构筛选标签改为 `data-org-filter`，时间维度按钮改为 `data-org-dim`，季度/月度下拉框移除内联 `onchange`。
- 调整：`js/org-analysis.js` 新增 `bindOrgFilterControls()`、`bindOrgDimControls()`、`bindOrgPeriodControls()`，统一绑定机构筛选、时间维度和季度/月度变化。
- 调整：`switchOrgDim()` 不再依赖浏览器全局 `event`，改为显式接收当前按钮；季度/月度下拉变化会同步 `orgSubPeriod` / `orgSubMonth` 后重渲染。
- 测试：`tests/test_frontend_static.py` 增加机构维度控件不得回退到 `toggleOrgFilter`、`switchOrgDim`、`renderOrgTable` 内联事件的静态约束。
- 验证：前端静态测试 `44 passed`；搜索确认机构筛选区域已无旧内联事件。

## 2026-06-30 KPI 卡片点击入口声明式绑定

- 任务：继续提升 KPI 模块可维护性，降低后续新增、调整、删减指标卡片时的 HTML 与弹窗函数耦合。
- 调整：`经营分析模板.html` 中 8 张 KPI 卡片由 `onclick="openModal(...)"` 改为 `data-kpi-modal` 声明详情类型。
- 调整：`js/kpi-cards.js` 新增 `bindKPICardActions()`，通过 `.kpi-grid` 事件代理统一打开 KPI 详情弹窗。
- 调整：`js/dashboard-config.js` 的卡片标题配置应用改为通过 `.kpi-card[data-kpi-modal]` 查找，不再依赖旧 `onclick` 选择器。
- 测试：`tests/test_frontend_static.py` 增加 KPI 卡片入口、绑定函数和配置选择器约束。
- 验证：前端静态测试 `43 passed`；搜索确认 KPI 区域已无 `onclick="openModal(...)"`。

## 2026-06-30 主工具栏动作绑定模块化

- 任务：继续提升前端入口可维护性，降低后续新增、调整、删减顶部功能按钮时的 HTML 与全局函数耦合。
- 调整：新增 `js/dashboard-actions.js`，集中维护顶部工具栏动作表和事件代理。
- 调整：`经营分析模板.html` 顶部权限管理、操作日志、人员管理、荣誉体系、导出 Excel、参数设置、设置目标、重新计算、退出按钮改为 `data-dashboard-action` 声明式动作。
- 调整：`js/README.md` 记录 `dashboard-actions.js` 为当前生产运行脚本。
- 测试：`tests/test_frontend_static.py` 增加顶部工具栏动作绑定约束，防止该组按钮回退到内联 `onclick`。
- 验证：前端静态测试 `43 passed`；搜索确认顶部工具栏已无 `openPermissionAdmin()`、`openOperationLogs()`、`exportDashboardExcel()`、`openProductConfigModal()`、`openTargetModal()`、`recalculateDashboard()`、`logout()` 的内联调用。

## 2026-06-30 产品配置弹窗事件绑定收敛

- 任务：继续提升前端模块可维护性，先从范围较小的产品配置弹窗移除内联点击事件。
- 调整：`js/product-config-modal.js` 中取消/保存按钮改为 `data-product-config-action` 标记，并由 `bindProductConfigActions()` 在脚本内绑定事件。
- 保持：弹窗加载、产品分类保存、经代业绩重算和看板刷新流程不变。
- 测试：`tests/test_frontend_static.py` 增加产品配置弹窗不得回退到 `onclick="closeModal()"` / `onclick="saveProductConfig()"` 的静态约束。
- 验证：前端静态测试 `42 passed`；`rg` 确认 `js/product-config-modal.js` 已无 `onclick=`。

## 2026-06-30 荣誉体系 summary builder 拆分

- 任务：继续降低星钻联盟荣誉体系计算主流程复杂度，便于后续调整机构汇总、会员率、奖励测算等展示口径。
- 调整：新增 `backend/honor/summary.py`，集中承接 `build_org_summary()` 和 `build_quarter_rewards()`。
- 调整：`backend/honor/calculator.py` 改为调用 summary builder，自身只保留星钻余额流转、离职清零、人员月度和人员汇总职责。
- 效果：`backend/honor/calculator.py` 从上一轮约 `235` 行降至约 `174` 行；机构汇总和季度奖励测算独立为约 `77` 行纯函数。
- 测试：新增 `tests/test_honor_summary.py`，覆盖当前在职会员统计、资深及以上统计、月度增减、会员率、预估奖励和季度归属。
- 验证：荣誉体系 summary、sources、calculator、dashboard、API、normalizers、规则、字段审计、导出和权限专项测试 `28 passed, 1 warning`。

## 2026-06-30 荣誉体系 sources 拆分

- 任务：继续降低星钻联盟荣誉体系计算主流程的复杂度，便于后续新增人员、保单、团队类规则。
- 调整：新增 `backend/honor/sources.py`，集中承接人力源表加载、保单源表加载、个人/主管/经理指标索引构造、45天回销异常、负数保费异常和缺人员工号异常。
- 调整：`backend/honor/calculator.py` 改为调用 `load_staff()`、`load_policies()`、`metric_for_staff()`，自身保留星钻流水、离职清零、人员汇总、机构汇总和奖励测算职责。
- 效果：`backend/honor/calculator.py` 从约 `542` 行降至 `235` 行；源数据准备逻辑独立为 `backend/honor/sources.py` 约 `276` 行。
- 测试：新增 `tests/test_honor_sources.py`，覆盖主管团队指标合格时优先使用团队指标、不合格时回落个人指标。
- 验证：荣誉体系 sources、calculator、dashboard、API、normalizers、规则、字段审计、导出和权限专项测试 `26 passed, 1 warning`。

## 2026-06-30 荣誉体系 dashboard builder 拆分

- 任务：继续降低星钻联盟荣誉体系后续新增 dashboard 展示维度、预警和历史明细时的改动风险。
- 调整：新增 `backend/honor/dashboard.py`，集中承接荣誉体系 dashboard 派生聚合，包括项目/机构排序、会员结构、专员/管理职历史、月度预警、等级分布和趋势。
- 调整：`backend/honor/repository.py` 保留批次、审计、结果写入、摘要读取和基础表读取职责，`fetch_dashboard()` 读取数据库后交给 `build_honor_dashboard_payload()` 组装。
- 效果：`backend/honor/repository.py` 从约 `633` 行降至 `243` 行；dashboard 派生逻辑独立为约 `414` 行，后续展示扩展不再挤在持久化层。
- 测试：新增 `tests/test_honor_dashboard.py`，直接覆盖 dashboard builder 的项目、机构会员结构、专员历史、管理职历史、预警和趋势派生字段。
- 验证：荣誉体系 dashboard、API、导出、权限、计算、normalizers、规则和字段审计专项测试 `24 passed, 1 warning`。

## 2026-06-30 荣誉体系 normalizers 拆分

- 任务：继续降低星钻联盟荣誉体系后续新增规则、调整人员/保单字段清洗口径时的维护成本。
- 调整：新增 `backend/honor/normalizers.py`，集中承接文本清洗、人员代码补零、数字转换、整数转换、日期解析、年月解析、业务线归一和职级角色识别等纯函数。
- 调整：`backend/honor/calculator.py` 改为复用 `honor.normalizers`，删除本地重复的清洗函数和职级识别函数，星钻计算主流程保留规则计算与结果组装职责。
- 测试：新增 `tests/test_honor_normalizers.py`，覆盖人员代码、日期、数字、业务线和职级归一规则。
- 验证：荣誉体系 normalizers、calculator、API、规则、字段审计、导出和权限专项测试 `23 passed, 1 warning`。

## 2026-06-30 数据流文档与 API 查询参数继续收敛

- 任务：继续降低后续新增模块时误用旧导入链路、重复手写 API 参数校验的风险。
- 调整：`docs/数据流说明.md` 从旧 `backend/aggregator.py` 口径更新为当前 `backend/services/excel_pipeline.py` + `backend/etl/aggregates/` 数据流，补充 Web 上传、全量重建和新增聚合表的维护边界。
- 调整：新增 `tests/test_docs_current_data_flow.py`，约束当前数据流文档必须引用 `excel_pipeline` 和 `backend/etl/`，且不得把 `backend/aggregator.py` 写成当前链路。
- 调整：新增 `backend/api/params.py`，集中定义 `DashboardYearQuery` 和 `AsOfQuery`；KPI、机构、产品、交期、平台趋势、AI 只读、导出、目标和队伍接口迁移到公共查询参数类型。
- 验证：API 参数与文档专项测试 `65 passed`；相关 API 文件语法编译通过。

## 2026-06-30 原始表日期 SQL helper 继续收敛

- 任务：继续降低后续新增原始 Excel 表读取逻辑时的重复代码和日期过滤口径漂移风险。
- 调整：`services.raw_table_reader.compact_period_expr()` 增加对 `:` 的剔除，兼容 `YYYY-MM-DD HH:MM:SS` 等带时间文本。
- 调整：`backend/api/product_config.py` 和 `backend/services/import_safety.py` 改为复用 `raw_table_reader` 的 `compact_period_expr()` 与 `quote_identifier()`，删除本地重复实现。
- 测试：`tests/test_raw_table_reader.py` 增加日期时间分隔符覆盖测试。
- 验证：产品配置、原始表读取、导入安全专项测试 `32 passed`；完整测试 `248 passed, 1 warning`；`backend/audit_data_quality.py --year 2026 --json` 返回 `status=ok, issue_count=0`；`scripts/preflight.ps1` 返回 `preflight ok`；`git diff --check` 无空白错误，仅有 LF/CRLF 换行提示。

## 2026-06-30 荣誉体系批次 meta helper 收敛

- 任务：继续提升 API 层可维护性，同时保持荣誉体系批次类响应与指标类响应的语义边界。
- 调整：`backend/services/response.py` 新增 `batch_meta()`，统一生成 `batchId`、`ruleVersion`、`dataSourceMode` 等批次响应 meta 字段。
- 调整：`backend/api/honor.py` 的字段审计、摘要、看板、机构表、人员表、异常表、趋势表接口迁移到 `batch_meta()`；`recalculate` 继续使用完整计算结果作为 meta，保持原有返回契约。
- 测试：`tests/test_targets_api.py` 新增 `batch_meta()` 公共契约测试。
- 验证：`backend/services/response.py`、`backend/api/honor.py` 语法编译通过；荣誉体系和响应契约专项测试 `11 passed, 1 warning`。

## 2026-06-30 AI 只读与产品配置 API meta 迁移

- 任务：继续推进 API 层响应说明统一，同时区分指标类接口与批次/规则类特殊接口。
- 调整：`backend/api/ai.py` 的 AI 只读 KPI、机构摘要、队伍摘要、指标定义、看板快照接口迁移到 `services.response.response_meta()`，保留 `access=ai-readonly`。
- 调整：`backend/api/product_config.py` 的经代产品配置读取和保存接口迁移到 `response_meta()`，保留 `scope=经代`。
- 保留：`backend/api/honor.py` 的 meta 主要围绕 `batchId`、`ruleVersion`、`dataSourceMode`，属于批次/规则版本类响应，暂不迁移到指标类 `response_meta()`。
- 验证：`backend/api/ai.py`、`backend/api/product_config.py` 语法编译通过；AI 只读、产品配置和响应契约专项测试 `25 passed, 1 warning`。

## 2026-06-30 目标交期配置 API meta 迁移到 response_meta

- 任务：继续推进 API 层统一响应说明，减少目标、交期和配置指标接口重复手写 meta 字典。
- 调整：`backend/api/targets.py`、`backend/api/payment_period.py`、`backend/api/config.py` 的指标类响应迁移到 `services.response.response_meta()`。
- 调整：`backend/api/payment_period.py` 将 `success_response` 从函数内部导入移到文件顶部，避免局部隐藏依赖。
- 保留：业务线配置列表接口不强行套用指标 meta；目标保存、交期结构和配置指标接口的 JSON 外壳与业务字段不变。
- 验证：相关 API 文件语法编译通过；目标、配置指标和 API 合约专项测试 `23 passed`。

## 2026-06-30 核心指标 API meta 迁移到 response_meta

- 任务：继续推进 API 层可维护性，减少 KPI、机构、产品、趋势和队伍接口中重复手写 meta 字典。
- 调整：`backend/api/kpi.py`、`backend/api/org.py`、`backend/api/product.py`、`backend/api/trend.py` 迁移到 `services.response.response_meta()`；上一轮已迁移的 `backend/api/team.py` 保持该模式。
- 保留：接口路径、参数、权限、数据读取、`success/data/message/meta` 外壳、`meta.updatedAt` 注入方式和前端契约不变。
- 验证：相关 API 文件语法编译通过；API 合约、指标配置、平台趋势相关专项测试 `64 passed`。

## 2026-06-30 API 响应 meta helper 起步

- 任务：继续提升 API 层新增模块时的可维护性，减少各接口重复手写 `metric`、`unit`、`dataSource`、`definitions` 等 meta 字段。
- 调整：`backend/services/response.py` 新增 `response_meta()`，统一生成指标类 API 响应 meta 字典；`success_response()` 原结构不变，仍统一附加 `updatedAt`。
- 调整：`backend/api/team.py` 的 `/api/team-analysis` 与 `/api/team-enhanced-analysis` 改为使用 `response_meta()`，接口返回字段和前端契约不变。
- 测试：`tests/test_targets_api.py` 新增 `response_meta()` 公共契约测试。
- 验证：`backend/services/response.py`、`backend/api/team.py` 语法编译通过；响应、队伍和指标配置相关专项测试 `27 passed`。

## 2026-06-30 队伍分析空响应结构收敛

- 任务：继续降低队伍分析后续新增返回字段时的漏改风险。
- 调整：`backend/db/repositories/team_enhanced.py` 新增 `_empty_team_analysis_response()`，集中维护无 `hr_data` 表或无可选月份时的完整空结果结构。
- 调整：`get_team_enhanced_analysis()` 中两个早退分支改为复用该 helper，正常样本计算、趋势、标准人力和筛选逻辑不变。
- 测试：`tests/test_team_enhanced.py` 新增无 `hr_data` 表、无选中月份两类空响应测试，锁定 `summary`、`standardManpower`、`filters` 等关键字段。
- 验证：`backend/db/repositories/team_enhanced.py` 语法编译通过；队伍分析专项测试 `12 passed`。

## 2026-06-30 队伍分析纯工具函数迁出 repository

- 任务：继续提升队伍分析模块可维护性，减少 `backend/db/repositories/team_enhanced.py` 中数据库查询、样本组装和纯计算/清洗函数混放的问题。
- 调整：新增 `backend/services/team_analysis_utils.py`，集中承接业务线归一、人员代码清洗、日期压缩解析、百分位、分档、比例和阈值计数等纯函数与队伍分析常量。
- 调整：`backend/db/repositories/team_enhanced.py` 改为从 service 导入这些 helper，保留数据库读取、样本构造、结构分析和接口返回组装职责。
- 测试：新增 `tests/test_team_analysis_utils.py`，覆盖业务线归一、人员代码清洗、期间解析、百分位、阈值计数、比例和产能分档。
- 验证：`backend/db/repositories/team_enhanced.py` 与 `backend/services/team_analysis_utils.py` 语法编译通过；队伍分析专项测试 `10 passed`。

## 2026-06-30 平台数据 repository 与 KPI repository 拆分

- 任务：继续提升后端查询层可维护性，降低平台数据底座与 KPI 概览逻辑混放带来的后续改动风险。
- 调整：新增 `backend/db/repositories/platform.py`，承接原 `backend/db/repositories/kpi.py` 中的 `get_platform_data()` 平台聚合数据查询。
- 调整：`backend/db/__init__.py` 和 `backend/db/repositories/__init__.py` 改为从 `db.repositories.platform` 导出 `get_platform_data`；外部调用仍保持 `from db import get_platform_data` 不变。
- 效果：`backend/db/repositories/kpi.py` 从约 `502` 行降至 `363` 行，平台数据 repository 独立为约 `141` 行；后续调整平台趋势、队伍分析、KPI 概览时边界更清晰。
- 验证：`backend/db/repositories/kpi.py`、`backend/db/repositories/platform.py`、`backend/db/__init__.py`、`backend/db/repositories/__init__.py` 语法编译通过；趋势、API 合约和指标配置相关专项测试 `64 passed`。

## 2026-06-30 KPI 日级 YTD 查询 helper 收敛

- 任务：继续提升后续指标模块维护性，减少 `get_kpi_data()` 中转型、经代、产品指标按日级截止累计时的重复 SQL。
- 调整：`backend/db/repositories/kpi.py` 新增 `_sum_daily_columns()`、`_sum_daily_column_by_channel()`，统一处理“按 month/day 截止累计日表字段”的查询。
- 调整：KPI 期交保费、经代期交、转型产品指标和经代产品指标的日级读取改为复用 helper；月级回退、长险期交、`asOf` 策略和接口返回字段不变。
- 安全边界：helper 增加 SQL 标识符校验，只允许内部表名、列名和别名使用普通 SQL identifier，避免后续复用时引入动态 SQL 风险。
- 验证：`backend/db/repositories/kpi.py` 语法编译通过；KPI/产品配置/配置接口/AI 只读接口相关专项测试 `35 passed`；截止策略、机构长险和原始表 helper 专项测试 `8 passed, 1 warning`。

## 2026-06-30 原始表日期过滤 helper 收敛

- 任务：继续提升后续模块维护性，减少直接读取原始 Excel 表时重复编写中文日期字段解析、年份/月度过滤和 `asOf` 截止过滤。
- 调整：`backend/services/raw_table_reader.py` 新增 `raw_table_column_set()`、`pick_existing_column()`、`compact_period_expr()`、`append_period_filter()`、`append_cutoff_filter()`，集中处理原始表列选择与日期过滤 SQL。
- 调整：`backend/db/repositories/product.py` 删除本地重复的原始表列选择、日期压缩、期间过滤和截止过滤 helper，产品结构和各业务模式前三产品查询改为复用 `raw_table_reader`。
- 测试：新增 `tests/test_raw_table_reader.py`，覆盖候选列选择、分隔日期文本期间过滤、截止日参数生成。
- 验证：产品/趋势/API/前端相关专项测试 `95 passed`；完整测试 `240 passed, 1 warning`；`backend/audit_data_quality.py --year 2026 --json` 返回 `status=ok, issue_count=0`；`scripts/preflight.ps1` 返回 `preflight ok`。

## 2026-06-30 机构日级截止 SQL helper 收敛

- 任务：继续提升后续模块维护性，减少机构维度中按渠道日级截止查询条件的重复拼装。
- 调整：`backend/services/cutoff_policy.py` 新增 `channel_cutoff_filter_sql()`，统一生成“按渠道分别截至 month/day”的 SQL 条件和参数。
- 调整：`backend/db/repositories/org.py` 中机构年度期交、产品指标、长险期交三处日级查询改为复用该 helper，业务计算口径不变。
- 测试：`tests/test_cutoff_policy.py` 新增渠道截止 SQL 生成测试，锁定参数顺序和 SQL 形态。
- 验证：专项测试 `27 passed`；完整测试 `237 passed, 1 warning`；`backend/audit_data_quality.py --year 2026 --json` 返回 `status=ok, issue_count=0`；`scripts/preflight.ps1` 返回 `preflight ok`。

## 2026-06-30 平台趋势运行逻辑与兜底数据拆分

- 任务：继续提升项目可维护性，降低后续调整平台趋势图时在超大 JS 文件中误改历史兜底数据的风险。
- 调整：新增 `js/platform-seed-data.js`，承接原 `js/platform-trend-main.js` 中约 `16290` 行 `platformMock` 本地兜底数据。
- 调整：`js/platform-trend-main.js` 保留平台趋势图状态、筛选、缓存、接口加载和渲染逻辑，文件规模从约 `16936` 行降至 `647` 行。
- 调整：`经营分析模板.html` 在 `seed-data.js` 后、`data-integration.js` 前加载 `platform-seed-data.js`；`tests/test_frontend_static.py` 和 `js/README.md` 同步更新生产运行边界。
- 验证：`tests/test_frontend_static.py` 结果 `42 passed`；完整测试 `236 passed, 1 warning`；`backend/audit_data_quality.py --year 2026 --json` 返回 `status=ok, issue_count=0`；`scripts/preflight.ps1` 返回 `preflight ok`。

## 2026-06-30 导入链路统一 pipeline 重构

- 任务：优化项目可维护性，降低后续模块新增、调整、优化、删减时 Web 上传链路与本地 Excel 重建链路逻辑漂移的风险。
- 调整：新增 `backend/services/excel_pipeline.py`，集中承接四类 Excel 的解析、聚合、活动人力回填、年份收集、日级截止警告、聚合表写入和原始表写入。
- 调整：`backend/main.py` 的 `/api/upload` 不再直接维护各聚合表生成细节，改为逐个源文件追加到统一 pipeline；保留重复文件跳过、部分失败处理、导入历史、增量写库和操作日志。
- 调整：`backend/rebuild_from_excels.py` 改为复用同一 pipeline 做全量重建；后续新增聚合表或调整导入顺序时，只需优先改 pipeline，避免 Web 上传和命令行重建两处重复维护。
- 调整：`pyproject.toml` 版本从 `1.0.97` 同步到当前 `1.0.98`，与 `VERSION`、后端默认版本和页面缓存参数一致。
- 验证：`python -m py_compile backend/main.py backend/rebuild_from_excels.py backend/services/excel_pipeline.py` 通过；相关测试 `34 passed`；完整测试 `236 passed, 1 warning`；`backend/audit_data_quality.py --year 2026 --json` 返回 `status=ok, issue_count=0`；`scripts/preflight.ps1` 返回 `preflight ok`。

## 2026-06-30 代码精简与 Rust 化可行性审查

- 任务：评估当前代码是否能在不改变业务逻辑的前提下精简、重构，或改用 Rust 等更高性能方案。
- 已读取：`AGENTS.md`、`README.md`、`pyproject.toml`、`requirements.txt`、`backend/requirements.txt`、`backend/main.py`、`backend/rebuild_from_excels.py`、`backend/db/repositories/kpi.py`、`backend/db/repositories/product.py`、`backend/db/repositories/team_enhanced.py`、`backend/etl/aggregates/org.py`、`backend/etl/aggregates/jingdai.py`、`js/platform-trend-main.js`、`js/platform-trend.js`、`js/seed-data.js`、`js/data-integration.js` 和 `docs/ai-context/` 项目记忆。
- 结构判断：当前后端约 `114` 个 Python 文件、约 `14580` 行；前端约 `21` 个 JS 文件、约 `23077` 行。最大维护热点是 `js/platform-trend-main.js`，约 `16936` 行，其中大量内容为内嵌 `platformMock` 历史兜底数据，不是算法复杂度本身。
- 重构判断：优先做等价重构，不建议一上来改 Rust。当前项目主要依赖 FastAPI、pandas/openpyxl、SQLite 和原生前端；性能瓶颈更可能来自 Excel 解析、SQLite 查询/索引、前端大文件加载和重复聚合，而不是 Python 语言本身。
- 可精简方向：将 `js/platform-trend-main.js` 中内嵌兜底数据迁出到独立 seed/runtime fallback 文件；将 `backend/main.py` 的上传解析、聚合、写库流程抽成导入服务，与 `rebuild_from_excels.py` 复用同一套 pipeline；进一步收敛 `get_kpi_data()`、`get_org_kpi_data()`、产品结构查询中的日级截止和 SQL 拼装辅助逻辑。
- 边界提醒：重构必须保持转型产品分类读取源 Excel 标识、经代产品分类继续读取 `product_config` 手工配置、KPI/机构按 `asOf` 精准同日口径、趋势图展示完整已有趋势这几条近期决策不变。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `236 passed, 1 warning`；本次未修改业务代码。
- 发现：`VERSION`、后端默认版本和页面缓存参数为 `v1.0.98`，但 `pyproject.toml` 仍为 `1.0.97`；已在同日导入链路重构中同步。

## 2026-06-29 v1.0.98 产品指标日级截止口径修正

- 任务：复核 v1.0.97 转型产品标识读取后的计算逻辑，确认源 Excel、ETL、SQLite 聚合、KPI 和机构维度展示是否一致。
- 发现：`agg_org_performance` 月表中的商保年金/保障类与源 Excel 全年累计一致，但 KPI 概览在存在 `asOf` 日级截止时仍按整月读取 `agg_org_performance` / `agg_jingdai` 产品字段；例如默认 2026-06-28 截止时会把 2026-06-29 的少量商保/保障保费带入，选择 2026-06-18 时偏差更明显。
- 修复：`agg_org_daily_performance` 增加 `product_10year`、`product_annuity`、`product_protection` 字段并由 `aggregate_org_daily_performance` 写入；`agg_jingdai_daily` 增加 `product_annuity`、`product_protection` 字段并由经代参数设置口径写入。
- 修复：`get_kpi_data()` 在转型和经代日表均可用时，商保年金、保障类和转型 10 年期实绩按各自日级截止读取；无日表数据时回退月表，避免测试年份或旧库被 `selectedCutoff` 误判为日级可用。
- 修复：`get_org_kpi_data()` 的年度产品分解在有机构日表时使用日级累计覆盖，月度/季度明细仍保留月表展示。
- 数据核验：源 Excel 直算与本地日表一致，2026-06-18 截止商保年金 / 保障类为 `8435.09` / `10969.88`，2026-06-28 截止为 `8922.45` / `11741.52`；月表全年累计为 `8924.85` / `11741.69`，差额来自 2026-06-29 源表尾量。
- 边界确认：`是否个人养老金` 当前无独立 KPI/目标字段；2026 年个养期交 `154.98` 万，源表中均同时标记为商保年金和社会保障型产品，当前仍随对应两类指标计入。
- 验证：执行相关测试 `61 passed`；完整测试 `236 passed, 1 warning`；本地 `audit_data_quality.py --year 2026 --json` 返回 `status=ok`、`issue_count=0`。
- 部署：已手工部署到 `192.168.50.6`，线上 `/api/health` 返回 `app_version=v1.0.98`、`page_version=v1.0.98`、`latest_period=202606`；服务器执行 `audit_data_quality.py --year 2026 --json` 返回 `status=ok`、`issue_count=0`。线上 2026-06-28 口径拆分为商保年金转型 `8922.45`、经代 `40213.41`，保障类转型 `11741.52`、经代 `3252.75`。

## 2026-06-29 v1.0.97 服务器手工部署与 20260629 Excel 重建

- 部署对象：局域网服务器 `192.168.50.6`，应用目录 `/opt/business-analysis`。
- 已完成：将本地 `master` 最新代码部署到服务器，线上健康接口返回 `app_version=v1.0.97`、`page_version=v1.0.97`。
- 已完成：同步根目录四份最新源 Excel 到服务器，包括 `AI-经营分析业绩基表_20260629_09124457.xlsx`、`AI-经营分析价值基表_20260629_09030716.xlsx`、`N1AI-人力基表_20260629_09030310.xlsx`、`经代业绩分析 (39).xlsx`。
- 已完成：服务器旧 Excel 已备份到 `/opt/business-analysis-backups/excels.20260629_*`，SQLite 数据库部署脚本备份到 `/opt/business-analysis-backups/business_data.db.20260629_101509`。
- 已完成：以 `www-data` 运行 `backend/rebuild_from_excels.py` 重建数据库，确认读取 20260629 业绩、价值、人力和经代源文件；健康接口 `latest_period=202606`。
- 验证：线上 `product_config` 仅保留 `经代` 19 条；2026 年转型商保年金/保障类汇总为 `8924.85` / `11741.69`，与本地源 Excel 复核一致。
- 验证：服务器执行 `audit_data_quality.py --year 2026 --json` 返回 `status=ok`、`issue_count=0`。
- 遗留：服务器 `/opt/business-analysis/deploy/.webhook_env` 缺失，`webhook-deploy` 服务处于 inactive，`/webhook/deploy` 仍返回 502；自动部署需恢复并与 GitHub Webhook Secret 保持一致后再启用。

## 2026-06-29 部署推送与 webhook 阻塞

- 任务：将 `v1.0.97` 产品分类口径调整部署到服务器。
- 已完成：本地 `master` 提交 `1a00695 fix product config scope and deploy v1.0.97`，并成功推送到 GitHub `origin/master`。
- 部署验证：线上健康检查 `http://192.168.50.6/api/health` 仍返回 `app_version=v1.0.95`、`page_version=v1.0.95`、数据库路径 `/opt/business-analysis/backend/business_data.db`、最新期间 `202606`。
- 阻塞原因：`http://192.168.50.6/webhook/deploy` 返回 `502 Bad Gateway`，说明 nginx webhook 入口存在但后端 `webhook-deploy` 服务未正常响应；SSH 尝试 `yinli/root/ubuntu/www-data/codex@192.168.50.6` 均因无可用凭据失败，无法远程重启 webhook 服务或手工执行部署脚本。
- 当前状态：代码已到 GitHub，服务器未完成部署；需要服务器 SSH 凭据或在服务器本机执行 `sudo systemctl status webhook-deploy`、`sudo systemctl restart webhook-deploy` 后重新触发部署。

## 2026-06-29 v1.0.97 转型产品分类标识改为读取业绩基表

- 任务：根目录 2026-06-29 新业绩基表已包含转型业务 `是否个人养老金`、`是否商保年金产品`、`是否社会保障型产品` 标识，需取消转型产品分类在参数设置中的手工维护，仅保留经代手工配置。
- 已读取：`AGENTS.md`、`README.md`、`pyproject.toml`、`requirements.txt`、`backend/requirements.txt`、`backend/main.py`、`backend/rebuild_from_excels.py`、`backend/api/product_config.py`、`backend/services/product_config_service.py`、`backend/etl/aggregates/org.py`、`backend/etl/aggregates/jingdai.py`、`js/product-config-modal.js`、`js/kpi-cards.js`、相关测试和 `docs/ai-context/` 全量项目记忆。
- 数据核验：读取根目录 `AI-经营分析业绩基表_20260629_09124457.xlsx`，确认字段包含 `是否商保年金产品`、`是否社会保障型产品`、`是否个人养老金`，其中商保年金/社会保障型字段值为“是/否”，个人养老金字段值为“个养/非个养”。
- 逻辑调整：`aggregate_org_performance` 中转型业务 `product_annuity` 直接按 `是否商保年金产品=是` 汇总，`product_protection` 直接按 `是否社会保障型产品=是` 汇总，不再读取 `product_config`。
- 参数设置调整：`/api/product-config` 仅返回和保存 `business_type='经代'` 的产品配置；保存时跳过非经代 payload，只重算 `agg_jingdai`；Web 上传、`rebuild_from_excels.py` 和参数设置接口都会清理 `product_config` 中非经代历史行。
- 前端与导出：参数设置弹窗改为“经代产品分类”口径，导出说明改为“转型读取业绩基表标识；经代读取参数设置”，页面缓存版本提升到 `v1.0.97`。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_product_config.py -q`，结果 `16 passed`；执行 `.\.venv\Scripts\python.exe -m pytest tests\test_frontend_static.py -q`，结果 `42 passed`；执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `234 passed, 1 warning`；执行 `.\.venv\Scripts\python.exe backend\rebuild_from_excels.py`，根目录 4 份 2026-06-29 Excel 成功重建，加载年份 `[2022, 2023, 2024, 2025, 2026]`，并清理非经代 `product_config` 历史行 28 条；执行 `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1`，结果 `preflight ok`。

## 2026-06-24 v1.0.96 安全与展示审计整改

- 任务：围绕数据准确、安全、高效、扩展性和经营分析展示口径继续审计并落地一批低风险改进。
- 已读取：`AGENTS.md`、`README.md`、`pyproject.toml`、`docker-compose.yml`、`deploy/systemd.service`、`backend/auth.py`、`backend/api/auth_routes.py`、`js/auth-ui.js`、`js/kpi-cards.js`、`tests/` 相关用例和 `docs/ai-context/` 全量项目记忆。
- 安全整改：新增 `AUTH_ALLOW_PUBLIC_REGISTRATION` 开关，生产环境默认关闭公开自助注册；保留非生产环境默认可注册，便于本地测试；公开注册关闭时前端登录框隐藏“注册”按钮。
- 安全整改：新增用户名白名单校验，用户名仅支持中文、字母、数字、下划线、点、@ 和短横线；管理员创建、修改用户和公开注册均走同一校验。
- 前端整改：权限管理页新增/删除/统一保存从内联 `onclick` 改为 `data-action` 事件绑定，避免把用户名等用户输入拼入事件属性。
- 展示优化：KPI 概览下方新增经营摘要，基于整体期交达成率、同比、时间进度、经代/转型贡献、目标来源和 `asOf` 数据截止口径，输出“结论/关注/口径”三类可复核提示。
- 版本治理：运行版本、页面脚本缓存参数、`VERSION`、`backend/config/version.py`、`pyproject.toml` 和测试断言同步到 `v1.0.96`。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `234 passed, 1 warning`；执行 `backend\audit_data_quality.py --year 2026 --json`，结果 `status=ok, issue_count=0`；执行 `scripts\preflight.ps1`，结果 `preflight ok`。
- 注意：本次未重建本地 `backend/business_data.db`，本地运行库新鲜度问题仍需按需处理；用户在对话中暴露过邮箱授权码和 GitHub Token，本次未使用、未写入文件，建议用户自行轮换。

## 2026-06-20 项目整体审计

- 任务：审计项目是否符合业务要求、框架是否可扩展、整体逻辑是否严谨、数据是否准确。
- 已读取：`AGENTS.md`、`README.md`、`requirements.txt`、`pyproject.toml`、`Dockerfile`、`docker-compose.yml`、`deploy/`、`.github/workflows/docker-image.yml`、`backend/main.py`、`backend/auth.py`、`backend/db/`、`backend/services/`、`backend/metrics/`、主要 `backend/api/` 路由、前端 `js/` 关键脚本和 `docs/ai-context/` 全量项目记忆。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `231 passed, 1 warning`；执行 `backend\audit_data_quality.py --year 2026 --json`，结果 `status=ok, issue_count=0`；执行 `scripts\preflight.ps1`，结果 `preflight ok`。
- 业务口径判断：KPI、机构、趋势、交期、长险期交、标准人力等核心口径已集中在后端聚合、查询服务和指标配置中，`asOf` 精准同比与趋势完整展示的边界已有测试和项目记忆支撑。
- 数据准确性边界：当前本地 `backend/business_data.db` 仍截至 2026-05-25，`target_config` 为历史测试态 `categories: null` 且 `target_values` 为空；本地库不能作为 2026-06-19 最新经营口径依据。服务器端此前已确认 2026-06-19 数据与正式目标正常。
- 架构判断：现有 `api / services / db / etl / metrics / validators` 分层基本支持继续扩展，SQLite + 原生前端适合当前轻量看板，但后续并发写入、权限颗粒度、前端组件化和数据版本治理需要继续加强。
- 风险发现：公开注册普通用户后默认可读取核心经营数据；权限管理页把用户名拼接进 `onclick` 字符串参数，若用户名允许特殊字符，存在前端注入风险；交期结构当前按月级聚合，不能支持同月内按日精确切换；外部访问仍需补充 HTTPS/注册审批/账号治理策略。

## 2026-06-19 v1.0.95 趋势图展示口径修正

- 现象：业务平台趋势和队伍趋势在右上角选择截至日期后，被 `asOf` 截断，导致趋势数据不够完整，部分去年线出现下落或缺失。
- 原因：v1.0.93 将 `asOf` 同时接入 KPI、机构、平台趋势和队伍趋势链路；其中 KPI/机构需要精确同日同比，但趋势图更需要完整展示已有数据。
- 修复：前端 `/api/platform-data` 和 `/api/platform-trend` 请求不再传递 `asOf`；平台趋势日序列不再按 `asOf` 裁剪；截至日期上下文只从 KPI 返回值同步，避免平台数据默认口径覆盖用户选择。
- 保留：`/api/kpi` 与 `/api/org-analysis` 继续传递 `asOf`，用于 KPI 概览和机构维度精准同日同比。
- 版本：统一提升到 `v1.0.95`，刷新主页面、荣誉体系和人员管理页面脚本缓存参数。

## 2026-06-19 v1.0.94 数据加载失败修复

- 现象：页面数据未完整加载，点击“重新计算”提示失败。
- 原因：`loadYearFromApi()` 将带 `asOf` 的缓存 key（如 `2026::2026-06-18`）误当作业务年份继续传入 `fetchProductData()` 和 mock 数据转换，导致 `/api/product-analysis` 请求出现 `year=2026::2026-06-18`，后端返回 422。
- 修复：区分 `cacheKey` 与 `yearLabel`；缓存仍按 `year + asOf` 隔离，业务接口和前端 mock 数据年份始终使用纯年份 `2026` / `2025`；版本号提升到 `v1.0.94` 以刷新浏览器脚本缓存。
- 验证：新增前端静态回归断言；执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `230 passed, 1 warning`。

## 2026-06-19 v1.0.93 看板截至日期与经代同比口径修正

- 修复经代 6 月未满月同比口径：平台趋势、KPI 与日累计查询支持 `asOf`，选择 `2026-06-18` 时只统计至 6 月 18 日，去年同期自动映射为 `2025-06-18`，不再用 2025 年 6 月整月作比较。
- 页面右上角新增“数据截止”下拉控件；默认按当前系统日期上一天，若最新导入数据较系统日期滞后 2 天及以上，则按导入最新日期展示并提示“请注意数据口径”。
- 后端接口新增/透传 `asOf`：`/api/kpi`、`/api/platform-data`、`/api/platform-trend`、`/api/product-analysis`、`/api/org-analysis`、`/api/payment-period/{year}`。
- 前端切换截至日期后会清理运行缓存并刷新 KPI、业务平台趋势、产品结构、交期结构、机构维度、队伍分析等主要模块。
- 业务平台趋势切换到“月度”时默认取当前系统月份，不再固定为 4 月。
- 统一版本号到 `v1.0.93`，更新 README/CHANGELOG/页面缓存参数/后端版本常量/测试断言。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `230 passed, 1 warning`；警告为第三方 `python_multipart` 待弃用提示。

## 2026-06-19 KPI 概览经代数据复核

- 读取项目上下文、KPI 后端接口、经代 ETL 聚合、前端 KPI 卡片与目标配置链路。
- 复核当前本地库 `backend/business_data.db`：`get_kpi_data(2026)` 返回经代期交实绩 `31955.90` 万，去年同期 `19589.75` 万，日级截止为经代 `2026-05-25`、转型 `2026-05-24`。
- 发现当前 `target_config` 中 2026 目标 payload 为 `categories: null`，前端会回退到默认目标，经代期交默认目标为 `4800` 万；与 `targets_import.json` / `期交目标.xlsx` 中经代正式目标 `81900` 万不一致。
- 复核根目录最新 `经代业绩分析 (37).xlsx`：源文件已包含 `2026-06-19` 数据；按源文件汇总，2026 年经代期交截至 `2026-05-25` 为 `32169.5151` 万，截至 `2026-06-19` 为 `37665.5206` 万。
- 核心判断：当前 KPI 概览经代“实绩”读的是旧库数据；“达成率”若页面使用默认目标则明显不符合正式经营目标口径；“同比”公式可追溯，但当前结果基于旧库截至 5 月 25 日，不代表 6 月 19 日最新源文件口径。

## 2026-06-19 服务器端 KPI 概览经代数据复核

- 通过 SSH 只读检查服务器 `192.168.50.6`，`business-analysis.service` 运行中且开机启用，健康检查返回 `v1.0.92`，数据库最新期间为 `202606`。
- 服务器 `/opt/business-analysis/backend/business_data.db` 更新时间为 `2026-06-19 11:16:46`，`data_imports` 记录显示 4 份 `20260619` Excel 已由 Web 成功导入。
- 服务器经代聚合已更新到 `2026-06-19`：2026 年 1-6 月经代期交分别为 `3524.8880`、`8539.9853`、`9734.6173`、`5659.2924`、`5887.4486`、`4319.2889` 万；截至 `2026-06-19` YTD 为 `37665.5210` 万。
- 服务器经代去年同期截至 `2025-06-19` 为 `24487.2256` 万，同比为 `+53.8%`。
- 服务器 `target_config.payload` 结构正常，2026 经代期交年度目标为 `81900` 万；因此服务器端经代达成率应按 `37665.5210 / 81900 = 46.0%` 展示。
- 结论：本地库与服务器库状态不一致；服务器端经代 KPI 数据、正式目标和同比口径是最新状态，本地复核时发现的目标缺失问题仅存在于本地数据库。
- 补充复核 6 月单月同比：服务器经代 2026 年 6 月 1-19 日为 `4319.2890` 万，2025 年 6 月 1-19 日为 `3661.8091` 万，同日口径同比应为 `+18.0%`；若用 2025 年 6 月整月 `5932.3845` 万作分母，则得到 `-27.2%`，属于未满月对整月的非同口径比较，不应用作 6 月 MTD 同比。

## 2026-06-14 Ubuntu NAS 非 Docker 部署

- 任务：在局域网 Ubuntu NAS `192.168.50.8` 上按非 Docker 方式部署项目。
- 已做：上传当前源码到服务器临时目录，并同步到 `/opt/business-analysis`。
- 已做：安装/确认 Python 3、venv、pip、nginx、rsync 等依赖；创建后端虚拟环境并安装 `backend/requirements.txt`。
- 已做：初始化 SQLite 运行库，创建首个管理员账号；初始密码通过部署进程环境注入，未写入仓库、项目记忆或日志。
- 已做：安装并启用 `business-analysis.service`，配置 nginx 反向代理并启用 80 端口访问。
- 验证：`systemctl is-active business-analysis` 返回 `active`，`systemctl is-enabled business-analysis` 返回 `enabled`。
- 验证：`systemctl is-active nginx` 返回 `active`，`systemctl is-enabled nginx` 返回 `enabled`。
- 验证：`curl http://127.0.0.1:45679/api/health` 返回 `status=ok`，版本 `v1.0.92`。
- 验证：从 Windows 本机执行 `curl.exe -I http://192.168.50.8/` 返回 `HTTP/1.1 200 OK`。
- 遗留：服务器当前没有业务 Excel 原始表，`rebuild_aggregates_from_raw_tables.py` 提示 raw tables empty；页面可访问，但业务数据需要后续上传 Excel 或恢复已有 SQLite 数据库。

## 2026-06-13 容器化部署方案

- 任务：为项目补充可部署 Docker 镜像方案，并上传到 GitHub 以便后续复用。
- 已做：新增 `Dockerfile`、`.dockerignore`、`docker-compose.yml`、`.github/workflows/docker-image.yml`、`docs/DOCKER.md`。
- 已做：新增项目级 AI 上下文最小文件，记录容器化部署结论、运行方式和后续待办。
- 关键判断：不把镜像 tar 文件提交进 GitHub 仓库，改用 GitHub Container Registry 保存镜像，更适合版本化和服务器部署。
- 验证：本地环境未安装 Docker，无法本机构建；已完成 YAML 解析、Dockerfile/文档存在性检查、`backend/main.py` 与 `backend/db/connection.py` 语法编译检查。
- 验证：执行 `pytest -q`，结果为 `226 passed, 3 failed, 1 warning`；失败集中在既有 `tests/test_transform_and_trend.py` 产品结构断言，未涉及本次新增 Docker 文件。
- 遗留：需要在 GitHub Actions 页面确认首次 workflow 是否成功；如 GHCR 包默认私有，需要按使用场景调整包访问权限；既有产品结构测试失败需单独排查。

## 2026-06-13 开发环境完善

- 安装并验证本机开发工具：Python 3.12.10、Git 2.54.0、uv 0.11.21。
- 将 Python、Python Scripts、Git、uv 路径加入用户 PATH；当前 Codex 子进程可能仍需显式注入 PATH，新终端通常会生效。
- 创建本地 `.venv` 并安装 `requirements.txt` 与 `backend/requirements.txt`。
- 运行完整测试：`python -m pytest -q`，结果为 `229 passed, 1 warning`。
- 发现并修复 Windows 预检脚本依赖问题：`uv run` 原先未显式安装 requirements，导致新环境缺少 pytest。
- 同步修复 Bash 测试脚本，使其同时安装根目录与后端依赖。
- 将 `.venv/` 加入 `.gitignore`，避免本地虚拟环境进入版本状态。
- 重新执行 Windows 预检：`scripts\preflight.ps1` 通过，测试 `229 passed, 1 warning`，数据质量审计 `issues: 0`。
