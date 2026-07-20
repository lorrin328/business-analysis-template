# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) and OpenClaw for safe deployment.

## 项目概述

太平人寿网电多元条线经营分析看板 — FastAPI + SQLite + 原生 HTML/JS + ECharts 单页应用。

## 部署流程

### 一键部署（推荐）

```bash
sudo bash deploy/deploy.sh
```

已有生产数据库时，`deploy.sh` 默认不再用服务器根目录 Excel 全量重建数据库，避免旧 Excel 覆盖 Web 页面导入后的最新数据。如确需从 Excel 强制重建，使用：

```bash
REBUILD_DATABASE=1 sudo bash deploy/deploy.sh
```

### 可信发布包部署

从已经通过测试并提交的 Git commit 生成归档，上传到服务器临时目录后，在归档根目录执行 `sudo bash deploy/deploy.sh`。不要直接以 `/opt/business-analysis` 中的运行副本作为发布源，也不要把应用目录重新授权给 `www-data`。

部署脚本负责代码同步、依赖安装、数据库迁移与一致性备份、聚合重建、root 只读权限、systemd 和 nginx 更新。仅代码更新且保留现有数据库时使用：

```bash
REBUILD_DATABASE=0 sudo bash deploy/deploy.sh
```

## 关键配置注意项

### nginx client_max_body_size（必须）

**上传 4 份 Excel 合计约 16MB，nginx 默认限制仅 1MB，会导致 413 错误。** `deploy/nginx.conf` 已配置 `client_max_body_size 100m`，部署时必须确保该配置生效。

### 数据库重建

当 Excel 源文件更新后，需在服务器上重建数据库：

```bash
cd /opt/business-analysis/backend
sudo -u www-data BUSINESS_ANALYSIS_DB=/var/lib/business-analysis/business_data.db ./venv/bin/python rebuild_from_excels.py
```

或将新 Excel 文件放到 `/opt/business-analysis/` 目录后，通过 Web 上传界面导入。

注意：代码部署默认保护现有生产库，不会自动用旧 Excel 重建。只有明确需要以服务器根目录 Excel 作为新口径时，才使用 `REBUILD_DATABASE=1 sudo bash deploy/deploy.sh` 或手动执行 `rebuild_from_excels.py`。

### 文件权限

- `/opt/business-analysis/` 所有者为 `root:root`，应用账号不可写
- `/var/lib/business-analysis/` 所有者为 `www-data:www-data`，保存 SQLite 运行库
- `/var/log/business-analysis/` 所有者为 `www-data:www-data`，保存应用日志

## 常用运维命令

```bash
sudo systemctl status business-analysis
sudo journalctl -u business-analysis -f
sudo systemctl restart business-analysis
tail -f /var/log/business-analysis/app.log
sudo nginx -t && sudo systemctl reload nginx
```

## 数据备份

部署脚本会用 SQLite Online Backup API 将 `/var/lib/business-analysis/business_data.db` 备份到 `/opt/business-analysis-backups/`，同时生成包含 SHA256、`integrity_check` 和 `quick_check` 结果的 `.meta` 文件。

## Excel 文件说明

| 文件匹配模式 | 用途 | 大小 |
|-------------|------|------|
| `AI-经营分析业绩基表_*.xlsx` | 转型业务保单明细（OTO/证保/蚁桥） | ~10MB |
| `经代业绩分析.xlsx` | 经代渠道业务数据 | ~5MB |
| `N1AI-人力基表_*.xlsx` | 人力数据（在职/举绩） | ~1.2MB |
| `AI-经营分析价值基表_*.xlsx` | 价值保费数据 | ~12KB |

## 自动部署（已暂停）

GitHub Webhook 自动部署已因 root 权限链整改暂停。`deploy.sh` 会停用 `webhook-deploy`、删除 `/etc/sudoers.d/webhook-deploy`，nginx 对 `/webhook/deploy` 返回 404。恢复自动发布前必须使用 root-owned、应用账号不可写的固定部署入口并重新完成安全审计。

## 版本

当前版本见 `经营分析模板.html` 顶部 tag 标签。

## Docker 镜像部署

本项目已补充容器化部署路径，作为 Ubuntu systemd + nginx 部署方式的补充。

- 镜像发布目标：`ghcr.io/lorrin328/business-analysis-template:latest`
- 构建发布方式：推送到 `master`、推送 `v*` tag 或手动触发 GitHub Actions `Build Docker image`
- 本地编排文件：`docker-compose.yml`
- 详细说明：`docs/DOCKER.md`

容器化部署原则：

- 不将 Excel 源文件、SQLite 运行库、日志、真实密钥或 Token 打入镜像；
- SQLite 数据库通过 `BUSINESS_ANALYSIS_DB=/data/business_data.db` 写入 Docker volume；
- 日志通过 `/app/backend/logs` volume 持久化；
- 生产密钥只允许通过 `.env`、宿主机环境变量或平台 Secret 注入。
