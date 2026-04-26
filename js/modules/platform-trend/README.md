# 模块01：平台趋势

> 平台总保费 / 折算保费 / 期交保费 / 价值规保的多维度趋势分析。

## 状态

🟡 **迁移中**：6 个内联函数已拆分为 `query.js` + `view-main.js` + `view-yoy.js` + `view-kpi.js` + `view-daily-tip.js` + `index.js`（P1.6）。

inline 副本仍位于 `经营分析模板.html` 行 372-792，将于 P1.X 一次性切换时删除。

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

- [x] 提取 `query.js`（aggregate 函数 → SQL 工厂；新增 queryDaily）
- [x] 提取 `view-main.js`（render 主图；包含 getXLabels）
- [x] 提取 `view-yoy.js`（renderYoY）
- [x] 提取 `view-kpi.js`（renderKPI）
- [x] 提取 `view-daily-tip.js`（installDailyTooltip + showDailyTip）
- [x] 提取 `index.js`（renderTrend 串联各子视图）
- [ ] 单元测试关键聚合函数
- [ ] P1.X 一次性切换：删除 inline 函数，运行 `./build.sh --in-place`
- [ ] build.sh 合并后输出与原文件视觉一致
