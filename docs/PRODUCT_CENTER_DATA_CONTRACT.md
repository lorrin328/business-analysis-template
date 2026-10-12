# 产品研究中心数据合同 v1

2026-10-12，适用于 v1.0.165 的本地只读转换、受控导入与查询。

## 输入与身份

源项目只读。转换器 `INPUTS` 常量固定三份事实 JSON、`combined_results.json`、`产品分类基线.json` 和 `资料索引.csv` 的相对位置；不扫描整库、不跟随越界路径或符号链接。所有分类基线原件逐个核 SHA256，资料索引逐项对照，转换包只收实际事实/情景引用的必要原件。报告保留输入名称与哈希，不暴露源绝对路径。

版本 ID 为 `ver_<身份材料的确定性哈希>`，由公司、代码、渠道、阶段、来源版本/哈希共同确定。同名、同代码不同来源版本、正式/开发、OTO/证保分别保存。OTO 无统一代码或精确合同版本缺证据时 `identityStatus=provisional`；缺代码使用 `null`，不猜配。

人工身份覆盖的顶层 `scenarioMappings` 数组以及每项 `resultId/versionId/sourceSha256/locator/reason` 由转换器校验；核验日期 `reviewDate` 必须为有效 ISO 日期，可在每项或顶层提供；`resultId` 必须为明确的原始 `result_id`，来源 SHA 同时存在于情景和目标产品来源，定位、理由、日期必填。覆盖不会将临时产品自动升级为已确认或在售。审阅记录与覆盖 JSON 留在私人目录。

## 包结构与字段

ZIP 恰包含 `manifest.json` 和已登记的 `files/<sha256>.<扩展名>`，无目录项、额外文件、加密、链接或越界路径。上限：压缩包 100MB、展开 300MB、单文件 64MB、清单 16MB、最多 500 个来源；允许 PDF/PNG/JPG/JPEG/DOCX/XLSX/PPTX，并核文件签名、哈希及声明类型。清单不接受非有限数字、重复 JSON 字段、本地绝对路径或过深嵌套。

| 字段组 | 必要内容与边界 |
|---|---|
| 根 | `formatVersion=1`、`sourceDate`、`converterVersion`、`versions/facts/scenarios/sources`、`gaps`、`report` |
| versions | 不可变 `id`、名称、公司、代码或空值、OTO/证保、formal/development、来源版本、identityStatus、`saleStatus=unknown`、责任类型/利益机制、来源 ID、核验日期与限制 |
| facts | `id/versionId/dimension/label/text/status/sourceIds/locator/reviewDate/limitations`；七维事实保留原文条件与分支，不生成简化赔付承诺。非待核事实必有来源 |
| scenarios | 身份引用或空值、渠道、分区、利益性质、年龄/性别、缴期与保费、退出前已交额、观察年、领取与退出价值、原 IRR/复算 IRR/展示 IRR、算术与合同状态、来源定位和限制 |
| cashflows | 每情景的有序 `timeYear/amount/kind`，年度时点不伪造日期；互斥退出情景分别存储，不相加 |
| sources | `id/filename/sha256/entry/mediaType/versionIds/locator/reviewDate`；文件名仅 basename；API 仅返回来源元数据，不返回 entry、服务器路径或令牌 |
| gaps/report | 缺口、逐条身份映射、165/159 覆盖差异、参数冲突及缺失、独立算术报告；完整报告私有保存，界面按摘要和可展开的问题清单阅读 |

缺失数值始终 `null`。预定利率、实际演示投资利率、费用实绩、NBV/CSM 未确认时不反推、不补零。费用原文和冲突作为有来源事实保留，公司经济性缺资料时只显示缺口。资料阶段、事实核验、算术、身份、当前可售分开表示。

分区：`guarantee` 仅保证；`example` 容纳原说明书案例/非保证演示/万能假设并以 `benefitNature` 细分；`development` 仅开发稿。`benefitNature` 为 guaranteed/illustrated/assumed/development。开发产品不得进入保证或正式案例分区。合同/时点待核结果展示 IRR 必须为空，原假设复算仅作研究信息。

## 数值与批次

年度 IRR 解 `ΣCFₜ/(1+r)^t=0`，按时点合并现金流检查可用根；上传的非空 IRR 均由后端重新独立计算，绝对差须 ≤`1e-8`，NPV 残差 ≤0.01 元。转换工具对原底稿 `all_calculations` 的 774 条数值独立回归；其范围包含待核合同情景，不等于 774 条均可比较。16 条原待核保证结果与两条时点待核演示结果保持空值。无法唯一关联的情景保留身份空值并隔离。

原 `records/example_records/development_maturity` 规范化为 790 条，不将 `guaranteed_groups` 等展示索引重复入库。预检报告的数量由后端实数计算；可发布条目与待核区并存。清单规范 JSON 的 SHA256 控制批次幂等；任何结构、路径或哈希失败拒绝全包。发布前重验不可变包与所有引用资料，事务切换当前指针；撤回前同样验证上一批次。不直接编辑已经保存的批次。

表组：`product_center_batches/versions/facts/scenarios/cashflows/sources/evidence/publications/state`。迁移唯一键 `20261012_product_research_center`，`requires_aggregate_rebuild=0`。现有经营聚合、产品结构及经代配置无表结构改动。

## 接口与权限

| 接口（统一 `/api/product-center` 前缀） | 用途 |
|---|---|
| GET `/products` | 名称/代码、渠道、阶段、责任类型、利益机制筛选及统计 |
| GET `/products/{id}` | 版本、七维事实与来源 |
| GET `/products/{id}/scenarios` | 分区、缴期及观察年筛选 |
| GET `/scenarios/{id}/cashflows` | 当前批次已绑定产品的逐笔现金流 |
| POST `/compare` | 2—4 个明确版本的证据矩阵、收益与条件差异 |
| GET `/sources/{id}/file` | 登录认证后原件预览/下载、哈希复核、禁止共享缓存 |
| GET `/sources/{id}/text?page=1` | PDF 按物理页文字预览；保留原件下载，文字不代替图表与原始版式 |
| POST `/imports/preview` | multipart ZIP 上传与预检，不改变当前发布 |
| GET `/imports`、GET `/imports/{id}` | 批次历史与预检报告 |
| POST `/imports/{id}/publish`、`/withdraw` | 事务发布/撤回，记录必要批次 ID 的审计 |

全部直接 `require_admin`，匿名 401，非管理员 403。AI API 未新增产品研究读取功能。响应沿用项目统一 `success_response`；产品与资料请求禁止缓存。资料需每次以认证请求获取，链接不携带凭据；退出登录清空临时预览和结果。用户主动下载到磁盘的文件仍由其自行管理，无法由网页收回。
