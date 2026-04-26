# js/ 模块源码

> 本目录是经营分析模板的 **ES Module 源码**。
> 发布产物（`经营分析模板.html`）由 `build.sh` 在发布期合并生成。

## 目录布局

```
js/
├── README.md           # 本文件
├── main.js             # （待加入）应用入口（ESM bootstrap）
├── lib/                # 第三方库（暂留 CDN，本地化为 P2 任务）
│   └── README.md
├── core/               # 与业务模块解耦的核心工具
│   ├── README.md
│   ├── format.js       # ✅ 已提取
│   ├── db.js           # （待提取）sql.js 包装与 OPFS 适配
│   ├── schema.js       # （待提取）SCHEMA_SQL / INSERT_SQL / 迁移
│   ├── importer.js     # （待提取）Excel → SQLite ETL
│   ├── filters.js      # （待提取）FILTER_KEYS + buildWhere
│   └── store.js        # （待提取）IndexedDB 持久化与缓存
└── modules/            # 业务模块（一模块一目录）
    ├── platform-trend/        # 模块01 平台趋势（待迁移）
    │   └── README.md
    └── product-structure/     # 模块02 产品结构（待迁移）
        └── README.md
```

## 核心约定

1. **零循环依赖**：`core/` 不依赖 `modules/`；`modules/` 内部不互相 import。
2. **ESM 风格**：使用 `export` / `import`，不用 CommonJS、UMD、IIFE。
3. **不耦合 DOM**：`core/` 工具尽量纯函数；DOM 操作集中在 `modules/*/view-*.js`。
4. **金额单位规范**：金额一律以「分」（INTEGER）流转，仅在最终展示层 `/ 100` 还原元。
5. **命名规范**：
   - 文件：小写连字符 `kebab-case`（如 `view-trend.js`）
   - 函数/变量：小驼峰 `camelCase`
   - 常量：全大写 `SCREAMING_SNAKE_CASE`

## 发布流程（build.sh，待实现）

```
js/ ESM 源码
    ↓ build.sh （拓扑排序 + 内联合并）
经营分析模板.html （单文件可分发）
```

详见 [`docs/需求/2026-04-26_模块化重构总体方案.md`](../docs/需求/2026-04-26_模块化重构总体方案.md) Section 3.

## 关联文档

- [模块化重构总体方案](../docs/需求/2026-04-26_模块化重构总体方案.md)
- [保单数据规范](../docs/数据规范/保单数据规范.md)
- [人力数据规范](../docs/数据规范/人力数据规范.md)
- [CHANGELOG](../docs/修订记录/CHANGELOG.md)
