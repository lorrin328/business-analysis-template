# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and OpenClaw for automated deployment.

## 项目概述

太平人寿网电多元条线经营分析看板 — FastAPI + SQLite + 原生 HTML/JS + ECharts 单页应用。

## 部署流程

### 一键部署（推荐）

```bash
sudo bash deploy/deploy.sh
```

### 手动部署步骤

```bash
# 1. 同步代码到服务器
sudo rsync -a --delete \
  --exclude='.git' --exclude='node_modules' \
  --exclude='backend/__pycache__' --exclude='*.xlsx' \
  ./ /opt/business-analysis/

# 2. 安装 Python 依赖
cd /opt/business-analysis/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. 初始化/重建数据库（从 Excel 文件）
./venv/bin/python rebuild_from_excels.py

# 4. 安装 nginx 配置
sudo cp /opt/business-analysis/deploy/nginx.conf /etc/nginx/sites-available/business-analysis
sudo ln -sf /etc/nginx/sites-available/business-analysis /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 5. 安装并启动 systemd 服务
sudo cp /opt/business-analysis/deploy/systemd.service /etc/systemd/system/business-analysis.service
sudo systemctl daemon-reload
sudo systemctl enable --now business-analysis

# 6. 设置权限
sudo chown -R www-data:www-data /opt/business-analysis
```

### 仅更新代码（不重建数据库）

```bash
sudo rsync -a --delete \
  --exclude='.git' --exclude='node_modules' \
  --exclude='backend/__pycache__' --exclude='*.xlsx' \
  --exclude='business_data.db' \
  ./ /opt/business-analysis/

sudo systemctl restart business-analysis
sudo nginx -t && sudo systemctl reload nginx
```

## 关键配置注意项

### nginx client_max_body_size（必须）

**上传 4 份 Excel 合计约 16MB，nginx 默认限制仅 1MB，会导致 413 错误。** `deploy/nginx.conf` 已配置 `client_max_body_size 100m`，部署时必须确保该配置生效。

### 数据库重建

当 Excel 源文件更新后，需在服务器上重建数据库：

```bash
cd /opt/business-analysis/backend
sudo -u www-data ./venv/bin/python rebuild_from_excels.py
```

或将新 Excel 文件放到 `/opt/business-analysis/` 目录后，通过 Web 上传界面导入。

### 文件权限

- `/opt/business-analysis/` 所有者为 `www-data:www-data`
- `backend/logs/` 目录必须可写
- `business_data.db` 必须可写

## 常用运维命令

```bash
sudo systemctl status business-analysis
sudo journalctl -u business-analysis -f
sudo systemctl restart business-analysis
tail -f /opt/business-analysis/backend/logs/app.log
sudo nginx -t && sudo systemctl reload nginx
```

## 数据备份

部署脚本会在覆盖前备份 `business_data.db` 到 `/opt/business-analysis-backups/`。

## Excel 文件说明

| 文件匹配模式 | 用途 | 大小 |
|-------------|------|------|
| `AI-经营分析业绩基表_*.xlsx` | 转型业务保单明细（OTO/证保/蚁桥） | ~10MB |
| `经代业绩分析.xlsx` | 经代渠道业务数据 | ~5MB |
| `N1AI-人力基表_*.xlsx` | 人力数据（在职/举绩） | ~1.2MB |
| `AI-经营分析价值基表_*.xlsx` | 价值保费数据 | ~12KB |

## 版本

当前版本见 `经营分析模板.html` 顶部 tag 标签。
