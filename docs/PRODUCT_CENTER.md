# 产品研究中心：管理员使用说明

版本 v1.0.165，2026-10-12。本期仅内部研究、本地交付。实现范围以现有[规划 v2 的一期修订](产品分析模块规划_v2.md)为准。

## 查询和比较

1. 启动既有 FastAPI 服务，用管理员账号登录，点击主看板“产品研究中心”或打开 `/product-center`。页面空壳可公开加载，产品 API 和资料必须经后端管理员认证。
2. 默认查看正式材料，按名称/代码、渠道、责任类型及利益机制筛选。开发稿有独立页签和常驻提示；“正式材料”不确认现售。代码或合同版本缺证据时保留临时身份。
3. 打开产品详情查看原文责任、年龄/缴费分支、最低保费限制、核验日期、来源定位、费用研究与参数缺口。原件按钮使用认证请求获取文件；PDF 默认提供按物理页码的文字预览及翻页，也可切换浏览器 PDF 视图或下载原件核对表格版式。不含服务器路径或 URL 凭据。退出登录会清空本页资料、关闭预览并撤销临时文件链接。
4. 勾选 2—4 个版本进入比较，查看七维事实和证据。IRR 默认保证利益的 40 岁女性、计划总保费 150 万元方案，可选缴期和观察年。条件不一致会列差异，不给总排名。说明书案例、非保证演示、万能假设和开发稿分别查看。
5. 点击“查看逐笔现金流”核对投入、领取和退出价值。时点为原底稿的保单年度；本工具不计算任意报价，也不构造日历日期 XIRR。空值显示待核，不显示 0%。

## 只读转换与发布

在 Python 3.12 环境安装项目依赖，以下命令仅示例路径。输出必须在源项目与 Git 目录之外，使用管理员可读写的私人目录。Windows 文件 ACL 由宿主机管理，生产目录权限遵照 AGENTS.md；不得把受保护目录设置为静态挂载或同步到公开仓库。

```powershell
python -X utf8 scripts/build_product_center_package.py --source-root 'D:/work/007-产品管理' --output 'C:/private/product-import.zip'
python -X utf8 scripts/verify_product_center_data.py --source-root 'D:/work/007-产品管理' --report 'C:/private/numerical-regression.json'
```

转换白名单、临时身份及人工覆盖格式见[数据合同](PRODUCT_CENTER_DATA_CONTRACT.md)。出现身份歧义时，先核对原件并形成有来源 SHA、页码、理由和日期的私人覆盖记录，再用 `--overrides 'C:/private/reviewed-overrides.json'` 生成新包。不能仅因简称相似补配代码或产品。参数、费用和其他事实更正也必须回到有来源的结构化底稿并生成完整新批次；本期没有无来源自由编辑入口。

在“资料维护”上传 ZIP，先查看预检的产品/事实/情景/原件数量、覆盖差异、复算结果、身份映射和缺口；核对后勾选审核框并确认发布。预检不会改变查询中的当前批次。相同清单重复上传返回同一批次；结构、路径、哈希或数值错误拒绝整包。身份待核情景进入待核区，其余有来源条目可发布。

更正以完整新批次替换当前视图，不删除历史事实、来源和审核记录；产品内部 ID 按身份与来源版本生成。点击当前批次“撤回”恢复上一发布，首次发布撤回后为空目录。发布及撤回前均重验目标包和原件，缺损时拒绝切换。已归档批次可再次审核发布，其发布事件会记录当时的前一事件，避免反复发布造成循环。

## 存储和恢复

SQLite 位置沿用 `BUSINESS_ANALYSIS_DB`。资料默认放其相邻的 `product_center_data/`，可由 `PRODUCT_CENTER_DATA_DIR` 指定受保护目录，内含 `files/<sha256>.<扩展名>` 和 `packages/<清单哈希>.zip`。应用账号须对资料目录有读写权限，代码目录保持不可写。真实数据、原件、导入包及私人报告不入 Git、镜像或公开备份。

数据库与引用资料必须联合备份，包含历史批次原件及导入包。以下工具持有同一数据维护锁，使用 SQLite Online Backup，核验数据库完整性、资料哈希及包清单身份。数据库、归档哈希和恢复均按 1 MiB 分块处理，使用 ZIP64 支持多 GB 数据库。备份文件不覆盖，恢复只写新建或空目录。

```powershell
python -X utf8 scripts/backup_product_center.py create --database 'C:/private/business_data.db' --data-root 'C:/private/product_center_data' --archive 'C:/private/recovery-20261012.zip'
python -X utf8 scripts/backup_product_center.py verify --archive 'C:/private/recovery-20261012.zip'
python -X utf8 scripts/backup_product_center.py restore --archive 'C:/private/recovery-20261012.zip' --destination 'C:/private/recovery-check'
```

`restore` 只生成可审查的恢复目录，不切换运行库。实际恢复时先停服、保存故障现场与启动后的新增写入，明确恢复点，再按部署权限配置接入数据库和资料。不可仅凭数据库恢复成功认定资料可用。

## 后续生产发布

生产未在本次执行。获授权后，先备份生产 SQLite 与全部引用资料；从已测试可信提交生成归档，使用 `REBUILD_DATABASE=0 REBUILD_AGGREGATES=auto`，本迁移不触发聚合重建。已有 deploy.sh 的数据库备份不替代本模块联合备份，发布验收前须另外执行上述联合备份并验证恢复。

正式上传包、生产发布及验收分别按授权执行；核验本机健康、极空间 Nginx Proxy Manager 正式公网 HTTPS、鉴权、静态资源、业务数据、原件预览/下载与恢复后，再执行 `accept-release --confirm-review-complete`。不得用本地页面或 Ubuntu 80 端口代替公网验收。
