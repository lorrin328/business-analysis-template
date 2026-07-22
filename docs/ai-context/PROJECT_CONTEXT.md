# 项目上下文

## 项目定位

本项目是太平人寿网电多元条线经营分析看板，服务经营分析、目标追踪、机构与队伍分析、产品结构分析、Excel 数据导入、权限管理、AI 只读接口、星钻联盟荣誉体系、人员管理和寿险市场滚动研判等场景。

## 技术栈

- 后端：FastAPI + SQLite
- 前端：原生 HTML/JS + ECharts
- 数据源：业绩、经代、人力、价值等 Excel 文件
- 部署：Ubuntu + Nginx + systemd + FastAPI，后端默认端口 `45679`
- 容器化：Docker 镜像运行 FastAPI，SQLite 与日志通过 volume 持久化
- 本地测试：pytest，Windows 推荐执行 `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1`

## 当前运行边界

- 生产入口为根目录 `经营分析模板.html`。
- 本地后端默认运行库为 `backend/business_data.db`；systemd 生产环境通过 `BUSINESS_ANALYSIS_DB` 固定为 `/var/lib/business-analysis/business_data.db`。
- 业务 `/api/` 默认需要登录；`/api/auth/`、`/api/health`、`/api/ai/` 为公开前缀。
- 首次初始化管理员必须通过 `DEFAULT_ADMIN_PASSWORD` 环境变量提供密码。
- 生产环境默认关闭公开自助注册；如需临时开放，必须显式设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1`。
- 默认镜像发布目标为 `ghcr.io/lorrin328/business-analysis-template`。
- 市场研判由独立 `market-ai` 账号调用 Claude Code + DeepSeek V4 Pro，每三天生成一次结构化报告；FastAPI 只读取已通过证据校验的 JSON，不在请求线程中启动模型。
- 市场研判生产数据目录为 `/var/lib/business-analysis-market`，受保护配置为 `/etc/business-analysis-market/market-analysis.env`，不得进入代码树。

## 关键约束

- 不得将 Excel 源文件、SQLite 运行库、日志、真实 Token、密码或连接串打入镜像或提交到仓库。
- 镜像只包含应用代码和 Python 依赖；业务数据由运行时上传或挂载恢复。
