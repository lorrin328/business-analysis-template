# WORKLOG

## 2026-06-13

- 任务：为项目补充可部署 Docker 镜像方案，并上传到 GitHub 以便后续复用。
- 已做：新增 `Dockerfile`、`.dockerignore`、`docker-compose.yml`、`.github/workflows/docker-image.yml`、`docs/DOCKER.md`。
- 已做：新增项目级 AI 上下文最小文件，记录容器化部署结论、运行方式和后续待办。
- 关键判断：不把镜像 tar 文件提交进 GitHub 仓库，改用 GitHub Container Registry 保存镜像，更适合版本化和服务器部署。
- 验证：本地环境未安装 Docker，无法本机构建；已完成 YAML 解析、Dockerfile/文档存在性检查、`backend/main.py` 与 `backend/db/connection.py` 语法编译检查。
- 验证：执行 `pytest -q`，结果为 `226 passed, 3 failed, 1 warning`；失败集中在既有 `tests/test_transform_and_trend.py` 产品结构断言，未涉及本次新增 Docker 文件。
- 遗留：需要在 GitHub Actions 页面确认首次 workflow 是否成功；如 GHCR 包默认私有，需要按使用场景调整包访问权限；既有产品结构测试失败需单独排查。

## 2026-06-14

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
