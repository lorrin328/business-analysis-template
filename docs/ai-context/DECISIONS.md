# 决策记录

## 2026-06-30 前端控件事件采用声明式属性与模块绑定

### 决策

主看板页面和 `js` 目录内的用户交互控件不再新增 `onclick` / `onchange` 内联事件。静态页面控件使用 `data-*` 声明行为，动态模板控件使用所属模块的容器级事件代理。

### 原因

- 内联事件会把 HTML 结构、全局函数名和业务状态耦合在一起，后续新增、调整或删除模块时容易漏改。
- 目标弹窗、队伍增强面板等动态模板会反复重绘，容器级事件代理比逐项拼接函数调用更稳定。
- 静态测试已覆盖主要控件的防回退约束，可以在后续迭代中及时发现维护性倒退。

### 影响

- 后续新增按钮、下拉框、复选框或动态输入框时，优先添加语义化 `data-*` 属性，并在所属 `js` 模块集中绑定。
- 不在 HTML 字符串里拼接业务函数调用；需要复用业务逻辑时，保留函数作为模块内部入口，由绑定层调用。
- 若确需临时使用内联事件，必须同步记录原因并补充迁移 TODO。

## 2026-06-30 队伍增强动态控件由面板事件代理绑定

### 决策

队伍增强面板运行时生成的统计期间按钮、期间下拉框和业务模式复选框统一由 `js/team-analysis.js` 的 `bindTeamEnhancedControls()` 绑定事件。动态模板只输出 `data-team-enhanced-*` 声明属性，不再输出内联业务函数调用。

### 原因

- 队伍增强面板会随筛选刷新整体重绘，事件应绑定在稳定的 `teamEnhancedPanel` 容器上，避免每次模板生成都拼接业务函数调用。
- 队伍增强与队伍趋势共享年份、机构和业务线状态，事件入口继续集中在 `team-analysis.js`，便于后续新增队伍结构指标和筛选项。
- 业务线名称进入动态模板时统一走 `escapeTeamText()`，减少后续扩展业务线时的 HTML 属性和文本转义风险。

### 影响

- 后续新增队伍增强动态控件时，优先补充 `data-team-enhanced-*` 属性，并扩展 `bindTeamEnhancedControls()`。
- 不再为队伍增强面板新增 `onclick` / `onchange` 内联事件，对应静态测试会拦截回退。
- `switchTeamEnhancedPeriodType()`、`switchTeamEnhancedPeriodValue()`、`toggleTeamEnhancedBusinessLine()` 保留为模块内部状态更新入口。

## 2026-06-30 通用弹窗关闭事件由 modal script 绑定

### 决策

经营分析主页面通用弹窗的 overlay 背景点击和关闭按钮点击统一由 `bindModalControls()` 绑定事件。HTML 只保留 `id="modalOverlay"` 和 `data-modal-action="close"`，不再写 `closeModal()` 或 `event.stopPropagation()` 内联事件。

### 原因

- 通用弹窗被 KPI 详情、目标设置、产品配置等多个模块复用，关闭行为应集中维护。
- `closeModal()` 已通过 `e.target === modalOverlay` 判断背景点击，弹窗主体不需要单独用内联 `stopPropagation()`。
- 关闭按钮使用 `data-modal-action="close"` 后，后续新增同类关闭按钮可直接复用绑定逻辑。

### 影响

- 后续新增通用弹窗关闭按钮时，使用 `data-modal-action="close"`。
- 如需新增关闭前校验或统一清理逻辑，优先修改 `closeModal()` 和 `bindModalControls()`。
- 不再为通用弹窗关闭行为新增内联 `onclick`，对应静态测试会拦截回退。

## 2026-06-30 上传入口由 upload.js 绑定

### 决策

数据上传区域的上传卡片点击和文件输入变化统一由 `js/upload.js` 的 `bindUploadControls()` 绑定事件。HTML 只保留 `data-upload-input` 和 `data-upload-info` 声明属性。

### 原因

- 上传入口是导入链路的第一步，后续新增文件类型或调整文件说明时，HTML 不应直接引用文件输入 id 和上传处理函数。
- `data-upload-input` 明确上传卡片对应的文件输入，`data-upload-info` 明确文件输入对应的提示区域，后续新增上传卡片时更容易复制和测试。
- 保持 `handleFile()` 作为上传业务流程入口，事件绑定与上传逻辑分离。

### 影响

- 后续新增上传卡片时，必须在卡片上设置 `data-upload-input`，并在文件输入上设置 `data-upload-info`。
- 上传业务流程仍由 `handleFile()` 处理；如调整上传顺序、必填文件或接口字段，优先修改 `js/upload.js` 内部逻辑并补充测试。
- 不再为上传区域新增内联 `onclick` / `onchange`，对应静态测试会拦截回退。

## 2026-06-30 队伍趋势主控件由 team-analysis 绑定

