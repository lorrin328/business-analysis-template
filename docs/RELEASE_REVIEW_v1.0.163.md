# v1.0.163 权限管理布局修复发布验收

状态：2026-09-30，GitHub master 已同步，Ubuntu 保库部署及正式公网检查完成。恢复工具保持 healthy，保留此前待验收恢复点；未执行会清理既有备份的 accept-release。

## 修复与来源

- 应用提交：7921e2ee717a6907761690ac1929d34ee7a0007e。仅发布本次六个变更文件；工作区原有 PDF 删除及 docs/archive 未纳入提交。
- 根因：权限表增加状态和注册时间后，列宽仍按旧版五列配置；模块权限直接把 td 改成 grid，破坏表格布局。新增用户区五个控件也仍使用四列布局。
- 调整：权限网格移入单元格内的独立 div；宽屏明确分配七列宽度，较窄窗口分块展示，每个账户保留全部24项模块权限。用户列表独立滚动，新增用户区与统一保存区保留在可见范围。手机布局使用两列权限。
- 不改变权限键、账户状态接口或管理员防锁死校验；无数据库迁移、业务口径或聚合逻辑变更。
- 更新 VERSION、页面版本、版本回退值和 auth-ui.js 内容摘要缓存标识。

## 本地与 GitHub 验证

- Python 全量回归：952 passed、3 skipped；账户、前端和发布边界专项：108 passed、1 skipped。Node：59 passed。脚本语法、差异空白及发布文件边界检查通过。
- 浏览器以合成账户加载实际样式和账户脚本，检查1440、约1060、390像素宽度：每个账户均24项权限，无权限文字裁切，统一保存可见。模拟接口下完成勾选与统一保存，提交包含全部24项权限字段。
- 正式公网浏览器显示 v1.0.163 和登录页面。未用真实管理员账户登录并执行保存；生产账户权限未因本次验收而修改。
- [Validate application](https://github.com/lorrin328/business-analysis-template/actions/runs/36665328418) 与 [Build Docker image](https://github.com/lorrin328/business-analysis-template/actions/runs/36665328795) 均 success。

## Ubuntu 部署与公网检查

- 从已提交版本生成纯 LF 可信归档，SHA256：82c6d876c2837bfe7377a84b5efb05a69999f85efa4a99754211404d85ef3538。本地、上传件哈希一致；六个变更文件与 Git 对象及运行文件逐字节一致。
- 发布源：/var/tmp/business-analysis-v163-7921e2e；执行 REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto，跳过数据库及聚合重建。
- 部署脚本在线准备并切换候选 Python 环境，pip check 通过。本次没有复用旧环境。
- 本机 FastAPI 与正式公网 https://kpi.bcyt.tech:30443 的健康接口均返回 v1.0.163、status=ok、版本一致、无缺表。公网首页、账户脚本与两份 CSS 返回200并与发布文件一致。
- 匿名管理员列表、KPI、AI快照为401；源码路径为404。既有只读凭据对本机及正式公网业务快照均返回200、数据非空，凭据仅在服务器进程内调用。
- 首次并发公网探测遇到一次连接拒绝；随后 Windows 与 Ubuntu 访问成功，逐项公网验收全部通过。
- 部署前后关键表行数一致：performance=5,159,751；jingdai=383,810；hr_data=21,389；value_data=1,117；target_values=6,120；users=15。生产数据库 quick_check=ok。
- 主服务 active；nginx 配置检查通过；代码目录 root:root 755、运行库 www-data:www-data 640；Webhook inactive。
- 市场研判定时器原为 disabled/inactive。运行时 mask 被 /etc 单元文件优先级覆盖，补充临时启动条件保护；安装脚本虽写出“已启用”，实际启动因条件不满足而跳过。完成后恢复 disabled/inactive，临时保护已移除。长期部署脚本的定时器状态保护仍按既有 TODO 单独处理。

## 恢复材料

- 恢复目录：/opt/business-analysis-backups/release-20260930_114016-74877，状态 healthy。
- 在线备份与冻结库均通过 integrity_check、quick_check，55张表，大小4,989,345,792字节。
- 冻结库：/opt/business-analysis-backups/business_data.db.20260930_114016-74877.frozen，SHA256：df6ae6fc9a400e6bdf283e67477aa148c1f0de4653fdbb15bf77117b76a8c2fc。
- 另一文件系统副本：/var/backups/business-analysis-independent/v163-20260930-7921e2e/business_data.db，哈希与冻结库相同、quick_check=ok；同目录保留发布归档和备份元数据。副本未进入 Git 或同步代码目录。
- 保留当前及此前未验收的恢复点与依赖环境，不执行备份清理。若回滚，先检查上线后写入，再通过该恢复目录内的工具按项目规则操作。
