# CHANGELOG

> 项目变更累积记录。时间倒序。每个 commit 应在此追加一条摘要。
>
> 格式：`## [YYYY-MM-DD] <commit-id-short> <type>: <主题>`
>
> 详细内容指向对应文档（`docs/需求/...`）。

---

## [2026-04-26] 4fc3d83 chore: P1.8 迁移 bootstrap 模块（顶层 orchestrator）+ build.sh 多行 import/重导出剥离

**类型**：chore / 模块化重构 P1.8 + fix / build.sh

**变更**：

将 `经营分析模板.html` 内联 IIFE 中 boot UI / 事件绑定 / 文件导入 / 启动流相关的代码（行 ~800-1281）拆分为 5 个 bootstrap 子模块 + 1 个 core 子模块。bootstrap 是顶层 orchestrator，是 `js/README.md` 「模块互相不 import」原则的明确例外。同时修复 `build.sh` 未剥离多行 import 与 `export { ... } from '...'` 重导出的问题——P1.8 是首次出现重导出的 commit。

**新增文件**：
- `js/core/idb.js`（35 行）— IndexedDB KV 包装：`openIdb()` / `idbGet(key)` / `idbPut(key, val)`，从 inline 行 867-900 抽出
- `js/modules/bootstrap/boot-overlay.js`（30 行）— `setBoot(state, msg)` / `hideBoot()`：#bootOverlay 状态机
- `js/modules/bootstrap/render.js`（16 行）— `render() = renderTrend() + renderStructure()`：**唯一**跨业务模块 import 的文件，是顶层渲染编排
- `js/modules/bootstrap/events.js`（53 行）— `bindEvents()`：顶部按钮组 / 标签页 / 比较开关 / 筛选器 / window resize
- `js/modules/bootstrap/import-flow.js`（85 行）— `handleImport(file)` / `bindReimport()` / `bindEmptyUI(retryFn)`：通过 `parseAndBuild(file, msg=>setBoot('loading', msg))` 回调解耦 importer 与 boot UI
- `js/modules/bootstrap/init.js`（67 行）— `updateMetaInfo(meta)` / `initApp(meta)` / `bootFlow()`：顶层启动流（loads sql.js + 检查 IDB cached → setDb + initApp，否则 setBoot('empty') + bindEmptyUI(bootFlow)）
- `js/modules/bootstrap/index.js`（12 行）— barrel re-exports
- `js/modules/bootstrap/README.md` — 模块说明 + 启动顺序流程图 + 边界例外原因

**模块边界例外（重要）**：
- bootstrap/render.js **同时** import `platform-trend` 与 `product-structure`，是顶层应用编排
- 其他业务模块仍遵循「不互相 import」：
  - `platform-trend/index.js renderTrend()` 只渲染趋势/同比/KPI
  - `product-structure/index.js renderStructure()` 只渲染饼图
- 设计理由：避免业务模块互相耦合；将「应用层组合」集中在 bootstrap，未来增减模块只改一处

**build.sh 修复**：
- 重写 `strip_esm()` 改用 awk 状态机处理多行 import：`import {\n  X,\n  Y\n} from './x.js';`
- 新增重导出剥离：`export { X, Y } from './x.js';`
- 保留原有 `export ` 前缀剥离与命名导出 `export { X };` 删除规则
- 修复后注入行数 1108（P1.7）→ 1368（P1.8），符合 7 个新文件 ~298 行 + bootstrap 子模块间 import/export 剥离

**main.js**：
- 添加 `import * as idb from './core/idb.js';` 并暴露到 `__jyfx.idb`
- 添加 `import * as bootstrap from './modules/bootstrap/index.js';` 并暴露到 `__jyfx.modules.bootstrap`
- 仅 ESM 开发模式生效；bundled 单文件由内联 IIFE 兜底