### 决策

队伍趋势模块的年份、指标类型、时间维度、季度、业务系列和机构控件统一由 `js/team-analysis.js` 的 `bindTeamTrendControls()` 绑定事件。HTML 只保留控件 id 和 `data-team-*` 声明属性。

### 原因

- 队伍趋势与队伍增强分析共享年份、机构和业务线状态，主控件事件应集中在 `team-analysis.js` 内，避免 HTML 与模块状态耦合。
- 机构全选逻辑原先依赖 checkbox 顺序，后续新增或调整机构时不够稳健；改为 `data-team-org` 选择器后更明确。
- 本次仅迁移队伍趋势主控件；队伍增强面板由运行时 HTML 模板生成，后续单独收敛，避免一轮改动跨两个渲染层。

### 影响

- 后续新增队伍趋势指标按钮，必须设置 `data-team-metric` 并同步 `teamMetricNames` / `teamMetricUnits` / `getTeamAggregated()`。
- 后续新增队伍趋势时间维度，必须设置 `data-team-dim` 并同步 `switchTeamDim()` 和图表构造逻辑。
- 后续新增队伍趋势业务系列或机构筛选项，必须设置 `data-team-series` 或 `data-team-org`，由 `bindTeamTrendControls()` 事件代理处理。

## 2026-06-30 交期结构控件由 payperiod-chart 绑定

### 决策

交期结构模块的图表切换、年份、时间维度、季度/月度、业务系列、转型渠道、经代机构、转型机构和保费类型控件统一由 `js/payperiod-chart.js` 的 `bindPayPeriodControls()` 绑定事件。HTML 只保留控件 id 和 `data-pay-period-*` 声明属性。

### 原因

- 交期结构与产品结构同属“产品与交期结构”区域，后续新增筛选项和口径时应保持同样的声明式事件边界。
- 动态生成的机构复选框如果继续传业务函数，会和公共 `createCheckboxLabel()` 的职责混在一起；改为 data 属性后由所属模块事件代理接管。
- `data-pay-period-*` 与 `data-product-*` 分开，减少产品结构和交期结构之间的选择器误匹配。

### 影响

- 后续新增交期结构控件时，优先添加 `data-pay-period-*` 属性，并扩展 `bindPayPeriodControls()`。
- 后续动态生成交期结构筛选项时，不直接给节点绑定业务回调；应生成声明式 data 属性，由 `payperiod-chart.js` 事件代理接管。
- 不再为交期结构区域新增内联 `onclick` / `onchange`，对应静态测试会拦截回退。

## 2026-06-30 产品结构控件由 product-analysis 绑定

### 决策

产品结构模块的图表切换、业务来源、转型渠道、经代机构、转型机构、时间维度、季度/月度和保费类型控件统一由 `js/product-analysis.js` 的 `bindProductStructureControls()` 绑定事件。HTML 只保留控件 id 和 `data-product-*` 声明属性。

### 原因

- 产品结构是后续新增分类、机构筛选和产品口径调整的高频区域，内联事件会让 HTML 与运行状态、函数名和动态生成控件耦合。
- 经代机构复选框由接口数据动态生成，改为 `data-product-jingdai-org` 后可以通过事件代理统一处理，避免生成节点时传入业务函数。
- `data-product-*` 与其他模块的 `data-org` / `data-platform-*` 分开，减少跨模块选择器误匹配。

### 影响

- 后续新增产品结构控件时，优先添加 `data-product-*` 属性，并扩展 `bindProductStructureControls()`。
- 后续动态生成产品结构筛选项时，不直接给节点绑定业务回调；应生成声明式 data 属性，由产品模块事件代理接管。
- 不再为产品结构区域新增内联 `onclick` / `onchange`，对应静态测试会拦截回退。

## 2026-06-30 平台趋势控件由 platform-trend-main 绑定

### 决策

业务平台趋势模块的年份、时间维度、季度/月度、业务系列、机构和保费类型控件统一由 `js/platform-trend-main.js` 的 `bindPlatformTrendControls()` 绑定事件。HTML 只保留控件 id 和 `data-platform-*` 声明属性，不再写平台趋势相关内联 `onclick` / `onchange`。

### 原因

- 平台趋势图是多控件联动模块，后续新增保费口径、业务系列、机构筛选或时间维度时，应优先在一个运行模块内维护状态和事件。
- 内联事件会让 HTML 控件与全局函数名耦合，后续拆分或重命名函数时容易遗漏。
- 集中绑定后，静态测试可以约束平台趋势区不回退到旧模式，降低页面长期演进成本。

### 影响

- 后续新增平台趋势时间维度按钮，必须设置 `data-platform-time-dim` 并同步 `switchTimeDim()` 的展示逻辑。
- 后续新增平台趋势业务系列或机构筛选项，必须设置 `data-platform-series` 或 `data-platform-org`。
- 后续新增平台趋势保费口径按钮，必须设置 `data-platform-premium-type` 并同步 `switchPremiumType()` / 图表取数字段。

