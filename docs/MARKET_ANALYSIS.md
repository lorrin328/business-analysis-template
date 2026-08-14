# 寿险市场滚动研判运行说明

## 结论

生产运行采用 Claude Code CLI 直接连接 DeepSeek 官方 Anthropic 兼容端点，使用“Pro主研、Flash首修、Pro升级”的质量优先组合。服务器不依赖 CC Switch；模型配置由 `/etc/business-analysis-market/market-analysis.env` 管理，减少桌面工具、配置同步和headless兼容故障。

Web 服务不直接调用模型。独立 `market-analysis.service` 每次完成多源搜索、历史归并、结构化输出和证据校验，只有通过门禁的 JSON 才会替换 `latest.json`；失败时网页继续显示上一期有效报告。

管理员也可在市场研判页点击“立即运行研究”。页面只提交后台请求，不等待模型运行完成。定时器每天北京时间凌晨1点检查一次；只有距上次成功报告已满3个自然日才启动研究。手动任务成功后，以该报告日期重新计算后续三个自然日周期。

## 首次安装

在可信发布包根目录执行：

```bash
sudo bash deploy/install-market-analysis.sh
```

脚本使用 Claude Code 官方安装器，建立 `market-ai` 隔离账号、`market-analysis` 共享只读组、运行目录、受保护配置目录、service 和 timer。配置未完整时 timer 保持关闭。

## 安全配置

编辑：

```text
/etc/business-analysis-market/market-analysis.env
```

至少安全写入：

- `ANTHROPIC_AUTH_TOKEN`：已轮换且未在聊天、日志和仓库出现的新 DeepSeek Key；
- `AI_READONLY_TOKEN`：与主应用一致、已轮换的聚合经营快照只读 Token。

文件必须为 `root:market-analysis`、权限 `0640`。不要在命令行参数、shell 历史、Git、项目 `.env`、systemd unit 或日志中写真实值。

固定模型配置：

```text
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
MARKET_ANALYSIS_MODEL=deepseek-v4-pro[1m]
MARKET_ANALYSIS_PRIMARY_MODEL=deepseek-v4-pro[1m]
MARKET_ANALYSIS_REPAIR_MODEL=deepseek-v4-flash
MARKET_ANALYSIS_ESCALATION_MODEL=deepseek-v4-pro[1m]
MARKET_ANALYSIS_REPAIR_MAX_BUDGET_USD=3
MARKET_ANALYSIS_ESCALATION_MAX_BUDGET_USD=6
MARKET_ANALYSIS_MIN_QUALITY_SCORE=9.0
CLAUDE_CODE_EFFORT_LEVEL=max
```

首次深度研究和最终跨期综合由Pro完成；Claude Code的Haiku/轻量子任务和第一次定向修复使用Flash。Flash修复后仍不合格时只允许再用Pro升级修复一次，仍失败则不发布。CLI的`total_cost_usd`仅作为调用相对观察值，实际扣费以DeepSeek控制台为准。

## 首次验证与启用

```bash
sudo -u market-ai -g market-analysis /usr/local/bin/claude --version
sudo systemctl start market-analysis.service
sudo systemctl status market-analysis.service --no-pager
sudo journalctl -u market-analysis.service -n 100 --no-pager
sudo systemctl enable --now market-analysis.timer
systemctl list-timers market-analysis.timer --all
```

验收：

1. `status.json` 为 `success`，且无凭据、Cookie 或客户明细；
2. `latest.json` 四层完整，每层2—4个模块，至少12项来源、4项官方来源、5个发布主体和5个外部域名，全部 `evidenceIds` 可解析；
3. 宏观和监管有 A 级官方原文，每个同业模块均有公司/协会一手来源；每条来源均有可在 HTML、正文文本、PDF 或内部快照中逐字定位的 50 字内证据锚点；
4. `/api/market-analysis/latest` 登录后可读，普通用户未授权时返回403；
5. `/market-analysis.html` 可切换历史期次，桌面和手机无横向溢出；
6. timer 的下一次检查时间为次日凌晨1点；只有满3个自然日才启动完整研究，失败时 `latest.json` 不被覆盖并在次日凌晨1点重试；
7. `qualityAssessment.score` 不低于9.0，页面展示证据、覆盖、滚动分析、行动闭环和运行可靠性五项分值。

发布门禁还会阻止：页面标题不符、最终 URL 不一致、非公开地址、敏感查询参数、非标准端口、正文不可提取、事实与证据片段不匹配、事实数字未出现在证据、历史主题跳过最新一期或篡改 `history.since`。

