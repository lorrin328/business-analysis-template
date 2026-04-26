# 模块01：平台趋势

> 平台总保费 / 折算保费 / 期交保费 / 价值规保的多维度趋势分析。

## 状态

🟠 **待迁移**：现有逻辑位于 `经营分析模板.html` 行 ~295-1003 内的多个内联函数（`render`、`renderYoY`、`renderStructure`、`renderKPI`、`installDailyTooltip`）。

## 规划文件结构

```
modules/platform-trend/
├── README.md           # 本文件
├── index.js            # 模块入口；注册到 main.js Tab
├── view-trend.js       # 主趋势图（年/季/月/日）
├── view-yoy.js         # 同比对比视图
├── view-kpi.js         # KPI 卡片
├── view-daily-tip.js   # 日明细浮层
└── query.js            # SQL 查询工厂（聚合）
```

## 关联文档

- [需求：模块01 平台趋势](../../../docs/需求/模块01_平台趋势.md)
- [保单数据规范](../../../docs/数据规范/保单数据规范.md)

## 迁移检查清单

- [ ] 提取 `query.js`（aggregate 函数 → SQL 工厂）
- [ ] 提取 `view-trend.js`（render 主图）
- [ ] 提取 `view-yoy.js`（renderYoY）
- [ ] 提取 `view-kpi.js`（renderKPI）
- [ ] 提取 `view-daily-tip.js`（installDailyTooltip + queryDaily + showDailyTip）
- [ ] 单元测试关键聚合函数
- [ ] build.sh 合并后输出与原文件视觉一致