## 2026-06-30 机构维度筛选控件由 org-analysis 绑定

### 决策

机构维度筛选区的机构标签、时间维度按钮、季度/月度下拉框统一由 `js/org-analysis.js` 绑定事件。HTML 只保留 `data-org-filter`、`data-org-dim` 和控件 id，不再写 `toggleOrgFilter()`、`switchOrgDim()` 或 `renderOrgTable()` 的内联事件。

### 原因

- 机构维度后续可能新增机构、调整时间维度或扩展筛选项，如果继续把事件写在 HTML 中，模块逻辑会分散在页面结构和脚本里。
- 时间维度切换原先依赖浏览器全局 `event`，不利于测试和后续模块化；显式传入按钮可以减少隐式依赖。
- 季度/月度下拉框变化需要同步模块内部状态后再重渲染，集中绑定更符合当前 `org-analysis.js` 的状态管理方式。

### 影响

- 后续新增机构筛选项时，HTML 增加 `data-org-filter` 即可；筛选行为仍由 `bindOrgFilterControls()` 处理。
- 后续新增时间维度按钮时，必须设置 `data-org-dim` 并同步 `switchOrgDim()` 的展示逻辑。
- 不再为机构维度筛选区新增内联 `onclick` / `onchange`，对应静态测试会拦截回退。

## 2026-06-30 KPI 卡片详情入口使用 data-kpi-modal

### 决策

经营分析看板 KPI 卡片不再使用内联 `onclick="openModal(...)"` 打开详情弹窗，统一通过 `data-kpi-modal` 声明弹窗类型，并由 `js/kpi-cards.js` 的 `bindKPICardActions()` 在 `.kpi-grid` 上事件代理处理。

### 原因

- KPI 卡片是后续新增和删减指标模块的核心入口，内联点击会让卡片结构、弹窗函数和配置选择器相互耦合。
- `data-kpi-modal` 使 HTML 只描述卡片对应的业务类型，点击行为集中在 KPI 运行模块内，更便于测试和批量调整。
- `dashboard-config.js` 也改为按 `data-kpi-modal` 查找卡片标题，避免配置逻辑依赖事件属性。

### 影响

- 后续新增 KPI 卡片时，必须设置唯一的 `data-kpi-modal`，并在 `kpi-modal-content.js` 中补齐同名详情内容。
- 后续调整 KPI 卡片标题配置时，优先检查 `dashboard-config.js` 的 `data-kpi-modal` 匹配关系。
- 不再为 KPI 卡片新增 `onclick="openModal(...)"`，对应静态测试会拦截回退。

## 2026-06-30 主工具栏动作统一由 dashboard-actions 管理

### 决策

经营分析看板顶部工具栏按钮统一使用 `data-dashboard-action` 和 `data-dashboard-href` 声明动作，由 `js/dashboard-actions.js` 通过事件代理调用对应运行函数或执行页面跳转。

### 原因

- 顶部工具栏是后续新增、调整、删减模块入口最频繁的位置，继续使用内联 `onclick` 会把 HTML、全局函数名和跳转地址混在一起。
- 集中动作表便于检查每个按钮对应的运行行为，也便于后续把按钮配置化或按权限动态渲染。
- 本次仅收敛顶部工具栏，不触碰 KPI 卡片、图表切换和上传卡片等历史交互，避免一次性扩大前端回归范围。

### 影响

- 后续新增顶部模块入口时，HTML 只声明 `data-dashboard-action`；如是新动作，必须同步扩展 `js/dashboard-actions.js` 和 `tests/test_frontend_static.py`。
- 顶部工具栏跳转按钮优先使用 `data-dashboard-action="navigate"` 和 `data-dashboard-href`。
- 历史页面中其他内联事件仍按模块逐步迁移，不在本决策中一次性强制改完。

## 2026-06-30 前端弹窗按钮优先使用 data-action 与脚本绑定

### 决策

产品配置弹窗的取消、保存等交互按钮使用 `data-product-config-action` 标记，并在 `js/product-config-modal.js` 内集中绑定事件；新增或调整同类弹窗按钮时，不再优先使用内联 `onclick`。

### 原因

- 内联事件把 HTML 模板、全局函数名和交互行为耦合在一起，后续拆模块、改函数名或复用弹窗时容易遗漏。
- `data-action` + 事件绑定更容易被静态测试约束，也便于后续把弹窗渲染和行为继续拆成更小的函数。
- 本次只收敛产品配置弹窗内部按钮，不改变页面主导航、KPI 卡片等历史内联事件，避免扩大回归范围。

### 影响

- 后续调整产品配置弹窗交互，优先修改 `bindProductConfigActions()`。
- 后续清理其他弹窗或按钮内联事件时，应按小模块逐步迁移，并为对应模块补充静态约束。

