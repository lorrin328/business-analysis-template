# CHANGELOG

> 项目变更累积记录。时间倒序。每个 commit 应在此追加一条摘要。
>
> 格式：`## [YYYY-MM-DD] <commit-id-short> <type>: <主题>`
>
> 详细内容指向对应文档（`docs/需求/...`）。

---

## [2026-04-26] (待 commit) chore: P1.1 建立 js/ 模块源码骨架 + 提取 format.js

**类型**：chore / 模块化重构 P1.1

**变更**：

新建 `js/` 目录骨架（ESM 源码），后续业务模块将逐步从 `经营分析模板.html` 迁出：

```
js/
├── README.md                 # 总体架构说明
├── lib/                      # 第三方库（暂留 CDN，P2 阶段本地化）
│   └── README.md
├── core/                     # 解耦的核心工具
│   ├── README.md
│   └── format.js             # ✅ 首个提取模块（formatNum / formatShort）
└── modules/
    ├── platform-trend/
    │   └── README.md         # 模块01 待迁移
    └── product-structure/
        └── README.md         # 模块02 待迁移
```

**关键约定**（写入 `js/README.md`）：
- 零循环依赖：`core/` 不依赖 `modules/`；模块互相不 import
- 纯 ESM：`export` / `import`，不混 UMD/IIFE
- 金额单位：「分」流转，仅展示层 `/ 100`
- 命名：文件 kebab-case；函数 camelCase；常量 SCREAMING_SNAKE_CASE

**format.js 提取说明**：
- 与原 `经营分析模板.html` 行 793-805 行为完全一致
- 零依赖（不引用 DOM、ECharts、SQL）作为首个提取的模块
- HTML 暂未引用，下个 commit（P1.2）通过 build.sh 接入

**未变更**：
- `经营分析模板.html` 本次未修改（仅新增源码骨架）
- 第三方库仍走 CDN（`echarts.min.js` / `xlsx.full.min.js` / `sql-wasm.js`）

**关联**：
- 主方案 §3 ESM + 发布期 build.sh 合并策略
- 下一步：P1.2 编写 build.sh 与 ESM bootstrap，将 `format.js` 接入 HTML

---

## [2026-04-26] ce97764 fix: P0 清理 UI 与数据模型不一致——移除 3 个失效筛选器

**类型**：fix / P0 紧急修复

**问题**：UI 仍显示「是否在运营项目」「分红产品」「创新/传统」三个筛选器，但数据模型已停用对应字段（固定填 `'未知'`）。导致用户筛选后结果为空或与预期不符。

**变更**：
- `经营分析模板.html` 删除 3 个 `<select>` 控件（`selOperating` / `selDividend` / `selInnovate`）
- `boot-cols-hint` 提示文案移除 `是否在运营项目` / `分红产品` / `创新or传统` 三个列名
- `FILTER_KEYS` 数组删除对应 3 行
- 1301 行 → 1283 行（-18 行）

**保留**（向下兼容）：
- SQL schema 中 `is_operating` / `is_dividend` / `innovate` 字段保留
- `transformRow` 中三列固定填 `'未知'`
- 旧 IndexedDB 缓存数据仍可正常加载

**关联**：
- 主方案 §2 P0 目标 = 三个失效筛选器从 UI 消失 ✅
- 修复了 commit 7c608c5 (refactor: drop N2 old table support) 留下的 UI 不一致问题

---

## [2026-04-26] fb9f381 docs: backfill commit ids in CHANGELOG entries

**类型**：docs / chore

回填前两个条目的 commit 短 ID。

---

## [2026-04-26] d7e3b6c docs: 落地 8 项开放问题决策 + 术语修正活跃→活动 + 增量导入策略

**类型**：docs / 需求确认

**用户决策（2026-04-26）**：

8 项核心开放问题已确认：

