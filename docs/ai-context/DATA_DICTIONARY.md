# 数据字典

## 2026-07-20 可信计算与运行存储边界

| 数据项 | 规则 |
|---|---|
| systemd SQLite | `/var/lib/business-analysis/business_data.db`，由 `BUSINESS_ANALYSIS_DB` 注入。 |
| systemd 日志 | `/var/log/business-analysis`，由 `BUSINESS_ANALYSIS_LOG_DIR` 注入。 |
| 人均保费 | 用户确认任意日期范围均正常计算：所选区间转型期交保费 ÷ 覆盖自然月数 ÷ 覆盖月份月均在职人力。人力仍是月级精度，单日、月中截止及跨月自定义范围按覆盖月份折算。 |
| 正式目标 | 必须同时包含 5 类指标、6 条业务线，且每项含年度值、4 季度值、12 月度值；不完整配置不参与达成率。 |
| 目标更新人 | 只取已认证 Session 的用户名，不接受客户端传入的 `updatedBy`。 |
| 方案成功批次 | 不得存在高等级校验告警；缺关键表、空明细、关键公式缓存缺失均返回 422，最近成功批次保持不变。 |
| 前端 seed | 生产文件仅保留空运行容器，经营数据必须来自鉴权 API。 |

## 2026-07-20 全局统计范围

| 参数/字段 | 说明 |
|---|---|
| `rangeType` | `ytd` 年度累计、`month` 整月、`day` 单日、`custom` 自定义区间。 |
| `startDate` | 起始日，格式 `YYYY-MM-DD`，首尾均包含；`custom` 必填。 |
| `endDate` | 结束日，格式 `YYYY-MM-DD`；超过最新日级数据日时按最新数据日截断。 |
| `asOf` | 旧截止日参数，继续兼容；未提供 `endDate` 时作为结束日。 |
| `period.targetMode` | `year` 使用年度目标、`month` 使用月度目标、`none` 不计算目标达成率。 |
| `period.precision` | `premium/product/paymentPeriod=day`，`headcount/value=month`。 |

### 表：`agg_payment_period_daily`

| 字段 | 说明 |
|---|---|
| `year` / `month` / `day` | 交费期间聚合的自然日。 |
| `business_type` | `转型` 或 `经代`。 |
| `channel` / `org` | 业务模式、机构；经代业务模式为空，机构为经代机构。 |
| `category` | 趸交、1年交、2年交、3年交、5年交、10年及以上、短期险等交期分类。 |
| `qj_premium` / `gm_premium` / `count` | 当日分类期交保费、规模保费、件数；金额单位万元。 |

统计范围接入接口：`/api/kpi`、`/api/org-analysis`、`/api/product-analysis`、`/api/payment-period/{year}`、`/api/export/excel`。平台趋势和队伍分析保留模块自身的年/季/月期间，不跟随非年度全局范围截断。

## 容器运行数据

| 数据项 | 路径/变量 | 说明 |
|---|---|---|
| SQLite 数据库 | `BUSINESS_ANALYSIS_DB` | 默认 `/data/business_data.db`，由 Docker volume 持久化。 |
| 应用日志 | `/app/backend/logs` | 由 Docker volume 持久化。 |
| 上传文件限制 | `MAX_UPLOAD_SIZE_MB` | Compose 默认 `100`。 |
| 公开自助注册 | `AUTH_ALLOW_PUBLIC_REGISTRATION` | 生产环境默认关闭；显式设置 `1` 才允许 `/api/auth/register`。 |
| systemd 运行时配置 | `/opt/business-analysis/deploy/.admin_env` | 生产管理员初始化、注册开关等运行时配置；不进入 Git，部署时保留。 |
| AI 只读接口配置 | `/opt/business-analysis/deploy/.ai_env` | AI 只读 token 等运行时配置；不进入 Git，部署时保留。 |
| 自动部署配置 | `/opt/business-analysis/deploy/.webhook_env` | GitHub Webhook secret；不进入 Git，部署时保留。 |

## 业务口径参考

业务表、字段、指标口径优先参考：

- `docs/指标口径手册.md`
- `docs/数据流说明.md`
- `docs/数据规范/保单数据规范.md`
- `docs/数据规范/人力数据规范.md`