## 2026-06-30 荣誉体系机构汇总与奖励测算独立为 summary builder

### 决策

星钻联盟荣誉体系的机构汇总和季度奖励测算统一放入 `backend/honor/summary.py`，由 `build_org_summary()` 和 `build_quarter_rewards()` 生成。`backend/honor/calculator.py` 保留星钻余额流转、离职清零、人员月度和人员汇总职责。

### 原因

- 机构汇总和奖励测算是结果派生口径，和逐月钻石余额流转不是同一职责。
- 后续可能调整会员率、资深及以上口径、奖励金额或季度归属，独立 builder 更容易测试和审查。
- 该拆分不改变计算口径、接口返回、数据库表结构或导出文件。

### 影响

- 后续调整 `honor_org_summary` 字段生成、会员率、人均钻石、预估奖励时，优先修改 `backend/honor/summary.py` 并补充 `tests/test_honor_summary.py`。
- 后续调整钻石增减、新星判断、离职清零、人员 summary 字段时，仍修改 `backend/honor/calculator.py`。

## 2026-06-30 荣誉体系源数据加载与指标索引独立为 sources

### 决策

星钻联盟荣誉体系的人力源表加载、保单源表加载、个人/主管/经理指标索引构造和源表异常识别统一放入 `backend/honor/sources.py`。`backend/honor/calculator.py` 保留星钻流水计算、离职清零、人员汇总、机构汇总和奖励测算。

### 原因

- `calculator.py` 同时处理数据库读取、字段归一、保单有效性、团队指标和星钻余额流转，后续新增规则时很难判断改数据准备还是改计算主流程。
- 源数据准备有独立业务边界：从 `hr_data` 和 `performance` 转成标准 staff/policy index；星钻计算应只消费这些标准结构。
- 主管/经理团队指标优先级需要单独测试，避免后续调整团队规则时破坏个人指标回退。

### 影响

- 后续调整源表字段、回销异常、团队指标索引、个人/主管/经理指标来源时，优先修改 `backend/honor/sources.py` 并补充 `tests/test_honor_sources.py`。
- 后续调整钻石增减、离职清零、新星判断、机构汇总和奖励测算时，优先修改 `backend/honor/calculator.py`。
- 星钻计算口径、接口返回、数据库表结构和导出文件不变。

## 2026-06-30 荣誉体系 dashboard 派生逻辑独立为 builder

### 决策

星钻联盟荣誉体系 dashboard 的派生聚合逻辑统一放入 `backend/honor/dashboard.py`，由 `build_honor_dashboard_payload()` 接收数据库读取结果并生成前端需要的看板 payload。`backend/honor/repository.py` 保留 SQLite 持久化和基础表读取职责。

### 原因

- 荣誉体系 dashboard 同时包含项目排行、机构结构、专员历史、管理职历史、预警、等级分布和趋势，继续放在 repository 会让持久化层与展示聚合耦合。
- 后续新增 dashboard 卡片、分组或预警规则时，应能直接测试纯 payload builder，而不必构造数据库批次。
- 该拆分不改变 API、表结构、计算口径或导出，仅调整模块边界。

### 影响

- 后续调整 `/api/honor/dashboard` 的展示结构，优先修改 `backend/honor/dashboard.py` 并补充 `tests/test_honor_dashboard.py`。
- 后续调整批次、写库、读取基础表、通用 `fetch_table()` 时仍修改 `backend/honor/repository.py`。
- dashboard builder 中如需读取新的源表，应先在 repository 中显式读取，再作为参数传入 builder，避免 builder 直接访问数据库。

## 2026-06-30 荣誉体系清洗归一逻辑独立为 normalizers

### 决策

星钻联盟荣誉体系中的文本、人员代码、数字、日期、年月、业务线和职级角色归一逻辑统一放入 `backend/honor/normalizers.py`。`backend/honor/calculator.py` 保留星钻规则计算、人员月度流水和结果组装职责。

### 原因

- 荣誉体系后续可能继续新增规则或展示维度，如果计算主流程同时承载字段清洗、日期解析、业务线映射和职级判断，新增规则时容易复制私有 helper 或改错口径。
- 清洗归一函数是纯函数，适合独立测试；规则计算可在不连接数据库的情况下复核输入标准化边界。

### 影响

- 后续荣誉体系新增人员、团队、保单类规则时，优先复用 `honor.normalizers` 中的 `text_value()`、`staff_code()`、`number_value()`、`optional_int()`、`parse_date()`、`ym_from_value()`、`normalize_business_line()` 和 `role_type()`。
- 如需新增新的业务线或职级映射，必须同步更新 `tests/test_honor_normalizers.py`。
- 星钻计算口径、接口返回、数据库表结构和导出文件不变。

## 2026-06-30 API 公共查询参数与当前数据流文档防漂移

### 决策

