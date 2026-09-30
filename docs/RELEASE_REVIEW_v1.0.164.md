# v1.0.164 市场研判模型参数发布验收

状态：2026-09-30 GitHub master 已同步，Ubuntu 保库部署、公网及备份检查通过；本次发布已正式 accepted。

## 修改与依据

- 应用提交：[499398c](https://github.com/lorrin328/business-analysis-template/commit/499398c3507dbe2d93aa266d819bed56dbfc86f5)。Qwen3.8-Max 当前官方页面标注 1M；用户核对后明确确认保留 1M。思考模式最大输入 983616 单独说明，不把上下文等同输入额度。
- Qwen 从等价 xhigh 的 high 降为 medium。来源侦察、主研、修复、升级修复均优先 Qwen，凭据缺失或通道不可用/超时时允许一次 DeepSeek Flash 接替，独立使用 1M + max，受剩余预算与时间限制。内容/预算门禁失败不切换，历史报告保护与9分质量门禁不变。
- 运行计划、调用事件和实际成稿模型参数同步记录。安装脚本保留既有定时器启用及运行状态，页面显示备用模型与其思考深度。
- 无数据库迁移、聚合或业务口径变更。工作区原有 PDF 删除和 docs/archive 未纳入提交。

## 本地与 GitHub

- Windows 全量 Python：960 passed、3 skipped；后续新增4项定时器测试仅在 Linux 运行，Windows 专项正常跳过。Node 全量60 passed；脚本语法、差异空白和发布边界通过。
- [Validate application](https://github.com/lorrin328/business-analysis-template/actions/runs/36672475699)：success，Linux967项测试通过，依赖审计、真实镜像文件边界、非root和受保护接口冒烟通过。
- [Build Docker image](https://github.com/lorrin328/business-analysis-template/actions/runs/36672475740)：success。
- Ubuntu 单独执行生产安装脚本中的定时器恢复分支，4种启用/运行状态全部通过。运行环境未安装 pytest，因此未向生产环境安装测试依赖，完整 Linux 测试由 GitHub CI 执行。

## 真实通道与生产配置

- 使用可信发布源码、market-ai账户和服务器既有凭据，禁用工具且不持久化会话，实际调用一次。Qwen 因百炼专用凭据缺失判为 unavailable；DeepSeek Flash 接替成功返回 ack=true，配置为1000000上下文、max，耗时2066ms，CLI估算0.011915 USD、2轮，搜索/抓取均0。
- 该调用验证真实凭据与接替链；不是整期研究、Qwen真实握手、最高思考实际行为对比或百万tokens满载测试。
- 部署后解析真实受保护配置，四角色均为Qwen、reasoningEffort=medium、contextTokens=1000000；fallback=deepseek-flash、fallbackReasoningEffort=max、fallbackContextTokens=1000000。备用子进程模型为deepseek-flash[1m]。
- 服务器仍无百炼专用Key，因此下一次研究会由DeepSeek接替；未借用Kimi或其他供应商密钥。定时器仍disabled/inactive，手动触发路径active。没有启动完整一期研究，没有回写历史报告或status.json。

## Ubuntu 与公网

- 发布源：/var/tmp/business-analysis-v164-499398c，来自已提交Git归档。归档SHA256：522e9f75cbfdd755e0bd8114ef994a6dad3adb1ad59af2f371ddf7e91d09be52，本地与上传件一致；9项关键运行文件与归档逐字节一致。
- REBUILD_DATABASE=0、REBUILD_AGGREGATES=auto；保留既有库及聚合，目标数据无需恢复。候选Python环境pip check通过后切换；未复用旧环境。
- 本机FastAPI和正式公网https://kpi.bcyt.tech:30443：健康status=ok、应用与页面版本均v1.0.164、版本一致、55张表、无缺表、业务数据可用。首页、市场页和市场脚本200，脚本与发布源一致。
- 匿名KPI、管理员列表、AI快照和市场状态401；源码及部署环境文件路径404。既有只读Token对两个入口的2026业务快照均200且非空；凭据仅在服务器内存中使用。
- 关键表行数与发布前一致：performance=5159751、jingdai=383810、hr_data=21389、value_data=1117、target_values=6120、users=15。生产quick_check=ok；原latest.json/status.json哈希不变。
- 主服务和市场手动路径active，定时器disabled/inactive，nginx配置检查通过。启动期间前两次本机健康探测连接拒绝，脚本后续健康检查及最终公网检查均通过。

## 恢复材料

- 专属备份目录：/opt/business-analysis-backups/v164-20260930，避免本次接受流程清理此前待验收恢复点。
- 发布接受结果：accepted，保留本次冻结库和恢复包，仅清理本次在线备份；专属目录外的既有恢复点全部保留。
- 恢复目录：/opt/business-analysis-backups/v164-20260930/release-20260930_131606-77247。
- 冻结库：business_data.db.20260930_131606-77247.frozen；4989345792字节，55张表，integrity_check/quick_check均ok，SHA256：0776ccbd26a49451ddbe8103dfe19851a65a8de1c9b75d7532f13e0f9847d382。在线备份与冻结库哈希一致。
- 另一文件系统副本：/var/backups/business-analysis-independent/v164-20260930-499398c/business_data.db，哈希一致、quick_check=ok，并保留归档和备份元数据。运行备份在/dev/sdb，独立副本在系统盘，均未进入Git或同步代码目录。
- 受保护市场配置原件备份为专属目录中的market-analysis.env.before。回滚先按项目规则复核上线后写入，再使用恢复目录工具；市场环境配置另从此原件恢复，不展示凭据。