来源计数、模块短标题及页面字段长度由程序按实际报告自动校准。生产9分门槛启用后，独立验证失败的外部来源只在所有引用项仍有替代证据、宏观/监管模块仍保留官方 A 级、每个同业模块仍保留一手 A/B 级且总来源仍不少于12项时才会剔除，并在研究边界中留下记录；唯一或关键证据失败时继续阻止发布。

行动提示同时是跨期台账。`actionKey`标识同一管理任务，`status`区分新增、持续、调整和完成，`progress`记录本期变化，`acceptanceMetric`定义验收标准，`nextReviewAt`明确下次复核日期；相同行动不能重新包装为“新增”，完成状态必须有内部证据。

独立抓取完成后，程序以实际页面内容校准标题、可核验发布日期和证据摘录；每个模块的“事实”直接采用最匹配的已核验原文锚点，模型的业务解释仅保留在判断、影响、复核条件和行动字段。该处理不会把证据不足的模型转述自动认定为事实。

已发布主题的 `history.since` 和上一报告编号属于仓库权威元数据，生成后由程序按最近一期自动续接。模型仍负责判断持续、强化、反转或失效，程序不替模型改变模块判断类别；五类变化信号则由程序依据当前模块的 `history.state` 确定性重建，保证每个模块恰好出现一次。历史遗留、重复或与模块状态冲突的信号不会进入发布结果。

失效主题必须在本期保留一个相同 `topicKey` 的当前模块，将其 `history.state` 标为 `expired`，并引用本期可核验证据解释失效原因。没有当前失效模块的历史主题不会被单独列入 `expired`，避免“模块仍持续、信号却失效”的结构冲突。

## 手动运行

- 仅管理员显示并可调用“立即运行研究”。
- FastAPI 只能在 `/run/business-analysis-market-trigger/request` 创建一次性请求文件。
- `market-analysis-manual.path` 监听该文件，由 root 运行固定 helper，并且只能启动 `market-analysis.service`。
- helper 设有5分钟冷却；研究已运行时重复请求不会启动第二个进程。
- 该链路不使用 sudoers，不允许网页传入服务名、命令或参数。

查看触发链路：

```bash
systemctl status market-analysis-manual.path --no-pager
systemctl status market-analysis-manual.service --no-pager
journalctl -t business-analysis-market-trigger -n 30 --no-pager
```

## 日常运维

```bash
systemctl status market-analysis.timer --no-pager
systemctl status market-analysis.service --no-pager
journalctl -u market-analysis.service --since '7 days ago' --no-pager
sudo systemctl start market-analysis.service
```

`market-analysis.timer` 每天凌晨1点唤醒 `market-analysis-scheduled.service`。调度器只读取最近成功报告的北京时间日期：日期间隔不足3天时正常退出，不调用模型；满3天时启动固定的 `market-analysis.service`。服务器凌晨1点关机时，`Persistent=true` 会在恢复开机后补做到期检查。

失败后优先查看journal中的校验错误。6小时内的修复检查点会复用已完成研究，来源元数据和变化信号映射类错误会先由程序确定性修复，不再次调用模型；结构或证据不合格时先用Flash定向修复，仍失败再升级Pro一次。同一进程遇到无法安全剔除的坏源时直接进入该修复链，不再先等待systemd重启。同业事实缺少一手依据时允许换成另一项有真实公司/协会来源支持的近期动作，但不得把媒体来源改标为一手证据。

TLS 验证不得使用 `-k`、关闭证书校验或把任意站点加入例外。若一手网站漏发中间证书，只能从叶子证书 AIA 指向的CA官方地址取得对应中间证书，核验主体、`CA:TRUE`和SHA256后加入系统信任链，并再次用研究服务自己的验证器确认标题、日期和摘录全部匹配。

报告目录：

```text
/var/lib/business-analysis-market/latest.json
/var/lib/business-analysis-market/status.json
/var/lib/business-analysis-market/reports/
```

## 模型切换

若未来确有多模型切换需求，先在测试运行中验证 Anthropic 接口、WebSearch/WebFetch、长上下文、JSON 输出和工具调用，再修改受保护环境文件。生产变更不依赖 CC Switch；如另行安装 CC Switch/其 CLI，只作为管理员辅助工具，不能成为 timer 的必需运行链路。

## 回滚

停止自动研究不会影响经营看板：

```bash
sudo systemctl disable --now market-analysis.timer
```

保留 `/var/lib/business-analysis-market` 即可继续查看历史与上一期有效报告。回滚代码后不要删除报告目录或把运行目录授权给 `www-data` 写入。