FastAPI 接口中通用的看板年份参数和 `asOf=YYYY-MM-DD` 参数统一由 `backend/api/params.py` 提供。当前数据流文档以 `backend/services/excel_pipeline.py` 和 `backend/etl/aggregates/` 为权威导入链路，不再使用旧 `backend/aggregator.py` 作为当前说明。

### 原因

- KPI、机构、产品、趋势、队伍、目标、导出和 AI 只读接口重复手写年份范围校验，后续新增模块容易出现范围不一致。
- `asOf` 日期参数是当前经营口径的重要边界，应统一校验格式，避免各接口自行维护正则。
- 文档仍保留旧导入入口会误导后续新增聚合表时在上传入口或旧文件中重复实现，增加 Web 上传和全量重建口径漂移风险。

### 影响

- 后续新增看板类接口时，年份参数优先使用 `DashboardYearQuery = DEFAULT_YEAR`；支持全局截至日期的接口优先使用 `AsOfQuery = None`。
- 后续新增导入字段或聚合表时，优先修改 `backend/etl/aggregates/` 与 `backend/services/excel_pipeline.py`，不要在 `backend/main.py` 的上传入口单独维护一套聚合逻辑。
- `tests/test_docs_current_data_flow.py` 会防止当前数据流文档再次把旧 `backend/aggregator.py` 写成现行入口。

## 2026-06-30 原始表日期表达式和 SQL 标识符转义统一入口

### 决策

原始 Excel 表相关的日期压缩表达式和 SQL 标识符转义统一由 `services.raw_table_reader` 提供。产品配置自动提取、导入安全校验和产品结构查询都复用同一 helper。

### 原因

- 多个模块需要从中文日期、月份、时间字段中过滤 `YYYYMM` 或按 `asOf` 截止，重复实现容易遗漏分隔符或产生不同口径。
- `quote_identifier()` 属于动态 SQL 内部安全边界，应集中维护，避免后续新增模块时临时拼接列名。

### 影响

- 后续新增直接读取原始表的模块，优先复用 `raw_table_column_set()`、`pick_existing_column()`、`compact_period_expr()`、`append_period_filter()`、`append_cutoff_filter()` 和 `quote_identifier()`。
- `compact_period_expr()` 当前剔除 `-`、`/`、`.`、`年`、`月`、`日`、空格和 `:`，可覆盖常见日期与日期时间文本；新增格式时只改公共 helper 和对应测试。

## 2026-06-30 指标类 API meta 统一通过 response_meta 构造

### 决策

指标类 API 的响应 meta 字段逐步通过 `services.response.response_meta()` 构造，优先覆盖新增或正在重构的模块。`success_response()` 仍负责统一响应外壳和 `updatedAt`。

2026-06-30 追加：KPI、机构、产品、平台数据、平台趋势、队伍分析、目标、交期结构、配置指标、AI 只读和产品配置接口已迁移到 `response_meta()`。

### 原因

- 多个 API 重复手写 `metric`、`unit`、`dataSource`、`definitions` 字段，后续新增模块时容易命名不一致或遗漏 `definitions`。
- `response_meta()` 提供统一入口，但不强制一次性改完所有接口，降低回归风险。

### 影响

- 已迁移 KPI、机构、产品、平台趋势、队伍分析、目标、交期结构、配置指标、AI 只读和产品配置相关接口。
- 荣誉体系接口的 meta 围绕 `batchId`、`ruleVersion`、`dataSourceMode` 等批次和规则版本字段，使用专用 `services.response.batch_meta()`，不套用指标类 `response_meta()`。
- 接口 JSON 外壳和前端契约不变：仍为 `success/data/message/meta`，`meta.updatedAt` 仍由 `success_response()` 注入。

## 2026-06-30 队伍分析空结果结构集中维护

### 决策

队伍分析接口的空结果结构统一由 `db.repositories.team_enhanced._empty_team_analysis_response()` 生成。无 `hr_data` 表、无可选月份等早退分支都复用同一结构。

### 原因

- 队伍分析返回字段较多，包含 `summary`、结构分布、分位数、标准人力、趋势和筛选条件；多个早退分支手写同样结构，后续新增字段时容易只改正常返回而漏掉空返回。
- 空结果也是前端稳定性契约的一部分，应当和正常结果一样集中维护并测试。

### 影响

- 正常数据计算和业务口径不变。
- 后续新增队伍分析返回字段时，必须同步检查 `_empty_team_analysis_response()`，确保无数据状态下前端仍拿到完整结构。

## 2026-06-30 队伍分析纯计算与清洗逻辑进入 service

### 决策

队伍结构和产能分析中的纯函数与常量集中到 `services.team_analysis_utils`，包括业务线归一、人员代码清洗、期间解析、百分位、分档、比例和标准人力阈值。`db.repositories.team_enhanced` 保留数据库读取、样本构造和结果组装。

