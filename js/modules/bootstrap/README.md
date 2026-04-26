# bootstrap 模块

> 顶层启动 orchestrator：boot UI / 事件绑定 / 文件导入 / 渲染编排。

## 状态

🟡 **迁移中**：5 个文件 + barrel index 完成（P1.8）。`js/core/idb.js` 同步落地。

inline 副本仍位于 `经营分析模板.html` 行 800-1281（boot/事件/导入/启动流），将于 P1.X 一次性切换时删除。

## 文件结构

```
modules/bootstrap/
├── README.md         # 本文件
├── boot-overlay.js   # setBoot(state, msg) / hideBoot()         —— #bootOverlay 状态机
├── render.js         # render() = renderTrend() + renderStructure()
├── events.js         # bindEvents() —— 顶部按钮组 / 标签页 / 比较开关 / 筛选器 / window resize
├── import-flow.js    # handleImport(file) / bindReimport() / bindEmptyUI(retryFn)
├── init.js           # updateMetaInfo(meta) / initApp(meta) / bootFlow()
└── index.js          # barrel re-exports
```

## 模块边界

⚠️ **bootstrap 是 `js/README.md` 「模块互相不 import」原则的明确例外**：

- `render.js` 同时 import `platform-trend` 与 `product-structure`，因为它是顶层渲染编排
- 其他模块仍遵循「不互相 import」：
  - `platform-trend/index.js renderTrend()` 只渲染趋势/同比/KPI，**不**触碰结构图
  - `product-structure/index.js renderStructure()` 只渲染饼图，**不**触碰趋势

设计理由：避免业务模块互相耦合；将「应用层组合」集中在 bootstrap，未来增减模块只改一处。

## 启动顺序（`bootFlow()`）

```
1. setBoot('loading', '正在加载 SQLite 引擎 ...')
2. initSqlJs(...) → window.__SQL
3. setBoot('loading', '正在检查浏览器缓存 ...')
4. idbGet('db')
   ├─ 命中：setDb + idbGet('meta') + initApp(meta)
   └─ 未命中：setBoot('empty') + bindEmptyUI(bootFlow)
                ↑ 用户拖拽/点击文件 → handleImport(file)
                                    ↓
                  parseAndBuild(file, msg=>setBoot('loading', msg))
                  → idbPut('db'/'meta')
                  → setDb(newDb)
                  → initApp(meta) 或 已有图表则 render() + initSelects()
```

`initApp(meta)`：

```
initSelects() → bindEvents() → bindReimport() → render() → updateMetaInfo(meta) → hideBoot()
```

## 关联文档

- [需求：模块化重构总体方案](../../../docs/需求/2026-04-26_模块化重构总体方案.md) §3 ESM bootstrap
- [js/README.md 模块互相不 import 原则](../../README.md)（本模块为唯一例外）

## 迁移检查清单

- [x] 提取 `boot-overlay.js`（setBoot / hideBoot）
- [x] 提取 `render.js`（顶层 orchestrator，唯一跨业务模块 import）
- [x] 提取 `events.js`（bindEvents）
- [x] 提取 `import-flow.js`（handleImport / bindReimport / bindEmptyUI 解耦 boot UI）
- [x] 提取 `init.js`（updateMetaInfo / initApp / bootFlow）
- [x] 同步落地 `js/core/idb.js`（openIdb / idbGet / idbPut）
- [ ] P1.X 一次性切换：删除 inline 副本，main.js 改为 `bootFlow()` 自启动