**build.sh 校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 2657
注入 JS 行数: 1368
```

注入行数 1108（P1.7）→ 1368（P1.8），增量 +260 行（7 个新文件总计 ~298 行 - 跨文件 import/export 剥离）。`grep -nE '^[[:space:]]*(export|import)[[:space:]]'` 确认 bundled 输出无残留 ESM 关键字。

**作用域分析（无冲突）**：
- 注入的 `openIdb / idbGet / idbPut / setBoot / hideBoot / render / bindEvents / handleImport / bindReimport / bindEmptyUI / updateMetaInfo / initApp / bootFlow` 在 Global Lexical Environment 声明
- inline IIFE 内同名 function 声明是函数作用域局部声明，**正确遮蔽**注入的全局版本（IIFE 启动时调用本地版本，全局版本无人调用，处于 frozen 状态）
- 这是迁移期的过渡形态：P1.X 一次性切换时删除 inline IIFE，main.js 改为 `bootFlow()` 自启动

**未变更**：
- `经营分析模板.html` 内联 IIFE 完全未动（37 sync + 5 async = 42 个函数声明数量验证通过；行数 1285 不变）
- file:// 直接打开行为完全保持
- 无 schema、UI、字段改动

**关联**：
- 主方案 §3 ESM + 发布期 build.sh
- 主方案 §模块边界例外说明（bootstrap 作为顶层 orchestrator）
- 下一步：P1.X 一次性切换 — 删除 inline IIFE 行 277-1282，改为 `<script type="module" src="js/main.js">` + main.js 调用 `bootFlow()`，运行 `./build.sh --in-place` 生成单文件发布产物

---

## [2026-04-26] 13d7189 chore: P1.7 迁移 importer 模块 + 修复 build.sh export 剥离

**类型**：chore / 模块化重构 P1.7 + fix / build.sh

**变更**：

将 `经营分析模板.html` 内联 IIFE 中 Excel 导入相关的 12 个函数（行 ~903-1167）拆分为 4 个 ESM 模块。同时修复 `build.sh` 在 P1.6 之前未覆盖 `export { name };` 形式的剥离 bug——P1.7 是首次出现该形式的 commit。

**新增文件**：
- `js/modules/importer/schema.js`（80 行）— `REQUIRED_TIME_COLS` / `DATE_COL_CANDIDATES` / `CORE_DIM_COLS` / `EXT_DIM_COLS` / `ALL_DIM_COLS` / `METRIC_COLS_ZH` / `COL_ALIASES` / `SCHEMA_SQL` / `INSERT_SQL`
- `js/modules/importer/column-resolve.js`（70 行）— `resolveCol` / `levenshtein` / `suggest` / `validateColumns` / `findDateColumn`
- `js/modules/importer/cell-transform.js`（115 行）— `pad2` / `toCents` / `trimDim` / `trimEmpty` / `fmtDateTime` / `parseDateCell` / `transformRow`
- `js/modules/importer/index.js`（90 行）— `parseAndBuild(file, onProgress)`（解耦 boot UI；进度通过回调）+ `collectMeta(targetDb, fileName)`
- `js/modules/importer/README.md` — 模块说明 + 检查清单

**模块边界设计**：
- `parseAndBuild` 通过 `onProgress(msg)` 回调暴露进度，**不**直接耦合 boot UI（原 inline 直接调用 `setBoot`）
- importer 不写 IDB、不操作全局 `db` 句柄；只返回内存 db 与文件名
- 调用方（bootstrap，待 P1.8）负责进度展示、`setDb()`、`idbPut()`、`collectMeta`

**build.sh 修复**：
- 新增 sed 规则：`/^\s*export\s*\{[^}]*\}\s*;?\s*$/d` 删除 `export { pad2 };` 等命名导出行
- 该行在 ESM 模式下必需（用于 `import * as importer` 命名空间）；在 bundled 模式下标识符已是全局 → 必须剥离，否则 `<script>` 上下文 SyntaxError
- 修复后注入行数 1109 → 1108

**main.js**：扩展 `__jyfx.modules.importer` 命名空间（仅 ESM 开发模式生效）。

**build.sh 校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 2396
注入 JS 行数: 1108
```

注入行数 750（P1.6）→ 1108（P1.7），增量 +358 行符合预期（4 个新文件总计 ~355 行）。

