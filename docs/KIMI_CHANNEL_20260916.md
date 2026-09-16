# Kimi Code主通道与DeepSeek备用（2026-09-16）

用户授权本项目使用Kimi Code k3-256k为主力，无法调用时路由至DeepSeek。官方说明：https://www.kimi.com/code/docs/en/third-party-tools/claude-code.html

- Kimi：固定官方Anthropic兼容地址`https://api.kimi.com/coding/`，模型`k3-256k`，上下文/压缩窗口262144。
- DeepSeek备用：`https://api.deepseek.com/anthropic`，`deepseek-flash[1m]`，上下文1000000、压缩窗口786432。
- KIMI_CODE_API_KEY与DEEPSEEK_AUTH_TOKEN仅在受保护的生产环境文件配置；子进程仅接收本通道凭据，移除其他通道密钥、内部只读接口及知乎密钥。禁用CC settings来源，防止用户/项目文件覆盖路由凭据。
- 每阶段优先Kimi；仅Provider鉴权/限流/HTTP服务错误、网络错误及超时触发一次DeepSeek备用。预算耗尽、轮数耗尽、结构化输出失败及报告内容不合格不触发备用。
- Kimi调用最多900秒，且不超过该阶段总时限的一半；备用只使用剩余时限和已知CLI估算预算余额。超时无法取得完整用量时不能保证CLI估算总额等同真实账单。
- 不更改报告发布门槛或原有阶段预算。遥测分别记录实际模型和通道，报告主模型按成功的主研调用记录；执行过程内环境隔离，不修改进程全局环境。
- 安装脚本检测受保护配置中的Kimi密钥后选择Kimi各阶段；未配置Kimi的旧安装仍可使用DeepSeek。通用ANTHROPIC配置保留DeepSeek兼容来源，项目worker显式隔离Kimi配置。

本地95项相关测试通过；已在Ubuntu以market-ai账号实际调用Kimi，返回OK，CC报告contextWindow=262144。后续部署与备用演练结果补录。未对整期报告或256K/1M满载作成功承诺。
