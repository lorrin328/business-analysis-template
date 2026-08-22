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

### 推荐：使用现有看板用户名和密码

AI工具使用HTTP Basic认证，把现有看板用户名和密码放在标准`Authorization`请求头中：

```http
Authorization: Basic <用户名:密码的Base64编码>
```

账号方式不要求服务器配置`AI_READONLY_TOKEN`，并按账号现有模块权限控制可读范围：KPI接口需要KPI权限，机构接口需要机构权限，队伍接口需要队伍增强权限，综合快照同时需要KPI和机构权限。

账号密码必须通过HTTPS传输，不得放在URL、查询参数、OpenAPI文件、日志或提示词中。

### 兼容：网页登录会话或专用Token

通过`POST /api/auth/login`登录得到的会话Token也可直接访问：

```http
Authorization: Bearer <登录返回的会话Token>
```

为避免中断现有自动市场研判服务，仍兼容服务器受保护环境文件中的`AI_READONLY_TOKEN`：

```http
Authorization: Bearer <AI_READONLY_TOKEN>
```

也兼容`X-AI-Token`请求头。专用Token不再是人工配置AI读取接口的必需项。

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

1. 账号认证只复用身份和读取权限，不向AI开放任何写接口。
2. 普通账号只能读取其已有模块权限允许的数据；管理员账号可读取全部AI只读接口。
3. 不开放任何 `POST`、`PUT`、`DELETE` 业务写接口。
4. 不开放 SQLite 直连和任意 SQL 查询。
5. 不返回用户密码、会话、权限配置等账号管理数据。
6. 账号密码错误复用登录失败限流和锁定；AI访问会写入操作日志，管理员可审计真实操作人。

## 六、服务器配置（仅兼容Token需要）

systemd 服务会读取：

```text
/opt/business-analysis/deploy/.ai_env
```

仅现有自动服务仍需Token时配置：

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