**作用域分析（无冲突）**：
- 注入的 `pad2 / toCents / trimDim / trimEmpty / fmtDateTime / parseDateCell / transformRow / resolveCol / levenshtein / suggest / validateColumns / findDateColumn / parseAndBuild / collectMeta` 在 Global Lexical Environment 声明
- 同样名为 `SCHEMA_SQL / INSERT_SQL / REQUIRED_TIME_COLS / ALL_DIM_COLS / METRIC_COLS_ZH / COL_ALIASES / DATE_COL_CANDIDATES / CORE_DIM_COLS / EXT_DIM_COLS` 的 const 在全局；inline IIFE 内同名 const 是块作用域局部声明，**正确遮蔽**注入的全局版本
- 注入的全局 `parseAndBuild` 引用 `XLSX` 全局 + `window.__SQL`，但因无人调用它（inline IIFE 自带 `parseAndBuild`），处于 frozen 状态

**未变更**：
- `经营分析模板.html` 内联 IIFE 完全未动（37 个函数声明数量验证通过）
- file:// 直接打开行为完全保持
- 无 schema、UI、字段改动

**关联**：
- 主方案 §3 ESM + 发布期 build.sh
- 保单数据规范 §schema 必填列
- 下一步：P1.8 迁移 bootstrap（boot-overlay / events / reimport / empty-ui / init / idb-wrapper） + P1.9 一次性切换

---

## [2026-04-26] 3088f52 chore: P1.6 迁移平台趋势模块到 js/modules/platform-trend/

**类型**：chore / 模块化重构 P1.6

**变更**：

将 `经营分析模板.html` 内联 IIFE 中平台趋势相关的 8 个函数（行 372-792）拆分为 6 个 ESM 模块文件。inline 副本暂保留，由 build.sh 注入产生全局副本待命，将于 P1.X 一次性切换时删除 inline 代码。

**新增文件**（顺序按 ECharts 依赖关系）：
- `js/modules/platform-trend/query.js`（73 行）— `aggregate()` + `queryDaily()`：聚合 + 单期间日明细 SQL，金额已 `/100`（元）
- `js/modules/platform-trend/view-main.js`（103 行）— `getXLabels()` + `renderMain(periodMap)`：主累计折线图，返回 `{years, dimKeys, xLabels}`
- `js/modules/platform-trend/view-yoy.js`（97 行）— `renderYoY(...)`：YoY 同比图（含 `state.compare === false` 时的清空逻辑）
- `js/modules/platform-trend/view-kpi.js`（49 行）— `renderKPI(...)`：KPI 卡片直接 `innerHTML` 渲染
- `js/modules/platform-trend/view-daily-tip.js`（121 行）— `installDailyTooltip()` + `showDailyTip(period, x, y)`：主图 hover 浮层
- `js/modules/platform-trend/index.js`（30 行）— `renderTrend()`：串联 query + main + yoy + kpi（不含 product-structure 调度）

**模块边界设计**：
- `index.js` 仅串联本模块内部子视图；**不**调用 `productStructure.renderStructure()`
- 跨模块编排留给最终顶层控制器（main.js）：`renderTrend()` + `productStructure.renderStructure()` 分别调度
- 严格遵循 `js/README.md` 「模块互相不 import」原则

**main.js**：扩展 `__jyfx.modules.platformTrend` 命名空间（仅 ESM 开发模式生效）。

**README**：`js/modules/platform-trend/README.md` 状态从 🟠 待迁移 → 🟡 迁移中；勾选已完成的 6 项检查清单。

