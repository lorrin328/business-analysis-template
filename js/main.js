// 应用入口（ESM bootstrap）
//
// 当通过 HTTP 服务以 `<script type="module" src="js/main.js"></script>` 加载时启用。
// 直接 file:// 打开 经营分析模板.html 时不会加载本文件（CORS 限制），届时由
// 内联脚本块兜底——这是迁移过程中的过渡形态。
//
// build.sh 会将本文件以及通过 import 引入的所有模块展开后注入到
// 经营分析模板.html 的 `<!-- BUILD:JS:CORE -->` 标记位置，作为单文件发布产物。

import * as constants        from './core/constants.js';
import * as state            from './core/state.js';
import * as db               from './core/db.js';
import * as filters          from './core/filters.js';
import * as format           from './core/format.js';
import * as platformTrend    from './modules/platform-trend/index.js';
import * as productStructure from './modules/product-structure/index.js';

// 暴露到全局，供尚未迁出的内联脚本回退使用
// 现阶段（P1）内联块仍保留同名局部声明（IIFE 内局部覆盖 window/script 全局），
// 不会冲突；后续逐模块抽离时可逐步移除内联声明，自然回退到这里。
globalThis.__jyfx = Object.assign(globalThis.__jyfx || {}, {
  constants,
  state,
  db,
  filters,
  format,
  modules: Object.assign((globalThis.__jyfx && globalThis.__jyfx.modules) || {}, {
    platformTrend,
    productStructure
  })
});
