# 运行手册

## 市场研判服务

- 安装与完整运维流程见 `docs/MARKET_ANALYSIS.md`。
- 生产服务：`market-analysis.service`；定时器：`market-analysis.timer`，按 `OnUnitActiveSec=3d` 滚动运行。
- 运行数据：`/var/lib/business-analysis-market`；受保护配置：`/etc/business-analysis-market/market-analysis.env`。
- 手工触发：`sudo systemctl start market-analysis.service`；查看结果：`sudo systemctl status market-analysis.service --no-pager` 和 `sudo journalctl -u market-analysis.service -n 100 --no-pager`。
- 失败处置：先查看 `status.json` 和 journal；不要删除 `latest.json`，模型失败时网页应继续展示上一期有效报告。
- 失败恢复：服务保留6小时修复检查点；来源标题、日期、摘录等确定性错误会复用已有报告，不重新执行整轮模型研究。systemd 只进行一次延迟2分钟的自动重试，连续失败后应读取校验错误再处理。
- 证据边界：独立抓取负责确定真实标题、发布日期、内容哈希和50字内原文锚点；发布前模块“事实”会收敛为最接近的已核验原文，判断、影响和行动属于模型推演，页面不得把二者混为同一事实层。
- 凭据轮换：同时更新 DeepSeek Key 和主应用/研究服务的 AI 只读 Token；验证旧值失效后再启用 timer。

## Windows 本地开发环境

### 前置工具

- Python 3.10+
- Git
- uv

### 推荐检查命令

```powershell
python --version
uv --version
git --version
```

### 安装依赖并运行测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### Windows 预检

```powershell
powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1
```

若当前进程尚未继承新 PATH，可重启 PowerShell 后重试。

## Docker 镜像构建与发布

GitHub Actions 会在 `master` 分支推送、`v*` tag 推送或手动触发时构建镜像：

```bash
ghcr.io/lorrin328/business-analysis-template:latest
```

## Docker Compose 启动

```bash
docker compose up -d
docker compose logs -f business-analysis
```

访问：

```text
http://<server-ip>:45679
```

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

## Ubuntu systemd 部署

当前非 Docker 部署路径：

```text
代码：/opt/business-analysis
数据库：/var/lib/business-analysis/business_data.db
日志：/var/log/business-analysis/app.log
```

代码部署：

```bash
sudo bash deploy/deploy.sh
```

已有生产数据库时，部署脚本默认不再使用 `/opt/business-analysis/` 根目录中的 Excel 全量重建数据库，避免旧 Excel 覆盖 Web 页面导入后的最新数据。脚本会用 SQLite Online Backup API 备份当前库，校验完整性并生成 SHA256 元数据，再基于 SQLite 原始明细表重建聚合；重建失败时部署中止。

如确需用服务器根目录 Excel 全量重建数据库，必须显式执行：

```bash
REBUILD_DATABASE=1 sudo bash deploy/deploy.sh
```

服务：

```bash
sudo systemctl status business-analysis
sudo systemctl restart business-analysis
sudo journalctl -u business-analysis -f
```

nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx
```

部署后静态资源边界验证：

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/honor
curl -I http://127.0.0.1/scheme-calculator.html
curl -I http://127.0.0.1/js/api-client.js

# 以下路径必须返回 404
curl -I http://127.0.0.1/backend/main.py
curl -I http://127.0.0.1/deploy/nginx.conf
curl -I http://127.0.0.1/.git/config
curl -I http://127.0.0.1/backend/business_data.db
curl -I http://127.0.0.1/targets_import.json
curl -I http://127.0.0.1/Dockerfile
curl -I http://127.0.0.1/requirements.txt
```

若任一敏感路径返回 200，立即停止对外访问，检查 `/etc/nginx/sites-enabled/business-analysis` 是否已同步仓库中的 `deploy/nginx.conf`，执行 `sudo nginx -t && sudo systemctl reload nginx` 后重新验证。

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

首次部署要求：

