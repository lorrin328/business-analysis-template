# 运行手册

## 客户清单网页增量导入

- 页面：`/customer-analysis` → `数据导入`；查看需要`customer_analysis`，预检和确认导入还需要`upload`。
- 支持CSV/XLSX；推荐CSV使用UTF-8 BOM。模板通过`GET /api/customer-analysis/import/template?format=csv|xlsx`下载。
- 创建任务：`POST /api/customer-analysis/import/uploads`；浏览器向`POST /api/customer-analysis/import/uploads/{uploadId}/files/{fileIndex}/chunks?offset=`顺序上传8MB分片。
- 文件完整后调用`POST /api/customer-analysis/import/uploads/{uploadId}/process`启动后台预检；用`GET /api/customer-analysis/import/uploads/{uploadId}`轮询`processing → ready|blocked|failed`。
- 预检为`ready`后调用`POST /api/customer-analysis/import/uploads/{uploadId}/commit`；继续轮询`importing → success|failed`，不需要重新上传文件。
- 批次：`GET /api/customer-analysis/import/batches`。批次只展示汇总，不提供客户或保单明细下载。
- 应用不设置固定文件大小、文件数和行数上限。实际可处理规模受`/var/lib/business-analysis`可用磁盘、临时解析库体积和后台处理时间约束；上传前应确保至少预留“源文件合计大小+归并临时库+SQLite增长+备份”的空间。
- 导入完成后核验：批次`status=success`、新增/更新/旧快照跳过数量、`linked_performance_policies`、客户页面数据截止日、保单匹配率、`PRAGMA quick_check`。
- 回滚：部署前使用SQLite Online Backup。客户增量业务回滚不得只删除批次记录；应从完整备份恢复，或使用经核验的更晚客户快照更正。
- 预检`ready`任务最多保留24小时；成功、阻断、失败或过期后清理受保护临时目录。全量历史库重建完成后，早于该全量批次的网页客户导入只保留审计，不再决定页面数据截止日。

## 全量历史库主看板性能

- 队伍增强应查询`agg_staff_month_performance`，产品结构应查询`agg_product_daily`；生产两表为空时虽然可回退原始明细，但应视为聚合未完成并立即排查。
- 查看规模：`SELECT COUNT(*) FROM agg_staff_month_performance;`、`SELECT COUNT(*) FROM agg_product_daily;`。当前全量基线分别约36.8万行、5.64万行。
- 全量聚合重建在5GB副本上约需6分钟、峰值内存约1.6GB。生产执行前先形成在线备份并停止主服务释放内存，完成后再启动服务。
- 代码部署保留生产库使用`REBUILD_DATABASE=0 sudo bash deploy/deploy.sh`；部署脚本会从运行库原始表按年度重建聚合，不会使用服务器根目录旧Excel覆盖数据。
- 重建后确认`PRAGMA integrity_check`、`PRAGMA quick_check`均为`ok`，并用`EXPLAIN QUERY PLAN`确认队伍查询命中`ix_staff_perf_year_month`、产品查询命中`ix_product_daily_filter`。
- 页面验收至少覆盖：主页面首次打开、产品年度/季度/月度切换、队伍模块保持折叠时不请求增强接口、展开后单次加载、客户分析页面正常打开。

## 全量历史业绩与客户分析

- 页面：`/customer-analysis`；权限：`customer_analysis`。管理员和高级用户默认开启，普通用户默认关闭。
- API：`GET /api/customer-analysis/overview`；支持 `year`、`periodType=year|quarter|month`、`periodValue`、`businessLine=OTO|证保|蚁桥`、`org` 和 `policyScope=all|longterm`。
- 页面中的保单状态取客户清单数据截止日快照；不得将“当前有效率”表述为13个月或25个月继续率。
- “持单与间隔”统计所选期间业绩客户的全部已知保单；首次复购间隔固定为第一张到第二张保单的承保日期间隔。

首次全量导入必须在生产运行库的SQLite Online Backup副本上执行，禁止直接对运行中的 `business_data.db` 导入：

```bash
sudo -u www-data /opt/business-analysis/backend/venv/bin/python /opt/business-analysis/backend/import_full_history.py \
  --database /var/lib/business-analysis/business_data.next.db \
  --source-dir /var/lib/business-analysis-import/full-history \
  --imported-by release

sudo -u www-data /opt/business-analysis/backend/venv/bin/python /opt/business-analysis/backend/audit_customer_analysis.py \
  --database /var/lib/business-analysis/business_data.next.db --full-integrity
```

当前2026-07-31批次门禁：

