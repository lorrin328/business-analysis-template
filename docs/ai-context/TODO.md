# 待办事项

## 2026-06-29 自动部署待恢复

- 【已完成 2026-06-29】已通过 SSH 手工部署 `v1.0.97` 到 `192.168.50.6`，并同步 20260629 四份源 Excel 后重建数据库；线上 `/api/health` 返回 `app_version=v1.0.97`、`page_version=v1.0.97`、`latest_period=202606`。
- 【高】修复服务器 `192.168.50.6` 的 `webhook-deploy` 服务：当前 `/opt/business-analysis/deploy/.webhook_env` 缺失，服务 inactive，`/webhook/deploy` 返回 `502 Bad Gateway`，GitHub push 不能触发自动部署。
- 【高】恢复 webhook 时必须同时处理服务器 `WEBHOOK_SECRET` 与 GitHub Webhook Secret 的一致性；不要只在服务器生成新密钥，否则 GitHub 签名会校验失败。

## 2026-06-20 审计整改建议

- 【已完成 2026-06-24】生产环境默认关闭公开自助注册，保留 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 作为显式开关；普通用户默认只读经营数据的范围仍需按实际保密要求确认。
- 【已完成 2026-06-24】修复权限管理页用户名拼接 `onclick` 的前端注入风险：后端限制用户名字符集，前端改为 `data-action` / `data-user-id` / `data-username` 加事件绑定，不在内联事件属性里拼接用户输入。
- 【高】本地如需继续复核最新经营数据，应先用 2026-06-19 四份 Excel 重建 `backend/business_data.db`，并导入正式目标，避免默认目标影响达成率判断。
- 【中】如业务要求交期结构支持 6 月 18 日/6 月 19 日等日级切换，新增日级交期聚合表或改为按原始明细实时聚合。
- 【中】补充生产安全基线：HTTPS、账号开通审批、密码复杂度/失败锁定、Session 清理、备份恢复演练和操作审计留存周期。
- 【已完成 2026-06-24】将 `pyproject.toml`、`VERSION`、README 当前版本口径统一治理；当前应用版本为 `v1.0.96`。
- 【低】清理前端超大脚本和内联 `innerHTML` 拼接模式，逐步收敛为可测试、可复用的渲染组件或安全模板函数。

## KPI 与数据口径

- 【已完成 2026-06-29】转型业务商保年金/保障类产品改为读取业绩基表标识列，参数设置仅保留经代产品分类维护。
- 本地 `backend/business_data.db` 曾发现与服务器库不一致；服务器库已确认 2026 目标和 2026-06-19 数据正常。后续如需本地复核最新数据，应先用根目录最新四份 Excel 重建本地库。
- 若业务要求交期结构在同月内也按 `asOf` 精确到日，需要新增日级交期聚合表，或将 `/api/payment-period/{year}` 改为从 `performance` / `jingdai` 原始明细实时聚合。
- 后续新增业务模块时，必须先确认模块用途：若是 KPI/机构同比复核，接入 `asOf` 精准同日口径；若是趋势展示，默认展示完整已有数据，不随 `asOf` 截断。

## 部署与容器

- 推送到 GitHub 后检查 Actions `Build Docker image` 是否成功。
- 在 GitHub Packages/GHCR 中确认 `ghcr.io/lorrin328/business-analysis-template:latest` 已生成。
- 在目标 Ubuntu/NAS 机器上执行一次 `docker pull` 和 `docker run` 冒烟验证。
- 按生产访问方式补充 nginx 反向代理到 Docker 容器的正式配置。
- 明确容器部署时 `.env` 示例文件，记录必要但不含真实值的环境变量。
- 根据是否多人访问，补充备份和恢复脚本，重点覆盖 `/data/business_data.db` 和 `/opt/business-analysis/backend/business_data.db`。

## 开发环境

- 新开 PowerShell 后执行 `python --version`、`uv --version`、`git --version`，确认用户 PATH 已被新终端继承。
- 后续如需统一依赖管理，可评估是否把运行依赖迁入 `pyproject.toml`，减少 requirements 与脚本之间的重复。

## 项目文档

- `docs/数据流说明.md` 中仍提到旧的 `backend/aggregator.py`，需要后续按当前 `backend/etl/` 与 `backend/rebuild_from_excels.py` 链路更新。
