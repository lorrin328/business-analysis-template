# 经营分析 - 产品结构测算

保险经营分析单页看板。**纯浏览器实现**：双击 HTML 打开 → 选择 Excel → 自动入库。无需 Python，无需服务器。

> 📚 **完整文档体系**：本 README 描述当前实现现状。架构演进、模块化方案、新模块需求、数据规范请见 [docs/](./docs/README.md)。
>
> 当前规划：5 个业务模块（平台趋势、产品结构、队伍规模、长险活动率、队伍产能），见 [模块化重构总体方案 v0.1](./docs/需求/2026-04-26_模块化重构总体方案.md)。

---

## 目录

- [特性](#特性)
- [使用方法](#使用方法)
- [数据要求](#数据要求)
- [技术栈](#技术栈)
- [业务逻辑详解](#业务逻辑详解)
  - [数据模型](#数据模型)
  - [Excel 解析与入库](#excel-解析与入库)
  - [聚合查询](#聚合查询)
  - [筛选系统](#筛选系统)
  - [主图渲染](#主图渲染)
  - [同比图（YoY）](#同比图yoy)
  - [产品结构饼图](#产品结构饼图)
  - [KPI 卡片](#kpi-卡片)
  - [日明细浮层](#日明细浮层)
- [IndexedDB 持久化](#indexeddb-持久化)
- [修改历史](#修改历史)
- [已知问题与排查](#已知问题与排查)
- [开发注意事项](#开发注意事项)

---

## 特性

- **零安装**：双击 `经营分析模板.html` 即可使用
- **浏览器内入库**：SheetJS 解析 Excel → sql.js 构建内存 SQLite → 毫秒级查询
- **持久化**：导入后存入浏览器 IndexedDB，下次打开自动恢复
- **日级精度**：月/季视图主图保持累计折线形态，hover 任意月/季弹出当期日累计 sparkline
- **任意维度筛选**：10 个产品维度 × 3 个保费口径
- **多年同比**：支持 2024 / 2025 / 2026 任意年份的累计对比与 YoY 增速

---

## 使用方法

1. 在 Finder 双击 `经营分析模板.html`，浏览器打开
2. 首次使用：点击「📂 选择 Excel 文件」或拖入 .xlsx 文件
3. 等待 5–30 秒解析（取决于文件大小），主界面自动渲染
4. 后续打开：浏览器自动从 IndexedDB 恢复数据，秒级进入主界面
5. 替换数据：点击右上角「📁 重新导入」按钮

---

## 数据要求

源文件需要包含的列（中文表头）——**核心必需列**（缺失会报错）：

- **时间**：`年`、`月`（或 `年月`）、`季`（或 `年季`）、`日期`（或 `投保日期`/`签单日期`/`年月日`）
- **核心维度**：`销售机构名称`、`业务模式`、`长短险`、`是否商保年金产品`、`缴费年限`、`保障年限`、`产品设计分类`
- **指标**：`期交保费`、`年化规保`、`折算保费`（单位为元）

**可选字段**（有则入库，无则填默认值，不报错）：

- `人员工号`、`主管工号`、`经理工号`、`投保单号`、`自保件标记`
- `投保时间`、`承保时间`、`入账时间`、`回销时间`
- `产品代码`、`产品名称`、`是否个人养老金`、`价值规保`

`月标签` 可选，缺失时自动按「年+月」生成。缺失列会显示具体列名并给出最相近的实际列名建议。

### 保费统计口径

**当前主口径按 `入账时间` 统计**。表格中的 `年`、`年月`、`年季`、`年月日` 等时间字段均按 `入账时间` 做处理。

### 激励方案口径（待实现）

用于激励方案计算时，采用以下规则：
- 以 **`承保时间`** 为准
- 承保后 **30 个自然日（含）** 内
- 再过 **15 个自然日（含）** 回销
- 且 **未发生负金额**（即无撤单/退保）

满足以上全部条件的保单，计入激励方案口径。该逻辑尚未在看板中实现，仅作为预留规则入库。

---

## 技术栈

| 组件 | 用途 | CDN |
|------|------|-----|
| ECharts 5.5 | 图表 | jsdelivr |
| sql.js 1.10.3 | 浏览器内 SQLite（WASM） | jsdelivr |
| SheetJS 0.18.5 | Excel 解析 | jsdelivr |
| IndexedDB | 二进制 db 持久化 | 浏览器原生 |

---

## 业务逻辑详解

### 数据模型

单表 `fact_premium`，32 列。支持新旧两套 Excel 表结构，可选字段缺失时填默认值：

**时间字段（7 列）**：
| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增主键 |
| `date` | TEXT | 日期，格式 `YYYY-MM-DD`（取自 `年月日`） |
| `year` | TEXT NOT NULL | 年，统一存字符串 |
| `quarter` | INTEGER NOT NULL | 季 1-4 |
| `month` | INTEGER NOT NULL | 月 1-12 |
| `day` | INTEGER | 日，可空 |
| `month_label` | TEXT NOT NULL | 月标签，如「2024年1月」 |

**核心维度（7 列）**：
| 列名 | 类型 | 说明 |
|------|------|------|
| `org` | TEXT | 销售机构名称 |
| `biz_mode` | TEXT | 业务模式 |
| `term_type` | TEXT | 长短险 |
| `is_annuity` | TEXT | 是否商保年金产品 |
| `pay_years` | TEXT | 缴费年限 |
| `cov_years` | TEXT | 保障年限 |
| `design_cat` | TEXT | 产品设计分类 |

**扩展维度（12 列）**：
| 列名 | 类型 | 说明 |
|------|------|------|
| `staff_id` | TEXT | 人员工号 |
| `supervisor_id` | TEXT | 主管工号 |
| `manager_id` | TEXT | 经理工号 |
| `policy_no` | TEXT | 投保单号 |
| `self_mark` | TEXT | 自保件标记（`Y`/`N`） |
| `app_date` | TEXT | 投保时间 `YYYY-MM-DD HH:MM:SS` |
| `underwrite_date` | TEXT | 承保时间 `YYYY-MM-DD HH:MM:SS` |
| `entry_date` | TEXT | 入账时间 `YYYY-MM-DD HH:MM:SS` |
| `cancel_date` | TEXT | 回销时间 `YYYY-MM-DD HH:MM:SS` |
| `product_code` | TEXT | 产品代码 |
| `product_name` | TEXT | 产品名称 |
| `is_pension` | TEXT | 是否个人养老金 |

**已停用维度（3 列，保留在库中但新导入固定为 `'未知'`）**：
| 列名 | 类型 | 说明 |
|------|------|------|
| `is_operating` | TEXT | 是否在运营项目（旧 N2 表字段，已停用） |
| `is_dividend` | TEXT | 分红产品（旧 N2 表字段，已停用） |
| `innovate` | TEXT | 创新or传统（旧 N2 表字段，已停用） |

**金额指标（4 列，单位「分」，INTEGER）**：
| 列名 | 类型 | 说明 |
|------|------|------|
| `qj_cents` | INTEGER DEFAULT 0 | 期交保费 |
| `ghgb_cents` | INTEGER DEFAULT 0 | 年化规保 |
| `zhsf_cents` | INTEGER DEFAULT 0 | 折算保费 |
| `jzgb_cents` | INTEGER DEFAULT 0 | 价值规保（新表特有，暂不用于看板） |

索引：
- `ix_ym` (year, month)
- `ix_yq` (year, quarter)
- `ix_ymd` (year, month, day)
- `ix_org` (org)
- `ix_mode` (biz_mode)
- `ix_dsg` (design_cat)

**金额按「分」存 INTEGER**：`元 × 100` 后 `Math.round()` 入库，彻底避免 IEEE754 浮点尾噪。查询时 `SUM(col) / 100.0` 还原。

### Excel 解析与入库

文件：`经营分析模板.html` 内联 JS，函数 `parseAndBuild(file)`

流程：
1. `XLSX.read(buf, { type: 'array', cellDates: true })` 解析 Excel
2. `XLSX.utils.sheet_to_json(sheet, { defval: null, raw: true })` 提取首 sheet 全部行
3. `validateColumns(allCols)` 校验必需列（支持别名，见下文）
4. `findDateColumn(allCols)` 从候选列名中找日期列
5. 构建 `colMap`：标准列名 → 实际列名（支持别名映射）
6. `transformRow(r, dateCol, colMap)` 逐行转换：
   - `年` → `String().trim()`
   - `月`：优先 `Date.getMonth() + 1`，否则 `parseInt`
   - `季`：支持字符串如 `'2024-1'`（split `-` 取末段），否则 `parseInt`
   - `月标签`：可选，缺失时自动衍生为 `${year}年${month}月`
   - 维度列：trim，空/`nan`/`None` → `'未知'`
   - 金额列：`parseFloat(v) × 100` 后 `Math.round()`
7. `newDb.exec(SCHEMA_SQL)` 建表 + 索引（`exec` 支持多语句，`run` 不支持）
8. `prepare(INSERT_SQL)` + `BEGIN`/`COMMIT` 批量插入
9. `ANALYZE` 更新统计信息

**列名别名系统**（`COL_ALIASES`）：

| 标准列名 | 别名 | 说明 |
|----------|------|------|
| `月` | `年月` | 年月列常为 Date 类型，取月份 |
| `季` | `年季` | 年季列常为 `'2024-1'` 字符串 |
| `日期` | `年月日` | 年月日列常为 Date 类型 |

`resolveCol(standard, availableCols)` 优先匹配标准名，其次遍历别名。

### 聚合查询

函数 `aggregate()` 根据当前 `state` 生成 SQL：

```sql
SELECT year, <periodCol> AS period, <dimSelect>,
       SUM(<metricCol>) / 100.0 AS amount
FROM fact_premium
<where>
GROUP BY <groupBy>
ORDER BY year, period
```

- `periodCol` = `quarter`（季视图）或 `month`（日/月视图）
- `dimCol` = `org`（分机构视图）或 `biz_mode`（分业务模式视图）或 `null`（整体视图）
- `dimSelect` = `, <dimCol> AS dim_key`（有维度）或 `, '' AS dim_key`（整体）
- `groupBy` 相应变化

返回的 `periodMap` 结构：
```js
{
  "year||dimKey": {
    year: "2024",
    dimKey: "",
    dimLabel: "",
    periods: { 1: amount1, 2: amount2, ... },
    cumulative: [empty, cum1, cum2, ...]  // 索引 1-based
  }
}
```

`cumulative[i]` = 第 1 期到第 i 期的累计和。即使某期无数据（如 2026 年仅到 4 月），后续期 cumulative 保持最后一期值不变（`cum += 0`）。

### 筛选系统

`FILTER_KEYS` 定义 10 个维度筛选器：

```js
[
  { key: '销售机构名称', sel: 'selOrg', col: 'org' },
  { key: '业务模式', sel: 'selMode', col: 'biz_mode' },
  // ... 共 10 个
]
```

`buildWhere(extraClauses, extraParams)` 读取所有 `<select>` 当前值，非空则生成 `col = $col` 条件。`extraClauses` 用于附加条件（如日明细查询时的 `year = $y` 和 `month = $p`）。

`filterStateHash()` 生成当前筛选状态的字符串签名，用于 `dailyCache` 的 key，确保切换筛选后日明细缓存失效。

### 主图渲染

函数 `render()` 内的主图逻辑：

- x 轴：`type: 'category'`，数据为 `MONTH_LABELS`（12 月）或 `QUARTER_LABELS`（4 季）
- 系列：每年一条折线，`data` 为 `g.cumulative[i+1]` 的 12/4 个值
- 基准年（2024）且开启对比时，线型为 `dashed`
- `symbolSize: 6`，`smooth: true`

**注意**：`state.gran` 默认为 `'day'`，但主图始终按 `month` 聚合（`gran === 'quarter' ? 'quarter' : 'month'`）。「日」与「月」的区别仅在于文案（`granLabels`），主图形态完全一致。这是刻意设计：日粒度主图在保险业务场景下与月粒度形态相同（都是累计折线），区别仅在于用户心理预期。

### 同比图（YoY）

函数 `renderYoY()`：

- 以 `BASE_YEAR`（2024）为基准，计算 `(current - base) / base × 100%`
- `base === 0` 时返回 `null`（ECharts 留空）
- 整体视图：每年一条线
- 分维度视图：每个「年 × 维度值」一条线
- `visualMap` 着色：负值红色，正值绿色

### 产品结构饼图

函数 `renderStructure()`：

- 按 `design_cat`（产品设计分类）分组汇总当前口径
- 过滤 `v === 0` 的项（保留负值，即撤单/退保）
- 饼图半径 `['35%', '65%']`，玫瑰图效果由数据自然分布产生

### KPI 卡片

函数 `renderKPI()`：

- 遍历 `periodMap`，取每组的「最后非零期」的累计值
- 与基准年同维度比较，计算同比百分比
- 最多展示 6 张卡片

### 日明细浮层

函数 `installDailyTooltip()` + `showDailyTip()`：

- 主图初始化时通过 `mainChartInstance.getZr()` 注册 `mousemove`/`mouseout` 事件
- `convertFromPixel({ seriesIndex: 0 }, [x, y])` 将鼠标像素坐标转数据索引
- 取索引对应期数，调用 `showDailyTip(period, clientX, clientY)`
- `queryDaily(year, period)` 查询该年该期的日明细：`SELECT day, SUM(metric)/100.0 GROUP BY day`
- 日明细 sparkline 为**累计折线**：逐日排序后累加，x 轴为 `day`（value 型），y 轴为累计金额
- 缓存键：`${year}|${gran}|${period}|${metric}|${filterHash}`，`dailyCache` 为内存 Map，非 IndexedDB

---

## IndexedDB 持久化

数据库名：`business-analysis-template`  
Store：`kv`（key-value）

存入两个 key：
- `'db'`：sql.js `Database.export()` 的 `Uint8Array`（整库二进制）
- `'meta'`：`{ importedAt, fileName, rowCount, byYear, sumQj, sumGhgb, sumZhsf }`

启动流程 `bootFlow()`：
1. `initSqlJs()` 加载 WASM
2. `idbGet('db')` 尝试恢复缓存
3. 有缓存 → `new SQL.Database(new Uint8Array(cached))` → `initApp(meta)`
4. 无缓存 → 显示导入 UI（拖拽/点击选文件）

---

## 修改历史

### 2026-04-26 `xxx` feat: extend schema to support AI 业绩基表 (32 columns)

**背景**：用户提供新表 `AI-经营分析业绩基表`，字段与旧表 `N2` 不一致。新表新增 12 个字段，同时缺失旧表 3 个字段。要求全部入库备用。

**业务规则确认**：
- 保费统计口径：**按 `入账时间` 统计**，`年`/`年月`/`年季`/`年月日` 均按 `入账时间` 处理
- 激励方案口径（预留）：以 **`承保时间`** 为准，承保后 **30 个自然日（含）** 内，再过 **15 个自然日（含）** 回销，且未发生负金额
- `价值规保` 先入库，暂不用于看板

**改动**：
- Schema 从 19 列扩展至 **32 列**：
  - 新增 12 个 TEXT 列：`staff_id`, `supervisor_id`, `manager_id`, `policy_no`, `self_mark`, `app_date`, `underwrite_date`, `entry_date`, `cancel_date`, `product_code`, `product_name`, `is_pension`
  - 新增 1 个 INTEGER 列：`jzgb_cents`（价值规保，分）
- `DIM_COLS_ZH` 拆分为 `CORE_DIM_COLS`（7 个必需）+ `EXT_DIM_COLS`（12 个扩展）
- `validateColumns` 仅检查核心必需列，可选列缺失不报错
- `transformRow` 新增 `trimEmpty()` 和 `fmtDateTime()` 辅助函数
- `collectMeta` 增加 `sumJzgb` 统计
- README 更新数据模型、数据要求、保费口径说明

**同日后续调整**（用户确认以后只用新表）：
- 旧 N2 表字段 `是否在运营项目`、`分红产品`、`创新or传统` 从 `ALL_DIM_COLS` 移除
- `transformRow` 中这三列固定填 `'未知'`，不再尝试从 Excel 读取
- 保留数据库中的这三列以兼容已缓存到 IndexedDB 的旧数据
- README 更新：旧表字段标记为「已停用」

---

### 2026-04-25 `0e00917` debug: remove axisPointer and add per-chart error tracing

**问题**：用户导入 N2 Excel 后 ECharts 报 `undefined is not an object (evaluating 'p[0].coord')`，主图无法渲染。

**根因推测**：ECharts 5.5 的 `axisPointer.type='line'` 配合 `snap=true` 在数据刚渲染时，内部 snapping 计算可能访问空数组的 `[0].coord`。

**改动**：
- 主图完全移除 `axisPointer` 配置
- 主图 `setOption` 加独立 try-catch
- 空 series 时填充占位空系列 `[{ name: '', type: 'line', data: [] }]`
- `render()` 内各子图（同比、结构、KPI）独立 try-catch，控制台可定位具体失败组件
- `initApp`/`handleImport` 的 `render()` 外层包 try-catch，错误信息直接显示在 UI

### 2026-04-25 `a0b1e09` fix: guard against ECharts edge cases

**问题**：同一 `p[0].coord` 错误，第一次修复（移除 `snap: true`）后仍出现。

**改动**：
- `axisPointer.label.formatter` 增加空值防御
- 所有 tooltip formatter（同比图、日明细浮层）增加 `!params || !params.length` 判断
- `installDailyTooltip` 的 `mousemove` 增加 series 存在性和 `convertFromPixel` 结果校验

### 2026-04-25 `80a19d8` fix: support alternative column names in Excel import

**问题**：用户 Excel 列名与模板预期不一致：
- `年月` 代替 `月`（且为 Date 类型）
- `年季` 代替 `季`（且为 `'2024-1'` 字符串）
- `年月日` 代替 `日期`
- 缺失 `月标签`

**改动**：
- 引入 `COL_ALIASES` 别名映射系统：`年月`→`月`、`年季`→`季`、`年月日`→`日期`
- `transformRow` 支持 Date 类型的月份提取（`getMonth() + 1`）
- `transformRow` 支持字符串季度解析（`'2024-1'` → `1`）
- `月标签` 从必需列改为可选，缺失时自动衍生 `${year}年${month}月`
- `validateColumns` 使用 `resolveCol` 进行别名匹配
- 更新 UI 提示和 README 数据要求说明

### 2026-04-25 `071a59f` refactor: switch to in-browser Excel import via SheetJS

**架构大改**：从「Python 预生成 SQLite + 本地 HTTP 服务」改为「纯浏览器端解析」。

**原因**：Python 方案要求非技术用户跑脚本 + 起服务，双击 HTML 直接报错「data.db 未找到」。

**改动**：
- 删除 `build_db.py`、`requirements.txt`
- HTML 新增 SheetJS CDN 引用
- 新增导入 UI：三态 boot overlay（loading/empty/error）
- 新增 `parseAndBuild()`：SheetJS 解析 → sql.js 建库 → 批量插入
- 新增 IndexedDB 持久化：`idbGet`/`idbPut`
- 新增「重新导入」按钮
- README 改写为纯浏览器使用说明

### 2026-04-25 `fd72bf3` chore: update .gitignore and add README

- 添加 `.gitignore`，屏蔽敏感 Excel 文件
- 添加 README

### 2026-04-25 `21335e5` refactor: replace inline RAW_DATA with sql.js + daily tooltip

- 将原先内联在 JS 中的 `RAW_DATA`（JSON 数组）改为 sql.js 查询
- 新增日明细 sparkline tooltip

### 2026-04-25 `713f46e` feat: add build_db.py and python deps for sqlite pipeline

- 初版 Python 预处理方案
- `build_db.py`：Excel → SQLite，金额转分，维度空白填「未知」
- `requirements.txt`：pandas + openpyxl

### 更早 `9d41639` 经营分析模板：保费趋势对比看板

- 初代版本，内联 JSON 数据，无 SQLite，无日明细

---

## 已知问题与排查

### 1. ECharts `p[0].coord` 崩溃

**状态**：已尝试修复（`0e00917` 移除 axisPointer + 加错误追踪），待验证。

**排查步骤**：
1. F12 打开控制台，看红色报错前是否有 `主图渲染失败:` / `同比图渲染失败:` 等前缀
2. 若「主图渲染失败」→ 检查 `series` 数据是否含 `NaN`/`undefined`
3. 若「同比图渲染失败」→ 检查 `yoySeries` 是否全为 `null`（base 为 0）
4. 若「结构图渲染失败」→ 检查 `pieData` 是否含 `NaN`

**临时绕过**：若主图持续崩溃，可尝试在 `render()` 中注释掉 `mainChartInstance.setOption(...)`，仅保留 KPI 和饼图。

### 2. SheetJS 日期解析时区问题

`cellDates: true` 时，Excel 的日期序列号转为 JS Date 对象。如果用户电脑时区与数据生成时区差异大（如 UTC-8  vs UTC+8），`getMonth()` 可能返回前一个月。**当前用户在中国时区，暂未触发**。

**保险做法**：`parseDateCell` 中优先使用 `XLSX.SSF.parse_date_code()`（基于 Excel 序列号，无时区问题），再用 `Date` 对象兜底。

### 3. 大文件性能

6.5 万行 Excel 解析约 5–15 秒，期间 UI 显示 spinner。瓶颈在 SheetJS 的 `sheet_to_json`，非 sql.js 插入。

### 4. IndexedDB 容量限制

浏览器对 IndexedDB 的单条记录大小通常有几百 MB 上限。6.5 万行导出后 db 约 8–12 MB，远未触及。

---

## 开发注意事项

### 修改图表配置时

ECharts `setOption(obj, true)` 的第二个参数 `true` 表示 `notMerge`（完全替换）。修改系列数据时不需要手动 `clear()`，直接 `setOption` 即可。但 tooltip/axisPointer 等配置如果在上一次 `setOption` 中设置，后续不传入不会自动清除——`notMerge=true` 会清空未指定的组件。

### sql.js 多语句执行

`db.run(sql)` 只能执行单条 SQL。建表 + 6 条索引必须用 `db.exec(sql)`（支持多语句分号分隔）。`BEGIN`/`COMMIT`/`ANALYZE` 同理。

### 金额精度

**所有金额运算必须走「分」**：
- 入库：`Math.round(parseFloat(v) * 100)`
- 查询：`SUM(col) / 100.0`
- 严禁在 JS 中直接对元做浮点累加

### 列名校验

新增列名别名时，需同时修改三处：
1. `COL_ALIASES` 常量
2. `resolveCol()` 逻辑（如无特殊逻辑则自动支持）
3. UI 提示文本（`.boot-cols-hint`）
4. README「数据要求」

### 新增维度/指标

1. `FILTER_KEYS` 增加条目（`key` 是中文显示名，`col` 是 SQLite 列名，`sel` 是 DOM id）
2. HTML 中新增 `<select id="selXxx">`
3. `METRIC_MAP` 增加口径映射
4. `SCHEMA_SQL` / `INSERT_SQL` / `transformRow` 同步新增列

### 扩展 Schema（新增表字段）

当前 Schema 已支持新旧两套表结构共 32 列。如需再增字段：
1. `SCHEMA_SQL` 的 `CREATE TABLE` 中新增列定义
2. `INSERT_SQL` 的列名列表和 `VALUES` 占位符同步增加
3. `transformRow` 的 return 数组末尾追加新字段值
4. `ALL_DIM_COLS` 或新增常量中注册字段中文名（用于 `colMap` 自动映射）
5. `collectMeta` 如为金额指标，需在 `SUM(...)` 中追加

### 日期时间字段处理

投保时间、承保时间、入账时间、回销时间等字段通过 `fmtDateTime()` 处理：
- `Date` 对象 → `YYYY-MM-DD HH:MM:SS` 字符串
- 字符串 → 原样 trim
- `null`/`空` → SQLite `NULL`

SheetJS `cellDates: true` 会将 Excel 日期/时间单元格转为 JS Date 对象，可直接传入 `fmtDateTime()`。

### 基准年切换

修改 HTML 顶部 `const BASE_YEAR = '2024'` 即可。所有同比逻辑（YoY 图、KPI 卡片）均引用此常量。

### 清理浏览器数据

浏览器 DevTools → Application → IndexedDB → `business-analysis-template` → 删除 `kv` store。

---

## 协作规范（必读）

> 以下规则适用于所有参与此项目的人员，确保换电脑后能完全接手。

### 1. 每次更改必须同步到 GitHub

- 任何代码修改完成后，**必须** `git add` + `git commit` + `git push` 到 `master` 分支
- Commit message 必须说明「改了什么」和「为什么改」，禁止无意义的 message（如 `update`、`fix`）
- 禁止只在本地修改、长期不推送到远程

### 2. 必须做好完整说明文档

- 每次功能性修改，README「修改历史」章节必须追加新条目，包含：
  - **问题/背景**：为什么要改
  - **改动清单**：具体改了哪些文件、哪些函数/配置
  - **业务规则**：如有新增或变更的业务逻辑，必须写明
- 数据模型变更时，README「数据模型」表格必须同步更新
- 新增字段/指标时，README「数据要求」必须同步更新

### 3. 保证换电脑能完全理解

- 代码中的业务逻辑（如口径规则、计算公式、筛选条件）必须有注释或文档说明，不能仅靠代码本身推断
- 复杂的 SQL 查询、ECharts 配置、日期处理逻辑，必须在 README 或代码注释中解释设计意图
- 项目依赖（CDN 版本、浏览器兼容性要求）必须在 README「技术栈」中明确列出
