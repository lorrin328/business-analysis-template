// 应用入口（ESM bootstrap）
//
// 当通过 HTTP 服务以 `<script type="module" src="js/main.js"></script>` 加载时启用。
// 直接 file:// 打开 经营分析模板.html 时不会加载本文件（CORS 限制），届时由
// 内联脚本块兜底，逐步迁移过程中的过渡形态。
//
// build.sh 会将本文件展开后的合并产物注入到 经营分析模板.html 中
// `<!-- BUILD:JS:CORE -->` 标记位置，作为单文件发布产物。

import { formatNum, formatShort } from './core/format.js';

// 暴露到全局，供尚未迁移的内联脚本回退使用
// 现阶段（P1）内联块仍声明本地同名函数（局部覆盖 window），不会冲突；
// 后续逐模块抽离时可逐步移除内联声明，自动 fallback 到本处。
globalThis.__jyfx = globalThis.__jyfx || {};
Object.assign(globalThis.__jyfx, { formatNum, formatShort });