- 12份业绩文件、5份客户文件；
- `performance=5175228`；
- 客户源记录 `3539935`，保单快照 `3100006`；
- 业绩月份2007-07至2026-07，共229个月；
- `source_text_issue_rows=1710`，仅来自早期 `人员工号` 源文本替换字符；
- `PRAGMA integrity_check` 和 `PRAGMA quick_check` 均为 `ok`；
- 2026年度客户分析的保单关联率应为99%以上，未关联保单必须保留为“未关联”，不得删除后抬高匹配率。

候选库完成后，先停止服务，核对候选库所有者和权限，以同目录临时文件原子替换 `/var/lib/business-analysis/business_data.db`，再启动服务。回滚使用部署前在线备份，不得复制运行中的WAL主文件。

部署后至少验证：

```text
GET /api/health                                  -> 200, v1.0.123, latest_period=202607
GET /customer-analysis                           -> 200
GET /js/customer-analysis.js                     -> 200
GET /api/customer-analysis/overview              -> 未登录401
GET /api/customer-analysis/overview?year=2026    -> 管理员200
```

还需复核客户页六项首屏指标、五个页签、年度/季度/月度、业务、机构和长险筛选；“持单与间隔”应同时出现持单数、有效持单数、首次复购间隔和口径说明，并确认后台warning以上日志为空。


## 星钻月份与过程版本

- 页面：`/honor`；普通用户具备 `honor_view` 后可查看。
- 可用月份：`GET /api/honor/periods` 只列出状态成功且已有人员汇总结果的批次；页面默认选择最新年份、最新月份及该月截至日最新的版本。
- 月份查看不写库。需要形成新的过程版本时，由有 `honor_recalculate` 权限的用户在“数据与规则”填写过程截至日并重新测算。
- 过程批次验收：月份、数据版本、状态栏和说明中的年月及截至日必须一致；首屏“本月未达标”应与人员追踪未达标明细条数一致。
- 差额复核：个人追踪人数应等于达标人数加未达标人数；标保差额合计为逐个未达标人员 `max(门槛-当月标保, 0)` 之和，缺长险件人数为长险件数未达到1件的未达标人数。
- OTO个人标保门槛2万元，证保个人标保门槛3万元；两者均至少1件长险。主管、经理团队规则不并入个人差额。

## 证保网点分析

- 页面：`/branch-analysis`；登录后通过主导航“网点分析”进入。
- 权限：`branch_analysis`；管理员和高级用户默认开启，普通用户默认关闭。
- 实际名单保存在项目本地 `data/reference/证保网点参考表.csv` 和生产运行库，不进入公开GitHub。
- 本地生成：`python scripts/build_branch_reference.py --source "<证保业务报表.xlsx>" --output "data/reference/证保网点参考表.csv"`。
- 生产导入前先执行SQLite在线备份；再以`www-data`身份运行 `backend/import_branch_reference.py --source <私密CSV>`。
- 导入门禁：必须为147个常规网点、86个转介绍网点，参考编号和网点名称均唯一；失败时事务回滚。
- 期间接口：年度累计使用`periodType=year`；季度使用`periodType=quarter&periodValue=1..4`；月度使用`periodType=month&periodValue=1..12`。`asOf`用于限制统计截止，已完成自然期间自动落到期末。
- 部署后验证页面和脚本返回200、未登录API返回401、普通用户返回403；管理员API应返回`regularStock=147`、`referralStockExcluded=86`。
- 数据勾稽：匹配保费与待匹配保费合计应等于证保总期交；广发主网点汇总保费不得在常规匹配额与转介绍贡献中重复相加。

## 市场研判服务

