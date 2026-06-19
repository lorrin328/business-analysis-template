# 数据字典

## 容器运行数据

| 数据项 | 路径/变量 | 说明 |
|---|---|---|
| SQLite 数据库 | `BUSINESS_ANALYSIS_DB` | 默认 `/data/business_data.db`，由 Docker volume 持久化。 |
| 应用日志 | `/app/backend/logs` | 由 Docker volume 持久化。 |
| 上传文件限制 | `MAX_UPLOAD_SIZE_MB` | Compose 默认 `100`。 |

## 业务口径参考

业务表、字段、指标口径优先参考：

- `docs/指标口径手册.md`
- `docs/数据流说明.md`
- `docs/数据规范/保单数据规范.md`
- `docs/数据规范/人力数据规范.md`

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