## 2026-07-09 方案计算模块

### 表：`scheme_import_batches`

| 字段 | 说明 |
|---|---|
| `id` | 方案测算批次 ID。 |
| `scheme_id` | 方案唯一标识，当前为 `2026-org-dev-policy`。 |
| `scheme_name` | 方案名称，当前为 `2026年组发政策`。 |
| `rule_version` | 规则版本，当前为 `2026-org-dev-v1`。 |
| `file_name` / `file_hash` / `file_size` | 上传的方案 Excel 文件名、SHA256、大小。 |
| `summary_json` | 方案、摘要、复核提示、口径说明、来源审计。 |
| `detail_json` | 三类测算对象及 7-12 月明细。 |
| `status` / `error_message` | 导入状态与错误信息。 |
| `imported_by` / `imported_at` | 上传人和上传时间。 |

### 当前方案：`2026年组发政策`

- 来源文件：`组织发展追踪模板.xlsx`。
- 工作表：`业绩清单`、`人力清单`、`参数表`、`入职主管`、`入职经理`、`晋升主管`。
- 展示分组：`引才奖-主管`、`引才奖-经理`、`晋升育成`。
- 当前已解析指标：团队数、达标团队、维持资格、淘汰状态、团队人力、主管架构、开单率、首期标保、奖励、组织育成奖、星钻育成奖、最终奖励。
- 当前复核缺口：推荐人、推荐关系、推荐人当月活动人力、有效保单 45 日内撤保退保、回执回访、犹豫期、自保互保、活动主管/经理校验、育成奖实际发放对象。

## 2026-07-01 星钻联盟荣誉体系口径

- 适用范围：2026 年 OTO、证保外勤销售人员；蚁桥/网服不参与星钻 MVP 计算。
- 月度个人达标：OTO 为个人月度承保标保不低于 `20000` 且至少 1 件长险；证保为个人月度承保标保不低于 `30000` 且至少 1 件长险。
- 管理职团队达标：OTO 主管为团队星钻人力不低于 `4` 且团队月度承保标保不低于 `100000`；OTO 经理为团队星钻人力不低于 `12` 且团队月度承保标保不低于 `320000`；证保主管为团队星钻人力不低于 `4` 且团队月度承保标保不低于 `100000`。当前未配置证保经理获钻规则。
- 证保季度通算：自然季度结束后，按固定 3 个月判断；季度内 3 个月每个月均至少 1 件长险，且季度标保合计不低于 `90000`，则该季度 3 个月均计为达标。不按人员在职月数缩短季度。
- 星曜钻石流转：按“人员 + 身份轨道”分别连续计算，身份轨道包括 `个人`、`主管`、`经理`。个人轨道只看本人月度达标；主管/经理轨道只看对应团队达标；同一管理职人员的个人轨道和团队轨道互不合并、互不抵扣。各轨道未达标扣 1 钻至 0；证保个人轨道当月至少 1 件长险但未达标时保号不扣；非在职按该轨道清零处理。
- 标保折算：优先按 `年化规保 × 缴费年限折算系数` 复算；短期险 `0`，趸交 `0.1`，2-4 年 `0.3`，5-9 年 `0.5`，10 年及以上 `1.0`。无法复算且为长险时回退源表 `折算保费`。
- 长险判断：优先使用 `performance.长短险`；包含短险含义的记录不计入，明确长期/一年期以上或缴费年限可推断为长期的记录计入。
- 回销观察：未显式设置 `HONOR_AS_OF_DATE` 时，按统计月月末后 45 天作为观察截止日；观察期内未回销暂不剔除，超过观察期仍未回销或回销超 45 天计入异常并不计入保费。
- 冲销/退保净额：正向保单先判断是否符合星钻统计条件；已计入统计的正向保单，如出现同一投保单号负向冲销，则负向标保和负向件数参与净额扣回；正向保单本身未计入统计的，后续负向记录不再重复扣减。负向冲销的团队扣回沿用对应有效正向保单的团队归属。源表明确 `承保件数=0` 的调整记录按 0 件处理，不默认算作 1 件。
- 等级分布：dashboard API 的 `levels` 表示已入会会员等级分布，只统计 `membership_level <> '未入会'` 的身份轨道；追踪池和未入会人员通过追踪人力、累计追踪池和人员明细另行展示。
- 过程截至日：荣誉重算支持 `asOf` / `sourceCutoff`，保存到 `honor_import_batches.source_cutoff`；当前月源保单按承保/入账日期不晚于截至日纳入，缺日期且无法判断是否已发生的同月记录进入异常提示。
- 荣誉追踪 dashboard：`/api/honor/dashboard` 新增 `tracking`，包含 `overview`、`orgMembers`、`newMembers`、`topContributors`、`promotions`、`memberRoster`。会员数按身份轨道统计，不按自然人去重。
- 荣誉追踪当月件数：`tracking_policy_count` 为追踪展示件数，按当前月投保单去重，剔除 `长短险=一年期` 且非“一年期以上”的一年期/医疗类件数，以及短期类件数；`longterm_policy_count` 仍为底层月度计算件数。
- 新星人力：当年入职，入职月起 4 个月内累计钻石达到 3 颗及以上。
- 证保季度边界：已按同事底稿确认采用自然季度 3 个月固定判断；每个月均需有长险且季度标保合计不低于 `9万`。
- 当前数据缺口：自保/互保、4M/13M 继续率、投诉、违规、合同制外勤、政治面貌等方案规则暂无稳定源字段，暂作为待补数据源或人工复核项。

