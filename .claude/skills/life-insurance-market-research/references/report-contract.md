# 网页报告契约

输出必须是 JSON 对象，`schemaVersion` 为 `1.0`，包含：

- `reportId`、`title`、`generatedAt`、`period`、`model`、`reviewStatus`；自动发布只能标记为 `machine_validated`，不得冒充人工审核；
- `coverage`：查询主题数、来源数、官方来源数、微信公众号来源数和研究边界；
- `executiveSummary`：一句主判断、一段短说明和证据编号；
- `changeSignals`：`persistent`、`strengthened`、`reversed`、`new`、`expired` 五类数组；
- `modules`：四层原子研究卡片；
- `actions`：条线行动提示；
- `sources`：证据台账；
- `limitations`：不可得资料、来源缺口和适用边界。

## 原子研究卡片

每个 `modules` 项只表达一个核心结论，字段为：

- `id`、`section`、`title`、`question`；
- `topicKey`：跨期稳定的英文小写主题标识，相同主题不得每期重新编号；
- `fact`：已核验事实；
- `judgment`：基于事实的分析判断；
- `impact`：对网电多元条线的影响；
- `watchCondition`：继续观察指标或判断失效条件；
- `confidence`：`high`、`medium`、`low`；
- `evidenceIds`；
- `history`：本期相对历史的状态、起始日期和上一报告编号。

每个模块必须且只能被一条 `changeSignals` 记录引用。变化记录必须含相同 `topicKey`、当前 `relatedModuleIds`、非空 `evidenceIds`；除 `new` 外还必须引用该主题最新一期真实存在且更早的 `previousReportId`，并沿用该主题最初的 `history.since`。

## 数量与长度

- 每层 1—4 个模块，总计 4—16 个；
- 每类变化信号不超过 16 条，行动不超过 6 条；页面默认只展开每类前 3 条，避免信息堆叠；
- 模块标题不超过 40 字，执行摘要不超过 240 字；
- `fact`、`judgment`、`impact`、`watchCondition` 各不超过 180 字；
- 来源 `excerpt` 必须是正文中可逐字复核的原文片段，不超过 50 字。

页面不会展示整篇长文。执行摘要、五类变化信号、四层模块、行动提示和证据台账将分别渲染，因此不要把不同问题塞入同一个字段。
