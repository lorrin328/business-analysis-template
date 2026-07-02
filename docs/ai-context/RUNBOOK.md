# 运行手册

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
/opt/business-analysis
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

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

首次部署要求：

- 初始化首个管理员账号时必须提供 `DEFAULT_ADMIN_PASSWORD`。
- 初始密码应仅通过临时环境变量或安全配置注入，不得写入仓库、日志或项目记忆。
- 首次登录后建议立即修改管理员密码。
- 生产环境默认关闭公开自助注册；确需开放时在 `/opt/business-analysis/deploy/.admin_env` 设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 并重启服务，关闭时改为 `0` 或移除该配置并重启服务。
- `/opt/business-analysis/deploy/.admin_env`、`.ai_env`、`.webhook_env` 属于服务器运行时配置，部署脚本会保留这些文件；不得提交到 Git。
- 自动部署 webhook 需要 `/opt/business-analysis/deploy/.webhook_env` 中的 `WEBHOOK_SECRET` 与 GitHub Webhook Secret 一致，并确认 `webhook-deploy` 服务为 `active`。

## 数据与日志

- Docker SQLite 数据库：`business-analysis-data` volume，对应容器内 `/data/business_data.db`。
- Docker 应用日志：`business-analysis-logs` volume，对应容器内 `/app/backend/logs`。
- systemd 部署数据库：`/opt/business-analysis/backend/business_data.db`。

## 回滚

如某次镜像异常，优先回滚到上一个 tag 或 sha 镜像；systemd 部署优先恢复 `/opt/business-analysis-backups/` 中的数据库备份，再回退代码版本并重启服务。
