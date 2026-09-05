# 项目上下文

## 最近核验状态（2026-09-05）

v1.0.150 已完成导入一致性、上传重入、迟到请求、产品空选、权限保持及目标数值校验修复，并部署 Ubuntu。Windows 810 项、Linux 811 项回归通过，GitHub PR #27 已合并并发布镜像；公网登录、业务接口、静态资源和实际页面筛选通过。新增强制聚合迁移从当前 SQLite 原始明细重建历史汇总，补回 2024 年活动人力 3,193 人月（非年度去重人数），独立 SQL 与演练一致；32 张原始及受保护表逐行不变，18 张汇总和客户事实与演练一致，全库完整性及严格审计通过。冻结恢复点已复制到独立 Windows 目录并通过哈希和完整性检查，16:57:54 发布状态确认为 `accepted`。详细证据见 `docs/RELEASE_REVIEW_v1.0.150.md`。

## 项目定位

本项目是太平人寿网电多元条线经营分析看板，服务经营分析、目标追踪、机构与队伍分析、产品结构分析、客户分析、Excel 数据导入、权限管理、AI 只读接口、星钻联盟荣誉体系、人员管理和寿险市场滚动研判等场景。

## 技术栈

- 后端：FastAPI + SQLite
- 前端：原生 HTML/JS + ECharts
- 数据源：业绩、客户、经代、人力、价值等 CSV/Excel 文件
- 部署：Ubuntu以systemd运行FastAPI，后端端口`45679`；正式公网入口由极空间Docker Nginx Proxy Manager提供TLS并反向代理到FastAPI，Ubuntu本机nginx仅为局域网80端口备用入口
- 容器化：Docker 镜像运行 FastAPI，SQLite 与日志通过 volume 持久化
- 本地测试：pytest，Windows 推荐执行 `powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1`

## 当前运行边界

- 生产入口为根目录 `经营分析模板.html`。
- 正式公网访问链路为“极空间 Nginx Proxy Manager → Ubuntu FastAPI:45679”；验收以公网HTTPS域名为准，Ubuntu本机80端口只做备用入口检查。
- 本地后端默认运行库为 `backend/business_data.db`；systemd 生产环境通过 `BUSINESS_ANALYSIS_DB` 固定为 `/var/lib/business-analysis/business_data.db`。
- 业务 `/api/` 默认需要登录；`/api/auth/`、`/api/health`、`/api/ai/` 为公开前缀。
- 首次初始化管理员必须通过 `DEFAULT_ADMIN_PASSWORD` 环境变量提供密码。
- 生产环境默认关闭公开自助注册；如需临时开放，必须显式设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1`。
- 默认镜像发布目标为 `ghcr.io/lorrin328/business-analysis-template`。
- 市场研判由独立`market-ai`账号调用Claude Code + DeepSeek，来源侦察、主研、首次修复、升级修复及轻量子任务统一使用实验模型`deepseek-v4-flash-vision-exp`，程序并发核验候选。微信公众号只有公开直达页且标题、账号主体、正文锚点和哈希全部核验通过时才能纳入；不设数量硬指标。知乎只通过官方搜索API发现，候选经公开原文复核后按C级观点证据使用，不替代A级监管原文或B级同业一手证据。每天北京时间凌晨1点检查，距上次成功报告满3个自然日时生成结构化报告。发布需同时通过来源独立验证和不低于9.0分的五维质量门槛；FastAPI只读取已发布JSON，不在请求线程中启动模型。
- 市场研判生产数据目录为 `/var/lib/business-analysis-market`，受保护配置为 `/etc/business-analysis-market/market-analysis.env`，不得进入代码树。
- 全量历史和客户源通过命令行写入生产在线备份候选库，完成对账、聚合和完整性校验后原子切换；Web导入链不承接数百万行首次装载。
- 可信代码发布采用低停机路径：SQLite在线备份和候选依赖环境准备在服务在线期间完成，requirements未变化时复用通过自检的venv；部署前后没有新增`requires_aggregate_rebuild=1`迁移时保留现有聚合，主服务通过健康检查后再同步市场研判附属单元。
- 客户分析页面为 `/customer-analysis`，当前覆盖OTO、证保、蚁桥；除新老客、持单和状态外，提供按首现月、首现后12个月、首现当年度观察的新客经营页签，支持业务、机构、长险和产品筛选。客户状态为源清单截止日快照，不等同于13个月或25个月继续率。
- 税优产品测算页面为 `/tax-calculator`（v1.0.143新增），以年收入、其他税前扣除、个人养老金扣除为主要输入，另可调整税优健康险本年可扣除金额；纯浏览器计算，不上传或保存个人输入、不改经营数据库。口径、政策来源及测试见 `docs/TAX_CALCULATOR.md`。
- 职拓业务分析页面为`/zhituo-analysis`，按业绩基表“是否职拓=是”统计，不改变原业务模式；支持年度、月份、机构复选及机构、人员、产品、产品类型、交期分析。
- 客户分析内提供受权限控制的客户清单CSV/XLSX增量导入：浏览器分片上传，后台流式预检，确认后只更新客户归属与保单状态，不产生业绩；应用不设置固定文件大小、文件数和行数上限，临时数据在成功、失败或过期后清理。

## 关键约束

- 不得将 Excel 源文件、SQLite 运行库、日志、真实 Token、密码或连接串打入镜像或提交到仓库。
- 镜像只包含应用代码和 Python 依赖；业务数据由运行时上传或挂载恢复。
