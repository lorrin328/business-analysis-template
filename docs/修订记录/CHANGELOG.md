# CHANGELOG

> 项目变更累积记录。时间倒序。每个 commit 应在此追加一条摘要。
>
> 格式：`## [YYYY-MM-DD] <commit-id-short> <type>: <主题>`
>
> 详细内容指向对应文档（`docs/需求/...`）。

---

## [2026-04-26] (待 commit) docs: 立项模块化重构总体方案

**类型**：docs / 立项

**变更内容**：
- 新建 `docs/` 目录结构（需求、数据规范、修订记录）
- 完成主需求文档：[模块化重构总体方案](../需求/2026-04-26_模块化重构总体方案.md)
- 完成数据规范：[保单数据规范](../数据规范/保单数据规范.md)、[人力数据规范](../数据规范/人力数据规范.md)
- 完成 5 个业务模块需求大纲：
  - [模块01 平台趋势](../需求/模块01_平台趋势.md)
  - [模块02 产品结构](../需求/模块02_产品结构.md)
  - [模块03 队伍规模](../需求/模块03_队伍规模.md)
  - [模块04 长险活动率](../需求/模块04_长险活动率.md)
  - [模块05 队伍产能](../需求/模块05_队伍产能.md)
- 建立文档索引 `docs/README.md`
- 建立文档生命周期与 GitHub 同步规则

**重要决策**：
1. 模块化采用 ES Module + 发布期 build.sh 合并策略
2. P2 阶段升级 sql.js → @sqlite.org/sqlite-wasm + OPFS
3. 引入维度表+事实表星型模型，支持多事实表共享维度
4. 建立 N1AI-人力基表 数据规范，作为队伍/活动率/产能模块基础
5. 强化 GitHub 同步与文档留痕规则

**待用户确认的开放问题**：详见各文档「开放问题」章节，主要包括：
- 长险活动率分母选择（月末/月均/月初）
- 队伍产能主定义选择（D1-D6 哪个）
- 主管/经理层级聚合方式
- 是否硬编码基准年

**关联**：
- 用户需求确认：选择 ESM、纳入 sqlite-wasm、人力数据来自月度 Excel、本轮先出文档
- 用户提供数据样本：`N1AI-人力基表_20260421_1637302.xlsx`（17 列、2114 行、4 个月）

**下一步**（待用户 review 后启动）：
- P0 紧急修复：清理三个失效筛选器
- P1：建立 `js/` 模块结构、迁移现有平台趋势 + 产品结构

---

## [2026-04-26] af73ed6 docs: add collaboration rules to README

**类型**：docs

**变更内容**：README 新增「协作规范」章节：每次更改必须同步 GitHub、必须做完整说明文档、保证换电脑能完全理解。

---

## [2026-04-26] 7c608c5 refactor: drop N2 old table support, AI table is the only format

**类型**：refactor

**变更内容**：
- 旧 N2 表字段（`是否在运营项目`、`分红产品`、`创新or传统`）从 `ALL_DIM_COLS` 移除
- `transformRow` 中这三列固定填 `'未知'`
- Schema 保留这三列以兼容已缓存的旧 IndexedDB 数据
- README 更新：旧表字段标记为「已停用」

⚠️ **遗留问题**：UI 上的对应筛选器和 boot-cols-hint 提示文字未同步删除，导致 UI 与数据不一致。已识别为 P0 任务，将在 2026-04-27 处理。

---

## [2026-04-26] 2e1f7b8 feat: extend schema to 32 columns, support AI 业绩基表

**类型**：feat

**变更内容**：
- Schema 从 19 列扩展至 32 列
- 新增 12 个 TEXT 列：staff_id / supervisor_id / manager_id / policy_no / self_mark / app_date / underwrite_date / entry_date / cancel_date / product_code / product_name / is_pension
- 新增 1 个 INTEGER 列：jzgb_cents（价值规保）
- `DIM_COLS_ZH` 拆分为 `CORE_DIM_COLS`（7 个必需）+ `EXT_DIM_COLS`（12 个扩展）
- `validateColumns` 仅检查核心必需列
- `transformRow` 新增 `trimEmpty()` 和 `fmtDateTime()` 辅助函数
- 业务规则：保费按 `入账时间` 统计；激励方案口径预留（按 `承保时间`）

---

## [2026-04-26] 6b75089 docs: comprehensive README with full business logic and revision history

**类型**：docs

完整 README 重写，包含数据模型、业务逻辑、修改历史、协作规范。

---

## [2026-04-25] 0e00917 debug: remove axisPointer and add per-chart error tracing

**类型**：fix / debug

修复 ECharts `p[0].coord` 崩溃，主图移除 axisPointer，各子图独立 try-catch。

---

## [2026-04-25] a0b1e09 fix: guard against ECharts edge cases with empty/undefined tooltip params

**类型**：fix

防御 tooltip formatter 中的空值访问。

---

## [2026-04-25] 80a19d8 fix: support alternative column names in Excel import

**类型**：fix

支持 `年月`、`年季`、`年月日` 等列名别名。

---

## [2026-04-25] 071a59f refactor: switch to in-browser Excel import via SheetJS

**类型**：refactor / 架构变更

从 Python 预处理 + 本地 HTTP 服务方案，改为纯浏览器 SheetJS + sql.js 方案。

---

## [2026-04-25] fd72bf3 chore: update .gitignore and add README

初始 .gitignore 与 README。

---

## [2026-04-25] 21335e5 refactor: replace inline RAW_DATA with sql.js + daily tooltip

引入 sql.js，移除内联 JSON 数据，新增日明细浮层。

---

## [2026-04-25] 713f46e feat: add build_db.py and python deps for sqlite pipeline

初版 Python 预处理方案（已废弃，见 071a59f）。

---

## [2026-04-25] 9d41639 经营分析模板：保费趋势对比看板

初代版本，内联 JSON 数据。
