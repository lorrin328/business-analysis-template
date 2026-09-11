# CC模型更新（2026-09-11）

用户指定将旧模型更名为deepseek-flash，启用1M上下文。官方接入说明：https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/

- 研究默认模型及来源侦察、主研、修订、升级修订统一为deepseek-flash；worker显式传递deepseek-flash[1m]到CC，避免--model覆盖环境默认值后失去长上下文。
- CC默认、Opus和Sonnet映射为deepseek-flash[1m]；Haiku和子任务映射按官方示例使用deepseek-flash。
- CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432，CLAUDE_CODE_DISABLE_1M_CONTEXT=0。1M是上下文窗口，自动压缩阈值与最大输出长度是不同参数。
- 保留原有预算、研究门禁、调度、密钥及历史报告。仅发布市场worker和部署配置，不重建数据库。
- 相关82项测试通过。Ubuntu实际调用验收结果另补录；没有进行1M tokens满载测试。
