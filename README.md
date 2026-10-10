# 经营分析看板 - 太平人寿网电多元条线

保险经营分析单页看板，采用 **FastAPI + SQLite + 原生 HTML/JS + ECharts**。核心目标：数据处理准确、指标口径统一、页面清晰、多人访问稳定。

- 当前版本：见根目录 [`VERSION`](./VERSION)（唯一版本来源，后端经 `backend/config/version.py` 读取）。
- 逐版本变更：[CHANGELOG.md](./CHANGELOG.md)；整理前的 README 完整历史：[docs/修订记录/README_版本历史_至v1.0.164.md](./docs/修订记录/README_版本历史_至v1.0.164.md)。
- 文档索引：[docs/README.md](./docs/README.md)；部署与协作规则：[AGENTS.md](./AGENTS.md)。
- 最近一次重要变更：市场研判模型路由，见 [docs/MODEL_ROUTING_20260930.md](./docs/MODEL_ROUTING_20260930.md)。

本项目覆盖以下业务线：

| 业务线 | 说明 |
|--------|------|
| **OTO** | 线上到线下融合业务 |
| **证保** | 证券渠道保险业务 |
| **蚁桥** | 蚂蚁渠道桥梁业务（网服） |
| **经代** | 线上保险经纪/代理业务 |

**当前重点**：正在推动 **职域营销** 新模式，主要与 **团险渠道** 合作开展，目前处于 **试点阶段**。

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `经营分析模板.html` | **唯一生产页面**：完整看板，已合并目标设置、Excel 上传、图表展示与筛选交互 |
| `js/api-client.js` | **前端 API 客户端**：统一封装读取接口、登录态请求头和统一响应解包 |
| `backend/business_data.db` | **运行时 SQLite 数据库**：FastAPI 实际读写的聚合数据与目标数据，本文件不提交 Git |
| `targets_import.json` | **可选目标配置种子**：部署时在无目标数据的情况下导入 |
| `docs/` | 需求文档、修订记录、数据规范、功能逻辑与更新说明 |

---

## 核心模块

### 1. KPI 概览
- 期交保费达成率（整体 / 经代 / 转型 / OTO / 证保 / 蚁桥）
- 价值达成率
- 活动率（同比）
- 人均保费 / 人均产能

### 2. 业务分析
- **业务平台趋势**：支持年度/季度/月度维度，多业务系列复选加总，三种保费口径切换；季度、月度统一按日累计趋势展示，并加入上一年度同期同口径趋势线

### 3. 产品与交期结构
- **产品结构**：饼图展示产品分类占比，并以表格列示 OTO、证保、蚁桥、经代四类业务模式中期交保费占比最高的前三名产品及其模式内占比
- **交期结构**：按交期分类展示保费、保费占比、件数、件数占比，保留图表并增加表格化明细，便于经营复核

### 4. 机构维度
- 支持机构复选、年度/季度/月度切换
- 按机构 × 业务模式展示期交保费、价值保费、长险期交（年度）、10年期产品、商保年金、保障类产品
- 实际、目标、达成率、同比均按所选期间同口径计算

### 5. 队伍分析
- **队伍趋势**：人力规模、活动率、人均保费、人均产能
- 支持年度/季度维度，OTO/证保/蚁桥复选
- **队伍结构与产能分析**：在队伍趋势下方展示司龄段结构、产能段结构、零/负产能占比和标准人力贡献分析；支持年度、季度、月度和业务模式（全部、OTO、证保、蚁桥）切换；口径以 `hr_data` 人员月度原始表为样本，按人员和同一年月左关联 `performance` 保单明细，保留零/负产能人员，避免产能结构被高估

---

## 当前架构

> **运行入口边界**：主看板 `经营分析模板.html` 通过 `<script src="js/...">` 显式加载其所需的 `js/` 模块（以该 HTML 的 script 列表为准）；其余页面（`honor.html`、`customer-analysis.html` 等）加载各自专属脚本。未被任何 HTML 显式加载的 `js/` 文件不应视为运行时代码；新增或接入脚本必须同步更新 HTML 的 `<script>` 列表并通过前端静态测试（`tests/test_frontend_static.py`）。

