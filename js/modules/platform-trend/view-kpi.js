// 平台趋势：KPI 卡片区
//
// 与原 经营分析模板.html renderKPI()（行 628-667）完全一致。
// 直接 innerHTML 渲染到 #kpiArea。

import { BASE_YEAR } from '../../core/constants.js';
import { state } from '../../core/state.js';
import { formatNum } from '../../core/format.js';

export function renderKPI(periodMap, years, dimKeys, xLabels) {
  const kpiArea = document.getElementById('kpiArea');
  const maxPeriods = xLabels.length;
  const yearLatest = {};

  Object.values(periodMap).forEach(g => {
    let lastPeriod = 0;
    for (let i = maxPeriods; i >= 1; i--) {
      // 取最后非零期（含负数）
      if ((g.periods[i] || 0) !== 0 || (g.cumulative[i] || 0) !== 0) { lastPeriod = i; break; }
    }
    if (lastPeriod === 0) return;

    const label = g.year + (g.dimKey ? ' - ' + g.dimKey : '');
    yearLatest[label] = {
      year: g.year,
      dimKey: g.dimKey,
      val: g.cumulative[lastPeriod] || 0,
      time: xLabels[lastPeriod - 1]
    };
  });

  let html = '';
  const sorted = Object.values(yearLatest).sort((a, b) => b.val - a.val);
  sorted.slice(0, 6).forEach(item => {
    const base = yearLatest[BASE_YEAR + (item.dimKey ? ' - ' + item.dimKey : '')];
    let subHtml = '';
    if (base && item.year !== BASE_YEAR && state.compare) {
      const pct = base.val !== 0 ? ((item.val - base.val) / Math.abs(base.val) * 100).toFixed(1) : '-';
      const cls = parseFloat(pct) >= 0 ? 'up' : 'down';
      subHtml = '<div class="kpi-sub ' + cls + '">同比 ' + (parseFloat(pct) >= 0 ? '+' : '') + pct + '%</div>';
    }
    const label = item.year + (item.dimKey ? ' - ' + item.dimKey : '');
    html += '<div class="kpi-card">' +
      '<div class="kpi-label">' + label + ' (截至 ' + item.time + ')</div>' +
      '<div class="kpi-value">' + formatNum(item.val) + '</div>' +
      subHtml + '</div>';
  });
  kpiArea.innerHTML = html;
}
