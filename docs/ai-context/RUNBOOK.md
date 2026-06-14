# RUNBOOK

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

## 数据与日志

- SQLite 数据库：`business-analysis-data` volume，对应容器内 `/data/business_data.db`。
- 应用日志：`business-analysis-logs` volume，对应容器内 `/app/backend/logs`。

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

访问：

```text
http://192.168.50.8/
```

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

首次部署要求：

- 初始化首个管理员账号时必须提供 `DEFAULT_ADMIN_PASSWORD`。
- 初始密码应仅通过临时环境变量或安全配置注入，不得写入仓库、日志或项目记忆。
- 首次登录后建议立即修改管理员密码。

## 回滚

如某次镜像异常，优先回滚到上一个 tag 或 sha 镜像：

```bash
docker compose pull
docker compose up -d
```

如果使用固定 tag，请先修改 `docker-compose.yml` 中的镜像 tag，再执行上述命令。
