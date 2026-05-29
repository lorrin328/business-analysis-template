# AI 只读接口说明

## 一、定位

本接口用于让 ChatGPT、自定义 GPT 或其他外部 AI 工具读取经营分析看板数据。接口只读，不允许导入 Excel、重新计算、设置目标、参数设置、权限管理或访问原始明细表。

## 二、访问地址

生产环境外网地址示例：

```text
https://kpi.bcyt.tech:30443/api/ai/dashboard-snapshot?year=2026
```

OpenAPI 描述：

```text
https://kpi.bcyt.tech:30443/api/ai/openapi.json
```

## 三、鉴权方式

AI 接口使用独立环境变量：

```text
AI_READONLY_TOKEN=<高强度随机字符串>
```

请求时二选一：

```http
Authorization: Bearer <AI_READONLY_TOKEN>
```

或：

```http
X-AI-Token: <AI_READONLY_TOKEN>
```

如果服务器未配置 `AI_READONLY_TOKEN`，接口返回 `503`，不提供任何经营数据。

## 四、接口清单

| 接口 | 作用 | 写操作 |
|---|---|---|
| `GET /api/ai/dashboard-snapshot` | 返回 KPI、机构摘要、目标摘要和指标口径 | 否 |
| `GET /api/ai/kpi` | 返回 KPI 概览原始聚合结果 | 否 |
| `GET /api/ai/org-summary` | 返回机构摘要，可选机构明细 | 否 |
| `GET /api/ai/team-summary` | 返回队伍结构与产能分析结果 | 否 |
| `GET /api/ai/metric-definitions` | 返回指标定义和展示约束 | 否 |
| `GET /api/ai/openapi.json` | 返回 AI 只读 OpenAPI 描述 | 否 |

## 五、安全边界

1. 不复用管理员账号。
2. 不开放后台登录态。
3. 不开放任何 `POST`、`PUT`、`DELETE` 写接口。
4. 不开放 SQLite 直连和任意 SQL 查询。
5. 不返回用户密码、会话、权限配置等账号管理数据。
6. AI 访问会写入操作日志，管理员可在“操作日志”中审计。

## 六、服务器配置

systemd 服务会读取：

```text
/opt/business-analysis/deploy/.ai_env
```

建议服务器上执行：

```bash
sudo mkdir -p /opt/business-analysis/deploy
echo 'AI_READONLY_TOKEN=请替换为高强度随机字符串' | sudo tee /opt/business-analysis/deploy/.ai_env
sudo chmod 600 /opt/business-analysis/deploy/.ai_env
sudo systemctl restart business-analysis
```

## 七、推荐给 ChatGPT 使用的主接口

优先使用：

```text
GET /api/ai/dashboard-snapshot?year=2026
```

该接口已经包含：

- 当前版本；
- 数据截止日；
- KPI 概览；
- 机构摘要；
- 目标配置摘要；
- 指标口径与展示约束。

如需减少返回体，可保持默认 `includeOrgDetail=false`；只有需要机构明细核对时，再使用 `includeOrgDetail=true`。
