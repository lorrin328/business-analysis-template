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
| `/api/platform-data?year=2026` | GET | 平台聚合数据，供生产页面年度数据装载使用 |
| `/api/platform-trend?year=2026&month=5&businessLines=经代,OTO&metric=qj` | GET | 平台趋势统一接口 |
| `/api/org-analysis?year=2026` | GET | 机构分析 |
| `/api/team-analysis?year=2026` | GET | 队伍分析 |
| `/api/team-enhanced-analysis?year=2026&periodType=quarter&periodValue=2&businessLines=OTO,证保&orgs=上海` | GET | 队伍结构与产能分析；支持年度/季度/月度，输出司龄段、产能段、业务模式/机构 P25/P50/P75 及达标人数 |
| `/api/product-analysis?year=2026&dimension=product_mix&months=4,5,6&metric=gm` | GET | 产品结构，支持业务线、机构、月份和保费口径筛选 |
| `/api/targets?year=2026` | GET | 读取目标配置 |
| `/api/targets?year=2026` | POST | 保存目标配置并同步写入 `target_values` |
| `/api/import` | POST | 上传 Excel 并导入 |

## 兼容接口

为保证历史页面和外部书签不丢功能，暂时保留 `/api/data/{year}`、`/api/kpi/{year}`、`/api/product/{year}`、`/api/org-kpi/{year}`、`/api/targets/{year}`。当前生产页面读取链路已优先使用统一响应接口；兼容接口集中维护在 `backend/api/legacy.py`，响应头会返回 `X-API-Deprecated: true` 和 `X-API-Replacement`，后续删除前需先确认无人调用。
