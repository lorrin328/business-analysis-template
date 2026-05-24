# 经营分析看板 - 需求与开发文档

## v1.0.40 更新说明（2026-05-24）
**类型**：fix / data-quality

**变更内容**：
- 修复人力原始表增量导入时，`统计日期` 为 `YYYY-MM-DD` 等日期格式时旧月份未被删除的问题，避免重复上传导致人力数据倍增。
- SQLite 原始表重建聚合时自动去重，防止历史重复明细继续放大 `agg_hr_data` 等聚合结果。
- 补充回归测试覆盖日期型月份列删除和原始表去重重建。
- 统一版本号到 v1.0.40

## v1.0.39 更新说明（2026-05-24）
**类型**：fix / metric-quality

**变更内容**：
- 修复 KPI 概览“人均保费”偏低的问题：分母由“多个月月均在职人力直接相加”修正为“各渠道月均在职人力平均后汇总”。
- 修复人均保费弹窗年度累计、季度累计同类分母错误，确保累计保费除以对应期间月均在职人力。
- 同步检查人均产能：当前趋势图为月度口径，使用当月保费除以当月活动人力，不存在本次累计分母放大问题。
- 新增前端静态回归测试，防止人均类指标再次误用累计人力作为分母。
- 统一版本号到 v1.0.39

## v1.0.38 更新说明（2026-05-24）
**类型**：architecture / data-quality / deploy

**变更内容**：
- 新增从 SQLite 原始明细表重建所有聚合表的能力，生产环境没有 Excel 文件时也可以在口径修复后重算聚合数据。
- 新增共享日级截止日策略模块，KPI 继续按转型、经代各自真实截止日计算，并显式保留共同截止日供同日对比场景使用。
- Excel 上传导入默认改为严格模式：部分文件解析失败时不再写入成功部分，避免形成半新半旧数据；确需部分导入时需显式设置 `allow_partial=true`。
- 部署脚本在无 Excel 时自动尝试从 SQLite 原始表重建聚合；Webhook 缺少密钥时拒绝启动，避免无签名自动部署入口。
- 管理员 Token 前端缓存从 `localStorage` 改为 `sessionStorage`，并补充清理方法，降低共享浏览器残留风险。
- 文档移除默认明文 Token 示例，统一要求生产环境显式配置 `ADMIN_TOKEN`。
- 统一版本号到 v1.0.38

## v1.0.37 更新说明（2026-05-23）
**类型**：fix / data-quality

**变更内容**：
- 修复 KPI 概览与机构维度期交保费达成率不一致的问题。
- KPI 概览中转型业务按转型日表最新截止日计算，经代业务按经代日表最新截止日计算，不再用经代较早截止日截断转型业务。
- 长险期交同步按业务线各自截止日计算，确保转型期交与转型长险、经代期交与经代长险分别同源同日。
- 验证当前数据下转型期交达成率为 `41.6%`，转型长险期交达成率为 `41.5%`，与机构维度口径一致。
- 统一版本号到 v1.0.37

## v1.0.36 更新说明（2026-05-23）
**类型**：fix / data-quality

**变更内容**：
- 修复 KPI 概览中长险期交达成率可能高于期交保费达成率的问题。
- `agg_longterm_qj` 从月级聚合升级为日级聚合，转型业务和经代业务均保留 `day` 维度。
- KPI 计算中长险期交与期交保费共用同一日级截止日，避免转型 5 月 23 日数据被长险提前纳入、而总期交按共同截止日只算到 5 月 22 日。
- 用当前 Excel 重建本地 SQLite 后验证：2026 年总期交 `47434.28` 万，长险期交 `47414.42` 万，长险期交低于总期交。
- 新增回归测试覆盖转型/经代长险日级聚合，以及 KPI 长险期交共同截止日过滤。
- 统一版本号到 v1.0.36

## v1.0.35 更新说明（2026-05-23）
**类型**：fix / data-quality

**变更内容**：
- 修复业务平台趋势月度/季度日累计展示口径：当前月只展示到当前日期，历史同期和上月对比展示完整自然月。
- 无新增保费日期不再截断趋势线，累计值延续上一日，避免 OTO、证保、蚁桥曲线提前停止。
- 当前季度趋势不提前展示未来月份，已完成月份按完整自然月展示，当前月份展示到当前日。
- 用当前项目目录 Excel 重建本地 `backend/business_data.db`，验证 OTO、证保、蚁桥 2026 年 5 月均已聚合到 5 月 23 日。
- 新增/调整趋势线回归测试，覆盖当前月、历史月、上月、闰年 2 月和当前季度展示边界。
- 统一版本号到 v1.0.35

