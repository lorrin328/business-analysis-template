// 顶层渲染编排
//
// bootstrap 是顶层 orchestrator，可同时引用 platform-trend 与 product-structure。
// 这是 js/README.md「模块互相不 import」原则的明确例外。
//
// 等价于原 经营分析模板.html 内联 `render()`：trend + yoy + kpi + structure。

import { renderTrend } from '../platform-trend/index.js';
import { renderStructure } from '../product-structure/index.js';

export function render() {
  renderTrend();
  try { renderStructure(); }
  catch (e) { console.error('结构图渲染失败:', e); }
}