| # | 问题 | 决策 |
|---|------|------|
| Q1 | 长险活动率分母 | ✅ 月均（月初+月末）/2 |
| Q2 | 队伍产能定义 | ✅ 三定义：P1 人均保费 / P2 人均产能 / P3 人均件数 |
| Q3 | 滚动 12 月活动率 | ✅ 不做（v1） |
| Q4 | 历史人力数据 | ✅ 后续陆续补充，支持增量导入 |
| Q5 | 工号变更 | ✅ 视为不同人 |
| Q6 | 主管/经理聚合 | ✅ 合并为「外勤管理职」 |
| Q7 | 模块布局 | ✅ Tab 切换 |
| Q8 | 基准年 | ✅ 系统当前年份自动滚动 |

**术语修正**：
- 「活跃人力 → 活动人力」（业务方惯用术语）
- 新增「长险活动人力」概念（活动人力的子集）
- 移除「合格人均长险」「司龄校准产能」（用户明确不需要）
- 留存率移至 v2（先不做，后续再定义）

**变更内容**：
- [主方案](../需求/2026-04-26_模块化重构总体方案.md) v0.1 → v0.2：
  - Section 5（业务模块概览）：术语规范说明
  - Section 9（开放问题）：8 项已确认 + 5 项后续待确认（附加险/外勤管理职边界等）
  - 新增 ADR-005 ~ ADR-008（术语统一/产能口径/基准年自动滚动/外勤管理职）
- [模块01 平台趋势](../需求/模块01_平台趋势.md) v0.1 → v0.2：基准年改为系统当前年份自动滚动
- [模块02 产品结构](../需求/模块02_产品结构.md) v0.1 → v0.2：默认对比年份对（当前-1 vs 当前）随基准年滚动；新增附加险分类策略待确认
- [模块03 队伍规模](../需求/模块03_队伍规模.md) v0.1 → v0.2：
  - 移除留存率（v1 不做）
  - 新增外勤管理职聚合维度
  - 新增增量导入工作流（DELETE+INSERT 事务整月覆盖）
- [模块04 长险活动率](../需求/模块04_长险活动率.md) v0.1 → v0.2：
  - 分母固定为月均（移除 UI 切换）
  - 术语「出单人 → 长险活动人力」
- [模块05 队伍产能](../需求/模块05_队伍产能.md) v0.1 → v0.2：
  - 收敛为 3 个定义（P1/P2/P3）
  - 分子统一用期交保费 qj_cents
  - 件数排除附加险（待 Q10 确认规则）
- [人力数据规范](../数据规范/人力数据规范.md) v1.0 → v1.1：
  - schema 新增 `mgmt_level` 派生列
  - 增量导入章节
  - 派生指标重写（活动人力/长险活动人力/3 定义产能）
- [保单数据规范](../数据规范/保单数据规范.md) v1.0 → v1.1：
  - 新增件数定义（COUNT DISTINCT policy_no）
  - 新增附加险识别规则（待 Q10 确认）
  - 新增开放问题章节

**字段名修正**：
- 修正全文档中「期交保费」字段为 `qj_cents`（与现有 schema 一致），废弃错用的 `qjbf_cents`

**后续待确认（衍生问题）**：
- Q9 「外勤管理职」具体职级边界（P3 启动前）
- Q10 「附加险」识别规则（P5 启动前；与模块 02 联动）
- Q11 `term_type` 实际值（P4 启动前数据校验）
- Q12 月均活动人力精确算法（P5 实现时）
- Q13 期交保费字段确认（数据校验）

**关联**：
- 用户原话：「长险活动率分母采用月均。队伍产能需要有人均保费（期交保费/月均在职人力）、人均产能（期交保费/月均活动人力）、没有活跃人力应该叫活动人力以及长险活动人力、人均件数没有问题（产品件数应不包含附加险，人均仍采用月均在职人力）、没有合格人均长险这个指标。留存率先不要体现，后续再做定义。主管和经理做聚合，统一为外勤管理职。历史人力数据后期我会再补充，你可以同步拼接入sqlite。工号如果变更则视为不同人。模块不同应使用不同标签页，不要单页滑动。基准年应采用系统当前时间的年份。」

**下一步**（待用户 review 后启动）：
- P0 紧急修复：清理三个失效筛选器
- P1：建立 `js/` 模块结构、迁移现有平台趋势 + 产品结构、ESM bootstrap

---

## [2026-04-26] 8053b4f docs: 立项模块化重构总体方案

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
