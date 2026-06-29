# 工作日志

## 2026-06-29 v1.0.97 服务器手工部署与 20260629 Excel 重建

- 部署对象：局域网服务器 `192.168.50.6`，应用目录 `/opt/business-analysis`。
- 已完成：将本地 `master` 最新代码部署到服务器，线上健康接口返回 `app_version=v1.0.97`、`page_version=v1.0.97`。
- 已完成：同步根目录四份最新源 Excel 到服务器，包括 `AI-经营分析业绩基表_20260629_09124457.xlsx`、`AI-经营分析价值基表_20260629_09030716.xlsx`、`N1AI-人力基表_20260629_09030310.xlsx`、`经代业绩分析 (39).xlsx`。
- 已完成：服务器旧 Excel 已备份到 `/opt/business-analysis-backups/excels.20260629_*`，SQLite 数据库部署脚本备份到 `/opt/business-analysis-backups/business_data.db.20260629_101509`。
- 已完成：以 `www-data` 运行 `backend/rebuild_from_excels.py` 重建数据库，确认读取 20260629 业绩、价值、人力和经代源文件；健康接口 `latest_period=202606`。
- 验证：线上 `product_config` 仅保留 `经代` 19 条；2026 年转型商保年金/保障类汇总为 `8924.85` / `11741.69`，与本地源 Excel 复核一致。
- 验证：服务器执行 `audit_data_quality.py --year 2026 --json` 返回 `status=ok`、`issue_count=0`。
- 遗留：服务器 `/opt/business-analysis/deploy/.webhook_env` 缺失，`webhook-deploy` 服务处于 inactive，`/webhook/deploy` 仍返回 502；自动部署需恢复并与 GitHub Webhook Secret 保持一致后再启用。

## 2026-06-29 部署推送与 webhook 阻塞

- 任务：将 `v1.0.97` 产品分类口径调整部署到服务器。
- 已完成：本地 `master` 提交 `1a00695 fix product config scope and deploy v1.0.97`，并成功推送到 GitHub `origin/master`。
- 部署验证：线上健康检查 `http://192.168.50.6/api/health` 仍返回 `app_version=v1.0.95`、`page_version=v1.0.95`、数据库路径 `/opt/business-analysis/backend/business_data.db`、最新期间 `202606`。
- 阻塞原因：`http://192.168.50.6/webhook/deploy` 返回 `502 Bad Gateway`，说明 nginx webhook 入口存在但后端 `webhook-deploy` 服务未正常响应；SSH 尝试 `yinli/root/ubuntu/www-data/codex@192.168.50.6` 均因无可用凭据失败，无法远程重启 webhook 服务或手工执行部署脚本。
- 当前状态：代码已到 GitHub，服务器未完成部署；需要服务器 SSH 凭据或在服务器本机执行 `sudo systemctl status webhook-deploy`、`sudo systemctl restart webhook-deploy` 后重新触发部署。

## 2026-06-29 v1.0.97 转型产品分类标识改为读取业绩基表