## 本地测试环境

项目代码和部署脚本要求 **Python 3.10+**。完整测试及发布前检查还要求 **Node.js 18+**（用于税优测算的浏览器计算测试，无需npm依赖），运行前先确认`node --version`满足要求。Node.js仅是测试依赖，FastAPI生产服务和Docker运行镜像不依赖Node.js。本地建议使用 `scripts/test.sh` 运行测试，它会优先选择 `python3.12`、`python3.11`、`python3.10`，并在版本不符合时直接停止。

```bash
bash scripts/test.sh
```

如需指定解释器：

```bash
PYTHON=python3.11 bash scripts/test.sh
```

```text
Excel 基表
  -> FastAPI 后端导入
  -> 字段转换与数据校验
  -> SQLite 聚合表与目标表
  -> 统一 API
  -> 经营分析模板.html + ECharts 展示
```

主要目录：

| 目录 | 用途 |
|---|---|
| `backend/api/` | 统一 API 路由 |
| `backend/metrics/` | 指标公式中心 |
| `backend/config/` | 业务线、指标、机构、运行配置 |
| `backend/services/` | 数据转换、查询服务、响应格式 |
| `backend/validators/` | 导入、目标、机构校验 |
| `deploy/` | Ubuntu 部署文件 |
| `tests/` | 基础验收测试 |

## 数据流程

```
Excel 基表（4个文件）
    ↓  Python 解析 + 聚合
SQLite 数据库（backend/business_data.db）
    ↓  FastAPI 接口
生产 HTML 动态读取（platformMock + teamMock + 机构聚合）
    ↓  浏览器渲染
ECharts 图表
```

### 数据源

| 文件名 | 内容 | 规模说明 |
|--------|------|------|
| `AI-经营分析业绩基表_*.xlsx` | 转型业务保单明细（OTO/证保/蚁桥） | 日常增量按期间导入；2007—2026 全量历史库约 500 万行（v1.0.124 记录 517 万） |
| `AI-经营分析价值基表_*.xlsx` | 价值保费数据 | 行数很少（百余行量级） |
| `N1AI-人力基表_*.xlsx` | 人力数据（在职/活动人力） | 按月人员记录 |
| `经代业绩分析.xlsx` | 经代渠道业绩数据 | 十万行量级 |

### 数据更新步骤

1. 启动 FastAPI 服务。
2. 通过页面上传 Excel，或调用 `/api/import`。
3. 后端完成解析、校验、聚合并写入 `backend/business_data.db`。
4. 页面通过 API 重新读取数据并刷新 KPI、平台趋势、机构、队伍和产品图表。

---

## 目标设置

目标数据已迁移为服务端优先：

1. 目标设置功能已合并入 `经营分析模板.html`，不再维护独立 `目标设置.html`。
2. 当前生产页面保存目标时优先调用统一接口 `/api/targets?year=YYYY`。
3. 后端同时写入 `target_config` JSON 配置和 `target_values` 行表。
4. `localStorage` 仅作为后端不可用时的降级缓存，不作为正式多人共享数据源。
5. 修改目标后可通过页面“重新计算”刷新相关 KPI 和图表。

支持指标：
- 期交保费
- 价值保费
- 商保年金
- 保障类产品
- 10 年期产品

每个指标分年度/季度/月度三个维度，支持整体/经代/转型/OTO/证保/蚁桥六个口径。

---

## 技术栈

| 组件 | 用途 | 来源 |
|------|------|------|
| ECharts 5.x | 图表渲染 | CDN |
| SQLite (Python) | 数据存储与聚合 | Python 标准库 + pandas |
| FastAPI | 后端 API 与导入服务 | `backend/main.py` |
| SQLite | 服务端数据存储 | `backend/business_data.db` |
| 纯 HTML + JS | 前端展示 | `经营分析模板.html` |

---

## 本地运行

```bash
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 45679
```

访问：`http://127.0.0.1:45679/`

