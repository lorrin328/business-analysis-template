# 寿险市场滚动研判运行说明

## 结论

生产运行采用 Claude Code CLI 直接连接 DeepSeek 官方 Anthropic 兼容端点，固定模型为 `deepseek-v4-pro[1m]`。当前只有单一生产模型，服务器不依赖 CC Switch；模型配置由 `/etc/business-analysis-market/market-analysis.env` 管理，减少桌面工具、配置同步和 headless 兼容故障。

Web 服务不直接调用模型。独立 `market-analysis.service` 每次完成多源搜索、历史归并、结构化输出和证据校验，只有通过门禁的 JSON 才会替换 `latest.json`；失败时网页继续显示上一期有效报告。

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
MARKET_ANALYSIS_MODEL=deepseek-v4-pro[1m]
CLAUDE_CODE_EFFORT_LEVEL=max
```

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
2. `latest.json` 四层完整，至少8项来源，全部 `evidenceIds` 可解析；
3. 宏观和监管有 A 级官方原文，同业有公司/协会一手来源；每条来源均有可在 HTML、正文文本、PDF 或内部快照中逐字定位的 50 字内证据锚点；
4. `/api/market-analysis/latest` 登录后可读，普通用户未授权时返回403；
5. `/market-analysis.html` 可切换历史期次，桌面和手机无横向溢出；
6. timer 显示下一次约三天后运行，失败时 `latest.json` 不被覆盖。

发布门禁还会阻止：页面标题不符、最终 URL 不一致、非公开地址、敏感查询参数、非标准端口、正文不可提取、事实与证据片段不匹配、事实数字未出现在证据、历史主题跳过最新一期或篡改 `history.since`。

独立抓取完成后，程序以实际页面内容校准标题、可核验发布日期和证据摘录；每个模块的“事实”直接采用最匹配的已核验原文锚点，模型的业务解释仅保留在判断、影响、复核条件和行动字段。该处理不会把证据不足的模型转述自动认定为事实。

## 日常运维

```bash
systemctl status market-analysis.timer --no-pager
systemctl status market-analysis.service --no-pager
journalctl -u market-analysis.service --since '7 days ago' --no-pager
sudo systemctl start market-analysis.service
```

失败后优先查看 journal 中的校验错误。6小时内的修复检查点会复用已完成研究，来源元数据类错误不会再次调用模型；服务仅自动重试一次，防止网络或模型故障形成无限循环和重复费用。

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
