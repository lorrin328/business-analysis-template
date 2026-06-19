# 项目上下文

## 项目定位

本项目是太平人寿网电多元条线经营分析看板，服务经营分析、目标追踪、机构与队伍分析、产品结构分析、Excel 数据导入、权限管理、AI 只读接口、星钻联盟荣誉体系和人员管理等场景。

## 技术栈

- 后端：FastAPI + SQLite
- 前端：原生 HTML/JS + ECharts
- 数据源：业绩、经代、人力、价值等 Excel 文件
- 部署：Ubuntu + Nginx + systemd + FastAPI，后端默认端口 `45679`
- 容器化：Docker 镜像运行 FastAPI，SQLite 与日志通过 volume 持久化
- 本地测试：pytest，Windows 推荐执行 `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1`

## 当前运行边界

- 生产入口为根目录 `经营分析模板.html`。
- 后端默认运行库为 `backend/business_data.db`，可通过 `BUSINESS_ANALYSIS_DB` 覆盖。
- 业务 `/api/` 默认需要登录；`/api/auth/`、`/api/health`、`/api/ai/` 为公开前缀。
- 首次初始化管理员必须通过 `DEFAULT_ADMIN_PASSWORD` 环境变量提供密码。
- 默认镜像发布目标为 `ghcr.io/lorrin328/business-analysis-template`。

## 关键约束

- 不得将 Excel 源文件、SQLite 运行库、日志、真实 Token、密码或连接串打入镜像或提交到仓库。
- 镜像只包含应用代码和 Python 依赖；业务数据由运行时上传或挂载恢复。
