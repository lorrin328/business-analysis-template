# 市场研判切换阿里百炼 qwen3.8-max（2026-09-27）

## 结论

市场研判子系统的四个模型角色（来源侦察、主研、首次修复、升级修复）统一改为阿里百炼（Model Studio）`qwen3.8-max`，思考深度固定 `high`，并改为单供应商路由。本次只完成代码、配置模板、部署脚本、前端标签与本地回归；**未使用真实百炼 API Key 发起过任何实际调用，未推送 GitHub，未构建镜像，未部署 Ubuntu 生产**。生产仍为 v1.0.159 且仍走 Kimi 通道。

## 接入参数（逐项核对官方文档）

| 项目 | 取值 | 依据 |
|---|---|---|
| 端点 | `https://dashscope.aliyuncs.com/apps/anthropic` | 百炼「Anthropic兼容-Messages」按量计费接入信息；华北2（北京） |
| 端点约束 | 只能到 `/apps/anthropic`，不得追加 `/v1` | 该端点仅提供 `/v1/messages`，无 `/v1/models`；追加 `/v1` 会让 Claude Code 的模型发现拼出 `/v1/v1/models` 并返回 404 |
| 鉴权 | 百炼 API Key（`sk-` 开头），`Authorization: Bearer` 或 `x-api-key` | 同上；401 `invalid_api_key` 的常见原因即 Key 类型与 base_url 不配套 |
| 模型 ID | `qwen3.8-max`（快照 `qwen3.8-max-0902`，别名 `qwen3.8-max-2026-09-02`） | 百炼「qwen3.8-max 模型信息」，且该模型在 Anthropic 兼容支持列表的千问 Max 系列内 |
| 上下文 | 1,000,000 tokens；思考模式下最大输入 983,616，最大输出 131,072，最大思维链 262,144 | 同上 |
| 思考深度 | `high` | 百炼规定 qwen3.8-max 的 `output_config.effort` 合法档位为 `xhigh`/`medium`/`low`，并明确 **`max`、`high` 映射为 `xhigh`**，默认值即 `xhigh` |
| 计价（华北2-北京原价） | 输入 12 元/百万 tokens，输出 36 元/百万 tokens，缓存命中输入 1.5 元/百万 tokens，显式缓存创建 15 元/百万 tokens | 百炼模型价格页 |

**思考深度口径说明**：百炼对 qwen3.8-max 只承认 `xhigh`/`medium`/`low` 三档，`high` 是 `xhigh` 的别名。因此本项目配置的 `high` 等价于该模型的最高思考档，且不会因取值非法被拒。程序侧对未知取值一律回落 `high`，不把非法值发往百炼。百炼同时说明 `thinking.budget_tokens` 即将废弃、新接入建议用 `output_config.effort`；本项目经 Claude Code CLI 调用，由 `CLAUDE_CODE_EFFORT_LEVEL` 承载该档位。

## 代码落点

| 文件 | 变更 |
|---|---|
| `backend/market_analysis/model_router.py` | 新增百炼通道：`is_bailian()`、`provider_name()` 返回「阿里百炼」、`availability_fallback()`、`reasoning_effort()`、`bailian_base_url()`、`bailian_credential()`、`_is_bailian_host()`；`provider_environment()` 增加百炼分支，注入端点、1M 上下文、786432 压缩窗口与 `CLAUDE_CODE_EFFORT_LEVEL`；凭据擦除清单加入三个百炼 Key；`availability_failure()` 识别 `AccessDenied`/`Arrearage`/`Flow control`/`Throttling` |
| `backend/run_market_research.py` | `DEFAULT_MARKET_MODEL` 改为 `qwen3.8-max`；`resolve_model_plan()` 输出 `bailian_qwen38_max_all_roles` 与 `reasoningEffort`；`invoke_claude()` 由硬编码 `k3-256k` 改为按 `availability_fallback()` 判定，单供应商通道使用完整阶段超时且不改换供应商；失败事件的 provider 改为动态取值；报告 `model` 增加 `reasoningEffort`；两处凭据存在性检查纳入百炼 Key |
| `deploy/market-analysis.env.example` | 百炼端点与 `BAILIAN_ANTHROPIC_BASE_URL`、`DASHSCOPE_API_KEY`/`BAILIAN_API_KEY`、四角色统一 `qwen3.8-max`、`CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000`、`MARKET_ANALYSIS_REASONING_EFFORT=high`、`CLAUDE_CODE_EFFORT_LEVEL` 由 `max` 改为 `high` |
| `deploy/install-market-analysis.sh` | 路由探测优先百炼 Key（其次 Kimi、最后 DeepSeek）；写入 `BAILIAN_ANTHROPIC_BASE_URL`、思考深度与 1M 上下文；定时器凭据门槛纳入 `DASHSCOPE_API_KEY`/`BAILIAN_API_KEY` |
| `deploy/configure-market-analysis.sh` | 交互提示改为「百炼 API Key」，变量改名 `BAILIAN_TOKEN`，仅写入 `DASHSCOPE_API_KEY`，避免旧 DeepSeek 路由读取通用 Token；健康检查通过后同步模型路由并启用凌晨1点定时器，不立即启动研究 |
| `js/market-analysis.js` | `shortModelName()` 识别 `qwen3.8-max` 与 `k3-256k`；`modelPlanLabel()` 追加「· 思考深度 high」 |

## 凭据隔离