- 安装与完整运维流程见 `docs/MARKET_ANALYSIS.md`。
- 生产研究服务：`market-analysis.service`；定时检查服务：`market-analysis-scheduled.service`；定时器：`market-analysis.timer`。timer每天北京时间凌晨1点检查，距最近成功报告满3个自然日才启动研究；不足3天正常跳过，不调用模型。
- 运行数据：`/var/lib/business-analysis-market`；受保护配置：`/etc/business-analysis-market/market-analysis.env`。
- 手工触发：管理员可在市场研判页点击“立即运行研究”；服务器仍可执行 `sudo systemctl start market-analysis.service`。网页触发链由 `market-analysis-manual.path` 监听固定请求文件，root helper 只允许启动固定研究服务，并设5分钟冷却，不使用 sudoers。
- 查看结果：`sudo systemctl status market-analysis.service --no-pager`、`sudo journalctl -u market-analysis.service -n 100 --no-pager`；触发器状态使用 `systemctl status market-analysis-manual.path --no-pager`。
- 查看定时判断：`systemctl list-timers market-analysis.timer --all`、`sudo journalctl -u market-analysis-scheduled.service -n 30 --no-pager`。timer显示的是下一次凌晨1点“到期检查”，不等同于每晚都执行完整研究；失败报告不会更新成功日期，因此次日凌晨1点自动重试。
- 失败处置：先查看 `status.json` 和 journal；不要删除 `latest.json`，模型失败时网页应继续展示上一期有效报告。
- 失败恢复：服务保留6小时修复检查点；来源计数、字段长度、来源标题/日期/摘录及变化信号映射等确定性错误会复用已有报告，不重新执行整轮模型研究。历史主题起始日期和上一报告编号由程序从最近已发布主题自动续接；变化信号按当前模块状态重建，每个模块必须恰好出现一次。冗余坏源只有在每个引用项仍满足证据等级且总来源不少于8项时才会剔除；结构或证据错误最多执行两轮定向修复，同业一手证据不足时改搜可核验的公司/协会页面，证据门槛不降低。
- 模型路由：主研`MARKET_ANALYSIS_PRIMARY_MODEL=deepseek-v4-pro[1m]`；第一次修复`MARKET_ANALYSIS_REPAIR_MODEL=deepseek-v4-flash`；第二次升级`MARKET_ANALYSIS_ESCALATION_MODEL=deepseek-v4-pro[1m]`。`ANTHROPIC_DEFAULT_HAIKU_MODEL`和`CLAUDE_CODE_SUBAGENT_MODEL`均使用Flash。修改后先做Flash最小JSON调用，再用dry-run核对`modelPlan`，不得输出受保护环境文件全文。
- 调用审计：`status.json.modelCalls`记录本次调用角色、模型、耗时、轮次、token、WebSearch/WebFetch次数和CLI估算成本。CLI估算值不等于DeepSeek实际账单，只用于同一链路的相对比较；不得将提示词、密钥和网页正文写入状态。
- 证据边界：独立抓取负责确定真实标题、发布日期、内容哈希和50字内原文锚点；发布前模块“事实”会收敛为最接近的已核验原文，判断、影响和行动属于模型推演，页面不得把二者混为同一事实层。
- 凭据轮换：同时更新 DeepSeek Key 和主应用/研究服务的 AI 只读 Token；验证旧值失效后再启用 timer。
- TLS链修复：禁止使用`-k`或关闭验证。2026-08-02为中国人寿站点安装的中间证书为`DigiCert Secure Site OV G2 TLS CN RSA4096 SHA256 2022 CA1`，DER SHA256=`7cd6cdd25eee2512aaf1419afd44c146c43aa1093d5a60d4ed39efbdda815ad4`，来源为叶子证书AIA指向的DigiCert官方地址。若证书更新或失效，必须重新读取AIA并核验，不机械复用旧文件。

## Windows 本地开发环境

### 前置工具

- Python 3.10+
- Git
- uv

### 推荐检查命令

```powershell
python --version
uv --version
git --version
```

### 安装依赖并运行测试

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### Windows 预检

```powershell
powershell -ExecutionPolicy Bypass -File scripts\preflight.ps1
```

若当前进程尚未继承新 PATH，可重启 PowerShell 后重试。

## Docker 镜像构建与发布

GitHub Actions 会在 `master` 分支推送、`v*` tag 推送或手动触发时构建镜像：

```bash
ghcr.io/lorrin328/business-analysis-template:latest
```

## Docker Compose 启动

```bash
docker compose up -d
docker compose logs -f business-analysis
```

访问：

```text
http://<server-ip>:45679
```

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

## Ubuntu systemd 部署

当前非 Docker 部署路径：

```text
代码：/opt/business-analysis
数据库：/var/lib/business-analysis/business_data.db
日志：/var/log/business-analysis/app.log
```

代码部署：

```bash
sudo bash deploy/deploy.sh
```

已有生产数据库时，部署脚本默认不再使用 `/opt/business-analysis/` 根目录中的 Excel 全量重建数据库，避免旧 Excel 覆盖 Web 页面导入后的最新数据。脚本会用 SQLite Online Backup API 备份当前库，校验完整性并生成 SHA256 元数据，再基于 SQLite 原始明细表重建聚合；重建失败时部署中止。

如确需用服务器根目录 Excel 全量重建数据库，必须显式执行：

```bash
REBUILD_DATABASE=1 sudo bash deploy/deploy.sh
```

服务：

```bash
sudo systemctl status business-analysis
sudo systemctl restart business-analysis
sudo journalctl -u business-analysis -f
```

nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx
```

部署后静态资源边界验证：

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/honor
curl -I http://127.0.0.1/scheme-calculator.html
curl -I http://127.0.0.1/js/api-client.js

# 以下路径必须返回 404
curl -I http://127.0.0.1/backend/main.py
curl -I http://127.0.0.1/deploy/nginx.conf
curl -I http://127.0.0.1/.git/config
curl -I http://127.0.0.1/backend/business_data.db
curl -I http://127.0.0.1/targets_import.json
curl -I http://127.0.0.1/Dockerfile
curl -I http://127.0.0.1/requirements.txt
```