## 测试

```bash
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.uv-python uv run python -m pytest -q
```

## Ubuntu 部署

```bash
sudo bash deploy/deploy.sh
```

已有生产数据库时，部署脚本默认保护现有数据库，不再用服务器根目录中的 Excel 自动全量重建，避免旧 Excel 覆盖 Web 页面导入的新数据。如确需以服务器 Excel 作为新基准强制重建，执行：

```bash
REBUILD_DATABASE=1 sudo bash deploy/deploy.sh
```

纯代码升级继续使用 `REBUILD_DATABASE=0`。部署脚本会在主服务在线期间完成SQLite一致性备份和候选依赖环境准备；requirements未变化且现有venv自检通过时直接复用。`init_db()` 后仅当发现本次新增且标记 `requires_aggregate_rebuild=1` 的迁移时自动重建聚合，否则保留现有聚合，避免约十分钟级维护窗口。如需主动按SQLite原始明细重算：

```bash
REBUILD_DATABASE=0 REBUILD_AGGREGATES=1 sudo bash deploy/deploy.sh
```

新聚合表、聚合字段或会改变历史聚合结果的逻辑变更，必须同步新增唯一迁移版本并设置 `requires_aggregate_rebuild=1`；该安全标记优先于 `REBUILD_AGGREGATES=0`。

首次部署且数据库中尚无管理员账号时，需在部署环境文件中配置管理员初始密码：

```bash
sudo mkdir -p /opt/business-analysis/deploy
echo 'DEFAULT_ADMIN_PASSWORD=请替换为强密码' | sudo tee -a /opt/business-analysis/deploy/.admin_env
sudo chmod 600 /opt/business-analysis/deploy/.admin_env
```

生产环境默认关闭公开自助注册。确需临时开放注册窗口时，可在受控内网环境中显式配置：

```bash
echo 'AUTH_ALLOW_PUBLIC_REGISTRATION=1' | sudo tee -a /opt/business-analysis/deploy/.admin_env
sudo systemctl restart business-analysis
```

完成账号开通后建议移除该配置或改为 `AUTH_ALLOW_PUBLIC_REGISTRATION=0`，并重启服务。

详细说明见 `docs/部署说明.md`。

---

## 开发说明

### 业务口径映射

Excel 原始口径 → 看板口径：

| Excel 口径 | 看板口径 |
|-----------|---------|
| 证券 | 证保 |
| 网服 | 蚁桥 |
| OTO | OTO |

### 保费类型定义

- **期交保费**：非趸交的长期险规模保费 + 短期险规模保费 + 长险趸交规模保费 × 0.1
- **规模保费（年化规保）**：各类产品的规模保费
- **折算保费**：长险趸交 × 0.1 + [3年,5年) × 0.3 + [5年,10年) × 0.5 + 10年及以上 × 1 + 短险 × 0.1

### 指标计算

- **活动率** = 活动人力 / 在职人力 × 100%
- **人均保费** = 月均新单保费 / 月均在职人力
- **人均产能** = 新单保费 / 月均活动人力

---
## 协作规范

1. **每次更改必须同步到 GitHub**：`git add` + `git commit` + `git push`
2. **Commit message 必须说明「改了什么」和「为什么改」**
3. **版本变更记入 `CHANGELOG.md`，README 只描述当前状态，不再追加版本流水账**

## Docker 镜像

项目已支持构建可部署 Docker 镜像，并通过 GitHub Actions 发布到 GitHub Container Registry：

```bash
ghcr.io/lorrin328/business-analysis-template:latest
```

运行示例：

```bash
docker run -d \
  --name business-analysis \
  --restart unless-stopped \
  -p 45679:45679 \
  -e BUSINESS_ANALYSIS_DB=/data/business_data.db \
  -v business-analysis-data:/data \
  -v business-analysis-logs:/app/backend/logs \
  ghcr.io/lorrin328/business-analysis-template:latest
```

详细部署、环境变量、数据持久化和回滚说明见 [docs/DOCKER.md](./docs/DOCKER.md)。
