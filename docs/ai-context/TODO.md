# 待办事项

## 2026-07-01 荣誉体系校验待修复

- 【已完成 2026-07-02】修正荣誉体系冲销/退保净额处理：负向冲销仅在同一投保单号正向保单已计入星钻统计时扣回，显式 `承保件数=0` 不再默认按 1 件；本地真实库重算 2026 年 6 月后，系统 `59` 个会员身份轨道与同事底稿逐人一致。
- 【已完成 2026-07-02】补强冲销净额延伸边界：正向保单缺承保时间但有效计入时仍可被同单负向冲销扣回；负向冲销行缺团队字段时，团队扣回沿用有效正向保单团队归属。
- 【已完成 2026-07-02】修正荣誉 dashboard 等级分布：`levels` 仅展示已入会会员等级分布，不再混入未入会追踪池。
- 【已完成 2026-07-02】按同事底稿修正证保季度通算边界：自然季度固定 3 个月判断，3 个月均需有长险且季度标保合计不低于 `9万`，不再按在职月数缩短周期。
- 【已解决 2026-07-02】`10066607 陈萍` 差异不是源清单权威问题，而是同一投保单号 5 月正向、6 月负向但承保归属 5 月的冲销净额问题；按已计入正向保单匹配扣回后，与同事底稿一致。
- 【已完成 2026-07-02】继续核对截至 2026 年 6 月同事表差异：完整读取同事底稿 V:AB 名单后，修正冲销净额和显式 0 件口径，系统总数、机构、业务线、等级和逐人名单均已对齐。
- 【已完成 2026-07-01】修复星钻长险件判断：`backend/honor/sources.py` 已按 `performance.长短险` 和缴费年限识别长险，短险不计入标保和长险件数。
- 【已完成 2026-07-01】固定荣誉体系 45 天回销校验时间锚点：未设置 `HONOR_AS_OF_DATE` 时默认使用统计月月末后 45 天。
- 【已完成 2026-07-01】修复历史月份重算的人力状态口径：`load_staff()` 当前状态使用所选月份或已有最近月份，不再用未来月份清零历史批次。
- 【已完成 2026-07-01】统一字段审计与实际计算兜底：实际计算已按“年化规保 × 缴费年限折算系数”复算标保，字段审计说明同步调整。
- 【已完成 2026-07-01】优化荣誉页面默认月份：`honor.html` 默认 `honorMonth=6`，加载 dashboard 后回填服务端批次年月。
- 【已完成 2026-07-01】调整展示标签和说明：`star_manpower_count` 展示为“团队会员人数”，人员明细 `qualified_months` 展示为“累计获钻次数”。
- 【中】补齐星钻联盟质量/资格数据源：自保互保剔除、4M/13M 继续率、客户投诉、违规违纪、合同制外勤等规则在方案中存在，但当前源表缺少可计算字段。
- 【中】补齐专项荣誉展示：三星人力、党员之星当前尚未形成独立展示模块；如需上线，需补充季度权益、政治面貌和年度排名数据结构。

## 2026-06-30 等价重构建议

