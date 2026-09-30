# 市场研判模型参数与接替路由（2026-09-30）

## 参数依据与用户确认

阿里云当前 [Qwen3.8-Max 模型页](https://help.aliyun.com/zh/model-studio/qwen3-8-max) 标注上下文 1,000,000 tokens、思考模式最大输入 983,616；不能把上下文等同单次最大输入。用户最初反馈没有 1M，核对官方页面后确认保留 1M。本项目采用该确认，不将 256K 写成模型官方属性。按当前 [Anthropic 兼容说明](https://help.aliyun.com/zh/model-studio/anthropic-api-messages)，合法思考档为 xhigh/medium/low，high 与 max 都映射 xhigh；此次从最高档降至 medium。

DeepSeek 使用独立官方端点；按其 [Claude Code 集成说明](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) 使用 deepseek-flash[1m]、CLAUDE_CODE_EFFORT_LEVEL=max、压缩窗口 786432。两通道子进程固定独立上下文与思考参数，凭据不混用。

| 角色 | 优先模型 | 接替模型 |
|---|---|---|
| 来源侦察、主研、首次修复、升级修复 | Qwen3.8-Max：1M、medium | DeepSeek Flash：1M、max |

`MARKET_ANALYSIS_QWEN_CONTEXT_TOKENS` 可按实际接入降低上限，默认 1000000；非法或超过官方上限的值回落默认值。低于 1M 时关闭 Claude Code 的 1M 标志并按上限的 75% 压缩。Qwen 模型名去掉旧 [1m] 后缀；DeepSeek 按官方集成保留该后缀。

## 接替与保护

百炼缺少凭据、认证/限流/网络/服务失败及超时才允许一次 DeepSeek 接替，受同阶段剩余预算与时间限制。预算、轮数、结构化输出或内容门禁失败不触发换供应商；两通道都失败保留上一期有效报告。9分质量门槛、独立来源核验、公众号分层和业务数据只读范围不变。

运行计划增加 contextTokens、fallbackReasoningEffort、fallbackContextTokens；实际调用事件记录模型自己的参数。报告如由 DeepSeek 成稿，记录实际模型的 max/1M，保留 configuredPrimary。历史报告与运行状态不回写。

安装脚本保留已存在的市场研判定时器启用与运行状态，代码发布不重新启动原本停用的定时器。配置变更保留在受保护服务器文件中。

## 验证边界

本次回归覆盖主通道成功不切换、缺凭据接替、接替次数与剩余预算、内容/预算门禁不切换、凭据与参数隔离、上下文上限校验、模型计划与实际报告参数。真实通道调用和生产发布结果见 RELEASE_REVIEW_v1.0.164.md；短调用不代表完整研究或百万 tokens 满载验收。
