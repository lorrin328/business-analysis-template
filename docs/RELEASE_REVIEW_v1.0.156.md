# v1.0.156 看板口径与 Hermes 市场研判发布验收

状态：2026-09-23 已同步 GitHub `master`、完成 Ubuntu 保库部署及公网验收，发布恢复工具状态为 `accepted`。

## 发布来源与范围

- 应用提交：`90d2dd5e4d712f4e0e5033fc38068db83a70ed8d`。包含 v1.0.156 机构目标、Excel 数值与日期精度、客户筛选缓存、荣誉导出及展示修复，也纳入此前已定向部署但尚未入 GitHub 的 Hermes 公开资料采集和公众号参考分层展示。
- GitHub [应用验证](https://github.com/lorrin328/business-analysis-template/actions/runs/35809740527)与 [Docker 镜像构建](https://github.com/lorrin328/business-analysis-template/actions/runs/35809740760)均成功。本地完整回归为 **919 passed、3 skipped、1 warning**；Node 为 **57 passed**。跳过项属 Windows 环境门禁，警告为既有 Starlette/httpx 弃用提示。
- 可信 Git 归档 SHA256：`07a6628b01cfc8c2e88dcadd275dd52858e5a9ad6b299cdf352c1602bc9c07f4`，本机和服务器上传件一致。发布源为 `/var/tmp/business-analysis-v156-90d2dd5-r9tr13`，没有从 `/opt/business-analysis` 运行副本发布。

## 生产预检与部署

- 部署前发现生产业绩原始表 1,996,364 行期交保费为空；这是历史业务明细的合法空值。新增修复将该字段改为允许空值按业务零处理，非空非法数值仍拦截。只读扫描显示四类原始表关键数值字段无非法值。生产经代原始表 20 行短时间文本均为“合计”尾行，不属于月份。用户提供的四份最新 Excel 也均通过导入数值校验。
- 以 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto` 执行标准 `deploy/deploy.sh`。数据库没有用服务器旧 Excel 重建；新增 `20260923_source_day_precision` 迁移自动触发从现有 SQLite 明细重建聚合。
- 发布编号：`20260923_102121-31264`。在线备份、最终冻结恢复点及启动后的本机健康检查通过。部署探测曾在服务启动瞬间连接拒绝，内置重试后健康检查通过；最终服务异常重启数为 0。

## 业务、入口与权限验收

- 本机和正式 Nginx Proxy Manager 公网入口 `https://kpi.bcyt.tech:30443` 均返回健康状态 `ok`，应用与页面版本均为 `v1.0.156`，最新期间为 `202609`，库表数 55。
- 公网 8 个页面、共享 CSS 和 7 个关键脚本共 16 项与可信归档逐字节一致。荣誉页按实际路由 `/honor` 验证。
- 匿名 KPI 和市场报告接口均返回 401；受保护 AI 汇总凭据分别经本机和正式公网读取 2026 年经营快照，均返回 200 且非空。凭据未出现在验收输出或仓库。
- 生产与冻结库的业绩 5,159,622、经代 138,655、人力 21,383、价值 1,105、目标 6,120、客户主表 2,158,127、荣誉保单源 460,391 行均一致；新迁移标记为 1。2024—2026 年转型和经代月度期交的行数及合计与发布前逐年一致；生产库 `quick_check=ok`。
- Hermes、公众号参考及市场页面的 5 个关键文件与可信发布源一致；Hermes 启用且受保护凭据存在。主服务、市场定时器及手动触发监听均为 active，主服务错误级日志 0 行。本轮没有额外触发完整付费市场研究，整期采集效果仍需下一次定时运行观察。

## 备份、恢复与接受

- 最终冻结库：`/opt/business-analysis-backups/business_data.db.20260923_102121-31264.frozen`，SHA256 `10f39b98b13c1ab4353dbd04b5fdf6e36f93a3c2b5467104a722ad02e9cb187a`。
- 跨盘独立副本：`/var/backups/business-analysis-independent/v156-20260923-90d2dd5/business_data.db`，与冻结库 SHA256 一致，`integrity_check=ok`、`quick_check=ok`；发布归档同目录保存。两者文件系统设备号不同，但仍位于同一 Ubuntu 主机，不属于异机备份。
- 恢复包：`/opt/business-analysis-backups/release-20260923_102121-31264`。完成上述验收后执行 `accept-release --confirm-review-complete`，结果 `accepted`；保留本次冻结库和恢复包。工具按既定策略清理上一版默认盘冻结库及本次初始在线副本，不影响跨盘独立副本。
- 未进行登录后浏览器全流程人工操作；正式页面字节一致性、鉴权和授权业务 API 已分别验证。