**build.sh 校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 2038
注入 JS 行数: 750
```

注入行数 288（P1.5）→ 750（P1.6），增量 +462 行符合预期（6 个新模块文件总计 ~470 行）。

**作用域分析（无冲突）**：
- 注入的 `aggregate / renderMain / renderYoY / renderKPI / installDailyTooltip / queryDaily / showDailyTip / getXLabels / renderTrend` 在 Global Lexical Environment 声明
- inline IIFE 内同名函数（`render` / `aggregate` / `renderYoY` / `renderKPI` / `installDailyTooltip` / `queryDaily` / `showDailyTip` / `getXLabels`）是函数作用域局部声明，**正确遮蔽**注入的全局版本
- 注入的全局 `aggregate` 调用注入的全局 `q`（来自 core/db.js），但 `_db` 未通过 `setDb()` 注入 → 全局 `aggregate` 处于「frozen 状态」永不被触发；不影响 IIFE 内的运行流
- 现阶段 inline IIFE 仍是事实运行的实现；注入版本「待命」，将在 P1.X 切换时启用

**未变更**：
- `经营分析模板.html` 内联 IIFE 完全未动
- file:// 直接打开行为完全保持
- 无 schema、UI、字段改动

**关联**：
- 主方案 §3 ESM + 发布期 build.sh
- 模块01 §平台趋势 v0.2
- 下一步：P1.X 一次性切换 = 删除 inline IIFE 已迁出的代码 + `./build.sh --in-place` + 接入 importer/setDb/initSelects 启动流

---

## [2026-04-26] 393f7fe chore: P1.5 迁移产品结构模块到 js/modules/product-structure/

**类型**：chore / 模块化重构 P1.5

**变更**：

将 `经营分析模板.html` 内联 IIFE 中的 `renderStructure()`（行 599-626）拆分为三个 ESM 模块。inline 副本暂保留，由 build.sh 注入产生全局副本待命，将于 P1.X 一次性切换时删除 inline 代码。

**新增文件**：
- `js/modules/product-structure/query.js`（21 行）— `fetchStructure()`：调用 `buildWhere()` + `metricCol()` 构造 design_cat 聚合 SQL，调用 `q()` 返回 `[{k, v}]`
- `js/modules/product-structure/view-pie.js`（30 行）— `renderPie(rows)`：构造 pieData，复用 `getChart('struct')`/`setChart('struct', ...)` 缓存 ECharts 实例，option 与原 inline 实现完全一致
- `js/modules/product-structure/index.js`（12 行）— `renderStructure()` = `renderPie(fetchStructure())`

**main.js**：扩展 `__jyfx.modules.productStructure` 命名空间（仅 ESM 开发模式生效）。

**README**：`js/modules/product-structure/README.md` 状态从 🟠 待迁移 → 🟡 迁移中；勾选已完成的 3 项检查清单。

**build.sh 校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 1576
注入 JS 行数: 288
```

注入行数 224（P1.4）→ 288（P1.5），增量 +64 行符合预期。

**作用域分析（无冲突）**：
- 注入的 `function renderStructure`、`function fetchStructure`、`function renderPie` 在 Global Lexical Environment 声明
- inline IIFE 内的 `function renderStructure`（行 599）是函数作用域局部声明，**正确遮蔽**注入的全局版本
- 现阶段 inline IIFE 仍是事实运行的实现；注入版本「待命」，将在 P1.X 切换时启用

**未变更**：
- `经营分析模板.html` 内联 IIFE 完全未动
- file:// 直接打开行为完全保持
- 无 schema、UI、字段改动

**关联**：
- 主方案 §3 ESM + 发布期 build.sh
- 模块02 §产品结构 v0.2
- 下一步：P1.6 迁移平台趋势模块（aggregate / render* / queryDaily，行 ~372-790）

---

## [2026-04-26] f4534a2 chore: P1.4 抽出 core/ 工具底座（constants/state/db/filters）

**类型**：chore / 模块化重构 P1.4

**变更**：

并行抽出业务无关的 core/ 工具，作为后续 product-structure / platform-trend 模块的依赖底座。inline IIFE 保持不动，build.sh 注入产生全局副本。

**新增文件**：
- `js/core/constants.js`（30 行）— `BASE_YEAR`、`MONTH_LABELS`、`QUARTER_LABELS`、`FILTER_KEYS`、`METRIC_MAP`、`VIEW_DIM_COL`
- `js/core/state.js`（45 行）— `state` 对象、`dailyCache`、`allYears`、`getChart`/`setChart`/`disposeAllCharts`
- `js/core/db.js`（45 行）— `setDb`/`getDb`/`isReady`、`q`（参数化查询）、`exec`、`exportSnapshot`
- `js/core/filters.js`（60 行）— `metricCol`、`buildWhere`、`filterStateHash`、`initSelects`

**main.js**：扩展为聚合所有 core/ 模块到 `globalThis.__jyfx` 命名空间（仅 ESM 开发模式生效）。