## v1.0.34 更新说明（2026-05-23）
**类型**：fix / data-quality

**变更内容**：
- 转型业务保留实时到拉取当天的数据，经代业务保留截至拉取日前一日的数据，不再要求两类 Excel 截止日完全一致。
- 经代与转型混合统计时，年度/季度/月度趋势自动按共同截止日截断，避免整体口径多算转型多出来的一天。
- 产品结构在经代+转型混合展示时同步使用共同截止日，单独查看经代或转型时仍展示各自真实源数据。
- 上传导入遇到截止日差异时改为返回提示信息，不再阻断导入。
- 测试环境兼容：FastAPI 集成测试在轻量依赖环境下跳过，在完整依赖环境下继续执行。
- 新增回归测试覆盖混合截止日趋势、产品结构截断、导入提示和轻量/完整测试环境。
- 统一版本号到 v1.0.34

## v1.0.33 更新说明（2026-05-23）
**类型**：fix / data-quality / documentation

**变更内容**：
- KPI 期交保费按转型与经代共同最早截止日计算，避免不同截止日数据混算。
- 平台月度/季度日累计趋势按共同截止日截断，确保展示口径与 KPI 一致。
- 上传导入时校验转型与经代日级截止日，不一致时拒绝写入并提示重新使用同一截止日文件。
- 顶部数据截止标签在有日级口径时展示到具体日期。
- 指标口径文档明确长险期交达成率沿用期交保费目标，`target_config` 为当前目标权威主源。
- 新增最终审计与指标口径确认报告，沉淀当前底座口径与剩余维护风险。
- 新增测试覆盖共同截止日计算、趋势截断和导入拒绝场景。
- 统一版本号到 v1.0.33

## v1.0.32 更新说明（2026-05-23）
**类型**：fix / security / maintainability

**变更内容**：
- 修复上传链路产品配置函数调用错误，避免转型业绩上传时报 `_extract_products_to_config` 未定义。
- 统一长短险、短险、产品代码 4281 等业务判断规则，交期结构、长险期交、活动人力共用同一套口径。
- 修复商保年金弹窗展示，经代、转型及 OTO/证保/蚁桥子模式均按目标展示达成和达成率。
- 生产页面不再静默回退本地 Mock 数据，API 无数据时明确显示空态或失败提示。
- 移除前端、Docker Compose、部署脚本、启动脚本中的默认明文 Token，生产环境必须显式配置 `ADMIN_TOKEN`。
- `product_config` 唯一键升级为 `(business_type, product_code)`，支持经代和转型同码产品分别配置。
- 新增/调整测试覆盖长短险口径、产品配置业务类型维度、商保年金展示、Token 硬编码和 Mock 兜底行为。
- 统一版本号到 v1.0.32

## v1.0.31 更新说明（2026-05-22）
**类型**：fix

**变更内容**：
- 修复长险期交转型业务数据错误：去掉 aggregate_transform_longterm 中的 ORG_SCOPE 过滤
- 放宽长短险匹配条件：支持常见变体（长险、长期险）
- 修复缴费年限解析：处理文本格式（如 '终身'、'5年'）
- 修复 term_col 为 None 时的灾难性过滤（只保留产品 4281）
- 修复 aggregate_jingdai_longterm 的 pay_col 容错
- 新增 GET /api/diagnostics 诊断端点
- 统一版本号到 v1.0.31

## v0.9.997 更新说明（2026-05-22）
**类型**：fix / safety / deployment

**变更内容**：
- **统一后台管理 Token**：前端、Docker Compose 和部署脚本统一改为显式配置管理 Token，不再提供默认明文值。
- **修复参数设置产品提取口径**：`GET /api/product-config` 从原始 `performance` 表自动提取产品时，兼容 `202605`、`2026-05`、`2026/05/01` 等年月格式。
- **强化产品配置保存逻辑**：`POST /api/product-config` 改为 upsert，未知产品代码也可写入配置，并返回真实更新数量。
- **修复保障类 KPI 展示**：后端 `/api/kpi` 返回 `protection_total`，前端保障类产品卡片按参数设置与目标值展示，不再停留在“口径待完善”。
- **修复参数设置弹窗展示安全**：产品代码、产品名称、业务模式进入表格前进行 HTML 转义，避免特殊字符破坏页面或形成注入风险。
- 主页面版本号更新为 `v0.9.997`。
---

