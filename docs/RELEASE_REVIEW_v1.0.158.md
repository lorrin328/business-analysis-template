# v1.0.158 账户注册审批发布验收

状态：2026-09-23，GitHub `master` 已同步，Ubuntu 保库部署和正式公网验收完成，恢复工具状态 `accepted`。

## 发布来源与功能

- 应用提交：`59bfbca22e9686ce5b73b91621a1e9a7eb16bc60`，基于已发布的 v1.0.157。隔离目录制作，原有未提交工作区未纳入发布。
- 自助注册创建待激活普通账户，不签发会话；管理员在账户管理中激活后才能登录。账户状态区分待激活、已启用、已停用；停用撤销现有会话。现有账户状态不变，管理员直接创建的账户仍可立即使用。
- 新增 `20260923_account_activation` 数据库迁移，`requires_aggregate_rebuild=0`。
- [应用验证](https://github.com/lorrin328/business-analysis-template/actions/runs/35825572859)和 [Docker 构建](https://github.com/lorrin328/business-analysis-template/actions/runs/35825573047)均为 `success`。本地全量回归初跑为 923 passed、3 skipped、2 项前端静态断言失败；修正提示断言和缓存标识后，相关 80 项回归通过。Node 57 项通过。

## 部署与验收

- 从上述 GitHub 提交生成归档，SHA-256 为 `62b17606292da914d2c8b3daa91e3a81701aa5c7de1a4fceddb3c68eb7061f50`，本地与 Ubuntu 上传件一致。Windows 归档将文本文件转为 CRLF；20 个变更文件统一换行后与 GitHub 对应对象一致，Ubuntu 运行文件与归档逐字节一致。
- 发布编号 `20260923_141350-36296`；使用 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`，未重建生产库或聚合。部署启动瞬间曾出现连接拒绝，脚本最终健康检查通过。
- 正式公网 `https://kpi.bcyt.tech:30443` 首页、健康接口、账户脚本和注册配置可用；应用与页面版本均为 v1.0.158，数据库无缺表，匿名 `/api/auth/me` 返回 401。自助注册目前开启。
- 公网 API 用临时测试账户完成注册无 Token、待激活拒绝登录、管理员查看和激活、激活后登录、停用后旧会话失效、重新启用后需重新登录；临时账户、会话和相关日志已清理。本轮未使用真实浏览器操作管理员页面。
- 生产 `performance=5,159,622`、`jingdai=138,655`、`target_values=6,120`、`users=15`，与部署前一致；待激活账户数为 0，数据库 `quick_check=ok`。主服务和市场定时器均为 active，Webhook 仍 inactive。

## 恢复点

- 冻结库：`/opt/business-analysis-backups/business_data.db.20260923_141350-36296.frozen`，SHA-256 为 `152c585f1e8a16a44a605119c3fac33a69653b82553103352c3087df82ed7c47`。
- 另一文件系统的独立副本：`/var/backups/business-analysis-independent/v158-20260923-59bfbca/business_data.db`；与冻结库哈希一致，`quick_check=ok`。同目录发布归档哈希与上传件一致。
- 恢复包：`/opt/business-analysis-backups/release-20260923_141350-36296`，验收后执行 `accept-release --confirm-review-complete`，状态为 `accepted`。