**build.sh 校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 1512
注入 JS 行数: 224
```

**作用域分析（无冲突）**：
- 注入的 `<script>` 块在 Global Lexical Environment 声明 const/let/function
- IIFE 内的同名 `const`/`function` 处于函数作用域，**正确遮蔽**注入的全局版本
- 现阶段 IIFE 仍是事实运行的实现；注入版本「待命」，将在 P1.X 切换时启用

**未变更**：
- `经营分析模板.html` 内联 IIFE 完全未动
- file:// 直接打开行为完全保持
- 无 schema、UI、字段改动

**关联**：
- 主方案 §3 ESM + 发布期 build.sh
- 下一步：P1.5 迁移 product-structure 模块（renderStructure → js/modules/product-structure/）

---

## [2026-04-26] 92eb68c fix: 应用 Q8 决策——BASE_YEAR 改为系统当前年份自动滚动

**类型**：fix / P1.3a 用户决策落地

**变更**：

`经营分析模板.html` 第 279 行：

```diff
-  const BASE_YEAR = '2024';
+  const BASE_YEAR = String(new Date().getFullYear());  // 基准年自动滚动（用户 2026-04-26 Q8 决策）
```

**背景**：
- 用户 2026-04-26 决策 Q8：「基准年应采用系统当前时间的年份」
- 已在 `主方案 ADR-007`、`模块01_平台趋势.md`、`模块02_产品结构.md` 中文档化
- 但代码层面尚未应用，运行时仍以 2024 作为基准年（已过时 2 年）
- 影响：YoY 同比图色阶/对比组、KPI 卡片基准、视觉强调线 都仍以 2024 为锚点

**生效**：
- 系统当前为 2026 → BASE_YEAR 现取 '2026'
- 跨年自动滚动，无需手动维护

**关联**：
- 主方案 §6 ADR-007（基准年自动滚动）
- 模块01 §2 v0.2、模块02 §2 v0.2

**未变更**：
- 无字段、schema、UI 控件改动；零结构性影响
- 模块化重构 P1 主线（module 抽离）继续在后续 commit 推进

---

## [2026-04-26] fc6dc06 docs: backfill 8fb4f3d commit id in CHANGELOG

**类型**：docs / chore

回填 8fb4f3d commit id。

---

## [2026-04-26] 8fb4f3d feat: P1.2 build.sh 发布期合并 + ESM bootstrap

**类型**：feat / 模块化重构 P1.2

**变更**：

新增工程化发布机制，将 `js/` ESM 源码合并回 `经营分析模板.html` 单文件交付。

**新增文件**：
- `build.sh`（可执行，bash + sed + awk，无需额外工具链）
- `js/main.js`（ESM 入口，导出 `__jyfx` 全局命名空间）

**HTML 变更**：
- `经营分析模板.html` 第 273 行注入 `<!-- BUILD:JS:CORE -->` 标记（HTML 注释，不影响现有运行）

**README 变更**：
- 新增「目录结构与模块化构建」一节，文档化 build.sh 工作原理与模块迁移进度表

**build.sh 行为**：
- 按字母序读取 `js/core/*.js` + `js/modules/*/*.js`
- 简易剥离 ESM：删除 `export ` 前缀、删除相对路径 import 行
- 注入到 HTML 模板的 `<!-- BUILD:JS:CORE -->` 位置
- 默认输出 `dist/经营分析模板.html`（已 gitignore）
- 支持 `--check`（仅校验）与 `--in-place`（覆盖根文件）

**校验**：
```
$ ./build.sh --check
模板行数: 1285
合并后行数: 1311
注入 JS 行数: 23
```

**注意（过渡形态）**：
- 现阶段 `经营分析模板.html` 内联 IIFE 仍含完整业务逻辑（包括重复的 formatNum/formatShort）
- build.sh 注入的合并代码处于「函数声明全局可见，但 IIFE 内有同名局部声明」共存状态，**无运行时冲突**
- 后续 P1.3+ 逐模块从内联 IIFE 中删除已迁出的代码后，build 注入版本将自动接管

**关联**：
- 主方案 §3 ESM + 发布期 build.sh 合并策略（已落地最简实现）
- 下一步：P1.3 迁移平台趋势模块（aggregate/render*/queryDaily）

---

## [2026-04-26] 0e2601c chore: P1.1 建立 js/ 模块源码骨架 + 提取 format.js

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