## v0.9.995 更新说明（2026-05-22）
**类型**：fix

**变更内容**：
- **修复产品配置保存响应解析**：`saveProductConfig()` 改用 `apiUrl('/api/product-config')` 拼接完整 URL，增加 `resp.ok` 检查，并先 `await resp.json()` 再传给 `unwrapApiResponse`。之前直接把 `Response` 对象传给 `unwrapApiResponse`，导致保存失败后仍提示"已保存"，且无法读取 `recalculated` 字段。
- 主页面版本号更新为 `v0.9.995`。
---

## v0.9.994 更新说明（2026-05-22）
**类型**：fix

**变更内容**：
- **保存参数后自动重算机构业绩**：`POST /api/product-config` 保存产品分类配置后，自动从 `performance` 原始表重新计算 `agg_org_performance`，使商保年金 / 保障类产品指标立即生效，无需重新导入 Excel。
- **前端保存后自动刷新看板**：`saveProductConfig()` 保存成功后若后端返回 `recalculated > 0`，自动调用 `recalculateDashboard()` 刷新看板数据，并提示用户已重新计算。
- 主页面版本号更新为 `v0.9.994`。
---

## v0.9.993 更新说明（2026-05-22）
**类型**：feat / fix

**变更内容**：
- **参数设置免 Excel 导入**：点击「参数设置」不再要求先导入 Excel。当 `product_config` 表为空时，`GET /api/product-config` 自动从 `performance` 原始表提取年份 ≥ 2026 的产品列表（产品代码、产品名称、业务模式），默认标识为 N，用户可直接在弹窗中设置商保年金/保障类产品标识。
- **前端移除强制导入提示**：`openProductConfigModal()` 移除 "暂无产品数据，请先导入 Excel 文件" 的 alert 阻断，空表时正常渲染表头供用户查看。
- 主页面版本号更新为 `v0.9.993`。
---

## v0.9.992 更新说明（2026-05-22）
**类型**：feat / fix

**变更内容**：
- **产品分类参数设置**：主页面右上角新增「参数设置」按钮，弹窗展示所有产品代码（去重），可手动设置商保年金/保障类产品标识（Y/N）。
- **产品分类可配置化**：新建 `product_config` 表存储产品分类配置；`aggregate_org_performance` 不再读取 Excel "是否商保年金产品" 列，改为查询 `product_config` 表判断分类；保障类产品不再硬编码为 0。
- **自动提取产品列表**：导入 Excel 时自动提取年份 ≥ 2026 的产品列表到 `product_config` 表（INSERT OR IGNORE），默认全 N。
- **去年同期定义明确化**：`docs/指标口径说明.md` 新增「去年同期定义」专节；`config/metrics.py` 补充同比指标的数据精度说明；`kpi.py` 期交保费 YTD 优先使用日累计表按统计日截取去年同期。
- **指标定义统一返回**：所有 API 端点 `meta.definitions` 统一注入相关指标口径定义。
- 主页面版本号更新为 `v0.9.992`。
---

## v0.9.991 更新说明（2026-05-21）
**类型**：stability / security / maintainability

**变更内容**：
- **原始明细写入安全**：已存在的业务原始表无法识别年月或出现字段漂移时，不再静默整表替换，改为中止导入并保留历史数据。
- **上传完整性状态**：上传接口新增 `status` 与 `data_integrity`，部分成功时前端明确提示“数据口径不完整”。
- **产品结构年月口径**：产品结构原始表查询兼容 `202605`、`2026-05`、`2026/05/01` 等文本格式。
- **前端注入点修复**：动态机构勾选项改为 DOM API 创建，不再把接口/Excel 值拼接进 `innerHTML` 和内联事件。
- **运行入口边界**：README 与 `js/README.md` 明确当前生产页只加载 `经营分析模板.html` 与 `js/api-client.js`。
- **代码防线补强**：通用 repository 写入时对动态列名进行安全引用，降低未来扩展风险。
- 主页面版本号更新为 `v0.9.991`。
---


## v0.9.99 更新说明（2026-05-21）

**类型**：hotfix / revert

