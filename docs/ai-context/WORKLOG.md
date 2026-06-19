# 工作日志

## 2026-06-19 v1.0.93 数据加载失败修复

- 现象：页面数据未完整加载，点击“重新计算”提示失败。
- 原因：`loadYearFromApi()` 将带 `asOf` 的缓存 key（如 `2026::2026-06-18`）误当作业务年份继续传入 `fetchProductData()` 和 mock 数据转换，导致 `/api/product-analysis` 请求出现 `year=2026::2026-06-18`，后端返回 422。
- 修复：区分 `cacheKey` 与 `yearLabel`；缓存仍按 `year + asOf` 隔离，业务接口和前端 mock 数据年份始终使用纯年份 `2026` / `2025`。
- 验证：新增前端静态回归断言；执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `230 passed, 1 warning`。

## 2026-06-19 v1.0.93 看板截至日期与经代同比口径修正

- 修复经代 6 月未满月同比口径：平台趋势、KPI 与日累计查询支持 `asOf`，选择 `2026-06-18` 时只统计至 6 月 18 日，去年同期自动映射为 `2025-06-18`，不再用 2025 年 6 月整月作比较。
- 页面右上角新增“数据截止”下拉控件；默认按当前系统日期上一天，若最新导入数据较系统日期滞后 2 天及以上，则按导入最新日期展示并提示“请注意数据口径”。
- 后端接口新增/透传 `asOf`：`/api/kpi`、`/api/platform-data`、`/api/platform-trend`、`/api/product-analysis`、`/api/org-analysis`、`/api/payment-period/{year}`。
- 前端切换截至日期后会清理运行缓存并刷新 KPI、业务平台趋势、产品结构、交期结构、机构维度、队伍分析等主要模块。
- 业务平台趋势切换到“月度”时默认取当前系统月份，不再固定为 4 月。
- 统一版本号到 `v1.0.93`，更新 README/CHANGELOG/页面缓存参数/后端版本常量/测试断言。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `230 passed, 1 warning`；警告为第三方 `python_multipart` 待弃用提示。

## 2026-06-19 KPI 概览经代数据复核

- 读取项目上下文、KPI 后端接口、经代 ETL 聚合、前端 KPI 卡片与目标配置链路。
- 复核当前本地库 `backend/business_data.db`：`get_kpi_data(2026)` 返回经代期交实绩 `31955.90` 万，去年同期 `19589.75` 万，日级截止为经代 `2026-05-25`、转型 `2026-05-24`。
- 发现当前 `target_config` 中 2026 目标 payload 为 `categories: null`，前端会回退到默认目标，经代期交默认目标为 `4800` 万；与 `targets_import.json` / `期交目标.xlsx` 中经代正式目标 `81900` 万不一致。
- 复核根目录最新 `经代业绩分析 (37).xlsx`：源文件已包含 `2026-06-19` 数据；按源文件汇总，2026 年经代期交截至 `2026-05-25` 为 `32169.5151` 万，截至 `2026-06-19` 为 `37665.5206` 万。
- 核心判断：当前 KPI 概览经代“实绩”读的是旧库数据；“达成率”若页面使用默认目标则明显不符合正式经营目标口径；“同比”公式可追溯，但当前结果基于旧库截至 5 月 25 日，不代表 6 月 19 日最新源文件口径。

## 2026-06-19 服务器端 KPI 概览经代数据复核

- 通过 SSH 只读检查服务器 `192.168.50.6`，`business-analysis.service` 运行中且开机启用，健康检查返回 `v1.0.92`，数据库最新期间为 `202606`。
- 服务器 `/opt/business-analysis/backend/business_data.db` 更新时间为 `2026-06-19 11:16:46`，`data_imports` 记录显示 4 份 `20260619` Excel 已由 Web 成功导入。
- 服务器经代聚合已更新到 `2026-06-19`：2026 年 1-6 月经代期交分别为 `3524.8880`、`8539.9853`、`9734.6173`、`5659.2924`、`5887.4486`、`4319.2889` 万；截至 `2026-06-19` YTD 为 `37665.5210` 万。
- 服务器经代去年同期截至 `2025-06-19` 为 `24487.2256` 万，同比为 `+53.8%`。
- 服务器 `target_config.payload` 结构正常，2026 经代期交年度目标为 `81900` 万；因此服务器端经代达成率应按 `37665.5210 / 81900 = 46.0%` 展示。
- 结论：本地库与服务器库状态不一致；服务器端经代 KPI 数据、正式目标和同比口径是最新状态，本地复核时发现的目标缺失问题仅存在于本地数据库。
- 补充复核 6 月单月同比：服务器经代 2026 年 6 月 1-19 日为 `4319.2890` 万，2025 年 6 月 1-19 日为 `3661.8091` 万，同日口径同比应为 `+18.0%`；若用 2025 年 6 月整月 `5932.3845` 万作分母，则得到 `-27.2%`，属于未满月对整月的非同口径比较，不应用作 6 月 MTD 同比。

