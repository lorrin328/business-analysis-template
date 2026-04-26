# 模块02：产品结构

> 按 `产品设计分类`（`design_cat`）展示保费金额构成的分布与趋势。

## 状态

🟡 **迁移中**：`renderStructure` 已拆分为 `query.js` + `view-pie.js` + `index.js`（P1.5）。

inline 副本仍位于 `经营分析模板.html` `renderStructure()`（行 ~599），将于 P1.X 一次性切换时删除。

## 规划文件结构

```
modules/product-structure/
├── README.md           # 本文件
├── index.js            # 模块入口；注册到 main.js Tab
├── view-pie.js         # 当期产品分类饼图
├── view-stacked.js     # （新增）历年堆积柱图（按 design_cat）
├── view-compare.js     # （新增）默认 (当前-1) vs 当前 年份对比，基准年自动滚动
└── query.js            # SQL 查询工厂
```

## 业务规则

- **默认对比年份**：`(currentYear - 1)` vs `currentYear`，跟随系统当前时间自动滚动（用户决策 2026-04-26）
- **附加险归类**：待 Q10 业务方提供识别规则后明确（见主方案）

## 关联文档

- [需求：模块02 产品结构](../../../docs/需求/模块02_产品结构.md)
- [保单数据规范](../../../docs/数据规范/保单数据规范.md)

## 迁移检查清单

- [x] 提取 `query.js`（design_cat 聚合 SQL）
- [x] 提取 `view-pie.js`（renderStructure 当前实现）
- [x] 提取 `index.js`（模块入口）
- [ ] 新增 `view-compare.js`（年份对比视图）
- [ ] 新增 `view-stacked.js`（多年堆积柱图）
- [ ] P1.X 一次性切换：删除 inline `renderStructure`，运行 `./build.sh --in-place`
- [ ] build.sh 合并后输出与原文件视觉一致