- 【已完成 2026-06-30】先拆 `js/platform-trend-main.js`：内嵌 `platformMock` 历史兜底数据已迁到 `js/platform-seed-data.js`，平台趋势运行逻辑文件已降至约 `647` 行。
- 【已完成 2026-06-30】拆分后端平台数据查询边界：`get_platform_data()` 已从 `db.repositories.kpi` 迁到 `db.repositories.platform`，外部 `from db import get_platform_data` 调用保持不变。
- 【已完成 2026-06-30】整理队伍分析工具边界：业务线归一、人员代码清洗、期间解析、百分位、比例和产能分档已迁入 `services.team_analysis_utils`，`team_enhanced` 保留数据访问和结果组装。
- 【已完成 2026-06-30】收敛队伍分析空响应结构：无 `hr_data` 表或无可选月份时统一由 `_empty_team_analysis_response()` 返回完整结构，后续新增字段只需集中维护。
- 【已完成 2026-06-30】API meta helper 起步：`services.response.response_meta()` 已承接指标类 API 的通用 meta 字段，KPI、机构、产品、平台趋势、队伍分析、目标、交期结构、配置指标、AI 只读和产品配置相关接口已迁移；荣誉体系批次类 meta 已使用 `services.response.batch_meta()`。
- 【已完成 2026-06-30】API 查询参数收敛：看板年份和 `asOf` 日期格式校验已集中到 `backend/api/params.py`，KPI、机构、产品、交期、平台趋势、AI 只读、导出、目标和队伍接口已迁移。
- 【已完成 2026-06-30】荣誉体系清洗归一收敛：人员代码、日期、数字、业务线和职级角色识别已集中到 `backend/honor/normalizers.py`，星钻计算主流程复用该模块并补充专项测试。
- 【已完成 2026-06-30】荣誉体系 dashboard 派生逻辑拆分：项目/机构排序、会员结构、专员/管理职历史、预警、等级分布和趋势已迁入 `backend/honor/dashboard.py`，repository 回归持久化和基础读取职责。
- 【已完成 2026-06-30】荣誉体系源数据准备拆分：人力/保单源表加载、异常识别、个人/主管/经理指标索引已迁入 `backend/honor/sources.py`，calculator 回归星钻流水和汇总职责。
- 【已完成 2026-06-30】荣誉体系汇总与奖励测算拆分：机构汇总和季度奖励测算已迁入 `backend/honor/summary.py`，calculator 进一步收敛为星钻余额流转和人员摘要职责。
- 【已完成 2026-06-30】抽取统一 Excel 导入 pipeline：Web 上传和 `backend/rebuild_from_excels.py` 已复用 `backend/services/excel_pipeline.py` 中的解析、聚合、活动人力回填、写库和校验流程。
- 【已完成 2026-06-30】收敛日级截止查询辅助逻辑：机构维度按渠道日级截止 SQL 已集中到 `services.cutoff_policy.channel_cutoff_filter_sql()`；产品结构、产品配置和导入安全的原始表日期过滤已集中到 `services.raw_table_reader`；KPI 日级 YTD 查询已集中到 `backend/db/repositories/kpi.py` 内部 helper。
- 【已完成 2026-06-30】产品配置弹窗事件绑定收敛：取消/保存按钮已由内联 `onclick` 改为 `data-product-config-action` + `bindProductConfigActions()`，并补充静态测试防回退。
- 【已完成 2026-06-30】主工具栏动作绑定模块化：顶部权限、日志、人员、荣誉、导出、参数、目标、重算、退出按钮已迁移到 `data-dashboard-action` + `js/dashboard-actions.js` 事件代理，并补充静态测试防回退。
- 【已完成 2026-06-30】KPI 卡片详情入口声明式绑定：8 张 KPI 卡片已由 `onclick="openModal(...)"` 改为 `data-kpi-modal` + `bindKPICardActions()`，`dashboard-config.js` 同步改为按 `data-kpi-modal` 应用标题配置。
- 【已完成 2026-06-30】机构维度筛选控件事件绑定收敛：机构标签、时间维度按钮、季度/月度下拉框已迁移到 `data-org-filter` / `data-org-dim` + `org-analysis.js` 绑定函数，并补充静态测试防回退。
- 【已完成 2026-06-30】平台趋势控件事件绑定收敛：年份、时间维度、季度/月度、业务系列、机构和保费类型控件已迁移到 `data-platform-*` + `bindPlatformTrendControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】产品结构控件事件绑定收敛：图表切换、业务来源、转型业务、经代/转型机构、时间维度、季度/月度和保费类型控件已迁移到 `data-product-*` + `bindProductStructureControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】交期结构控件事件绑定收敛：图表切换、年份、时间维度、季度/月度、业务系列、转型渠道、经代/转型机构和保费类型控件已迁移到 `data-pay-period-*` + `bindPayPeriodControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】队伍趋势控件事件绑定收敛：年份、指标类型、时间维度、季度、业务系列和机构控件已迁移到 `data-team-*` + `bindTeamTrendControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】上传区域事件绑定收敛：上传卡片和文件输入已迁移到 `data-upload-input` / `data-upload-info` + `bindUploadControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】通用弹窗关闭事件绑定收敛：overlay 背景点击和关闭按钮已迁移到 `data-modal-action="close"` + `bindModalControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】队伍增强面板动态控件事件绑定收敛：`renderTeamEnhancedControls()` 已迁移到 `data-team-enhanced-*` + `bindTeamEnhancedControls()`，并补充静态测试防回退。
- 【已完成 2026-06-30】主页面与 `js` 目录内联事件清零：数据截止日期和目标弹窗已迁移到 `data-dashboard-as-of`、`data-target-*`、`data-org-target-*` + 模块事件绑定；全局搜索已无 `onclick=` / `onchange=`。
- 【已完成 2026-06-30】版本治理：`pyproject.toml` 已同步为 `1.0.98`，与 `VERSION`、页面和后端默认版本一致。
- 【暂不建议】Rust 改写：除非后续通过计时证明 Excel 解析/聚合存在明确瓶颈，否则不建议引入 Rust。当前更高收益路径是 pandas 向量化、SQLite 索引/预聚合、前端按需加载和导入链路复用。

## 2026-06-29 自动部署待恢复

