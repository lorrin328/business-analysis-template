# v1.0.160 市场研判百炼接入与凌晨 1 点调度：待完成模型验收

## 发布来源与验证

- GitHub PR #30 已合并，生产发布来源为 `892b3fd29bffc75f936b505952838851119ec13f` 的可信归档。归档 SHA256 为 `8930fc909c67f72c166175fe01d7bd84aecf6ca26a9da2840dd36ff4fbcf468e`，服务器上传件哈希相同；归档不含 Excel、SQLite 运行库或密钥文件。
- 审查修复了旧 DeepSeek 路由可能读取百炼密钥的问题；百炼配置脚本不再立即启动研究。定时器明确采用 `Asia/Shanghai` 每日 `01:00:00`，`AccuracySec=1s`，错过时点不在白天补跑。
- 本地 Python 951 项通过、3 项平台相关跳过；Node 57 项通过；Shell 与 JavaScript 语法检查通过。PR 与合并后的 GitHub 应用验证、Docker 构建均通过。

## Ubuntu 保库部署

- 2026-09-27 从 `/var/tmp/business-analysis-v160-892b3fd` 执行可信归档的 `deploy/deploy.sh`，明确设置 `REBUILD_DATABASE=0`、`REBUILD_AGGREGATES=auto`；复用现有 Python 环境，跳过生产库重建和历史聚合重建。发布恢复目录为 `/opt/business-analysis-backups/release-20260927_163300-59958`。
- 本机与正式公网 HTTPS 健康接口均返回 `v1.0.160`、`latest_period=202609`，55 张数据库表齐全。正式公网 TLS 校验通过；匿名 AI 快照和市场报告 API 均返回 401；使用服务器现有只读令牌的本机与公网业务快照均返回非空数据。首页、市场页及 3 个相关 CSS/JS 文件与服务器发布文件逐字节一致。
- 市场 `latest.json`、`status.json` 与发布前 SHA256 相同，没有用本次部署覆盖上期报告或运行状态。当前库 `quick_check=ok`；与停服冻结库相比，53 张业务表只有 `operation_logs` 新增 2 行，四类原始表行数未变。
- 冻结库 `/opt/business-analysis-backups/business_data.db.20260927_163300-59958.frozen` 为 4,989,345,792 字节，SHA256 `644e3b0e996fac502169abd4ab7b014d02cffd3337b5b72495fc9f656605c500`；元数据的 `integrityCheck`、`quickCheck` 均为 `ok`。同机另一文件系统的独立副本 `/var/backups/business-analysis-independent/v160-20260927-892b3fd/business_data.db` 与冻结库 SHA256 相同。该副本是同机跨盘备份，不是异机备份。

## 当前限制与完成条件

- 服务器尚无百炼专用 API Key，部署脚本保留原 Kimi 路由。用户明确要切换百炼，因此已暂时停用 `market-analysis.timer`，避免次日凌晨运行旧模型；主看板仍正常运行。
- 用户曾在聊天中提供一枚百炼 Key；该值不符合项目“不进入聊天”的密钥要求，**没有写入服务器、代码或日志**。应在百炼控制台停用并重建，由用户直接在 Ubuntu 运行 `sudo bash /opt/business-analysis/deploy/configure-market-analysis.sh`，在隐藏输入提示中录入新 Key。
- 新 Key 配置后，先确认四角色路由均为 `qwen3.8-max`、定时器下一次触发为北京时间 01:00，再用 `--source-scout-only` 验证真实 CLI 握手和来源工具，随后运行一次完整研究并核对 9 分质量门禁、独立证据及上期报告保护。真实百炼调用尚未验证，**本次发布尚未执行 `accept-release`**。
