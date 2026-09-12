# v1.0.155 日常Excel明细API发布验收

状态：用户已授权推送GitHub和部署Ubuntu，正在执行发布与验收，尚未accepted。

## 范围

- 新增四类日常原始表字段目录和全部字段明细分页读取、选列与精确筛选，最多1000行/页。
- 新增 `ai_raw_data` 权限；管理员可读，其他角色需显式授权，原有汇总Token不扩权。筛选值使用请求头传递，不写原始行到操作审计。
- 无业务数据结构、ETL、聚合口径或依赖变化，部署使用 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`，不从Excel重建。

## 发布前验证

- Windows完整回归 **888 passed, 3 skipped, 1 warning**。平台跳过项将在GitHub Linux验证；既有警告为Starlette/httpx弃用提示。
- 先前真实本地SQLite副本四类表203页、200,139行、所有字段值与独立SQL全量哈希一致，详见 `EXCEL_API_AUDIT_20260912.md`。
- Ubuntu预检：v1.0.154服务active、异常重启0，正式数据期间202609，55张表，市场timer及手动触发监听active。
- 生产应用/数据在 `/dev/sdb`，独立备份计划存系统盘根逻辑卷，两者设备不同；两盘容量预检足够。本次独立副本为同机跨盘，不是异机备份。

## 待完成

GitHub精确提交验证及镜像发布、可信归档、在线/冻结恢复点、Ubuntu部署、公网HTTPS与权限/静态资源/业务数据验收、独立副本完整性及accept-release。
