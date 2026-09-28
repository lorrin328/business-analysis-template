# v1.0.162 产品结构件数口径修复发布验收

## 变更与发布来源

- 应用提交为 `ad65eba2ad2a1c8abbf685240e0819ff083205d4`，已同步 GitHub `master`；GitHub 的 Validate application 与 Build Docker image 均成功。
- 产品结构按钮统一为“件数”。转型来源使用承保件数；经代源文件没有承保件数字段和保单唯一号，不再把数据行数返回为件数。混合来源保费仍覆盖两类，件数只统计转型；经代单选明确显示件数不可核算。
- 修复首次加载后产品结构统计范围仍显示“正在读取”的问题。无数据库迁移、聚合逻辑变更或 Excel 导入。
- 本地 Python 回归 `952 passed, 3 skipped`，Node `59 passed`；前端静态专项 `61 passed`。Ubuntu 发布源语法检查通过。

## Ubuntu 保库部署

- 可信 Git 归档 SHA256 为 `518bc1c24b2e3c1eeddf0c8c040672b7154c596ca72d507758676d1c0622ea68`，服务器上传件哈希一致。发布源为 `/var/tmp/business-analysis-v162-ad65eba`。
- 执行 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`；复用已有 Python 环境，不用旧 Excel 重建数据库，不触发历史聚合重建。
- 恢复目录为 `/opt/business-analysis-backups/release-20260928_110517-67840`，状态 `healthy`。停服冻结库为 `/opt/business-analysis-backups/business_data.db.20260928_110517-67840.frozen`，4,989,345,792 字节，SHA256 `93bfd4d34ed524b1ec7829ff0c352288bdeb38e0c0475774693742feed3a4173`；`integrityCheck=ok`、`quickCheck=ok`、55 张表。部署前在线备份亦通过相同检查。

## 正式入口与业务验收

- FastAPI 本机及正式公网 `https://kpi.bcyt.tech:30443` 健康接口均为 `v1.0.162`，最新期间 `202609`；主服务 active，Ubuntu nginx 配置校验通过。
- 公网首页及两份更新脚本与应用提交内容在统一 LF/CRLF 后逐字节一致；页面按钮为“件数”。匿名产品分析和 AI 快照接口返回 401；服务器既有只读令牌访问本机与公网 AI 业务快照均返回 200 且数据非空。
- 对生产运行库调用新版产品结构查询：混合来源保费同时包含转型和经代，件数非空且只含转型；经代单选保费非空、件数为空，`countBasis=unavailable`。应用代码目录为 `root:root 755`，运行库为 `www-data:www-data 640`。
- 部署脚本曾重新启用市场研判定时器，已立即恢复为 `disabled/inactive`，维持 v1.0.160 以来待百炼凭据验收期间的运行状态。

## 保留事项

- 本次恢复目录保留 `healthy`，未执行会清理旧备份的 `accept-release`；市场研判百炼凭据及真实研究验收仍按 v1.0.160 独立完成。
- 后续修改部署脚本，避免发布普通看板代码时自动启用原本停用的市场研判定时器。本次上线后已手工恢复停用状态。