**变更内容**：
- **恢复单文件架构**：`经营分析模板.html` 恢复为 v0.9.96 的单文件版本（21,462 行）。
  v0.9.97 引入的 15 模块拆分因 PowerShell 文本提取导致系统性 bug（3 个文件 SyntaxError、30+ 函数缺失 window 导出、`<script>` 标签残留、`\\`n` 字面量编码损坏）。
- **保留全部后端改进**：`/api/config/business-lines`、Docker HEALTHCHECK、`PRAGMA foreign_keys=ON`、metrics 冗余清理、配置外部化、91 个测试。
- `js/` 目录中的模块文件保留作为未来正确模块化的参考。
- 主页面版本号更新为 `v0.9.99`。

---

## v0.9.98 更新说明（2026-05-20）

**类型**：hotfix

**变更内容**：
- **紧急修复**：重写 `js/upload.js`，消除 `_uploading` 重复声明导致的 SyntaxError。
- **修复括号截断**：`mock-data.js`、`org-analysis.js`、`team-analysis.js` 括号不闭合问题。
- **恢复 getModalContent**：将截断丢失的 `getModalContent` 函数（530 行）从 v0.9.96 恢复至 `js/target-modal.js`。
- **修复 HTML 加载顺序**：移除重复的 `api-client.js` 引用，确保依赖顺序正确。
- **新增静态测试**：JS 括号平衡、无重复声明、HTML 引用完整性、upload.js 导出验证。
- 主页面版本号更新为 `v0.9.98`。

---

## v0.9.97 更新说明（2026-05-20）

**类型**：refactor

**变更内容**：
- **前端模块化**：`经营分析模板.html` 从 21,000+ 行缩减至 ~1,200 行（减重 91%），业务逻辑拆分为 15 个独立 JS 模块（js/constants.js、format-utils.js、cache-manager.js、state-manager.js、config.js、mock-data.js、target-modal.js、kpi-cards.js、platform-trend.js、org-analysis.js、product-analysis.js、payperiod-chart.js、team-analysis.js、upload.js）。
- **业务线配置统一**：新增 `GET /api/config/business-lines` 端点，前端 `js/config.js` 启动时动态加载，消除前后端双套业务线硬编码。
- **数据库加固**：`db/connection.py` 补充 `PRAGMA foreign_keys=ON`。
- **Docker 加固**：Dockerfile 和 docker-compose.yml 添加 healthcheck。
- **KPI 规范化**：删除 `metrics/` 下 4 个冗余空壳文件（achievement.py、activity.py、productivity.py、yoy.py），统一由 `formulas.py` 提供。
- **测试扩展**：新增 33 个测试用例（test_kpi_formulas.py、test_org_filter.py、test_config_api.py），总测试从 54 增至 87。
- **状态管理**：新增 `js/state-manager.js` 统一管理所有页面状态。
- **缓存管理**：新增 `js/cache-manager.js` 统一缓存入口。
- 主页面版本号更新为 `v0.9.97`。

---

## v0.9.96 更新说明（2026-05-20）

**类型**：fix / refactor

**变更内容**：
- 修复 `payment.py` 中 `jingdaiOrgs` 过滤条件 SQL 运算符优先级问题（OR 缺少括号）。
- `etl/aggregates/` 中重复常量（`CHANNEL_MAP`、`TRANSFORM_CHANNELS`、`ORG_SCOPE`）收敛到 `backend/config/`。
- `db/repository.py` 动态表名增加白名单校验，防御性加固。
- 默认年份、端口、文件上传大小限制改为读环境变量（`DEFAULT_YEAR`/`PORT`/`MAX_UPLOAD_SIZE_MB`）。
- `product.py` 原始表查询增加 try/except 和 warning 日志。
- 移除冗余依赖 `sqlalchemy`。
- `auth.py` 非生产环境无 token 时打印 warning 日志。
- 主页面版本号更新为 `v0.9.96`。

---

## v0.9.95 更新说明（2026-05-20）

**类型**：fix / refactor / docs / safety

**变更内容**：
- 修复重复 Excel 文件“显示跳过但实际写库”的导入幂等问题。
- 原始明细表写入改为优先按年月增量覆盖，避免局部上传覆盖全年明细。
- KPI 截止月份纳入业绩、人力、经代、价值数据源，并返回 `data_cutoff`。
- Docker 生产部署要求显式配置 `ADMIN_TOKEN`，数据库挂载统一到 `backend/business_data.db`。
- 生产页面读取链路迁移到统一响应接口，旧接口集中到 `backend/api/legacy.py` 并加弃用响应头。
- 前端 API 客户端拆分为 `js/api-client.js`，减少 `经营分析模板.html` 内联基础设施代码。
- 新增导入安全、API 契约和前端静态约束测试。
- 主页面版本号更新为 `v0.9.95`。

---

## v0.9.94 更新说明（2026-05-16）

**类型**：chore / docs / safety

**变更内容**：
- 删除独立 `目标设置.html`，目标设置统一在 `经营分析模板.html` 内维护。
- 删除旧 `经营分析看板重构-demo.html`、未引用 `data.json`、重复恢复脚本、旧 Docker Compose 文件和过期配置文件。
- 部署文档收敛为 Nginx + systemd + FastAPI，端口固定 `45679`。
- 主页面版本号更新为 `v0.9.94`。
- `.gitignore` 增强 Excel、SQLite、uv 缓存等敏感/运行产物保护。
- README 与 docs 变更记录同步更新项目文件边界。

---

## 项目概述

**太平人寿网电多元条线** 经营分析网页应用，覆盖 OTO、证保、蚁桥、线上经代等业务线。当前重点推进职域营销（团险合作，试点阶段），原电销业务已全面关停。

基于原生JS + sql.js + ECharts + XLSX + IndexedDB，单文件HTML交付。

---

## 已完成功能（2026-04-27）

### 页面架构
- [x] 顶部导航栏：四个版块入口 + 上传目标按钮
- [x] 主页门户：四个卡片（关键KPI/趋势表现/产品结构/队伍表现）
- [x] 全屏模态弹窗：点击按钮弹出对应版块
- [x] 弹窗关闭后内容自动归位

### 关键KPI版块
- [x] 表格展示：目标、达成、达成率、规模同比
- [x] 时间维度切换：年度 / 季度 / 月度
- [x] 指标口径切换：折算保费 / 期交保费 / 规模保费
- [x] 机构筛选
- [x] 达成率颜色标识（≥100%绿色，<100%红色）

### 趋势表现版块
- [x] 复用原有功能：折线图、同比图、KPI卡片、产品结构饼图
- [x] 移入弹窗展示
- [x] 保留全部交互（筛选、维度切换、日明细hover）

### 产品结构版块
- [x] 独立饼图弹窗
- [x] 保费口径切换

### 队伍表现版块
- [x] 表格展示七项指标：
  - 月末在职人力
  - 月均在职人力
  - 长险活动人力
  - 长险活动率
  - 人均保费
  - 人均产能
  - 标准人力（OTO≥2万 / 证保≥3万）
- [x] 时间维度：月度 / 季度
- [x] 机构、业务模式筛选

### 目标数据上传
- [x] 目标Excel上传解析
- [x] 自动匹配列名（年/季/月/机构/项目/指标目标值）
- [x] 支持多指标列（折算保费/期交保费/规模保费目标）
- [x] 存入 fact_target 表，与保费数据共享SQLite数据库
- [x] 覆盖同年度已有目标数据
- [x] 数据持久化到IndexedDB

---

## 已知问题与限制

### 数据限制
1. **队伍表现人力数据**：基于 `fact_premium` 出单记录近似推算在职人力，无完整人力档案（入离职日期）。
   - 月末在职人力 = 该期间有出单的去重工号数
   - 月均在职人力 = (上期期末 + 本期期末) / 2
   - 在网电多元渠道下相对合理（不出单≈无收入）

2. **目标数据格式**：目前需手动准备目标Excel，格式为：年/季/月/机构/项目/指标目标值列。

### 技术限制
3. **ESM模块与内联版本不一致**：ESM模块（js/目录）目前为占位实现，完整功能在内联IIFE中。build.sh生成的dist版本包含内联功能。
4. **趋势弹窗图表重渲染**：趋势弹窗关闭后再打开时，图表实例需要重新初始化。

---

## 待完成/优化项

### 高优先级
- [ ] **周维度支持**：目标数据已预留week字段，KPI查询和队伍查询需添加周维度
- [ ] **目标数据模板下载**：提供目标Excel模板下载功能
- [ ] **KPI导出**：关键KPI和队伍表现表格支持导出Excel
- [ ] **目标数据管理**：查看/删除已上传的目标数据

### 中优先级
- [ ] **ESM模块完整实现**：将内联IIFE中的新功能抽离到ESM模块，保持两套代码一致
- [ ] **KPI同比计算完善**：季度同比、月度同比需验证边界情况（如跨年度数据缺失）
- [ ] **队伍表现-月均在职人力优化**：当前使用简单平均，可考虑更精确的计算方式
- [ ] **标准人力阈值可配置**：OTO≥2万、证保≥3万应支持动态配置

### 低优先级
- [ ] **弹窗状态持久化**：刷新页面后记住上次打开的弹窗
- [ ] **主页概览数据**：主页portal卡片显示各版块核心数据摘要
- [ ] **响应式优化**：移动端弹窗显示优化
- [ ] **动画过渡**：弹窗打开/关闭添加过渡动画
- [ ] **数据时间范围选择**：队伍表现支持自定义时间范围

---

## 技术架构

### 文件结构
```
business-analysis-template/
├── 经营分析模板.html          # 开发版（内联IIFE，含全部新功能）
├── dist/经营分析模板.html       # 发布版（build.sh生成）
├── build.sh                    # 构建脚本
├── js/
│   ├── main.js                 # ESM入口（注册新模块）
│   ├── core/                   # 核心模块（state/db/idb等）
│   └── modules/                # 功能模块
│       ├── importer/           # 保费数据导入
│       ├── platform-trend/     # 趋势表现
│       ├── product-structure/  # 产品结构
│       ├── modal/              # 弹窗管理（占位）
│       ├── target-importer/    # 目标导入（占位）
│       ├── kpi/                # 关键KPI（占位）
│       └── team-performance/   # 队伍表现（占位）
```

### 数据表
- `fact_premium`：保费明细（原有）
- `fact_target`：目标数据（新增）
  - year, quarter, month, week, org, project, metric, target_value

### 交付物
- 直接使用：`dist/经营分析模板.html` 或根目录 `经营分析模板.html`
- 浏览器打开即可，无需服务器

---

## 使用说明

### 首次使用
1. 打开 `经营分析模板.html`
2. 在欢迎页拖拽或点击上传保费数据Excel
3. 点击导航栏 📋 上传目标，上传目标数据Excel
4. 点击各版块按钮查看分析

### 目标Excel格式
目标文件需包含以下列（列名支持模糊匹配）：
- **年**（必需）
- **季**、**月**（按时间维度填写）
- **机构**、**项目**（可选，按维度填写）
- **折算保费目标**、**期交保费目标**、**规模保费目标**（至少一个）

### 保费数据Excel格式
见页面底部提示，需包含：
- 时间列：日期、年、月、季
- 维度列：销售机构名称、业务模式、长短险、是否商保年金产品、缴费年限、保障年限、产品设计分类
- 指标列：期交保费、年化规保、折算保费

---

## 修改历史

### 2026-05-08 feat: KPI卡片修复 + 机构维度表格

**KPI概览修复**：
- **价值达成率子模块**: 大号数字下方标签从"实际"改为"经代"，展示经代达成率；无达成率时显示"-"
- **活动率弹窗**: 移除硬编码的"经代"行，经代渠道不参与活动率统计

**机构维度表格（新增）**：
- **数据聚合**: 后端新增 `agg_org_performance` 和 `agg_org_value` 表，按机构+业务模式聚合
- **产品分类**: 从原始数据自动识别 10年期产品、商保年金、保障类产品三类
- **API端点**: 新增 `/api/org-kpi/{year}` 返回机构维度KPI数据
- **前端表格**: 新增"机构维度"版块，含以下功能：
  - 机构复选过滤（10家机构：上海、湖北、四川、辽宁、山东、广东、福建、浙江、河南、北京）
  - 时间维度切换（年度/季度/月度）
  - 表格列：机构-业务模式-期交保费(目标/达成/达成率/同比)-价值保费(目标/达成/达成率/同比)-10年期(目标/达成/达成率)-商保年金(目标/达成/达成率)-保障类(目标/达成/达成率)
  - 机构小计行（多业务模式时自动汇总）
  - 总计行（底部合计，无目标行不计入达成率计算）
- **移动端适配**: 机构过滤器折叠优化，表格支持横向滚动

**技术细节**：
- `aggregate_org_performance` 解析原始Excel中的 `销售机构名称` 和 `业务模式` 字段
- `aggregate_org_value` 同理聚合价值数据
- 机构目标暂由总目标分摊（后续可扩展为独立配置）

---

### 2026-05-07 feat: 目标同步修复 + 平台趋势增强 + 生产环境优化

**背景**：50+人即将使用，部署到Ubuntu服务器。修复多设备目标不同步bug，优化平台趋势展示，提升生产环境安全性。

**目标数据同步修复**：
- `openModal` 改为 `async`，打开 'overall'/'value' 弹窗时先 `await fetchTargetData()` 从服务器获取最新目标
- 文件上传成功后增加 `fetchTargetData()`，确保目标数据同步
- 彻底修复手机访问时目标与电脑设置不一致的bug（原因为 `loadTargetData()` 仅从 localStorage 读取）

**平台趋势模块增强**：
- **convertApiToPlatformMock**: quarter/month 数据改为生成日累计序列（使用 `generateDailyCumulative`）
  - Quarter：基于季度总额和天数生成约90天的日累计数据
  - Month：基于月度总额和当月天数生成28-31天的日累计数据
- **年度视图**: 增加双Y轴 + 单月柱状图
  - 左Y轴：累计保费折线（当年实线 + 上年虚线）
  - 右Y轴：单月保费柱状图（当年蓝色半透明 + 上年灰色半透明）
- **月度视图修复**: 移除 `apiMonthMode` 硬编码判断，日期标签根据实际数据长度动态生成
- **季度/月度视图**: 现在正确展示日累计保费趋势图，含上一年同期对比

**目标设置页面重构 (`目标设置.html`)**：
- 完全重写，使用与主页面**相同的数据结构**（`metrics[metric] = { year, quarter: [4], month: [12] }`）
- 通过 `/api/targets/{year}` GET/PUT 与后端API交互
- 支持年度/季度/月度目标编辑，数据保存到服务器后所有人可见
- 移除仅 localStorage 的存储方式

**生产环境安全**：
- **CORS**: `backend/main.py` 默认关闭跨域，仅当设置 `CORS_ORIGINS` 环境变量时启用（生产环境HTML从同一服务提供，无需跨域）
- **deploy.sh**: 使用 `rsync` 排除开发文件（venv, __pycache__, .git, docs, js, build.sh等），增加数据库自动备份

**技术细节**：
- `generateDailyCumulative` 种子算法确保同一渠道同一时期生成的日累计分布稳定
- `normalizeData` / `normalizeTargetData` 函数确保新旧数据格式兼容
- 语法检查通过：HTML JS braces/parens/brackets 全部平衡
- Python 文件通过 `py_compile` 语法检查

**已知限制**（未在本次修复）：
- ESM 模块（js/目录）仍为占位实现，与内联IIFE不同步——建议后续清理
- SQLite 并发写入（50+人同时上传）可能出现锁库——建议错峰上传或迁移PostgreSQL
- 尚无权限控制——任何人可修改目标和上传数据
# 2026-05-09

## 应用级重构与修复

- 建立后端指标中心、业务线配置、字段转换、校验器、统一 API 和目标行表。
- 修复平台趋势月份类型、经代日累计去重、经代机构筛选提示、无日数据不生成伪曲线。
- 新增 `frontend/` 模块化迁移骨架，保留当前生产 HTML 和深色 ECharts 风格。
- 新增 Ubuntu 部署文件、日志体系、基础测试和架构/API/部署/指标文档。

---

# 2026-05-09 fix: 平台趋势 & 队伍分析 bug 修复

## 修复 Bug 1: 经代平台趋势 季度/月度无趋势线

- `buildDailyTrendOption`：当年日累计为空时不再立即返回空图表，改为同时计算当年和上年数据，仅当两者皆空时才空状态
- 当年数据为空但上年数据存在时，以上年数据为主展示

## 修复 Bug 2: 队伍分析默认不显示去年同期趋势线

- `loadYearFromApi`：加载上年数据后增加 `convertApiToTeamMock` 调用，将上年队伍数据写入 `teamMock`
- 修复前：初始化时 `teamMock[prevYear]` 为空，切上年再切回后才有数据残留
- 修复后：初始化即加载上年队伍数据，`getTeamOption` 可正确显示上年趋势线

## 图表状态管理

- 所有图表切换函数（平台趋势/队伍分析共 11 处）在 `setOption` 前调用 `chart.clear()` 清除旧 series
- 防止年份/维度切换后旧趋势线残留

## 测试补充

- `normalize_month` 扩展至覆盖 `20260401`, `2026-04-01`, `2026/04/01`, `4`, `"04"` 等格式
- 新增经代日累计链路测试（6 项）：日聚合、periodValue 驱动 daily、去重判断
- 新增平台趋势测试（2 项）：经代月度/季度日累计
- 新增队伍分析测试（1 项）：上年数据可正常加载
- 全部 23 个测试通过

---

# 2026-05-10 fix: 经代平台趋势深度修复（Phase 2 — 数据链路全闭环）

## 核心结论

沿"数据导入 → 聚合表 → API → 前端渲染 → 测试"链路排查，补齐 5 处缺口：经代日聚合缺少 ymd 字段、日期列候选不足、季度趋势 API 无 daily 输出、前端无调试日志、缺少季度日累计/ymd/日期候选相关测试。

## 后端修复

### database.py
- `agg_jingdai_daily` 表新增 `ymd TEXT` 列（`CREATE TABLE` + `ALTER TABLE` 兼容旧库）
- `get_platform_data` SELECT jingdai_daily 增加 `year` 和 `ymd` 字段返回

### aggregator.py
- `aggregate_jingdai_daily` 时间列候选扩展：`['时间', '年月日', '入账时间', '日期', '承保日期', '出单日期', '生效日期']`
- 输出行新增 `'ymd': f"{y:04d}-{m:02d}-{d:02d}"` 字段

### data_transform.py
- `FIELD_MAPPINGS["jingdai"]["day"]` 增加 `生效日期`, `出单日期`, `承保日期` 别名

### query_service.py
- 新增 `build_quarter_daily_cumulative()` 函数：按季度（3个月）跨月生成日累计序列
- `get_platform_trend` 季度模式新增 `daily` 输出（`periodType=quarter` + `periodValue` 时）

## 前端修复（经营分析模板.html）

### 调试日志
- `getMonthDailyCumulative`: 入口记录 year/month/premiumType/selectedKeys 及各数据源长度、jdDaily 样本；出口记录 resultLen
- `buildDailyTrendOption`: 记录 current/prev values 长度和样本
- `loadYearFromApi`: 记录上一年 platformMock/teamMock 加载状态

## 测试补充（11 项新增，全部 34 项通过）

- `test_build_quarter_daily_cumulative_q2_jingdai` — 经代 Q2 跨月日累计
- `test_build_quarter_daily_cumulative_q3_oto` — OTO Q3 日累计
- `test_build_quarter_daily_cumulative_mixed_jingdai_and_transform` — 经代+转型混合
- `test_build_quarter_daily_cumulative_empty_returns_message` — 空数据提示
- `test_get_platform_trend_quarter_returns_daily` — 季度 API 返回 daily
- `test_get_platform_trend_quarter_no_period_value_omits_daily` — 无 periodValue 不返回 daily
- `test_aggregate_jingdai_daily_date_candidates` — 承保日期/出单日期/生效日期 候选识别
- `test_aggregate_jingdai_daily_outputs_ymd` — ymd 字段输出验证
- `test_get_platform_data_includes_year_and_ymd_in_jingdai_daily` — API 返回 year+ymd
- `test_prev_year_team_mock_loaded` — 上年队伍数据可加载
- `test_field_mappings_jingdai_day_aliases` — jingdai day 别名覆盖

---

## 2026-05-10 — 修复 getMonthDailyCumulative org-path 缺失 platformMock 兜底 (commit 439258a)

### 问题

经代业务线在季度/月度维度下趋势线可能不显示，尤其当机构筛选条件生效时。

### 根因

`getMonthDailyCumulative` 的 org 分支（`useOrgDaily=true`）在 apiCache 无日数据时直接返回 `[]`，缺少非 org 分支已有的 platformMock 兜底逻辑。

### 数据流

经代日累计数据路径：
```
Excel 上传 → jingdai_daily 行 → SQLite agg_jingdai_daily →
GET /api/data/{year} → apiCache[year].platform.jingdai_daily →
getMonthDailyCumulative 的 jdDaily 分支
```

备用路径（apiCache 为空时）：
```
platformMock（嵌入式 JSON）→ month[m][type]['经代'] →
getJingdaiMonthFallback
```

### 修复内容

在 org 分支添加与非 org 分支相同的两级兜底：
1. `platformMock.month` — 从嵌入式 mock 数据读取日累计
2. `getJingdaiMonthFallback` — 经代专属兜底

### 注意事项

- `agg_daily_performance` 不包含经代数据（经代使用独立的 `agg_jingdai_daily`）
- `dist/` 为构建产物（gitignored），已同步更新
- 构建脚本 `build.sh` 当前不可用（模板缺少 `<!-- BUILD:JS:CORE -->` 标记）