- 任务：根目录 2026-06-29 新业绩基表已包含转型业务 `是否个人养老金`、`是否商保年金产品`、`是否社会保障型产品` 标识，需取消转型产品分类在参数设置中的手工维护，仅保留经代手工配置。
- 已读取：`AGENTS.md`、`README.md`、`pyproject.toml`、`requirements.txt`、`backend/requirements.txt`、`backend/main.py`、`backend/rebuild_from_excels.py`、`backend/api/product_config.py`、`backend/services/product_config_service.py`、`backend/etl/aggregates/org.py`、`backend/etl/aggregates/jingdai.py`、`js/product-config-modal.js`、`js/kpi-cards.js`、相关测试和 `docs/ai-context/` 全量项目记忆。
- 数据核验：读取根目录 `AI-经营分析业绩基表_20260629_09124457.xlsx`，确认字段包含 `是否商保年金产品`、`是否社会保障型产品`、`是否个人养老金`，其中商保年金/社会保障型字段值为“是/否”，个人养老金字段值为“个养/非个养”。
- 逻辑调整：`aggregate_org_performance` 中转型业务 `product_annuity` 直接按 `是否商保年金产品=是` 汇总，`product_protection` 直接按 `是否社会保障型产品=是` 汇总，不再读取 `product_config`。
- 参数设置调整：`/api/product-config` 仅返回和保存 `business_type='经代'` 的产品配置；保存时跳过非经代 payload，只重算 `agg_jingdai`；Web 上传、`rebuild_from_excels.py` 和参数设置接口都会清理 `product_config` 中非经代历史行。
- 前端与导出：参数设置弹窗改为“经代产品分类”口径，导出说明改为“转型读取业绩基表标识；经代读取参数设置”，页面缓存版本提升到 `v1.0.97`。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_product_config.py -q`，结果 `16 passed`；执行 `.\.venv\Scripts\python.exe -m pytest tests\test_frontend_static.py -q`，结果 `42 passed`；执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `234 passed, 1 warning`；执行 `.\.venv\Scripts\python.exe backend\rebuild_from_excels.py`，根目录 4 份 2026-06-29 Excel 成功重建，加载年份 `[2022, 2023, 2024, 2025, 2026]`，并清理非经代 `product_config` 历史行 28 条；执行 `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1`，结果 `preflight ok`。

## 2026-06-24 v1.0.96 安全与展示审计整改

- 任务：围绕数据准确、安全、高效、扩展性和经营分析展示口径继续审计并落地一批低风险改进。
- 已读取：`AGENTS.md`、`README.md`、`pyproject.toml`、`docker-compose.yml`、`deploy/systemd.service`、`backend/auth.py`、`backend/api/auth_routes.py`、`js/auth-ui.js`、`js/kpi-cards.js`、`tests/` 相关用例和 `docs/ai-context/` 全量项目记忆。
- 安全整改：新增 `AUTH_ALLOW_PUBLIC_REGISTRATION` 开关，生产环境默认关闭公开自助注册；保留非生产环境默认可注册，便于本地测试；公开注册关闭时前端登录框隐藏“注册”按钮。
- 安全整改：新增用户名白名单校验，用户名仅支持中文、字母、数字、下划线、点、@ 和短横线；管理员创建、修改用户和公开注册均走同一校验。
- 前端整改：权限管理页新增/删除/统一保存从内联 `onclick` 改为 `data-action` 事件绑定，避免把用户名等用户输入拼入事件属性。
- 展示优化：KPI 概览下方新增经营摘要，基于整体期交达成率、同比、时间进度、经代/转型贡献、目标来源和 `asOf` 数据截止口径，输出“结论/关注/口径”三类可复核提示。
- 版本治理：运行版本、页面脚本缓存参数、`VERSION`、`backend/config/version.py`、`pyproject.toml` 和测试断言同步到 `v1.0.96`。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `234 passed, 1 warning`；执行 `backend\audit_data_quality.py --year 2026 --json`，结果 `status=ok, issue_count=0`；执行 `scripts\preflight.ps1`，结果 `preflight ok`。
- 注意：本次未重建本地 `backend/business_data.db`，本地运行库新鲜度问题仍需按需处理；用户在对话中暴露过邮箱授权码和 GitHub Token，本次未使用、未写入文件，建议用户自行轮换。

## 2026-06-20 项目整体审计

- 任务：审计项目是否符合业务要求、框架是否可扩展、整体逻辑是否严谨、数据是否准确。
- 已读取：`AGENTS.md`、`README.md`、`requirements.txt`、`pyproject.toml`、`Dockerfile`、`docker-compose.yml`、`deploy/`、`.github/workflows/docker-image.yml`、`backend/main.py`、`backend/auth.py`、`backend/db/`、`backend/services/`、`backend/metrics/`、主要 `backend/api/` 路由、前端 `js/` 关键脚本和 `docs/ai-context/` 全量项目记忆。
- 验证：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `231 passed, 1 warning`；执行 `backend\audit_data_quality.py --year 2026 --json`，结果 `status=ok, issue_count=0`；执行 `scripts\preflight.ps1`，结果 `preflight ok`。
- 业务口径判断：KPI、机构、趋势、交期、长险期交、标准人力等核心口径已集中在后端聚合、查询服务和指标配置中，`asOf` 精准同比与趋势完整展示的边界已有测试和项目记忆支撑。
- 数据准确性边界：当前本地 `backend/business_data.db` 仍截至 2026-05-25，`target_config` 为历史测试态 `categories: null` 且 `target_values` 为空；本地库不能作为 2026-06-19 最新经营口径依据。服务器端此前已确认 2026-06-19 数据与正式目标正常。
- 架构判断：现有 `api / services / db / etl / metrics / validators` 分层基本支持继续扩展，SQLite + 原生前端适合当前轻量看板，但后续并发写入、权限颗粒度、前端组件化和数据版本治理需要继续加强。
- 风险发现：公开注册普通用户后默认可读取核心经营数据；权限管理页把用户名拼接进 `onclick` 字符串参数，若用户名允许特殊字符，存在前端注入风险；交期结构当前按月级聚合，不能支持同月内按日精确切换；外部访问仍需补充 HTTPS/注册审批/账号治理策略。

## 2026-06-19 v1.0.95 趋势图展示口径修正

- 现象：业务平台趋势和队伍趋势在右上角选择截至日期后，被 `asOf` 截断，导致趋势数据不够完整，部分去年线出现下落或缺失。
- 原因：v1.0.93 将 `asOf` 同时接入 KPI、机构、平台趋势和队伍趋势链路；其中 KPI/机构需要精确同日同比，但趋势图更需要完整展示已有数据。
- 修复：前端 `/api/platform-data` 和 `/api/platform-trend` 请求不再传递 `asOf`；平台趋势日序列不再按 `asOf` 裁剪；截至日期上下文只从 KPI 返回值同步，避免平台数据默认口径覆盖用户选择。
- 保留：`/api/kpi` 与 `/api/org-analysis` 继续传递 `asOf`，用于 KPI 概览和机构维度精准同日同比。
- 版本：统一提升到 `v1.0.95`，刷新主页面、荣誉体系和人员管理页面脚本缓存参数。

## 2026-06-19 v1.0.94 数据加载失败修复

- 现象：页面数据未完整加载，点击“重新计算”提示失败。
- 原因：`loadYearFromApi()` 将带 `asOf` 的缓存 key（如 `2026::2026-06-18`）误当作业务年份继续传入 `fetchProductData()` 和 mock 数据转换，导致 `/api/product-analysis` 请求出现 `year=2026::2026-06-18`，后端返回 422。
- 修复：区分 `cacheKey` 与 `yearLabel`；缓存仍按 `year + asOf` 隔离，业务接口和前端 mock 数据年份始终使用纯年份 `2026` / `2025`；版本号提升到 `v1.0.94` 以刷新浏览器脚本缓存。
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
