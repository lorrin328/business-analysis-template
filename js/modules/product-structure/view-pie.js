// 产品结构：当前期饼图视图
//
// 与原 经营分析模板.html renderStructure 中的 ECharts option 完全一致。

import { getChart, setChart } from '../../core/state.js';

// 渲染产品分类饼图
//   rows: [{ k, v }]   query.fetchStructure() 的返回
export function renderPie(rows) {
  const pieData = rows
    .filter(r => r.v !== 0)   // 保留负值（撤单），仅过滤恒零
    .map(r => ({ name: r.k || '未知', value: Math.round(r.v * 100) / 100 }));

  let chart = getChart('struct');
  if (!chart) {
    chart = echarts.init(document.getElementById('structChart'));
    setChart('struct', chart);
  }
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 20, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['40%', '55%'],
      data: pieData,
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.2)' } }
    }]
  }, true);
}
