# v1.0.157 AI 业务数据接口发布验收

状态：2026-09-23 13:47（北京时间）GitHub `master` 已同步，Ubuntu 保库部署与正式公网复核完成，恢复工具状态 `accepted`。

## 发布来源

- 应用提交：`b0a01310e1b59349f3bc99afea26c40ca312bccf`，从 GitHub v1.0.156 最新 `master` 制作；未从工作区未提交文件或服务器运行副本发布。
- [应用验证](https://github.com/lorrin328/business-analysis-template/actions/runs/35822451584)与 [Docker 构建](https://github.com/lorrin328/business-analysis-template/actions/runs/35822451750)均为 `success`。本地 Python `923 passed, 3 skipped`；Node `57 passed`。
- 可信 Git 归档 SHA256：`3805310044071e4842b5c21a8aef363c9f5e69980fed55f1004616259a2e2106`；本机与 Ubuntu 上传件一致。服务器发布源：`/var/tmp/business-analysis-v157-b0a0131-ReHA0s`。

## 部署与数据

- 部署编号：`20260923_133002-34269`。执行 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`；无新增强制重建迁移，保留现有生产库和聚合。部署前在线备份、停服冻结恢复点、启动后健康检查均通过。启动瞬间曾有连接拒绝，脚本重试后通过。
- 部署前后 `performance=5,159,622`、`jingdai=138,655`、`hr_data=21,383`、`value_data=1,105`、`target_values=6,120`、`customer_master=2,158,127`、`honor_source_policy=467,271`，逐表行数一致；生产库 `quick_check=ok`。38 张显式登记的业务表全部存在，目标表的 2026 年记录计数为 3,060。
- 公网正式 Nginx Proxy Manager HTTPS 入口健康状态 `ok`，应用和页面版本均为 `v1.0.157`，最新期间 `202609`，库表数 55。首页、共享 JS/CSS、AI OpenAPI 均返回 200；OpenAPI 包含新目录、分页、统计、项目口径及市场报告接口。生产代码与 Git 归档中的两个 AI Python 文件 SHA256 一致。

## 鉴权与接口

- 公网匿名访问项目口径、业务目录、业务分页、分组统计和市场报告均返回 401。
- 既有 AI 汇总 Token 在正式公网访问经营快照与项目口径返回 200；访问业务目录、分组统计和市场报告返回 403，未扩展明细权限。
- 本地测试覆盖管理员与普通账号的 Basic 鉴权、`ai_raw_data` 与对应模块权限、目录排除账号会话表、目标数据分页/统计、非法字段与注入输入；生产 SQLite 直接调用新服务完成目录、目标统计和分页取数。生产真实账号的公网 200 正向调用未做，因为发布环境未向本次任务提供该账号凭据；不能把本地账号测试说成线上真实账号验收。
- 通用分组统计直接计算 SQLite 存储值，不代表正式 KPI；业务结论仍需看板接口、项目口径和业务截止日复核。市场研判报告只提供已发布文件，未触发新的公开资料研究。

## 备份与接受

- 最终冻结库：`/opt/business-analysis-backups/business_data.db.20260923_133002-34269.frozen`，SHA256 `3e16215fbfeaa97c2ccca9c8ab7d14f96d2554241fad7a4742342a4a7e0804fb`。
- 跨盘独立副本：`/var/backups/business-analysis-independent/v157-20260923-b0a0131/business_data.db`，与冻结库 SHA256 一致，`quick_check=ok`；同目录保存发布归档，哈希与上传件一致。副本在同一 Ubuntu 主机的另一文件系统上，不属于异机备份。
- 恢复包：`/opt/business-analysis-backups/release-20260923_133002-34269`。验收后执行 `accept-release --confirm-review-complete`，结果 `accepted`。接受工具按既定保留策略清理上一版默认盘冻结库及本次初始在线副本，保留本次冻结库与恢复包。最终主服务及市场定时器均为 `active`。
