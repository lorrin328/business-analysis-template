# v1.0.164 市场研判模型参数发布验收

状态：本地修改及回归完成，GitHub 与 Ubuntu 发布验收进行中。

Qwen3.8-Max 按核对后的官方参数与用户确认保留 1M，上下文与思考模式最大输入分开描述；思考从等价 xhigh 的 high 降为 medium。Qwen 通道不可用时允许一次 DeepSeek Flash 接替，独立使用 1M + max，受剩余预算与时间限制。内容和预算失败不切换，历史报告保护与质量门禁不变。

本地 Python 全量 960 passed、3 skipped；新增定时器测试专项 Windows 跳过，待 Linux 验证。Node 60 passed。语法、差异空白与发布边界检查通过。无数据库迁移、聚合或业务口径变更。工作区原有 PDF 删除和 docs/archive 不纳入发布。

发布计划：从已提交 Git 生成可信归档；REBUILD_DATABASE=0、REBUILD_AGGREGATES=auto。备份采用专属子目录，验收接受仅管理本次备份，保留既有恢复点。原停用定时器保持 disabled/inactive。真实 DeepSeek 禁用工具短调用、公网、鉴权、业务快照、备份和跨盘副本结果待补。