- 初始化首个管理员账号时必须提供 `DEFAULT_ADMIN_PASSWORD`。
- 初始密码应仅通过临时环境变量或安全配置注入，不得写入仓库、日志或项目记忆。
- 首次登录后建议立即修改管理员密码。
- 生产环境默认关闭公开自助注册；确需开放时在 `/opt/business-analysis/deploy/.admin_env` 设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 并重启服务，关闭时改为 `0` 或移除该配置并重启服务。
- `/opt/business-analysis/deploy/.admin_env`、`.ai_env`、`.webhook_env` 属于服务器运行时配置，部署脚本会保留并收敛为 root 管理；不得提交到 Git。
- webhook 自动部署已暂停。正常状态为 `webhook-deploy` disabled/inactive、`/etc/sudoers.d/webhook-deploy` 不存在、`/webhook/deploy` 返回 404。
- `/opt/business-analysis` 应为 `root:root` 且 `www-data` 不可写；仅 `/var/lib/business-analysis` 和 `/var/log/business-analysis` 归 `www-data`。

## 方案计算

### 页面入口

1. 登录主看板。
2. 点击顶部“方案计算”。
3. 在方案选择弹层中选择“2026年组发政策”。
4. 有 `scheme_upload` 权限时，可在“方案专用上传”区域上传 `组织发展追踪模板.xlsx`。

### 接口

```text
GET  /api/scheme/options
GET  /api/scheme/latest?schemeId=2026-org-dev-policy
POST /api/scheme/upload
```

上传字段：

```text
schemeId=2026-org-dev-policy
tracking=<.xlsx 文件>
```

### 权限

- `scheme_calculation`：查看方案列表和最近一次测算结果。
- `scheme_upload`：上传方案专用 Excel 并写入方案测算批次。

### 本地验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scheme_calculation.py tests\test_frontend_static.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

### 注意

- 方案上传独立于主经营数据导入，不会写入 `/api/upload` 使用的 `data_imports` 或经营聚合表。
- 当前“2026年组发政策”页面展示的是底稿测算结果与复核提示；推荐人奖励、有效保单 45 日观察、回执回访、犹豫期、自保互保等字段补齐前，不能视为全自动最终结算结果。

## 荣誉体系过程追踪

### 月底最终版

1. 打开 `/honor.html`。
2. 选择年份和月份。
3. “过程截至”保持为空。
4. 点击“重新计算”。
5. 在“荣誉追踪”页签核对会员总览、机构排行、TOP3、新晋、晋升和会员清单。

### 月中过程版

1. 打开 `/honor.html`。
2. 选择年份和月份。
3. 在“过程截至”填写日期，例如 `2026-07-15`。
4. 点击“重新计算”。
5. 页面状态会显示“过程截至 YYYY-MM-DD”，该批次写入 `honor_import_batches.source_cutoff`。

### 注意事项

- 过程截至日不能早于所选月份首日；可以晚于月末，用于导入次月初清单后核对上月最终结果。
- 有承保/入账日期的保单按日期截断；同月缺承保/入账日期且无法判断是否已发生的记录会进入异常提示，不强行计入过程结果。
- 同一月份可以保留多个过程截至日批次；如需读取某个过程版本，可请求 `/api/honor/dashboard?year=2026&month=7&asOf=2026-07-15`。

## 数据与日志

- Docker SQLite 数据库：`business-analysis-data` volume，对应容器内 `/data/business_data.db`。
- Docker 应用日志：`business-analysis-logs` volume，对应容器内 `/app/backend/logs`。
- systemd 部署数据库：`/var/lib/business-analysis/business_data.db`。
- systemd 应用日志：`/var/log/business-analysis/app.log`。

## 回滚

如某次镜像异常，优先回滚到上一个 tag 或 sha 镜像。systemd 回滚应先停服务，使用 `backend/backup_database.py` 将 `/opt/business-analysis-backups/` 中通过完整性校验的数据库备份恢复到新的临时文件，核验后原子替换 `/var/lib/business-analysis/business_data.db`，再回退代码版本并重启服务；不得直接把 WAL 运行库主文件相互覆盖。
