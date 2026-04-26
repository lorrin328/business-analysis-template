// 平台趋势：日明细浮层
//
// installDailyTooltip()  在主图 zr 上挂 mousemove → showDailyTip
// showDailyTip(period, x, y)  按期间查询所有年份日累计，渲染到 #dailyTip

import { state, getChart, setChart, dailyCache, allYears } from '../../core/state.js';
import { filterStateHash } from '../../core/filters.js';
import { formatNum, formatShort } from '../../core/format.js';
import { queryDaily } from './query.js';
import { getXLabels } from './view-main.js';

// 必须在主图实例已存在后调用
export function installDailyTooltip() {
  const tipEl = document.getElementById('dailyTip');
  const main = getChart('main');
  if (!main) return;
  const zr = main.getZr();

  zr.on('mousemove', e => {
    const x = e.event.zrX, y = e.event.zrY;
    const inGrid = main.containPixel('grid', [x, y]);
    if (!inGrid) { tipEl.style.display = 'none'; return; }
    const opt = main.getOption();
    if (!opt.series || !opt.series.length) { tipEl.style.display = 'none'; return; }
    const pt = main.convertFromPixel({ seriesIndex: 0 }, [x, y]);
    if (!pt || pt[0] == null) { tipEl.style.display = 'none'; return; }
    const idx = Math.round(pt[0]);
    if (idx < 0 || idx >= getXLabels().length) { tipEl.style.display = 'none'; return; }
    showDailyTip(idx + 1, e.event.clientX, e.event.clientY);
  });
  zr.on('mouseout',   () => { tipEl.style.display = 'none'; });
  zr.on('globalout',  () => { tipEl.style.display = 'none'; });
}

export function showDailyTip(period, x, y) {
  const tipEl = document.getElementById('dailyTip');
  const fhash = filterStateHash();

  const datasets = [];
  allYears.forEach(year => {
    const ck = `${year}|${state.gran}|${period}|${state.metric}|${fhash}`;
    if (!dailyCache.has(ck)) {
      try { dailyCache.set(ck, queryDaily(year, period)); }
      catch (err) { dailyCache.set(ck, []); }
    }
    datasets.push({ year, rows: dailyCache.get(ck) });
  });

  const hasData = datasets.some(d => d.rows.length > 0);
  if (!hasData) {
    tipEl.style.display = 'block';
    tipEl.innerHTML = '<div style="padding:24px;color:#999;text-align:center;font-size:12px;">该期间无日明细数据<br/>（请确认源文件含日期列）</div>';
    tipEl.style.left = Math.min(window.innerWidth - 400, x + 16) + 'px';
    tipEl.style.top  = Math.min(window.innerHeight - 280, y + 16) + 'px';
    return;
  }

  const colors = ['#2d5f9a','#e8963e','#52c41a','#722ed1','#eb2f96','#13c2c2'];
  const xMax = state.gran === 'quarter' ? 92 : 31;

  const dailySeries = datasets.map((d, i) => {
    const sorted = d.rows.slice().sort((a, b) => a.day - b.day);
    let cum = 0;
    const cumData = sorted.map(r => { cum += r.amount; return [r.day, Math.round(cum * 100) / 100]; });
    return {
      name: d.year,
      type: 'line',
      smooth: true,
      symbolSize: 3,
      showSymbol: false,
      lineStyle: { width: 1.5 },
      itemStyle: { color: colors[i % colors.length] },
      data: cumData
    };
  });

  tipEl.innerHTML = '';
  const oldMini = getChart('mini');
  if (oldMini) oldMini.dispose();
  const mini = echarts.init(tipEl);
  setChart('mini', mini);
  mini.setOption({
    title: {
      text: state.gran === 'quarter'
        ? `Q${period} 日累计明细（${state.metric}）`
        : `${period}月 日累计明细（${state.metric}）`,
      left: 8, top: 4, textStyle: { fontSize: 12, fontWeight: 600, color: '#1a3a6b' }
    },
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        if (!params || !params.length) return '';
        const day = params[0].axisValue;
        let s = state.gran === 'quarter' ? `第 ${day} 天<br/>` : `${period}月${day}日<br/>`;
        params.forEach(p => {
          const val = Array.isArray(p.value) ? p.value[1] : p.value;
          if (val != null) s += `${p.marker} ${p.seriesName}: <b>${formatNum(val)}</b><br/>`;
        });
        return s;
      }
    },
    legend: { top: 4, right: 8, textStyle: { fontSize: 10 }, itemWidth: 12, itemHeight: 8 },
    grid: { top: 32, left: 48, right: 12, bottom: 24 },
    xAxis: {
      type: 'value', min: 1, max: xMax,
      name: state.gran === 'quarter' ? '季内日序' : '日',
      nameTextStyle: { fontSize: 10 },
      nameGap: 16,
      axisLabel: { fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: v => formatShort(v), fontSize: 10 }
    },
    series: dailySeries,
    animation: false
  }, true);

  tipEl.style.display = 'block';
  tipEl.style.left = Math.min(window.innerWidth - 400, x + 16) + 'px';
  tipEl.style.top  = Math.min(window.innerHeight - 280, y + 16) + 'px';
}
