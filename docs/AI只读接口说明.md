# AI 只读接口说明

## 一、定位

本接口用于让 ChatGPT、自定义 GPT 或其他外部 AI 工具读取经营分析看板数据。除原有汇总接口外，新增四类日常导入原始明细的授权读取。接口只读，不允许导入 Excel、重新计算、设置目标、参数设置或权限管理。

2026-09-12：原始明细能力已随v1.0.155部署并通过公网验收，下列新增地址已可使用。管理员可直接读取，其他账号需开通“AI原始明细读取”。

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
| `GET /api/ai/raw-datasets` | 列出四类日常导入表是否可用、全部字段名称和数据库类型 | 否 |
| `GET /api/ai/raw-data/{dataset}` | 分页读取全部原始字段，可选列及精确筛选 | 否 |
| `GET /api/ai/openapi.json` | 返回 AI 只读 OpenAPI 描述 | 否 |

## 五、安全边界

1. 账号认证只复用身份和读取权限，不向AI开放任何写接口。
2. 普通账号只能读取其已有模块权限允许的数据；管理员账号可读取全部AI只读接口。新增明细接口需要独立的 `ai_raw_data`（AI原始明细读取）权限，高级和普通账号默认关闭，管理员可在权限管理中勾选授权。原有 `AI_READONLY_TOKEN` 只保留汇总能力，不能读取明细；已授权账号的 Basic 或登录会话可读取明细。
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

## 八、四类日常导入明细

### 保存范围

| dataset | 对应日常 Excel | 2026-09-12 本地核对字段数 |
|---|---|---:|
| `performance` | AI-经营分析业绩基表 | 34 |
| `jingdai` | 经代业绩分析 | 9 |
| `hr_data` | N1AI-人力基表 | 17 |
| `value_data` | AI-经营分析价值基表 | 8 |

导入程序保存首个工作表识别表头之后的有效命名列，汇总未使用的列也会写入原始表；后续新增字段自动扩列。以上数量仅为本次核验快照，API实际返回运行库当时存在的全部字段。

保存的不是整本 Excel 原样归档：列名会去除首尾空格，无名称列会清理；标题、格式、公式表达式及其余工作表不保存，公式读取的是缓存结果。经代尾部明确合计行会剔除，附带的“过滤条件”工作表不导入。类型由解析器推断，日期等会转换，不能承诺单元格文本格式、前导零等逐字保真。

默认导入按上传数据覆盖的完整月份替换旧明细，保留其他月份，并非保存历次上传的每个版本。原始API返回当前SQLite值，不再额外修改字段名、换算万元或将null补成零。不得把原始金额与看板万元直接混用。

本次只开放上述四张表，不包含客户清单、独立历史业绩表、目标、账号、权限、会话或其他数据库表。四张表自身含有的历史月份会全部可读，不自动限定当前年。

### 调用步骤

1. 使用有明细权限的现有账号认证，调用 `GET /api/ai/raw-datasets` 获取字段目录。
2. 调用 `GET /api/ai/raw-data/performance?limit=1000` 获取第一页，默认返回全部字段和所有期间。
3. 若 `hasMore=true`，把 `nextAfterRowId` 作为下一次的 `afterRowId`，同时将第一页的 `latestImportId` 作为 `expectedImportId`；保留相同dataset、列和筛选。一直读取到 `hasMore=false`。每页最多1000行，总读取行数不设此上限。
4. `columns` 可重复传入，例如 `columns=业务模式&columns=期交保费`，列名通过URL编码传递。筛选通过 `X-AI-Filters` 请求头传递JSON对象，如 `{"业务模式":"OTO","期交保费":0}`；中文必须用JSON Unicode转义生成ASCII头值，Python可使用 `json.dumps(filters, ensure_ascii=True)`。最多20个字段、8000字符，字段间为AND精确匹配。字符串、数字和null分别表示相应值或SQL空值。字段必须来自目录，不接受SQL表达式、模糊匹配或范围运算。筛选值不放URL，避免进入代理和服务的常规访问日志。

返回仍使用 `success/data/meta`。`data.rows` 为行对象数组，字段是原中文名称；`returnedRows` 是本页行数，`hasMore` 指示是否还有数据，尾页 `nextAfterRowId=null`。`afterRowId` 是内部分页游标，不是Excel行号、保单号或业务期间，不应跨导入继续使用。

目录中 `available=false` 表示该表尚不存在；查询不存在的表返回404。存在的空表或没有匹配结果返回200和空数组。字段或筛选无效返回400，页大小/游标参数超范围返回422，未认证返回401，未授权返回403。

分页读取的是每次请求的数据库视图，不是跨请求冻结快照。`expectedImportId` 可以检测新增已落库日常导入（success/partial），变化返回409并要求从首页重读；它不能检测所有离线重建、手工修改或数据库切换。完整批量读取期间应避免这些变更。`latestImportId` 是导入记录ID，`meta.updatedAt` 是响应时间，均不能作为业务截止日。业务期间以原始日期字段为准。

访问审计记录账号、数据集、返回行数及是否筛选，不写入原始行、筛选值或凭据。
