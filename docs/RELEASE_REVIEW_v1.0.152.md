# v1.0.152 方案复核移除与寿险产品研判

状态：v1.0.152已上线；公网、业务对账与独立备份验证全部通过，2026-09-07 15:23:05（北京时间）发布状态确认为accepted。

## 变更

- 完整删除方案复核导航、页面、专属脚本、API和权限；保留历史数据库记录，无新增数据迁移。
- 市场研判加入寿险产品专题和10项一手证据字段，草稿、来源复核后及发布前共同验证；保证与非保证利益分开，未知资料明确披露。
- 修复市场历史加载竞态、刷新丢选择、空样本显示0%，改善手机顶部布局；变更脚本带内容指纹，防止旧缓存残留。
- 本次审查剩余8项问题单独列入TODO，不宣称已修复。

## GitHub与发布来源

- [PR #29](https://github.com/lorrin328/business-analysis-template/pull/29)已合并，部署代码提交`da4396df52f0ea70b951cc5be0915c11f85be3b0`。
- Linux完整回归842 passed、2条既有依赖弃用警告；依赖扫描、文件边界、镜像启动及鉴权检查通过。
- 主分支验证[34093240803](https://github.com/lorrin328/business-analysis-template/actions/runs/34093240803)和Docker镜像发布[34093240982](https://github.com/lorrin328/business-analysis-template/actions/runs/34093240982)均成功。
- 从合并提交生成Git归档，SHA256为`3b3e3bef8d586e1027a4ced7805d8d1fa09a03125caf17a66add75af0d9dd794`，上传服务器独立临时目录后执行标准`REBUILD_DATABASE=0 bash deploy/deploy.sh`。

## 生产验证

- 正式Nginx Proxy Manager公网入口`https://kpi.bcyt.tech:30443`首页显示v1.0.152；22个首页脚本与部署文件一致，430个归档文件逐字节一致，代码root所有、应用账号不可写。
- 方案复核页面、脚本、查询和上传接口在管理员授权下均404，导航与专属权限消失；历史数据库表保留。
- 未登录KPI及市场API返回401；授权KPI、市场latest/history/status均200且success=true，临时验收会话全部清理。
- 实际Chromium加载公网主页面及KPI成功，方案复核导航不存在；市场产品页签与历史报告说明可见，390px手机宽度无横向溢出，脚本错误0。
- 冻结恢复点与线上库对比：51张业务表记录数不变（排除会话及操作日志），18张聚合表全部行内容一致；2024、2025、2026三年KPI完整响应一致。2026严格审计status=ok、issue_count=0。
- 主服务active，异常重启0、运行退出状态0，发布后错误日志0；市场timer和手动监听active。产品开关=1，保留原DeepSeek模型，最新市场报告哈希仍为`f0d2e14c78b98660209cd1dbeb0b25d1fd7999bf9ce1f3c75b12a529cadfe4ae`，未生成新的产品报告。
- 依赖自检通过后复用原venv，没有重建Excel或聚合。服务15:02:37停止、15:06:37恢复，维护窗口约4分钟，主要用于约5GB数据库最终冻结和完整性校验。

## 恢复点与独立备份

- 发布编号`20260907_145940-275477`；恢复包`/opt/business-analysis-backups/release-20260907_145940-275477`。
- 冻结库`/opt/business-analysis-backups/business_data.db.20260907_145940-275477.frozen`，大小4,989,345,792字节，SHA256=`2cf5a53c3096684eca2cc374a23a1179507355f31e40d6748aae1908c1ec6664`，服务端integrity_check和quick_check均ok。
- 独立Windows目录`D:/business-analysis-backups/20260907/v152/`位于Git和Obsidian同步目录外，权限仅当前用户、SYSTEM、Administrators。
- 为降低慢速传输耗时，独立副本使用已验证的上一版冻结库与36,960,422字节差异包重建；新旧服务器库与独立基库均校验完整SHA256，重建结果再次核对目标完整SHA256，并执行SQLite integrity_check和quick_check。不以差异包成功传输替代完整备份校验。

独立Windows完整副本SHA256与上述冻结库一致，实际SQLite integrity_check与quick_check均为ok。验收会话已清理；发布恢复工具已于2026-09-07 15:23:05（北京时间）完成accept-release，保留本次冻结库与恢复包。验收JSON同时保存在恢复包及独立备份目录。

本轮中断的传输临时文件清理被执行策略拦截，未改用其他途径删除，现予保留；正式恢复文件以`business_data.frozen.db`和`independent-verification.json`为准，不使用未完成的传输副本。
