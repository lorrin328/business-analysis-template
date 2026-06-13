# PROJECT_CONTEXT

## 项目定位

本项目是寿险网电多元条线经营分析看板，采用 FastAPI + SQLite + 原生 HTML/JS + ECharts 架构，服务于经营分析、指标追踪、Excel 数据导入、目标配置和多用户访问。

## 当前部署形态

- 既有主线：Ubuntu systemd + nginx + FastAPI。
- 新增容器化形态：Docker 镜像运行 FastAPI，端口 `45679`，SQLite 与日志通过 Docker volume 持久化。

## 关键约束

- 不得将 Excel 源文件、SQLite 运行库、日志、真实 Token、密码或连接串打入镜像或提交到仓库。
- 镜像只包含应用代码和 Python 依赖；业务数据由运行时上传或挂载恢复。
- 默认镜像发布目标为 `ghcr.io/lorrin328/business-analysis-template`。
