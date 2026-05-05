// 队伍表现模块
//
// 提供 renderTeamModal(container) 和 renderTeamTable(periodType, orgFilter, modeFilter)
// 展示月末在职人力、月均在职人力、长险活动人力、长险活动率、
// 人均保费、人均产能、标准人力等七项指标。
// 支持月度/季度切换、机构、业务模式筛选。

import { q } from '../../core/db.js';
import { formatNum } from '../../core/format.js';

export function renderTeamModal(container) {
  container.innerHTML = `
    <div class="modal-filters">
      <div class="filter-group">
        <label>时间维度</label>
        <div class="btn-group" id="teamPeriodBtns">
          <button data-val="month" class="active">月度</button>
          <button data-val="quarter">季度</button>
        </div>
      </div>
      <div class="filter-group">
        <label>机构</label>
        <select id="teamSelOrg"><option value="">全部机构</option></select>
      </div>
      <div class="filter-group">
        <label>业务模式</label>
        <select id="teamSelMode"><option value="">全部模式</option></select>
      </div>
    </div>
    <div class="modal-section">
      <div id="teamTableArea"></div>
    </div>
  `;

  const orgRows = q(`SELECT DISTINCT org AS v FROM fact_premium WHERE org IS NOT NULL AND org != '' ORDER BY org`);
  const orgSel = document.getElementById('teamSelOrg');
  orgRows.forEach(r => { const opt = document.createElement('option'); opt.value = r.v; opt.textContent = r.v; orgSel.appendChild(opt); });

  const modeRows = q(`SELECT DISTINCT biz_mode AS v FROM fact_premium WHERE biz_mode IS NOT NULL AND biz_mode != '' ORDER BY biz_mode`);
  const modeSel = document.getElementById('teamSelMode');
  modeRows.forEach(r => { const opt = document.createElement('option'); opt.value = r.v; opt.textContent = r.v; modeSel.appendChild(opt); });

  const refresh = () => {
    const period = document.querySelector('#teamPeriodBtns button.active')?.dataset.val || 'month';
    const org = document.getElementById('teamSelOrg').value;
    const mode = document.getElementById('teamSelMode').value;
    renderTeamTable(period, org, mode);
  };

  document.getElementById('teamPeriodBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#teamPeriodBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    refresh();
  });
  document.getElementById('teamSelOrg').addEventListener('change', refresh);
  document.getElementById('teamSelMode').addEventListener('change', refresh);

  refresh();
}

export function renderTeamTable(periodType, orgFilter, modeFilter) {
  const area = document.getElementById('teamTableArea');

  let groupCols, periodLabelSql, periodOrder;
  if (periodType === 'quarter') {
    groupCols = 'year, quarter';
    periodLabelSql = "year || '-Q' || quarter";
    periodOrder = 'year, quarter';
  } else {
    groupCols = 'year, month';
    periodLabelSql = "year || '-' || printf('%02d', month)";
    periodOrder = 'year, month';
  }

  const params = {};
  const conditions = [];
  if (orgFilter) { conditions.push('org = $org'); params.$org = orgFilter; }
  if (modeFilter) { conditions.push('biz_mode = $mode'); params.$mode = modeFilter; }
  const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';

  const sql = `
    SELECT ${periodLabelSql} AS period_label, year, month, quarter,
      COUNT(DISTINCT staff_id) AS staff_count,
      COUNT(DISTINCT CASE WHEN term_type = '长险' THEN staff_id END) AS long_term_staff,
      SUM(zhsf_cents) / 100.0 AS total_zhsf,
      SUM(ghgb_cents) / 100.0 AS total_ghgb
    FROM fact_premium
    ${where}
    GROUP BY ${groupCols}
    ORDER BY ${periodOrder}
  `;
  const rows = q(sql, params);

  // 标准人力：按人员汇总月度折算保费，筛选达标人员
  // 阈值：OTO≥2万，证保≥3万（按业务模式区分）
  const stdSql = `
    SELECT ${periodLabelSql} AS period_label,
      COALESCE(COUNT(DISTINCT CASE WHEN biz_mode LIKE '%OTO%' AND staff_zhsf >= 20000 THEN staff_id END), 0) +
      COALESCE(COUNT(DISTINCT CASE WHEN (biz_mode LIKE '%证保%' OR biz_mode LIKE '%社保%') AND staff_zhsf >= 30000 THEN staff_id END), 0) AS std_count
    FROM (
      SELECT ${groupCols}, staff_id, biz_mode, SUM(zhsf_cents) / 100.0 AS staff_zhsf
      FROM fact_premium
      ${where}
      GROUP BY ${groupCols}, staff_id, biz_mode
    ) t
    GROUP BY ${groupCols}
    ORDER BY ${periodOrder}
  `;
  let stdRows = [];
  try { stdRows = q(stdSql, params); } catch (e) { console.warn('标准人力查询失败:', e); }
  const stdMap = {};
  stdRows.forEach(r => { stdMap[r.period_label] = r.std_count; });

  // 计算月均在职人力（近似：相邻两期末末人力的平均）
  const avgStaffMap = {};
  for (let i = 0; i < rows.length; i++) {
    const curr = rows[i].staff_count || 0;
    const prev = i > 0 ? (rows[i - 1].staff_count || 0) : curr;
    avgStaffMap[rows[i].period_label] = Math.round((prev + curr) / 2);
  }

  let html = '<table class="data-table"><thead><tr>' +
    '<th>期间</th><th>月末在职人力</th><th>月均在职人力</th><th>长险活动人力</th><th>长险活动率</th>' +
    '<th>人均保费</th><th>人均产能</th><th>标准人力</th>' +
    '</tr></thead><tbody>';

  if (rows.length === 0) {
    html += '<tr><td colspan="8" style="text-align:center;color:#999;padding:40px;">暂无数据</td></tr>';
  } else {
    rows.forEach(r => {
      const staffCount = r.staff_count || 0;
      const avgStaff = avgStaffMap[r.period_label] || staffCount;
      const longTermStaff = r.long_term_staff || 0;
      const activityRate = avgStaff > 0 ? (longTermStaff / avgStaff * 100).toFixed(1) + '%' : '-';
      const perCapitaPremium = avgStaff > 0 ? (r.total_ghgb / avgStaff).toFixed(0) : '-';
      const perCapitaCapacity = longTermStaff > 0 ? (r.total_ghgb / longTermStaff).toFixed(0) : '-';
      const stdCount = stdMap[r.period_label] || 0;

      html += '<tr>' +
        `<td>${r.period_label}</td>` +
        `<td class="num">${staffCount}</td>` +
        `<td class="num">${avgStaff}</td>` +
        `<td class="num">${longTermStaff}</td>` +
        `<td class="num">${activityRate}</td>` +
        `<td class="num">${perCapitaPremium !== '-' ? formatNum(+perCapitaPremium) : '-'}</td>` +
        `<td class="num">${perCapitaCapacity !== '-' ? formatNum(+perCapitaCapacity) : '-'}</td>` +
        `<td class="num">${stdCount}</td>` +
        '</tr>';
    });
  }
  html += '</tbody></table>';
  area.innerHTML = html;
}