- 子进程只接收本通道凭据。百炼分支会移除 `KIMI_CODE_API_KEY`、`DEEPSEEK_AUTH_TOKEN`、`AI_READONLY_TOKEN`、`ZHIHU_ACCESS_SECRET`、Hermes 密钥以及全部百炼 Key 本身，只以 `ANTHROPIC_AUTH_TOKEN` 传递一个值，且不同时保留 `ANTHROPIC_API_KEY`。
- 与既有 DeepSeek 分支一致：**仅当**未显式指定 `BAILIAN_ANTHROPIC_BASE_URL` **且**环境 `ANTHROPIC_BASE_URL` 主机确属 `aliyuncs.com` 时，才允许复用通用 `ANTHROPIC_AUTH_TOKEN`；其他供应商域名下的通用 Token 一律拒绝，避免把 Kimi 或 DeepSeek 凭据发往百炼。
- 真实 Key 只允许写入服务器 `/etc/business-analysis-market/market-analysis.env`（`root:market-analysis`、`0640`），不进 Git、镜像、命令行参数、shell 历史、日志或对话。

## 向后兼容

- Kimi `k3-256k` 与 DeepSeek `deepseek-flash` 分支完整保留；配置了对应 Key 时仍可路由，`kimi_primary_deepseek_fallback` 策略与「仅一次备用调用、剩余预算与时间内改换」的行为不变。
- 历史报告与运行台账中的 `provider`/`name` 字段不回写，仍显示当时的 Kimi Code 或 DeepSeek。
- 门禁语义不变：预算耗尽、轮数耗尽、结构化输出失败与内容不合格都不触发跨供应商重试；9.0 分五维门槛、独立来源核验、公众号与知乎证据分层、上一期有效报告保护全部保持原样。
- 本次不改变数据库结构、聚合口径或导入数据，**无需**新增 `schema_migrations` 版本，也不需要 `requires_aggregate_rebuild=1`。

## 验证

| 项目 | 结果 |
|---|---|
| Python 回归 | 950 项通过、3 项平台相关跳过（v1.0.159 基线为 938 项通过，本次净增 12 项） |
| Node 前端测试 | 57 项通过、0 失败 |
| 新增路由测试 | `tests/test_market_model_router.py` 由 10 项增至 25 项：凭据隔离与不泄漏、端点 `/v1` 剥除、思考深度默认值与非法值回落、单供应商不改换、完整阶段超时、`--model` 原样透传、预算上限不跨通道 |
| Shell 语法 | `bash -n` 通过（install 与 configure） |
| JS 语法 | `node --check` 通过 |
| 行尾 | `.sh` 保持纯 LF，符合 `.gitattributes`；未产生无关的整文件行尾变更 |

## 未验证边界（不得据此宣称已生效）

- **没有用真实百炼 API Key 发起过一次实际调用**。因此未验证：Claude Code CLI 与百炼端点的真实握手、`CLAUDE_CODE_EFFORT_LEVEL` 到 `output_config.effort` 的实际映射效果、固定 JSON Schema 强约束在该模型下的成稿率、1M 上下文在长研究任务中的真实表现。
- 未验证百炼对 Claude Code `--max-budget-usd`、`--allowedTools WebSearch/WebFetch`、`--no-session-persistence` 的兼容行为。百炼端点不提供 `/v1/models`，Claude Code 的模型发现会 404，需在真机确认不影响 `-p` 非交互调用。
- 未验证整期研究能否通过 9.0 分门禁与独立来源核验；模型更换可能改变首次成稿率与修复次数，需以运行台账实测，不能沿用 Kimi 通道的历史指标。
- 未推送 GitHub、未构建镜像、未部署 Ubuntu；未做公网、鉴权、静态资源与业务数据验收。
- 成本口径未实测。CLI 的 `total_cost_usd` 仍是相对观察值，实际扣费以百炼控制台为准。

## 上线前必做

1. 在服务器先执行 `sudo bash deploy/install-market-analysis.sh` 确认市场服务已安装，再执行 `sudo bash deploy/configure-market-analysis.sh` 交互写入百炼 API Key；配置脚本会同步模型路由并启用凌晨1点定时器，不立即启动研究。
2. 检查受保护配置的模型字段、定时器下一次触发时间和服务状态，确认路由为 `qwen3.8-max`、思考深度为 `high`。
3. 先跑只读验证 `run_market_research.py --source-scout-only`，确认真实握手、鉴权与工具可用；该模式不发布报告、不覆盖历史、不改运行状态。
4. 再跑 `--dry-run`，核对模型计划四角色均为 `qwen3.8-max`、`reasoningEffort=high`、`fallback=null`。
5. 通过后手动触发一次完整研究，核对成稿、9 分门禁、来源独立核验，以及市场研判页显示「模型组合 Qwen3.8-Max… · 思考深度 high」。
6. 观察首期运行台账的首次成稿率、修复次数、耗时与 token，与 Kimi 通道历史期次对比后再决定长期保留。
7. 按既定发布纪律完成公网、鉴权、静态资源、业务数据与备份验证后再执行 accept-release；健康接口通过不等于验收完成。

## 参考

- 百炼 Claude Code 接入：https://help.aliyun.com/zh/model-studio/claude-code
- 百炼 Anthropic 兼容 Messages：https://help.aliyun.com/zh/model-studio/anthropic-api-messages
- qwen3.8-max 模型信息：https://help.aliyun.com/zh/model-studio/qwen3-8-max
- 深度思考与思考模式：https://help.aliyun.com/zh/model-studio/deep-thinking
- 本仓库既有通道说明：`KIMI_CHANNEL_20260916.md`（已由本文取代）、`CC_MODEL_UPDATE_20260911.md`
