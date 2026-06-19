# 待办事项

## KPI 与数据口径

- 本地 `backend/business_data.db` 曾发现与服务器库不一致；服务器库已确认 2026 目标和 2026-06-19 数据正常。后续如需本地复核最新数据，应先用根目录最新四份 Excel 重建本地库。
- 若业务要求交期结构在同月内也按 `asOf` 精确到日，需要新增日级交期聚合表，或将 `/api/payment-period/{year}` 改为从 `performance` / `jingdai` 原始明细实时聚合。
- 后续新增业务模块时，必须确认是否需要接入全局 `asOf` 参数，避免与 KPI/平台趋势口径不一致。

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
