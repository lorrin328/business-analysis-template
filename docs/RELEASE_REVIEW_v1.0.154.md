# v1.0.154 UI 修复发布验收

状态：Ubuntu 已运行 v1.0.154，正式公网、鉴权、静态资源、业务数据和备份验证通过；已执行 accept-release，发布状态为 accepted。

## 发布范围

- 补齐 CSS 的 Docker 构建白名单，保留敏感文件和同步冲突文件排除。
- 九张 KPI 卡片采用宽屏九列、常规屏三列、窄屏两列且末项占满整行。
- 修正 Linux shell 测试的临时目录权限隔离，生产触发器权限不变。
- 无数据迁移、业务口径或聚合逻辑变更，部署使用 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`。

## 可信发布来源与测试

- 修复提交 `8f72b0a`，最终代码提交 `86b5bd2`，已同步 GitHub master。
- Windows 完整回归 860 passed、3 skipped；跳过项包含 Docker 和 Linux shell 测试。
- 首轮 Linux 验证发现原有 shell 测试以普通用户设置 root 目录所有权失败；仅调整测试临时目录的所有权设置，保留实际触发、失败重置和冷却断言。
- 最终 Linux 完整回归 863 passed；依赖扫描、实际镜像构建、敏感文件排除、非 root 镜像运行、健康及鉴权验证均通过。
- [应用验证](https://github.com/lorrin328/business-analysis-template/actions/runs/34616647990)成功；[Docker 镜像发布](https://github.com/lorrin328/business-analysis-template/actions/runs/34616648219)成功。
- Git 归档 SHA256：`11de65acc6b6cdb835023861d08adae2946c98e20e1531cb34929d03229b6d40`，服务端一致；从独立候选目录部署。

## 验收边界

- 本地浏览器静态副本覆盖桌面、平板及手机排列；不冒充真实数据交互验收。
- 生产基线保存 51 张业务表记录数、18 张聚合表内容摘要。KPI 响应包含每次请求变化的 `meta.updatedAt`，不使用含该字段的整包摘要判断数据变化；改用发布前代码与冻结库只读复算，仅去除该请求时间字段，与当前授权公网响应比较。
- 线上应用、运行库和默认备份目录实际均绑定到 `/dev/sdb`；独立副本另存系统盘，不以同盘不同目录代替独立备份。

## 生产验证结果

- 正式入口 `https://kpi.bcyt.tech:30443` 与 FastAPI 本机健康检查均通过，版本 v1.0.154。
- 首页引用的 23 个本地资源（22 个 JS、1 个 CSS）与部署文件逐字节一致；436 个归档文件与部署文件一致，所有者 root:root，应用账号不可写。核对以 Git 归档清单为准，不将执行部署脚本生成的 pyc 当作归档内容。
- 未登录 KPI、市场 latest 接口均为 401；后端源码、受保护配置、CSS 隐藏文件、旧方案页面和脚本均为 404。临时验收会话已清理。
- 51 张业务表记录数、18 张聚合表全行内容与部署前一致；2024、2025、2026 三年 KPI 响应与发布前代码及冻结库复算一致，仅排除请求时间字段。线上 SQLite quick_check 为 ok。
- 市场 latest 授权接口正常，上一有效报告哈希不变；未触发新的研究。
- 实际浏览器访问正式公网显示 v1.0.154，登录入口样式正常，浏览器错误日志为空。浏览器未建立登录会话；登录后业务内容由授权 API 比对验证，KPI 响应式布局由本地静态副本验证，不宣称完成全部登录后交互。
- 主服务 active，异常重启数 0、主进程退出状态 0；23:41:03 之后无 warning 及以上日志。nginx 配置有效；市场 timer 和手动触发监听 active。
- 23:37:05 开始停止服务，23:41:03 启动服务，维护窗口约 4 分钟。复用原 venv，未从 Excel 重建数据库，未重建聚合。

## 恢复点与独立副本

- 发布编号：`20260911_233420-297110`。
- 恢复包：`/opt/business-analysis-backups/release-20260911_233420-297110`。
- 冻结库：`/opt/business-analysis-backups/business_data.db.20260911_233420-297110.frozen`。
- 大小：4,989,345,792 字节；SHA256：`5ab779f09d296510f3f7e9559ab36db7b829a6b97fb42912df4d33d962eed902`。
- 独立副本：`/var/backups/business-analysis-independent/v154-20260911_233420/business_data.db`，父目录 root 专用 0700，数据库 0600；同时保留恢复包、可信代码归档、基线和验收 JSON。
- 运行库与默认备份在 `/dev/sdb`，独立副本位于系统盘 `/dev/sda` 上的根逻辑卷，两者文件系统设备号不同；这是同一 Ubuntu 主机的跨盘副本，不是异机备份。
- 独立副本先由完成的在线备份复制，校验其完整 SHA256、integrity_check、quick_check，随后与最终冻结库摘要复核完全一致；两份完整性检查均为 ok。
- 最终执行恢复工具 accept-release，状态 accepted，保留本次冻结库与恢复包；验收记录已保存到恢复资料目录及独立副本目录。
