# 数据字典

## 容器运行数据

| 数据项 | 路径/变量 | 说明 |
|---|---|---|
| SQLite 数据库 | `BUSINESS_ANALYSIS_DB` | 默认 `/data/business_data.db`，由 Docker volume 持久化。 |
| 应用日志 | `/app/backend/logs` | 由 Docker volume 持久化。 |
| 上传文件限制 | `MAX_UPLOAD_SIZE_MB` | Compose 默认 `100`。 |
| 公开自助注册 | `AUTH_ALLOW_PUBLIC_REGISTRATION` | 生产环境默认关闭；显式设置 `1` 才允许 `/api/auth/register`。 |

## 业务口径参考

业务表、字段、指标口径优先参考：

- `docs/指标口径手册.md`
- `docs/数据流说明.md`
- `docs/数据规范/保单数据规范.md`
- `docs/数据规范/人力数据规范.md`

## 2026-06-29 产品分类标识口径

- 转型业务商保年金：来源为业绩基表 `是否商保年金产品`，值为“是”时计入 `agg_org_performance.product_annuity`。
- 转型业务保障类产品：来源为业绩基表 `是否社会保障型产品`，值为“是”时计入 `agg_org_performance.product_protection`。
- 转型业务个人养老金：业绩基表已包含 `是否个人养老金`，当前用于保留数据源字段，现有 KPI 暂无独立个人养老金达成率卡片。
- 经代商保年金/保障类产品：继续来源于 `product_config`，按 `business_type='经代'`、`product_code=产品名称` 维护，保存后重算 `agg_jingdai.product_annuity` 与 `agg_jingdai.product_protection`。
- 参数设置模块展示范围：仅经代产品；转型 OTO、证保、蚁桥不再在参数设置中展示或保存。
- 日级截止：`agg_org_daily_performance` 同步保存 `product_10year`、`product_annuity`、`product_protection`；`agg_jingdai_daily` 同步保存 `product_annuity`、`product_protection`。KPI 概览和机构维度年度累计在有日级数据时按 `asOf` 截止日读取这些日级字段，无日级数据时回退月表。

## 2026-06-19 全局截至日期口径

- 参数：`asOf=YYYY-MM-DD`，用于主看板全局数据截止日期。
- 精准同比前端接入口径：`/api/kpi`、`/api/org-analysis`。
- 后端兼容支持 `asOf` 的接口：`/api/kpi`、`/api/platform-data`、`/api/platform-trend`、`/api/product-analysis`、`/api/org-analysis`、`/api/payment-period/{year}`。
- 趋势展示口径：业务平台趋势和队伍趋势默认展示已有完整趋势数据，前端不再向 `/api/platform-data`、`/api/platform-trend` 传递 `asOf`。
- 默认规则：无用户选择时取当前系统日期上一天；若最新导入数据日期与系统日期相差 2 天及以上，则按导入数据最新日期为准，并在页面提示“请注意数据口径”。
- 日期选项：基于最新导入数据日期提供最近 3 天选项。
- 同比公式：`同比 = 本年截至 asOf 的累计值 / 去年同月同日累计值 - 1`；例如选择 `2026-06-18` 时，去年同期映射为 `2025-06-18`。
- 日级来源：KPI/机构维度同比优先使用 `agg_daily_performance`、`agg_jingdai_daily`、`agg_org_daily_performance` 按 `(month < cutoff_month OR month = cutoff_month AND day <= cutoff_day)` 截断。
- 产品结构：`dimension=product_mix` 时从 `performance` / `jingdai` 原始明细按日期截断。
- 交期结构：当前使用 `agg_payment_period` 月级聚合表，随 `asOf` 截至月份截断，暂不支持同月内按日精确截断。
