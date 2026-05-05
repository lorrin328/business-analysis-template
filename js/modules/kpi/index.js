// 关键KPI模块
//
// 提供 renderKPIModal(container) 和 renderKPITable(periodType, metricType, orgFilter)
// 在弹窗中展示目标达成率、规模同比等核心经营指标。
// 支持年度/季度/月度切换、折算/期交/规模保费口径切换、机构筛选。

import { q, exec } from '../../core/db.js';
import { formatNum } from '../../core/format.js';

const TARGET_SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS fact_target (
    id INTEGER PRIMARY KEY,
    year TEXT NOT NULL,
    quarter INTEGER,
    month INTEGER,
    week INTEGER,
    org TEXT,
    project TEXT,
    metric TEXT NOT NULL,
    target_value REAL NOT NULL DEFAULT 0
  );
  CREATE INDEX IF NOT EXISTS ix_target_ym ON fact_target(year, month);
  CREATE INDEX IF NOT EXISTS ix_target_yq ON fact_target(year, quarter);
  CREATE INDEX IF NOT EXISTS ix_target_org ON fact_target(org);
`;

export function renderKPIModal(container) {
  container.innerHTML = `
    <div class="modal-filters">
      <div class="filter-group">
        <label>时间维度</label>
        <div class="btn-group" id="kpiPeriodBtns">
          <button data-val="year" class="active">年度</button>
          <button data-val="quarter">季度</button>
          <button data-val="month">月度</button>
        </div>
      </div>
      <div class="filter-group">
        <label>指标口径</label>
        <div class="btn-group" id="kpiMetricBtns">
          <button data-val="折算保费" class="active">折算保费</button>
          <button data-val="期交保费">期交保费</button>
          <button data-val="规模保费">规模保费</button>
        </div>
      </div>
      <div class="filter-group">
        <label>机构</label>
        <select id="kpiSelOrg"><option value="">全部机构</option></select>
      </div>
    </div>
    <div class="modal-section">
      <div id="kpiTableArea"></div>
    </div>
  `;

  // Init org select
  const orgRows = q(`SELECT DISTINCT org AS v FROM fact_premium WHERE org IS NOT NULL AND org != '' ORDER BY org`);
  const orgSel = document.getElementById('kpiSelOrg');
  orgRows.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.v; opt.textContent = r.v;
    orgSel.appendChild(opt);
  });

  const refresh = () => {
    const period = document.querySelector('#kpiPeriodBtns button.active')?.dataset.val || 'year';
    const metric = document.querySelector('#kpiMetricBtns button.active')?.dataset.val || '折算保费';
    const org = document.getElementById('kpiSelOrg').value;
    renderKPITable(period, metric, org);
  };

  document.getElementById('kpiPeriodBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#kpiPeriodBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    refresh();
  });
  document.getElementById('kpiMetricBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#kpiMetricBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    refresh();
  });
  document.getElementById('kpiSelOrg').addEventListener('change', refresh);

  refresh();
}

export function renderKPITable(periodType, metricType, orgFilter) {
  const area = document.getElementById('kpiTableArea');
  const metricCol = metricType === '折算保费' ? 'zhsf_cents' : metricType === '期交保费' ? 'qj_cents' : 'ghgb_cents';
  const scaleCol = 'ghgb_cents';

  let periodLabelSql, periodOrder;
  if (periodType === 'year') {
    periodLabelSql = 'year AS period_label';
    periodOrder = 'year';
  } else if (periodType === 'quarter') {
    periodLabelSql = "year || '-Q' || quarter AS period_label";
    periodOrder = 'year, quarter';
  } else {
    periodLabelSql = "year || '-' || printf('%02d', month) AS period_label";
    periodOrder = 'year, month';
  }

  const actualParams = {};
  const actualConds = [];
  if (orgFilter) { actualConds.push('org = $org'); actualParams.$org = orgFilter; }
  const actualWhere = actualConds.length ? 'WHERE ' + actualConds.join(' AND ') : '';

  const actualSql = `
    SELECT ${periodLabelSql},
           year, ${periodType === 'quarter' ? 'quarter' : periodType === 'month' ? 'month' : '1 AS dummy'},
           SUM(${metricCol}) / 100.0 AS actual,
           SUM(${scaleCol}) / 100.0 AS scale_amount
    FROM fact_premium
    ${actualWhere}
    GROUP BY ${periodOrder}
    ORDER BY ${periodOrder}
  `;
  const actualRows = q(actualSql, actualParams);

  // Target data
  const targetParams = { $metric: metricType };
  const targetConds = ['metric = $metric'];
  if (orgFilter) { targetConds.push('org = $org'); targetParams.$org = orgFilter; }
  const targetWhere = 'WHERE ' + targetConds.join(' AND ');
  const targetSql = `
    SELECT ${periodLabelSql},
           SUM(target_value) AS target
    FROM fact_target
    ${targetWhere}
    GROUP BY ${periodOrder}
    ORDER BY ${periodOrder}
  `;
  let targetRows = [];
  try {
    exec(TARGET_SCHEMA_SQL);
    targetRows = q(targetSql, targetParams);
  } catch (e) { /* no target table or no data */ }

  const targetMap = {};
  targetRows.forEach(r => { targetMap[r.period_label] = r.target; });

  // YoY: previous period scale amount
  const yoyMap = {};
  if (periodType === 'year') {
    actualRows.forEach(r => {
      const prevYear = String(parseInt(r.year) - 1);
      const prev = actualRows.find(x => x.year === prevYear);
      if (prev && prev.scale_amount > 0) {
        yoyMap[r.period_label] = ((r.scale_amount - prev.scale_amount) / prev.scale_amount * 100);
      }
    });
  } else if (periodType === 'month') {
    actualRows.forEach((r) => {
      const prevYear = String(parseInt(r.year) - 1);
      const monthVal = r.month;
      const prev = actualRows.find(x => x.year === prevYear && x.month === monthVal);
      if (prev && prev.scale_amount > 0) {
        yoyMap[r.period_label] = ((r.scale_amount - prev.scale_amount) / prev.scale_amount * 100);
      }
    });
  } else if (periodType === 'quarter') {
    actualRows.forEach((r) => {
      const prevYear = String(parseInt(r.year) - 1);
      const qVal = r.quarter;
      const prev = actualRows.find(x => x.year === prevYear && x.quarter === qVal);
      if (prev && prev.scale_amount > 0) {
        yoyMap[r.period_label] = ((r.scale_amount - prev.scale_amount) / prev.scale_amount * 100);
      }
    });
  }

  let html = '<table class="data-table"><thead><tr>' +
    '<th>期间</th><th>目标</th><th>达成</th><th>达成率</th><th>规模同比</th>' +
    '</tr></thead><tbody>';

  if (actualRows.length === 0) {
    html += '<tr><td colspan="5" style="text-align:center;color:#999;padding:40px;">暂无数据</td></tr>';
  } else {
    actualRows.forEach(r => {
      const target = targetMap[r.period_label] || 0;
      const actual = r.actual || 0;
      const achieveRate = target > 0 ? (actual / target * 100).toFixed(1) : '-';
      const yoy = yoyMap[r.period_label];
      const yoyStr = yoy != null ? yoy.toFixed(1) + '%' : '-';
      const yoyCls = yoy != null ? (yoy >= 0 ? 'pct-positive' : 'pct-negative') : '';
      const achieveCls = target > 0 ? (actual >= target ? 'achieve-high' : 'achieve-low') : '';

      html += '<tr>' +
        `<td>${r.period_label}</td>` +
        `<td class="num">${target > 0 ? formatNum(target) : '-'}</td>` +
        `<td class="num">${formatNum(actual)}</td>` +
        `<td class="num ${achieveCls}">${achieveRate}${achieveRate !== '-' ? '%' : ''}</td>` +
        `<td class="num ${yoyCls}">${yoyStr}</td>` +
        '</tr>';
    });
  }
  html += '</tbody></table>';
  area.innerHTML = html;
}