### 原因

- 队伍分析后续很可能继续新增维度和指标，如果 repository 同时承载数据访问、字段清洗、统计工具和返回结构，文件会继续膨胀。
- 纯函数迁出后可以单独测试，不依赖 SQLite 临时表，后续改分档或口径更容易做小范围回归。
- 该调整不改变接口、字段、统计公式和数据来源，只改变模块边界。

### 影响

- 后续新增队伍分析维度时，通用清洗和统计工具优先放入 `services.team_analysis_utils`。
- 后续涉及数据库表读取、月份范围、样本筛选和返回结构的改动仍放在 `db.repositories.team_enhanced`。
- 标准人力阈值仍为 `OTO=2.0`、`证保=3.0`，仅迁移位置，不改业务口径。

## 2026-06-30 平台数据查询独立为 platform repository

### 决策

平台聚合数据查询 `get_platform_data()` 从 `db.repositories.kpi` 拆分到 `db.repositories.platform`。公共导出仍由 `db.__init__` 提供，外部调用方继续使用 `from db import get_platform_data`。

### 原因

- `get_platform_data()` 是平台趋势、队伍分析和部分导出能力的数据底座，不属于 KPI 概览专属逻辑。
- KPI repository 同时承载平台数据和 KPI 概览，会让后续新增或调整指标时更难判断改动边界。
- 文件级拆分可以在不改变 API、接口返回和业务口径的前提下提高模块内聚性。

### 影响

- 后续调整平台底层聚合查询、趋势图数据来源或队伍分析基础数据时，优先修改 `db.repositories.platform`。
- 后续调整 KPI 卡片指标、达成率、同期口径和产品指标时，优先修改 `db.repositories.kpi`。
- 对 API 层、服务层和测试层的导入方式无破坏性影响。

## 2026-06-30 KPI 日级 YTD 查询集中到内部 helper

### 决策

`get_kpi_data()` 中读取日级累计表的 YTD 查询，统一通过 `_sum_daily_columns()` 和 `_sum_daily_column_by_channel()` 生成并执行。转型业务、经代业务和产品类指标继续按各自真实日级截止读取。

### 原因

- KPI 概览同时涉及转型日表、经代日表、机构产品日表，重复拼接 `date_filter_sql()` 和 `SUM(...)` 容易在新增指标时出现漏改或字段别名不一致。
- 近期 `asOf`、产品分类和经代/转型不同截止日规则已经成为核心业务边界，日级查询应有统一入口，便于审查和回归。
- 当前性能与维护收益可以通过 Python 内部 helper 获得，不需要为了这类查询改写为 Rust。

### 影响

- KPI 接口字段、月级回退策略、长险期交口径和前端展示不变。
- 后续新增 KPI 日级 YTD 指标时，优先复用这两个 helper；如果需要按业务线不同截止日混合查询，应继续使用 `cutoff_policy` 生成截止条件。
- helper 内置 SQL identifier 校验，后续不得把未校验的用户输入作为表名或列名传入。

## 2026-06-30 原始表日期过滤集中到 raw_table_reader

### 决策

直接读取 `performance`、`jingdai`、`hr_data`、`value_data` 等原始 Excel 表时，候选列选择、日期字段压缩、年份/月度过滤和截止日过滤优先使用 `services.raw_table_reader` 中的公共 helper。

### 原因

- 原始表字段多为中文列名且格式不稳定，日期可能出现 `YYYYMMDD`、`YYYY-MM-DD`、`YYYY.MM.DD`、中文年月日等形式。
- 产品结构查询已经有一套成熟处理逻辑，继续留在单个 repository 内会导致后续模块复制粘贴，增加口径漂移风险。
- `raw_table_reader` 已是原始表读取边界，将列选择和期间过滤放在同一服务更便于复用和测试。

### 影响

- 产品结构与各业务模式前三产品查询业务口径不变，但复用公共 helper。
- 后续新增直接读原始表的分析模块，应优先使用 `pick_existing_column()`、`append_period_filter()`、`append_cutoff_filter()`，不要在 repository 内重新实现日期清洗 SQL。

## 2026-06-30 日级截止 SQL 条件集中生成

### 决策

按渠道分别应用日级截止的 SQL 条件统一由 `services.cutoff_policy.channel_cutoff_filter_sql()` 生成。机构维度中的期交、产品指标和长险期交年度累计查询复用该 helper。

### 原因

- 机构维度需要按不同渠道真实截止日分别截取日表，手工复制 `(channel = ? AND (month < ? OR ...))` 容易在后续新增指标时漏改或参数顺序出错。
- 截止策略已经集中在 `services.cutoff_policy`，SQL 条件生成也应放在同一边界内，便于测试和复用。

### 影响

- 当前业务口径不变：仍按各渠道日级截止读取年度累计，缺少日表时回退月表。
- 后续新增机构日级指标时应优先复用 `channel_cutoff_filter_sql()`，不要在 repository 中重新拼接渠道截止条件。

