// 弹窗管理模块
//
// 管理全屏模态弹窗：打开/关闭、内容路由、图表生命周期。
// 四个版块：关键KPI、趋势表现、产品结构、队伍表现。
// 每个版块的内容渲染由对应模块负责（kpi / team-performance / product-structure / platform-trend）。

import { renderKPIModal } from '../kpi/index.js';
import { renderTeamModal } from '../team-performance/index.js';
import { q } from '../../core/db.js';
import { formatNum } from '../../core/format.js';
import { getChart, setChart } from '../../core/state.js';

let currentModal = null;
const modalChartInstances = {};

const TITLES = { kpi: '关键KPI', trend: '趋势表现', product: '产品结构', team: '队伍表现' };

export function openModal(type) {
  currentModal = type;
  const overlay = document.getElementById('modalOverlay');
  const title = document.getElementById('modalTitle');
  const body = document.getElementById('modalBody');
  overlay.classList.add('active');
  body.innerHTML = '';

  title.textContent = TITLES[type] || '经营分析';

  if (type === 'kpi') {
    renderKPIModal(body);
  } else if (type === 'trend') {
    renderTrendModal(body);
  } else if (type === 'product') {
    renderProductModal(body);
  } else if (type === 'team') {
    renderTeamModal(body);
  }
}

export function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
  // Dispose modal charts
  Object.values(modalChartInstances).forEach(c => { if (c && c.dispose) c.dispose(); });
  modalChartInstances.product = null;
  // Return trend content to hidden container
  if (currentModal === 'trend') {
    const trendContent = document.getElementById('trendContent');
    if (trendContent) { trendContent.style.display = 'none'; document.body.appendChild(trendContent); }
  }
  currentModal = null;
}

// --- Trend Modal ---
// 将主页的 #trendContent 移入弹窗，dispose 旧图表后重新 render
function renderTrendModal(container) {
  const trendContent = document.getElementById('trendContent');
  container.innerHTML = '';
  container.appendChild(trendContent);
  trendContent.style.display = 'block';

  // Re-init charts after DOM is stable in modal context
  setTimeout(() => {
    // Dispose existing chart instances (they'll be re-created by render)
    ['main', 'yoy', 'struct'].forEach(name => {
      const chart = getChart(name);
      if (chart) { chart.dispose(); setChart(name, null); }
    });
    try {
      // Dynamically import render to avoid circular deps
      import('../bootstrap/render.js').then(m => m.render());
    } catch (e) { console.error('趋势弹窗渲染失败:', e); }
  }, 50);
}

// --- Product Modal ---
// 独立的饼图 + 保费口径切换
function renderProductModal(container) {
  container.innerHTML = `
    <div class="modal-filters">
      <div class="filter-group">
        <label>保费口径</label>
        <div class="btn-group" id="prodMetricBtns">
          <button data-val="zhsf_cents" class="active">折算保费</button>
          <button data-val="qj_cents">期交保费</button>
          <button data-val="ghgb_cents">规模保费</button>
        </div>
      </div>
    </div>
    <div class="modal-section">
      <div class="chart-box" id="productChart" style="height:500px;"></div>
    </div>
  `;

  const refresh = () => {
    const metric = document.querySelector('#prodMetricBtns button.active')?.dataset.val || 'zhsf_cents';
    const sql = `SELECT design_cat AS k, SUM(${metric}) / 100.0 AS v FROM fact_premium WHERE design_cat IS NOT NULL GROUP BY design_cat ORDER BY v DESC`;
    const rows = q(sql);
    const pieData = rows.filter(r => r.v !== 0).map(r => ({ name: r.k || '未知', value: Math.round(r.v * 100) / 100 }));

    let chart = modalChartInstances.product;
    if (!chart) {
      chart = echarts.init(document.getElementById('productChart'));
      modalChartInstances.product = chart;
    }
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 10, top: 20, textStyle: { fontSize: 12 } },
      series: [{
        type: 'pie', radius: ['35%', '65%'], center: ['40%', '50%'],
        data: pieData, label: { formatter: '{b}\n{d}%', fontSize: 11 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.2)' } }
      }]
    }, true);
  };

  document.getElementById('prodMetricBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#prodMetricBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    refresh();
  });

  refresh();
}
