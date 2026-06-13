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

## 回滚

如某次镜像异常，优先回滚到上一个 tag 或 sha 镜像：

```bash
docker compose pull
docker compose up -d
```

如果使用固定 tag，请先修改 `docker-compose.yml` 中的镜像 tag，再执行上述命令。