## 2026-06-14 Ubuntu NAS 非 Docker 部署

- 任务：在局域网 Ubuntu NAS `192.168.50.8` 上按非 Docker 方式部署项目。
- 已做：上传当前源码到服务器临时目录，并同步到 `/opt/business-analysis`。
- 已做：安装/确认 Python 3、venv、pip、nginx、rsync 等依赖；创建后端虚拟环境并安装 `backend/requirements.txt`。
- 已做：初始化 SQLite 运行库，创建首个管理员账号；初始密码通过部署进程环境注入，未写入仓库、项目记忆或日志。
- 已做：安装并启用 `business-analysis.service`，配置 nginx 反向代理并启用 80 端口访问。
- 验证：`systemctl is-active business-analysis` 返回 `active`，`systemctl is-enabled business-analysis` 返回 `enabled`。
- 验证：`systemctl is-active nginx` 返回 `active`，`systemctl is-enabled nginx` 返回 `enabled`。
- 验证：`curl http://127.0.0.1:45679/api/health` 返回 `status=ok`，版本 `v1.0.92`。
- 验证：从 Windows 本机执行 `curl.exe -I http://192.168.50.8/` 返回 `HTTP/1.1 200 OK`。
- 遗留：服务器当前没有业务 Excel 原始表，`rebuild_aggregates_from_raw_tables.py` 提示 raw tables empty；页面可访问，但业务数据需要后续上传 Excel 或恢复已有 SQLite 数据库。

## 2026-06-13 容器化部署方案

- 任务：为项目补充可部署 Docker 镜像方案，并上传到 GitHub 以便后续复用。
- 已做：新增 `Dockerfile`、`.dockerignore`、`docker-compose.yml`、`.github/workflows/docker-image.yml`、`docs/DOCKER.md`。
- 已做：新增项目级 AI 上下文最小文件，记录容器化部署结论、运行方式和后续待办。
- 关键判断：不把镜像 tar 文件提交进 GitHub 仓库，改用 GitHub Container Registry 保存镜像，更适合版本化和服务器部署。
- 验证：本地环境未安装 Docker，无法本机构建；已完成 YAML 解析、Dockerfile/文档存在性检查、`backend/main.py` 与 `backend/db/connection.py` 语法编译检查。
- 验证：执行 `pytest -q`，结果为 `226 passed, 3 failed, 1 warning`；失败集中在既有 `tests/test_transform_and_trend.py` 产品结构断言，未涉及本次新增 Docker 文件。
- 遗留：需要在 GitHub Actions 页面确认首次 workflow 是否成功；如 GHCR 包默认私有，需要按使用场景调整包访问权限；既有产品结构测试失败需单独排查。

## 2026-06-13 开发环境完善

- 安装并验证本机开发工具：Python 3.12.10、Git 2.54.0、uv 0.11.21。
- 将 Python、Python Scripts、Git、uv 路径加入用户 PATH；当前 Codex 子进程可能仍需显式注入 PATH，新终端通常会生效。
- 创建本地 `.venv` 并安装 `requirements.txt` 与 `backend/requirements.txt`。
- 运行完整测试：`python -m pytest -q`，结果为 `229 passed, 1 warning`。
- 发现并修复 Windows 预检脚本依赖问题：`uv run` 原先未显式安装 requirements，导致新环境缺少 pytest。
- 同步修复 Bash 测试脚本，使其同时安装根目录与后端依赖。
- 将 `.venv/` 加入 `.gitignore`，避免本地虚拟环境进入版本状态。
- 重新执行 Windows 预检：`scripts\preflight.ps1` 通过，测试 `229 passed, 1 warning`，数据质量审计 `issues: 0`。
