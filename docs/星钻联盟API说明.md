# 星钻联盟 API 说明

所有接口均复用现有登录态，不使用独立 Token。

| 接口 | 权限 | 说明 |
|---|---|---|
| `GET /api/honor/field-audit` | `honor_audit` | 审计现有数据字段覆盖情况 |
| `POST /api/honor/recalculate` | `honor_recalculate` | 基于现有数据重算个人星钻 MVP |
| `GET /api/honor/summary` | `honor_view` | 星钻总览 KPI |
| `GET /api/honor/trend` | `honor_view` | 获钻/扣减趋势 |
| `GET /api/honor/orgs` | `honor_view` | 机构对比 |
| `GET /api/honor/persons` | `honor_view` | 人员汇总 |
| `GET /api/honor/exceptions` | `honor_view` | 异常清单 |
| `GET /api/honor/export` | `honor_export` | 多 Sheet Excel 导出 |
| `POST /api/honor/upload` | `honor_upload` | 本期预留，返回 501 |

重算请求体：

```json
{
  "year": 2026,
  "month": 5,
  "scope": "all",
  "force": true
}
```

所有重算、字段审计、导出和批次查看都会写入 `operation_logs`。
