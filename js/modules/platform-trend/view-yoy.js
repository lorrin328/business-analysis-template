// 平台趋势：YoY 同比对比图
//
// 与原 经营分析模板.html renderYoY()（行 521-597）完全一致。
// 当 state.compare === false 时，由 index.js 隐藏 #yoyCard 不调用本视图。

import { BASE_YEAR } from '../../core/constants.js';
import { state, getChart, setChart } from '../../core/state.js';

export function renderYoY(periodMap, xLabels, years, dimKeys) {
  const maxPeriods = xLabels.length;
  const yoySeries = [];
  const yoyColors = ['#e8963e','#52c41a','#722ed1','#eb2f96','#13c2c2','#faad14'];

  if (state.view === 'overall') {
    const baseG = Object.values(periodMap).find(x => x.year === BASE_YEAR && !x.dimKey);
    if (!baseG) {
      const ch = getChart('yoy');
      if (ch) ch.clear();
      return;
    }

    years.filter(y => y !== BASE_YEAR).forEach((year, ci) => {
      const g = Object.values(periodMap).find(x => x.year === year && !x.dimKey);
      if (!g) return;
      yoySeries.push({
        name: year,
        type: 'line',
        data: Array.from({length: maxPeriods}, (_, i) => {
          const cur = g.cumulative[i + 1] || 0;
          const base = baseG.cumulative[i + 1] || 0;
          if (base === 0) return null;
          return Math.round(((cur - base) / base) * 10000) / 100;
        }),
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: yoyColors[ci % yoyColors.length] }
      });
    });
  } else {
    years.filter(y => y !== BASE_YEAR).forEach(year => {
      dimKeys.forEach(dimKey => {
        const g = Object.values(periodMap).find(x => x.year === year && x.dimKey === dimKey);
        const baseG = Object.values(periodMap).find(x => x.year === BASE_YEAR && x.dimKey === dimKey);
        if (!g || !baseG) return;
        yoySeries.push({
          name: year + ' - ' + dimKey,
          type: 'line',
          data: Array.from({length: maxPeriods}, (_, i) => {
            const cur = g.cumulative[i + 1] || 0;
            const base = baseG.cumulative[i + 1] || 0;
            if (base === 0) return null;
            return Math.round(((cur - base) / base) * 10000) / 100;
          }),
          smooth: true,
          symbolSize: 5,
          lineStyle: { width: 2 },
          itemStyle: { color: yoyColors[yoySeries.length % yoyColors.length] }
        });
      });
    });
  }

  let chart = getChart('yoy');
  if (!chart) {
    chart = echarts.init(document.getElementById('yoyChart'));
    setChart('yoy', chart);
  }
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        if (!params || !params.length) return '';
        let s = (params[0].axisValue || '') + '<br/>';
        params.forEach(p => {
          if (p.value != null) s += `${p.marker} ${p.seriesName}: <b>${(+p.value).toFixed(1)}%</b><br/>`;
        });
        return s;
      }
    },
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 12 } },
    grid: { top: 40, left: 70, right: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { fontSize: 12 },
      boundaryGap: false
    },
    yAxis: { type: 'value', axisLabel: { formatter: v => v + '%' } },
    visualMap: { show: false, pieces: [{ lt: 0, color: '#f5222d' }, { gte: 0, color: '#52c41a' }] },
    series: yoySeries
  }, true);
}
