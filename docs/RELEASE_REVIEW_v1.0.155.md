# v1.0.155 日常Excel明细API发布验收

状态：GitHub推送、Ubuntu保库部署、公网及数据验收完成，发布已accepted。

## 范围

- 新增四类日常原始表字段目录和全部字段明细分页读取、选列与精确筛选，最多1000行/页。
- 新增 `ai_raw_data` 权限；管理员可读，其他角色需显式授权，原有汇总Token不扩权。筛选值使用请求头传递，不写原始行到操作审计。
- 无业务数据结构、ETL、聚合口径或依赖变化，部署使用 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`，不从Excel重建。

## 发布前验证

- Windows完整回归 **888 passed, 3 skipped, 1 warning**。平台跳过项将在GitHub Linux验证；既有警告为Starlette/httpx弃用提示。
- 先前真实本地SQLite副本四类表203页、200,139行、所有字段值与独立SQL全量哈希一致，详见 `EXCEL_API_AUDIT_20260912.md`。
- Ubuntu预检：v1.0.154服务active、异常重启0，正式数据期间202609，55张表，市场timer及手动触发监听active。
- 生产应用/数据在 `/dev/sdb`，独立备份计划存系统盘根逻辑卷，两者设备不同；两盘容量预检足够。本次独立副本为同机跨盘，不是异机备份。

## 可信来源与GitHub验证

- 代码提交：`38d8ecd8c0b19cf1e427a15affb899296755ad04`，已推送master。
- GitHub Linux完整回归 **891 passed, 2 warnings**；依赖检查无已知漏洞，镜像实际构建、文件边界、非root启动和鉴权检查通过。
- [应用验证](https://github.com/lorrin328/business-analysis-template/actions/runs/34701090727)与[Docker镜像发布](https://github.com/lorrin328/business-analysis-template/actions/runs/34701091025)均成功。
- 可信Git归档SHA256：`7e36bcd56b0ac25968a9e90b0eee44dd6294bb940666d8f957e5a5b2aedbd240`，上传后校验一致。
- 独立发布源：`/var/tmp/business-analysis-v155-38d8ecd`。正式运行代码为上述已验证提交，后续验收记录以纯文档提交同步。

## 部署与公网验收

- 发布编号：`20260912_230620-302600`。保留数据库及现有聚合，未新增迁移、未从Excel导入、未重建聚合，复用原venv。
- 主服务于北京时间23:10:23停止，23:12:54恢复，维护窗口2分31秒。本机及正式公网健康检查均为v1.0.155、数据期间202609、55张表。
- 正式入口：`https://kpi.bcyt.tech:30443`（极空间Nginx Proxy Manager转发FastAPI）。441个归档文件与部署文件一致，23项公网静态资源与部署文件一致；归档文件root:root，应用账号不可写。
- 真实公网临时普通账号未授权时明细接口403，显式授予 `ai_raw_data` 后字段目录及四类明细均200；匿名明细、KPI、市场接口401。原有汇总Token读取KPI为200、读取明细为403。
- 四类表的全部字段与运行库目录一致，各取首尾3行，经公网API读取并与独立SQL逐字段核对一致：

| 数据集 | 线上字段数 | 线上记录数 |
|---|---:|---:|
| performance | 38 | 5,159,244 |
| jingdai | 9 | 137,979 |
| hr_data | 17 | 21,369 |
| value_data | 8 | 1,091 |

- 线上业绩表含历史导入扩展字段，字段数与初次本地34列快照不同，接口动态返回实际全部38列。生产验收为首尾分页样本，不声称逐页下载了全部516万行；完整读取逻辑另由本地20万行全字段测试覆盖。
- 请求头筛选正确返回无匹配结果，越界页大小422，任意账号表访问404，POST明细405，原始明细响应禁止缓存。公开OpenAPI版本1.0.155且包含新增端点。
- 后端源码、受保护环境文件及旧方案路径404。临时验收账号、对应会话、权限和操作日志均已清理；不保留临时密码。
- 2024/2025/2026三年KPI授权公网结果与发布前一致，只排除请求级 `meta.updatedAt`。市场latest/status文件哈希不变。
- 浏览器实际打开公网，显示v1.0.155，登录界面显示正常，warning/error日志为空。未进行登录后浏览器交互；认证、授权和业务内容由独立公网API核验覆盖。
- 主服务active、异常重启0、主进程状态0，发布后warning及以上服务日志为空；nginx配置有效，市场timer及手动触发监听active。

## 数据保护与最终验收

- 对冻结恢复库与上线运行库逐表逐行序列化并计算有序SHA256：**49张业务表的记录数和全部内容一致**，包含四张原始表、客户表、荣誉表、18张聚合表、目标及迁移记录。账号/权限/会话/操作日志和SQLite内部表不混入业务数据比较。
- 线上 `PRAGMA main.quick_check=ok`。冻结恢复库：`/opt/business-analysis-backups/business_data.db.20260912_230620-302600.frozen`。
- 冻结库大小4,989,345,792字节，SHA256：`fe711cd1a6df7235fc09d503a9076f8d166e61acb83a2dfc6a1c03eefcc672b5`。
- 独立副本：`/var/backups/business-analysis-independent/v155-20260912/business_data.db`，完整SHA256与冻结库一致，`integrity_check=ok`、`quick_check=ok`；父目录0700、数据库及元数据0600，同时保留发布包、恢复包及核验JSON。
- 独立副本与冻结库实际文件系统设备不同。这是同一Ubuntu主机的系统盘跨盘备份，不是异机备份；此前v1.0.154独立副本仍保留。
- 全部验收完成后执行 `accept-release --confirm-review-complete`，状态accepted，保留本次冻结库与恢复包。按既定保留策略清理前一份默认盘冻结库及本次初始在线副本，不影响独立副本。

## 验收脚本修正

首轮验收脚本对代理响应头大小写、root组可写标志作了过严匹配而失败。已修正为HTTP头名大小写无关，并核验文件root:root、无其他用户写位、www-data不属于root组。复验通过；未因此修改生产权限或放宽应用账号写权限。