## 2026-06-29 产品分类标识口径

- 转型业务商保年金：来源为业绩基表 `是否商保年金产品`，值为“是”时计入 `agg_org_performance.product_annuity`。
- 转型业务保障类产品：来源为业绩基表 `是否社会保障型产品`，值为“是”时计入 `agg_org_performance.product_protection`。
- 转型业务个人养老金：业绩基表已包含 `是否个人养老金`，当前用于保留数据源字段，现有 KPI 暂无独立个人养老金达成率卡片。
- 经代商保年金/保障类产品：继续来源于 `product_config`，按 `business_type='经代'`、`product_code=产品名称` 维护，保存后重算 `agg_jingdai.product_annuity` 与 `agg_jingdai.product_protection`。
- 参数设置模块展示范围：仅经代产品；转型 OTO、证保、蚁桥不再在参数设置中展示或保存。
- 日级截止：`agg_org_daily_performance` 同步保存 `product_10year`、`product_annuity`、`product_protection`；`agg_jingdai_daily` 同步保存 `product_annuity`、`product_protection`。KPI 概览和机构维度年度累计在有日级数据时按 `asOf` 截止日读取这些日级字段，无日级数据时回退月表。

## 2026-06-19 全局截至日期口径（已由 2026-07-20 统一统计范围替代）

- 参数：`asOf=YYYY-MM-DD`，用于主看板全局数据截止日期。
- 精准同比前端接入口径：`/api/kpi`、`/api/org-analysis`。
- 后端兼容支持 `asOf` 的接口：`/api/kpi`、`/api/platform-data`、`/api/platform-trend`、`/api/product-analysis`、`/api/org-analysis`、`/api/payment-period/{year}`。
- 趋势展示口径：业务平台趋势和队伍趋势默认展示已有完整趋势数据，前端不再向 `/api/platform-data`、`/api/platform-trend` 传递 `asOf`。
- 默认规则：无用户选择时取当前系统日期上一天；若最新导入数据日期与系统日期相差 2 天及以上，则按导入数据最新日期为准，并在页面提示“请注意数据口径”。
- 日期选项：基于最新导入数据日期提供最近 3 天选项。
- 同比公式：`同比 = 本年截至 asOf 的累计值 / 去年同月同日累计值 - 1`；例如选择 `2026-06-18` 时，去年同期映射为 `2025-06-18`。
- 日级来源：KPI/机构维度同比优先使用 `agg_daily_performance`、`agg_jingdai_daily`、`agg_org_daily_performance` 按 `(month < cutoff_month OR month = cutoff_month AND day <= cutoff_day)` 截断。
- 产品结构：`dimension=product_mix` 时从 `performance` / `jingdai` 原始明细按日期截断。
- 交期结构：历史版本使用 `agg_payment_period` 月级聚合表；v1.0.104 起由 `agg_payment_period_daily` 支持同月内按日精确截断。