若任一敏感路径返回 200，立即停止对外访问，检查 `/etc/nginx/sites-enabled/business-analysis` 是否已同步仓库中的 `deploy/nginx.conf`，执行 `sudo nginx -t && sudo systemctl reload nginx` 后重新验证。

健康检查：

```bash
curl http://127.0.0.1:45679/api/health
```

首次部署要求：

- 初始化首个管理员账号时必须提供 `DEFAULT_ADMIN_PASSWORD`。
- 初始密码应仅通过临时环境变量或安全配置注入，不得写入仓库、日志或项目记忆。
- 首次登录后建议立即修改管理员密码。
- 生产环境默认关闭公开自助注册；确需开放时在 `/opt/business-analysis/deploy/.admin_env` 设置 `AUTH_ALLOW_PUBLIC_REGISTRATION=1` 并重启服务，关闭时改为 `0` 或移除该配置并重启服务。
- `/opt/business-analysis/deploy/.admin_env`、`.ai_env`、`.webhook_env` 属于服务器运行时配置，部署脚本会保留并收敛为 root 管理；不得提交到 Git。
- webhook 自动部署已暂停。正常状态为 `webhook-deploy` disabled/inactive、`/etc/sudoers.d/webhook-deploy` 不存在、`/webhook/deploy` 返回 404。
- `/opt/business-analysis` 应为 `root:root` 且 `www-data` 不可写；仅 `/var/lib/business-analysis` 和 `/var/log/business-analysis` 归 `www-data`。

## 方案计算

### 页面入口

1. 登录主看板。
2. 点击顶部“方案计算”。
3. 在方案选择弹层中选择“2026年组发政策”。
4. 有 `scheme_upload` 权限时，可在“方案专用上传”区域上传 `组织发展追踪模板.xlsx`。

### 接口

```text
GET  /api/scheme/options
GET  /api/scheme/latest?schemeId=2026-org-dev-policy
POST /api/scheme/upload
```

上传字段：

```text
schemeId=2026-org-dev-policy
tracking=<.xlsx 文件>
```

### 权限

- `scheme_calculation`：查看方案列表和最近一次测算结果。
- `scheme_upload`：上传方案专用 Excel 并写入方案测算批次。

### 本地验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scheme_calculation.py tests\test_frontend_static.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

### 注意

- 方案上传独立于主经营数据导入，不会写入 `/api/upload` 使用的 `data_imports` 或经营聚合表。
- 当前“2026年组发政策”页面展示的是底稿测算结果与复核提示；推荐人奖励、有效保单 45 日观察、回执回访、犹豫期、自保互保等字段补齐前，不能视为全自动最终结算结果。

## 荣誉体系过程追踪

### 月底最终版

1. 打开 `/honor.html`。
2. 选择年份和月份。
3. “过程截至”保持为空。
4. 点击“重新计算”。
5. 在“荣誉追踪”页签核对会员总览、机构排行、TOP3、新晋、晋升和会员清单。

### 月中过程版

1. 打开 `/honor.html`。
2. 选择年份和月份。
3. 在“过程截至”填写日期，例如 `2026-07-15`。
4. 点击“重新计算”。
5. 页面状态会显示“过程截至 YYYY-MM-DD”，该批次写入 `honor_import_batches.source_cutoff`。

### 注意事项

- 过程截至日不能早于所选月份首日；可以晚于月末，用于导入次月初清单后核对上月最终结果。
- 有承保/入账日期的保单按日期截断；同月缺承保/入账日期且无法判断是否已发生的记录会进入异常提示，不强行计入过程结果。
- 同一月份可以保留多个过程截至日批次；如需读取某个过程版本，可请求 `/api/honor/dashboard?year=2026&month=7&asOf=2026-07-15`。

## 数据与日志

- Docker SQLite 数据库：`business-analysis-data` volume，对应容器内 `/data/business_data.db`。
- Docker 应用日志：`business-analysis-logs` volume，对应容器内 `/app/backend/logs`。
- systemd 部署数据库：`/var/lib/business-analysis/business_data.db`。
- systemd 应用日志：`/var/log/business-analysis/app.log`。

## 回滚

如某次镜像异常，优先回滚到上一个 tag 或 sha 镜像。systemd 回滚应先停服务，使用 `backend/backup_database.py` 将 `/opt/business-analysis-backups/` 中通过完整性校验的数据库备份恢复到新的临时文件，核验后原子替换 `/var/lib/business-analysis/business_data.db`，再回退代码版本并重启服务；不得直接把 WAL 运行库主文件相互覆盖。