## 2026-06-30 平台趋势兜底数据独立加载

### 决策

将平台趋势图的 `platformMock` 本地兜底数据从 `js/platform-trend-main.js` 迁出到 `js/platform-seed-data.js`，页面在 `seed-data.js` 后、`data-integration.js` 前加载该文件。

### 原因

- `platform-trend-main.js` 同时承载一万六千多行兜底数据和趋势图运行逻辑，后续调整筛选、缓存、趋势展示时审查成本高。
- 兜底数据属于运行参考数据，不应与图表交互和 API 加载逻辑混在同一文件。
- 拆分后平台趋势运行逻辑文件降至数百行，更适合后续模块化、增删图表能力和代码审查。

### 影响

- `platformMock` 仍按原有脚本全局变量方式提供给 KPI 卡片、弹窗、数据接入和平台趋势逻辑，业务行为不变。
- 后续调整历史兜底数据时修改 `platform-seed-data.js`；调整趋势图交互和渲染时修改 `platform-trend-main.js`。
- 前端生产运行边界以 `经营分析模板.html` 和 `tests/test_frontend_static.py` 为准。

## 2026-06-30 Excel 导入统一 pipeline

### 决策

Web 上传和本地 `rebuild_from_excels.py` 全量重建统一复用 `backend/services/excel_pipeline.py`。四类 Excel 的解析、聚合、活动人力回填、年份收集、日级截止警告、聚合表写入和原始表写入集中维护。

### 原因

- 此前 Web 上传和命令行重建分别维护一套解析、聚合和写库顺序，新增模块或字段时容易只改一处，造成线上上传和本地/部署重建口径漂移。
- 近期产品分类、日级截止和经代配置规则已经形成较多跨表依赖，需要一个明确的导入扩展入口。
- 保留 FastAPI + pandas + SQLite 现有技术栈即可提升维护性，不需要为当前规模引入 Rust 或新的运行时复杂度。

### 影响

- 后续新增聚合表时，优先更新 `AGGREGATE_TABLE_ORDER`、对应解析聚合函数和 `write_excel_pipeline_result()` 的既有流程。
- `/api/upload` 仍保留重复文件跳过、部分失败处理、增量写库和导入历史；`rebuild_from_excels.py` 仍做全量重建，但与上传共享同一聚合来源。
- 转型产品分类读源 Excel、经代产品分类读 `product_config`、KPI/机构 `asOf` 日级口径等业务决策不变。

## 2026-06-29 产品指标随 asOf 日级截止

### 决策

KPI 概览和机构维度年度累计中的转型产品指标，在存在日级聚合数据时按 `asOf` 日级截止读取。商保年金和保障类分别使用日级表 `product_annuity`、`product_protection`；机构维度年度累计同时覆盖 `product_10year`。无日级数据时回退月表。

### 原因

- 主看板期交保费已经按 `asOf` 日级截断，如果商保年金/保障类继续按整月累计，会出现同一 KPI 区域内时间口径不一致。
- 2026-06-29 源表中存在 6 月 29 日尾量，默认 6 月 28 日口径若读取月表会多计少量产品实绩。
- 机构维度年度累计也服务达成率复核，应与 KPI 概览保持同一时间边界。

### 影响

- `agg_org_daily_performance` 新增产品字段，Excel 重建和 Web 上传会写入日级产品分解。
- `agg_jingdai_daily` 新增经代商保年金/保障类字段，继续受经代 `product_config` 手工配置影响。
- 月度/季度明细仍来自月表；年度累计在有日表时由日级累计覆盖。

## 2026-06-29 转型产品分类标识来源调整

### 决策

转型业务商保年金、保障类产品分类以业绩基表标识列为准：`是否商保年金产品` 对应商保年金实绩，`是否社会保障型产品` 对应保障类产品实绩。参数设置模块不再维护转型产品分类，只保留经代产品分类手工配置。

### 原因

- 2026-06-29 新业绩基表已提供转型业务个人养老金、商保年金、社会保障型产品标识，继续手工维护会产生源表口径和参数口径不一致风险。
- 经代表当前仍无等价结构化标识，继续沿用 `product_config` 手工维护更贴合现状。
- 将转型分类回归数据源，可减少导入后漏重算、历史参数残留和产品代码规范化造成的分类误差。

### 影响

- `agg_org_performance.product_annuity` 和 `agg_org_performance.product_protection` 对转型业务不再受 `product_config` 影响。
- `/api/product-config` 只返回和保存经代产品配置；保存后只重算 `agg_jingdai`。
- 本地重建、Web 上传和参数设置接口都会清理 OTO/证保/蚁桥等非经代 `product_config` 历史行，避免转型旧配置继续留在参数设置数据中。

## 2026-06-24 生产环境关闭公开自助注册