- 【已完成 2026-06-29】已通过 SSH 手工部署 `v1.0.97` 到 `192.168.50.6`，并同步 20260629 四份源 Excel 后重建数据库；线上 `/api/health` 返回 `app_version=v1.0.97`、`page_version=v1.0.97`、`latest_period=202606`。
- 【已完成 2026-06-30】已通过 SSH 手工部署提交 `5688acf` 到 `192.168.50.6`；线上 `/api/health` 返回 `app_version=v1.0.98`、`page_version=v1.0.98`、`latest_period=202606`，数据质量审计 `issue_count=0`。
- 【已完成 2026-07-02】已通过 SSH 手工部署提交 `8a60622` 到 `192.168.50.6`；线上 `/api/health` 返回 `app_version=v1.0.98`、`page_version=v1.0.98`、`latest_period=202607`，2026 年 6 月荣誉重算 `batchId=89` 与同事底稿一致。
- 【已完成 2026-07-02】已通过 SSH 手工部署提交 `cbfddc9` 到 `192.168.50.6`；线上 `/api/health` 返回 `app_version=v1.0.99`、`page_version=v1.0.99`、`latest_period=202607`，注册开关返回 `allowPublicRegistration=true`。
- 【已完成 2026-07-02】修复服务器 `webhook-deploy` 服务配置：`/opt/business-analysis/deploy/.webhook_env` 已配置，服务为 `active`，本机签名 ping 返回 `200 pong`，未签名 ping 返回 `403 invalid signature`，不再返回 `502`。
- 【已完成 2026-07-02】GitHub webhook 已创建并与服务器 secret 对齐，hook id 为 `648507986`。
- 【高】确认 GitHub 云端是否能访问 `http://192.168.50.6/webhook/deploy`：当前 URL 为内网地址，服务器端已可用，但 github.com 直接触发可能因网络不可达失败；如需真正自动发布，需提供公网可达地址、VPN/隧道或自托管中转。

## 2026-06-20 审计整改建议

- 【已完成 2026-06-24】生产环境默认关闭公开自助注册，保留 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 作为显式开关；普通用户默认只读经营数据的范围仍需按实际保密要求确认。
- 【已完成 2026-06-24】修复权限管理页用户名拼接 `onclick` 的前端注入风险：后端限制用户名字符集，前端改为 `data-action` / `data-user-id` / `data-username` 加事件绑定，不在内联事件属性里拼接用户输入。
- 【高】本地如需继续复核最新经营数据，应先用 2026-06-19 四份 Excel 重建 `backend/business_data.db`，并导入正式目标，避免默认目标影响达成率判断。
- 【中】如业务要求交期结构支持 6 月 18 日/6 月 19 日等日级切换，新增日级交期聚合表或改为按原始明细实时聚合。
- 【中】补充生产安全基线：HTTPS、账号开通审批、密码复杂度/失败锁定、Session 清理、备份恢复演练和操作审计留存周期。
- 【已完成 2026-06-24】将 `pyproject.toml`、`VERSION`、README 当前版本口径统一治理；当前应用版本为 `v1.0.96`。
- 【低】继续清理前端超大脚本和动态 `innerHTML` 拼接模式；内联事件已清零，后续重点转向可测试、可复用的渲染组件或安全模板函数。

## KPI 与数据口径

- 【已完成 2026-06-29】转型业务商保年金/保障类产品改为读取业绩基表标识列，参数设置仅保留经代产品分类维护。
- 本地 `backend/business_data.db` 曾发现与服务器库不一致；服务器库已确认 2026 目标和 2026-06-19 数据正常。后续如需本地复核最新数据，应先用根目录最新四份 Excel 重建本地库。
- 若业务要求交期结构在同月内也按 `asOf` 精确到日，需要新增日级交期聚合表，或将 `/api/payment-period/{year}` 改为从 `performance` / `jingdai` 原始明细实时聚合。
- 后续新增业务模块时，必须先确认模块用途：若是 KPI/机构同比复核，接入 `asOf` 精准同日口径；若是趋势展示，默认展示完整已有数据，不随 `asOf` 截断。

## 部署与容器

- 推送到 GitHub 后检查 Actions `Build Docker image` 是否成功。
- 在 GitHub Packages/GHCR 中确认 `ghcr.io/lorrin328/business-analysis-template:latest` 已生成。
- 在目标 Ubuntu/NAS 机器上执行一次 `docker pull` 和 `docker run` 冒烟验证。
- 按生产访问方式补充 nginx 反向代理到 Docker 容器的正式配置。
- 明确容器部署时 `.env` 示例文件，记录必要但不含真实值的环境变量。
- 根据是否多人访问，补充备份和恢复脚本，重点覆盖 `/data/business_data.db` 和 `/opt/business-analysis/backend/business_data.db`。

## 开发环境

- 新开 PowerShell 后执行 `python --version`、`uv --version`、`git --version`，确认用户 PATH 已被新终端继承。
- 后续如需统一依赖管理，可评估是否把运行依赖迁入 `pyproject.toml`，减少 requirements 与脚本之间的重复。

## 项目文档

- 【已完成 2026-06-30】`docs/数据流说明.md` 已按当前 `backend/services/excel_pipeline.py` 与 `backend/etl/aggregates/` 链路更新，并新增测试防止重新把旧 `backend/aggregator.py` 写成当前入口。
