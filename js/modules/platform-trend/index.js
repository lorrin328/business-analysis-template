// 平台趋势模块：入口
//
// 串联 query.aggregate → view-main + view-yoy + view-kpi。
// 不调用 product-structure（那是另一个模块；最终顶层控制器分别串联两者）。
//
// 与原 经营分析模板.html `render()` 等价，但去除了 renderStructure 调用——
// 后者在 P1.X 切换后由 main.js 顶层控制器另行调度，确保模块间零依赖。

import { state, dailyCache } from '../../core/state.js';
import { aggregate } from './query.js';
import { renderMain } from './view-main.js';
import { renderYoY } from './view-yoy.js';
import { renderKPI } from './view-kpi.js';

// 渲染平台趋势 Tab 的全部子视图（不含产品结构饼图）
export function renderTrend() {
  dailyCache.clear();
  const periodMap = aggregate();
  const { years, dimKeys, xLabels } = renderMain(periodMap);

  const yoyCard = document.getElementById('yoyCard');
  if (state.compare) {
    yoyCard.style.display = '';
    try { renderYoY(periodMap, xLabels, years, dimKeys); }
    catch (e) { console.error('同比图渲染失败:', e); }
  } else {
    yoyCard.style.display = 'none';
  }

  try { renderKPI(periodMap, years, dimKeys, xLabels); }
  catch (e) { console.error('KPI 渲染失败:', e); }

  return { periodMap, years, dimKeys, xLabels };
}
