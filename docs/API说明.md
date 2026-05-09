# API说明

## 统一返回格式

```json
{
  "success": true,
  "data": {},
  "message": "",
  "meta": {
    "year": 2026,
    "periodType": "month",
    "periodValue": 5,
    "businessLines": [],
    "orgs": [],
    "metric": "",
    "unit": "",
    "dataSource": "",
    "updatedAt": ""
  }
}
```

错误返回：

```json
{
  "success": false,
  "data": null,
  "message": "错误说明",
  "errorCode": "ERROR_CODE"
}
```

## 接口清单

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 健康检查 |
| `/api/kpi?year=2026` | GET | KPI 概览统一接口 |
| `/api/platform-trend?year=2026&month=5&businessLines=经代,OTO&metric=qj` | GET | 平台趋势统一接口 |
| `/api/org-analysis?year=2026` | GET | 机构分析 |
| `/api/team-analysis?year=2026` | GET | 队伍分析 |
| `/api/product-analysis?year=2026` | GET | 产品结构 |
| `/api/targets?year=2026` | GET | 读取目标配置 |
| `/api/targets?year=2026` | POST | 保存目标配置并同步写入 `target_values` |
| `/api/import` | POST | 上传 Excel 并导入 |

## 兼容接口

为保证现有页面不丢功能，保留 `/api/data/{year}`、`/api/kpi/{year}`、`/api/product/{year}`、`/api/org-kpi/{year}`、`/api/targets/{year}`。
