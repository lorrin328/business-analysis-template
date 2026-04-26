// 产品结构模块：入口
//
// 串联 query.js → view-pie.js。后续添加 view-compare / view-stacked 时
// 在此扩展（保持其它模块只引用本入口）。

import { fetchStructure } from './query.js';
import { renderPie } from './view-pie.js';

// 渲染产品结构当前期饼图（替代原内联 renderStructure 函数）
export function renderStructure() {
  const rows = fetchStructure();
  renderPie(rows);
}
