# importer 模块

> Excel → SQLite 导入流水线。

## 状态

🟡 **迁移中**：12 个内联函数 + 列名/schema 常量已拆分为 4 个 ESM 文件（P1.7）。

inline 副本仍位于 `经营分析模板.html` 行 902-1148，将于 P1.X 一次性切换时删除。

## 文件结构

```
modules/importer/
├── README.md            # 本文件
├── schema.js            # REQUIRED_TIME_COLS / DIM_COLS / METRIC_COLS_ZH / COL_ALIASES / SCHEMA_SQL / INSERT_SQL
├── column-resolve.js    # resolveCol / levenshtein / suggest / validateColumns / findDateColumn
├── cell-transform.js    # pad2 / toCents / trimDim / trimEmpty / fmtDateTime / parseDateCell / transformRow
└── index.js             # parseAndBuild(file, onProgress) / collectMeta(db, fileName)
```

## 模块边界

- **不**直接耦合 boot 进度 UI；`parseAndBuild` 通过 `onProgress(msg)` 回调暴露进度
- **不**写 IDB、**不**操作全局 `db` 句柄；仅返回内存 db
- 调用方（bootstrap）负责：进度展示、`setDb()`、`idbPut()`、调用 `collectMeta`

## 关联文档

- [保单数据规范](../../../docs/数据规范/保单数据规范.md)
- [需求：模块化重构总体方案](../../../docs/需求/2026-04-26_模块化重构总体方案.md) §3 ESM bootstrap

## 迁移检查清单

- [x] 提取 `schema.js`（列常量 + SCHEMA_SQL + INSERT_SQL）
- [x] 提取 `column-resolve.js`（5 个列解析与校验函数）
- [x] 提取 `cell-transform.js`（7 个单元格处理函数）
- [x] 提取 `index.js`（parseAndBuild 增加 onProgress 回调；collectMeta）
- [ ] P1.X 一次性切换：删除 inline 副本，运行 `./build.sh --in-place`
