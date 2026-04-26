// 平台趋势：主图（多年累计折线）
//
// 与原 经营分析模板.html render() 的主图渲染部分（行 420-503）完全一致。
// 不直接负责 yoy/kpi/structure；这些由 index.js 在主图渲染后串联。

import { BASE_YEAR, MONTH_LABELS, QUARTER_LABELS } from '../../core/constants.js';
import { state, getChart, setChart } from '../../core/state.js';
import { formatShort } from '../../core/format.js';
import { installDailyTooltip } from './view-daily-tip.js';

// 当前粒度对应的 X 轴标签
export function getXLabels() {
  return state.gran === 'quarter' ? QUARTER_LABELS : MONTH_LABELS;
}

// 渲染主图；返回 { years, dimKeys, xLabels } 供下游 view-* 复用
export function renderMain(periodMap) {
  const xLabels = getXLabels();
  const maxPeriods = xLabels.length;

  const yearsSet = new Set();
  Object.values(periodMap).forEach(g => yearsSet.add(g.year));
  const years = [...yearsSet].sort();

  const dimKeysSet = new Set();
  Object.values(periodMap).forEach(g => { if (g.dimKey) dimKeysSet.add(g.dimKey); });
  const dimKeys = [...dimKeysSet].sort();

  const colors = ['#2d5f9a','#e8963e','#52c41a','#722ed1','#eb2f96','#13c2c2','#faad14','#f5222d','#2f54eb','#fa541c','#a0d911'];
  const yearColors = {};
  years.forEach((y, i) => { yearColors[y] = colors[i % colors.length]; });

  const series = [];

  if (state.view === 'overall') {
    years.forEach(year => {
      const g = Object.values(periodMap).find(x => x.year === year && !x.dimKey);
      if (!g) return;
      const isBase = year === BASE_YEAR;
      series.push({
        name: year,
        type: 'line',
        data: Array.from({length: maxPeriods}, (_, i) => Math.round((g.cumulative[i + 1] || 0) * 100) / 100),
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2.5, type: isBase && state.compare ? 'dashed' : 'solid' },
        itemStyle: { color: yearColors[year] },
        emphasis: { lineStyle: { width: 4 } }
      });
    });
  } else {
    years.forEach(year => {
      dimKeys.forEach(dimKey => {
        const g = Object.values(periodMap).find(x => x.year === year && x.dimKey === dimKey);
        if (!g) return;
        const isBase = year === BASE_YEAR;
        series.push({
          name: year + ' - ' + dimKey,
          type: 'line',
          data: Array.from({length: maxPeriods}, (_, i) => Math.round((g.cumulative[i + 1] || 0) * 100) / 100),
          smooth: true,
          symbolSize: 5,
          lineStyle: { width: 2, type: isBase && state.compare ? 'dashed' : 'solid' },
          itemStyle: { color: yearColors[year] },
          emphasis: { lineStyle: { width: 3 } }
        });
      });
    });
  }

  const granLabels = { day: '日累计', month: '月度', quarter: '季度' };
  const viewLabels = { overall: '整体', org: '分机构', mode: '分业务模式' };
  document.getElementById('chartTitle').textContent =
    `${viewLabels[state.view]}${granLabels[state.gran]}保费趋势 - ${state.metric}（hover 查看日明细）`;

  let chart = getChart('main');
  try {
    if (!chart) {
      chart = echarts.init(document.getElementById('mainChart'));
      setChart('main', chart);
      installDailyTooltip();
    }
    chart.setOption({
      tooltip: { show: false },
      legend: { top: 0, type: 'scroll', textStyle: { fontSize: 12 } },
      grid: { top: 40, left: 70, right: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: xLabels,
        axisLabel: { fontSize: 12 },
        boundaryGap: false
      },
      yAxis: { type: 'value', axisLabel: { formatter: v => formatShort(v) } },
      series: series.length ? series : [{ name: '', type: 'line', data: [] }],
      animation: true
    }, true);
  } catch (e) {
    console.error('主图渲染失败:', e);
    throw new Error('主图渲染失败: ' + (e.message || String(e)));
  }

  return { years, dimKeys, xLabels };
}