### 决策

生产环境默认关闭 `/api/auth/register` 公开自助注册；如确需临时开放账号注册窗口，必须显式设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1`。非生产环境默认仍允许注册，便于本地测试和开发。

### 原因

- 系统承载经营数据，公开注册后普通用户默认可读取核心看板，生产环境不应把账号开通交给匿名用户。
- 管理员创建账号已经可覆盖常规开通场景，公开注册只适合受控内网或临时批量开通窗口。
- 显式环境变量比在代码中硬编码访问范围更便于不同部署环境治理。

### 影响

- 前端登录框会读取 `/api/auth/config`，生产关闭时隐藏“注册”按钮。
- 自动化测试通过 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 保持原有注册用例可执行。
- 生产部署如确需开放注册，必须在部署环境文件中临时配置并在完成后关闭。

## 2026-06-24 KPI 经营摘要展示口径

### 决策

在 KPI 概览下方新增“结论 / 关注 / 口径”摘要，但只使用已有 KPI 返回值、目标配置和 `asOf` 上下文，不新增独立推算口径。

### 原因

- 经营分析工作需要先形成可复核判断，再进入分模块拆解。
- 摘要若脱离既有指标公式，容易引入新的口径不一致风险。
- 当前轻量前端架构适合先做展示组织优化，后续再评估更复杂的规则引擎或诊断模型。

### 影响

- 摘要会展示整体期交、达成率、同比、时间进度、经代/转型贡献和目标来源。
- 趋势图仍按既定决策展示完整已有趋势，不受该摘要影响。

## 2026-06-19 趋势展示与精准同比口径解耦

### 决策

右上角 `asOf` 截至日期只作为 KPI 概览和机构维度精准同日同比的统计口径入口；业务平台趋势、队伍趋势等趋势图默认展示已有完整趋势数据，不再随 `asOf` 截断。

### 原因

- 趋势图用于浏览全年或跨月走势，需要尽量展示完整已有数据。
- KPI 概览和机构维度同比用于复核经营结果，需要未满月时按去年同月同日精确对比。
- 若趋势图也套用 `asOf`，会造成 2025 年曲线被截断或下落到 0，影响趋势判断。

### 影响

- 前端趋势数据请求不再向 `/api/platform-data` 和 `/api/platform-trend` 传递 `asOf`。
- `/api/kpi` 与 `/api/org-analysis` 继续传递 `asOf`，作为精准同比口径来源。
- 2026-06-19 的全局 `asOf` 决策中“主要业务模块统一截断”的描述已被本决策部分替代。

## 2026-06-19 看板全局截至日期口径

### 决策

经营分析主看板采用全局 `asOf` 截至日期控制主要业务模块的数据口径。前端以右上角“数据截止”下拉作为唯一交互入口，后端通过 `asOf=YYYY-MM-DD` 参数统一截断 KPI、平台趋势、产品结构、机构维度和交期结构。

### 原因

- 经代与转型业务存在导入日期和自然日期不一致的情况，未满月同比必须按同日口径比较。
- 右上角统一选择能避免 KPI、趋势、产品、机构等模块各自采用不同截止时间，降低经营复核误差。
- 现有日级聚合表已能支撑 KPI 和平台趋势按日截断，产品明细也可从原始明细按日期截断。

### 影响

- 导入数据最新日期与系统日期相差 2 天及以上时，页面提示“请注意数据口径”。
- 交期结构当前来源为月级聚合表，只能随 `asOf` 截至月份截断；若未来要求同月内按天精确截断，需要改为从原始明细或新增日级交期聚合表计算。

## 2026-06-13 容器镜像发布方式

- 决策：使用 GitHub Actions 构建镜像并推送到 GitHub Container Registry。
- 镜像名：`ghcr.io/lorrin328/business-analysis-template`。
- 原因：镜像二进制文件不适合直接提交到 Git 仓库；GHCR 支持 `latest`、分支、tag、sha 多维度版本管理，后续服务器可直接 `docker pull`。
- 约束：镜像不内置业务数据和真实密钥，SQLite 数据库、日志通过 volume 持久化。

## 2026-06-13 本地开发环境基线

### 决策

Windows 本地开发环境采用 Python 3.12、Git for Windows、uv 作为基础工具链；项目测试依赖继续保留在 `requirements.txt` 和 `backend/requirements.txt`，脚本显式安装或引用这两个 requirements 文件。

### 原因

- 项目声明 Python 3.10+，Python 3.12 可兼容当前测试集。
- `pyproject.toml` 当前未集中声明运行依赖，直接依赖 requirements 文件更贴合现状。
- `scripts/preflight.ps1` 是 Windows 上线前检查入口，必须能在新环境中自举测试依赖。

### 影响

- Windows 预检不再依赖预先手工安装 pytest/FastAPI/pandas 等包。
- Bash 测试脚本不再遗漏后端依赖。
