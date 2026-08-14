# 项目上下文

## 项目定位

本项目是太平人寿网电多元条线经营分析看板，服务经营分析、目标追踪、机构与队伍分析、产品结构分析、客户分析、Excel 数据导入、权限管理、AI 只读接口、星钻联盟荣誉体系、人员管理和寿险市场滚动研判等场景。

## 技术栈

- 后端：FastAPI + SQLite
- 前端：原生 HTML/JS + ECharts
- 数据源：业绩、客户、经代、人力、价值等 CSV/Excel 文件
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
- 市场研判由独立`market-ai`账号调用Claude Code + DeepSeek V4；Flash负责前置来源侦察，程序并发核验候选，Pro负责首次深度研究，Flash负责第一次定向修复，失败再由Pro升级一次。微信公众号只有公开直达页且标题、账号主体、正文锚点和哈希全部核验通过时才能纳入；不设数量硬指标。每天北京时间凌晨1点检查，距上次成功报告满3个自然日时生成结构化报告。发布需同时通过来源独立验证和不低于9.0分的五维质量门槛；FastAPI只读取已发布JSON，不在请求线程中启动模型。
- 市场研判生产数据目录为 `/var/lib/business-analysis-market`，受保护配置为 `/etc/business-analysis-market/market-analysis.env`，不得进入代码树。
- 全量历史和客户源通过命令行写入生产在线备份候选库，完成对账、聚合和完整性校验后原子切换；Web导入链不承接数百万行首次装载。
- 客户分析页面为 `/customer-analysis`，当前覆盖OTO、证保、蚁桥；除新老客、持单和状态外，提供按首现月、首现后12个月、首现当年度观察的新客经营页签，支持业务、机构、长险和产品筛选。客户状态为源清单截止日快照，不等同于13个月或25个月继续率。
- 客户分析内提供受权限控制的客户清单CSV/XLSX增量导入：浏览器分片上传，后台流式预检，确认后只更新客户归属与保单状态，不产生业绩；应用不设置固定文件大小、文件数和行数上限，临时数据在成功、失败或过期后清理。

## 关键约束

- 不得将 Excel 源文件、SQLite 运行库、日志、真实 Token、密码或连接串打入镜像或提交到仓库。
- 镜像只包含应用代码和 Python 依赖；业务数据由运行时上传或挂载恢复。
