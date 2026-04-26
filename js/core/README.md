# js/core/

> 与具体业务模块解耦的核心工具与基础设施。

## 已提取

- `format.js` — 金额显示格式化（`formatNum` / `formatShort`）

## 待提取（按优先级）

| 优先级 | 文件 | 来源（经营分析模板.html 行号） | 说明 |
|--------|------|-----------------------|------|
| 1 | `db.js` | 待整理 | sql.js / SQLite 实例管理 |
| 1 | `schema.js` | ~903-960 | `SCHEMA_SQL`、`INSERT_SQL`、列定义 |
| 2 | `importer.js` | ~960-1003+ | Excel → SQLite ETL；列名校验；Levenshtein |
| 2 | `filters.js` | ~295-310 | `FILTER_KEYS`、`buildWhere`、UI 联动 |
| 3 | `store.js` | ~850-898 | IndexedDB 缓存；schema 版本号；启动加载 |

## 设计原则

- 纯函数优先：可单元测试，无副作用
- 不依赖 DOM（除 `store.js` 操作 IndexedDB 外）
- 不依赖业务模块；可被多个模块复用
