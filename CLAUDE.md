# CLAUDE.md

本项目的 agent 规则、部署流程、权限与备份要求**只维护在 [AGENTS.md](./AGENTS.md)**，Claude Code 同样以它为准，请先阅读。

要点速览（详情以 AGENTS.md 为准）：

- 项目：太平人寿网电多元条线经营分析看板，FastAPI + SQLite + 原生 HTML/JS + ECharts。
- 当前版本：见根目录 `VERSION`（唯一版本来源）。
- 正式部署：可信发布包 + `sudo bash deploy/deploy.sh`；`/opt/business-analysis/` 归 root 只读，**不得**重新授权给 `www-data`。
- GitHub Webhook 自动部署已因 root 权限链整改暂停，**不得**恢复 sudoers 免密部署。
- 公网入口是极空间 Nginx Proxy Manager，Ubuntu 本机 nginx 80 端口仅为局域网备用入口。
- 公开资料采集协作使用 Hermes；旧 OpenClaw 已停用。
- 不得将 Excel 源文件、SQLite 运行库、日志、密钥、客户明细提交到 Git 或打入镜像。

> 整理说明：本文件旧版含手动 rsync 部署、`chown www-data`、webhook 免密 sudo 等已被安全整改废弃的步骤，已移除；原文可在 git 历史中查看。
