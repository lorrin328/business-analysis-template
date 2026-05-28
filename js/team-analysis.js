// team-analysis.js — team trend chart state and rendering
    // ---------- Chart 3: Team Trend ----------
    let currentTeamMetric = 'headcount';
    let currentTeamDim = 'year';
    let selectedTeamYear = DEFAULT_DASHBOARD_YEAR;
    let selectedTeamQuarter = 'Q2';
    const selectedTeamSeries = { 'OTO': true, '证保': true, '蚁桥': true };
    const ORG_LIST_TEAM = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
    const selectedTeamOrgs = {};
    ORG_LIST_TEAM.forEach(o => selectedTeamOrgs[o] = true);
    const teamOrgData = {};
    const teamMetricNames = {
      headcount: '人力规模',
      activity: '长险活动率',
      perCapitaPremium: '人均保费',
      perCapitaCapacity: '人均产能'
    };
    const teamMetricUnits = {
      headcount: '人',
      activity: '%',
      perCapitaPremium: '万',
      perCapitaCapacity: '万'
    };
    let teamEnhancedData = null;
    let teamEnhancedLoading = false;
    let selectedTeamEnhancedPeriodType = 'month';
    let selectedTeamEnhancedPeriodValue = null;
    const selectedTeamEnhancedBusinessLines = { OTO: true, '证保': true, '蚁桥': true };

    const teamChart = echarts.init(document.getElementById('teamChart'));

    function fmtTeamNumber(value, digits = 0) {
      const n = Number(value || 0);
      return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }

    function escapeTeamText(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }

    function latestTeamMonthIndex(year) {
      const data = teamMock[year];
      if (!data || !data.headcount) return -1;
      for (let i = 11; i >= 0; i--) {
        if (Object.keys(selectedTeamSeries).some(ch => selectedTeamSeries[ch] && data.headcount[ch]?.[i] !== null && data.headcount[ch]?.[i] !== undefined)) {
          return i;
        }
      }
      return -1;
    }

    function aggregateTeamMonth(year, monthIndex) {
      const selectedKeys = Object.keys(selectedTeamSeries).filter(k => selectedTeamSeries[k]);
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      const hasOrgFilter = selectedOrgs.length > 0 && selectedOrgs.length < ORG_LIST_TEAM.length;
      const useOrgData = hasOrgFilter && teamOrgData[year];
      const data = teamMock[year];
      const byLine = {};
      selectedKeys.forEach(ch => byLine[ch] = { headcount: 0, active: 0, premium: 0 });
      if (!data || monthIndex < 0) return { byLine, total: { headcount: 0, active: 0, premium: 0 } };
      if (useOrgData) {
        selectedOrgs.forEach(org => {
          const orgD = teamOrgData[year][org];
          if (!orgD) return;
          selectedKeys.forEach(ch => {
            byLine[ch].headcount += Number(orgD.headcount[ch]?.[monthIndex] || 0);
            byLine[ch].active += Number(orgD.activeHeadcount[ch]?.[monthIndex] || 0);
            byLine[ch].premium += Number(orgD.premium[ch]?.[monthIndex] || 0);
          });
        });
      } else {
        selectedKeys.forEach(ch => {
          byLine[ch].headcount += Number(data.headcount[ch]?.[monthIndex] || 0);
          byLine[ch].active += Number(data.activeHeadcount[ch]?.[monthIndex] || 0);
          byLine[ch].premium += Number(data.premium[ch]?.[monthIndex] || 0);
        });
      }
      const total = Object.values(byLine).reduce((sum, row) => ({
        headcount: sum.headcount + row.headcount,
        active: sum.active + row.active,
        premium: sum.premium + row.premium
      }), { headcount: 0, active: 0, premium: 0 });
      return { byLine, total };
    }

    function buildTeamEnhancedParams() {
      const params = new URLSearchParams({
        year: String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR),
        periodType: selectedTeamEnhancedPeriodType,
        scope: 'all'
      });
      const defaultMonth = latestTeamMonthIndex(String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR)) + 1 || 12;
      const periodValue = selectedTeamEnhancedPeriodValue || (
        selectedTeamEnhancedPeriodType === 'quarter' ? Math.ceil(defaultMonth / 3) :
        selectedTeamEnhancedPeriodType === 'month' ? defaultMonth : null
      );
      if (periodValue) params.set('periodValue', String(periodValue));
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      const selectedLines = getSelectedTeamEnhancedBusinessLines();
      if (selectedLines.length === 0) {
        params.set('businessLines', '__none__');
      } else if (selectedLines.length < Object.keys(selectedTeamEnhancedBusinessLines).length) {
        params.set('businessLines', selectedLines.join(','));
      }
      if (selectedOrgs.length === 0) {
        params.set('orgs', '__none__');
      } else if (selectedOrgs.length < ORG_LIST_TEAM.length) {
        params.set('orgs', selectedOrgs.join(','));
      }
      return params;
    }

    function teamEnhancedPeriodLabel(data) {
      if (!data) return '';
      const year = String(data.year || selectedTeamYear || DEFAULT_DASHBOARD_YEAR);
      if (data.periodType === 'year') return `${year}年`;
      if (data.periodType === 'quarter') return `${year}年Q${data.periodValue || ''}`;
      return `${year}年${data.month}月`;
    }

    function renderTeamEnhancedControls(data) {
      const periodType = data?.periodType || selectedTeamEnhancedPeriodType;
      const periodValue = data?.periodValue || selectedTeamEnhancedPeriodValue || data?.month || '';
      const selectedLines = getSelectedTeamEnhancedBusinessLines();
      const allSelected = selectedLines.length === Object.keys(selectedTeamEnhancedBusinessLines).length;
      const quarterOptions = [1, 2, 3, 4].map(q => `<option value="${q}" ${Number(periodValue) === q ? 'selected' : ''}>Q${q}</option>`).join('');
      const monthOptions = Array.from({ length: 12 }, (_, idx) => {
        const month = idx + 1;
        return `<option value="${month}" ${Number(periodValue) === month ? 'selected' : ''}>${month}月</option>`;
      }).join('');
      const selectHtml = periodType === 'year' ? '' : `
        <select class="chart-select" onchange="switchTeamEnhancedPeriodValue(this.value)">
          ${periodType === 'quarter' ? quarterOptions : monthOptions}
        </select>
      `;
      return `
        <div class="chart-controls team-enhanced-controls">
          <span class="team-enhanced-control-label">统计期间</span>
          <button class="chart-btn ${periodType === 'year' ? 'active' : ''}" onclick="switchTeamEnhancedPeriodType('year')">年度</button>
          <button class="chart-btn ${periodType === 'quarter' ? 'active' : ''}" onclick="switchTeamEnhancedPeriodType('quarter')">季度</button>
          <button class="chart-btn ${periodType === 'month' ? 'active' : ''}" onclick="switchTeamEnhancedPeriodType('month')">月度</button>
          ${selectHtml}
          <span class="team-enhanced-control-label">业务模式</span>
          <label class="check-label team-enhanced-check">
            <input type="checkbox" ${allSelected ? 'checked' : ''} onchange="toggleTeamEnhancedBusinessLine('全部', this.checked)">
            <span>全选</span>
          </label>
          ${Object.keys(selectedTeamEnhancedBusinessLines).map(line => `
            <label class="check-label team-enhanced-check">
              <input type="checkbox" ${selectedTeamEnhancedBusinessLines[line] ? 'checked' : ''} onchange="toggleTeamEnhancedBusinessLine('${line}', this.checked)">
              <span>${line}</span>
            </label>
          `).join('')}
        </div>
      `;
    }

    function switchTeamEnhancedPeriodType(periodType) {
      selectedTeamEnhancedPeriodType = periodType;
      const defaultMonth = latestTeamMonthIndex(String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR)) + 1 || 12;
      if (periodType === 'year') selectedTeamEnhancedPeriodValue = null;
      else if (periodType === 'quarter') selectedTeamEnhancedPeriodValue = Math.ceil(defaultMonth / 3);
      else selectedTeamEnhancedPeriodValue = defaultMonth;
      refreshTeamEnhancedPanel();
    }

    function switchTeamEnhancedPeriodValue(value) {
      selectedTeamEnhancedPeriodValue = Number(value);
      refreshTeamEnhancedPanel();
    }

    function getSelectedTeamEnhancedBusinessLines() {
      return Object.keys(selectedTeamEnhancedBusinessLines).filter(line => selectedTeamEnhancedBusinessLines[line]);
    }

    function toggleTeamEnhancedBusinessLine(value, checked) {
      if (value === '全部') {
        Object.keys(selectedTeamEnhancedBusinessLines).forEach(line => {
          selectedTeamEnhancedBusinessLines[line] = !!checked;
        });
      } else if (Object.prototype.hasOwnProperty.call(selectedTeamEnhancedBusinessLines, value)) {
        selectedTeamEnhancedBusinessLines[value] = !!checked;
      }
      refreshTeamEnhancedPanel();
    }

    async function fetchTeamEnhancedData() {
      const wrapper = document.getElementById('teamEnhancedPanel');
      if (teamEnhancedLoading) return;
      teamEnhancedLoading = true;
      if (wrapper && !teamEnhancedData) {
        wrapper.innerHTML = '<div class="structure-empty">正在加载队伍结构与产能分析...</div>';
      }
      try {
        const params = buildTeamEnhancedParams();
        const payload = await window.fetchJson(`/api/team-enhanced-analysis?${params.toString()}`);
        teamEnhancedData = window.unwrapApiResponse ? window.unwrapApiResponse(payload) : (payload?.data || null);
      } catch (error) {
        console.error('load team enhanced analysis failed', error);
        teamEnhancedData = null;
      } finally {
        teamEnhancedLoading = false;
      }
    }

    async function refreshTeamEnhancedPanel() {
      teamEnhancedData = null;
      await fetchTeamEnhancedData();
      renderTeamEnhancedPanel();
    }

    function renderRows(rows, columns, emptyText) {
      if (!rows || rows.length === 0) {
        return `<tr><td colspan="${columns.length}" class="muted">${escapeTeamText(emptyText)}</td></tr>`;
      }
      return rows.map(row => `
        <tr>
          ${columns.map(col => `<td class="${col.className || ''}">${col.render(row)}</td>`).join('')}
        </tr>
      `).join('');
    }

    function renderStandardManpowerRows(rows, emptyText, firstColumnName = '维度') {
      return renderRows(rows || [], [
        { render: row => `<span class="primary-text">${escapeTeamText(row.label || firstColumnName)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.trackedHeadcount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.qjPremium, 1)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardQjPremium, 1)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.premiumContributionRate, 1)}%` }
      ], emptyText);
    }

    function renderTeamEnhancedPanel() {
      const wrapper = document.getElementById('teamEnhancedPanel');
      if (!wrapper) return;
      const data = teamEnhancedData;
      if (!data || !data.month) {
        wrapper.innerHTML = '<div class="structure-empty">暂无队伍结构与产能分析数据</div>';
        return;
      }
      const year = String(data.year || selectedTeamYear || DEFAULT_DASHBOARD_YEAR);
      const summary = data.summary || {};
      const selectedOrgCount = Object.values(selectedTeamOrgs).filter(Boolean).length;
      const periodLabel = teamEnhancedPeriodLabel(data);
      const controlsHtml = renderTeamEnhancedControls(data);
      const selectedBusinessLines = getSelectedTeamEnhancedBusinessLines();
      const businessLineLabel = selectedBusinessLines.length === Object.keys(selectedTeamEnhancedBusinessLines).length
        ? 'OTO+证保+蚁桥'
        : (selectedBusinessLines.length ? selectedBusinessLines.join('+') : '未选择业务模式');
      const tenureRows = renderRows(data.tenureStructure || [], [
        { render: row => `<span class="primary-text">${escapeTeamText(row.label)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.share, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.activityRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.qjPremium, 1)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.avgPremium, 2)}万` }
      ], '暂无司龄段结构数据');
      const bandRows = renderRows(data.productivityBands || [], [
        { render: row => `<span class="primary-text">${escapeTeamText(row.label)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.share, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.qjPremium, 1)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.premiumShare, 1)}%` }
      ], '暂无产能段结构数据');
      const percentileRows = renderRows(data.percentiles || [], [
        { render: row => `<span class="primary-text">${escapeTeamText(row.label)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.sampleCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.zeroRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.avg, 2)}万` }
      ], '暂无分位数数据');
      const orgRows = renderRows(data.orgPercentiles || [], [
        { render: row => `<span class="primary-text">${escapeTeamText(row.label)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.sampleCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.zeroRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75Count)}人` }
      ], '暂无机构分位数数据');
      const trendRows = renderRows((data.trend || []).slice(-6), [
        { render: row => `${row.month}月` },
        { className: 'num', render: row => `${fmtTeamNumber(row.sampleCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.zeroRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p25Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50Count)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75Count)}人` }
      ], '暂无趋势数据');
      const standardManpower = data.standardManpower || {};
      const standardSummaryRows = renderStandardManpowerRows([
        ...(standardManpower.summary || []),
        ...(standardManpower.byBusinessLine || [])
      ], '暂无标准人力汇总数据');
      const standardOrgRows = renderStandardManpowerRows(standardManpower.byOrg || [], '暂无标准人力机构数据');
      const standardOrgLineRows = renderStandardManpowerRows(standardManpower.byOrgBusinessLine || [], '暂无标准人力机构+业务模式数据');
      const standardTrendRows = renderRows(standardManpower.trend || [], [
        { render: row => `${row.month}月` },
        { render: row => `<span class="primary-text">${escapeTeamText(row.label)}</span>` },
        { className: 'num', render: row => `${fmtTeamNumber(row.trackedHeadcount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.standardQjPremium, 1)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.premiumContributionRate, 1)}%` }
      ], '暂无标准人力分月数据');
      const standardCountLabel = Number(standardManpower.periodMonths || 0) > 1 ? '人月' : '人';

      wrapper.innerHTML = `
        ${controlsHtml}
        <div class="team-insight-grid">
          <div class="team-insight-card">
            <div class="team-insight-label">统计期间</div>
            <div class="team-insight-value">${periodLabel}</div>
            <div class="team-insight-note">人员月度原始表口径</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">月末在职样本</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.sampleCount)}人</div>
            <div class="team-insight-note">${escapeTeamText(businessLineLabel)}</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">零/负产能占比</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.zeroRate, 1)}%</div>
            <div class="team-insight-note">产能≤0人员 / 样本人数</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">P50 中位数</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.p50, 2)}万</div>
            <div class="team-insight-note">≥P50：${fmtTeamNumber(summary.p50Count)}人</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">P75 骨干门槛</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.p75, 2)}万</div>
            <div class="team-insight-note">≥P75：${fmtTeamNumber(summary.p75Count)}人</div>
          </div>
        </div>
        <div class="team-insight-layout">
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamTenureStructureTable">
              <thead>
                <tr>
                  <th>司龄段</th>
                  <th class="num">月末在职</th>
                  <th class="num">占比</th>
                  <th class="num">活动率</th>
                  <th class="num">期交保费</th>
                  <th class="num">人均保费</th>
                </tr>
              </thead>
              <tbody>${tenureRows}</tbody>
            </table>
          </div>
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamProductivityBandTable">
              <thead>
                <tr>
                  <th>产能段</th>
                  <th class="num">人数</th>
                  <th class="num">人数占比</th>
                  <th class="num">期交保费</th>
                  <th class="num">保费占比</th>
                </tr>
              </thead>
              <tbody>${bandRows}</tbody>
            </table>
          </div>
        </div>
        <div class="team-insight-layout" style="margin-top:10px;">
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamPercentileTable">
              <thead>
                <tr>
                  <th>维度</th>
                  <th class="num">样本</th>
                  <th class="num">零/负产能占比</th>
                  <th class="num">P25</th>
                  <th class="num">≥P25人数</th>
                  <th class="num">P50</th>
                  <th class="num">≥P50人数</th>
                  <th class="num">P75</th>
                  <th class="num">≥P75人数</th>
                  <th class="num">平均</th>
                </tr>
              </thead>
              <tbody>${percentileRows}</tbody>
            </table>
          </div>
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamProductivityTrendTable">
              <thead>
                <tr>
                  <th>月份</th>
                  <th class="num">样本</th>
                  <th class="num">零/负产能占比</th>
                  <th class="num">P25</th>
                  <th class="num">≥P25人数</th>
                  <th class="num">P50</th>
                  <th class="num">≥P50人数</th>
                  <th class="num">P75</th>
                  <th class="num">≥P75人数</th>
                </tr>
              </thead>
              <tbody>${trendRows}</tbody>
            </table>
          </div>
        </div>
        <div class="structure-table-wrapper" style="margin-top:10px;">
          <table class="structure-table" id="teamOrgPercentileTable">
            <thead>
              <tr>
                <th>机构</th>
                <th class="num">样本</th>
                <th class="num">零/负产能占比</th>
                <th class="num">P25</th>
                <th class="num">≥P25人数</th>
                <th class="num">P50</th>
                <th class="num">≥P50人数</th>
                <th class="num">P75</th>
                <th class="num">≥P75人数</th>
              </tr>
            </thead>
            <tbody>${orgRows}</tbody>
          </table>
        </div>
        <div class="structure-block-title">标准人力贡献分析</div>
        <div class="team-insight-layout" style="margin-top:10px;">
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamStandardManpowerSummaryTable">
              <thead>
                <tr>
                  <th>维度</th>
                  <th class="num">月末在职${standardCountLabel}</th>
                  <th class="num">标准人力${standardCountLabel}</th>
                  <th class="num">标准人力占比</th>
                  <th class="num">期交保费</th>
                  <th class="num">标准人力贡献</th>
                  <th class="num">贡献占比</th>
                </tr>
              </thead>
              <tbody>${standardSummaryRows}</tbody>
            </table>
          </div>
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamStandardManpowerTrendTable">
              <thead>
                <tr>
                  <th>月份</th>
                  <th>业务模式</th>
                  <th class="num">月末在职</th>
                  <th class="num">标准人力</th>
                  <th class="num">标准占比</th>
                  <th class="num">标准人力贡献</th>
                  <th class="num">贡献占比</th>
                </tr>
              </thead>
              <tbody>${standardTrendRows}</tbody>
            </table>
          </div>
        </div>
        <div class="team-insight-layout" style="margin-top:10px;">
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamStandardManpowerOrgTable">
              <thead>
                <tr>
                  <th>机构</th>
                  <th class="num">月末在职${standardCountLabel}</th>
                  <th class="num">标准人力${standardCountLabel}</th>
                  <th class="num">标准人力占比</th>
                  <th class="num">期交保费</th>
                  <th class="num">标准人力贡献</th>
                  <th class="num">贡献占比</th>
                </tr>
              </thead>
              <tbody>${standardOrgRows}</tbody>
            </table>
          </div>
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamStandardManpowerOrgLineTable">
              <thead>
                <tr>
                  <th>机构 / 业务模式</th>
                  <th class="num">月末在职${standardCountLabel}</th>
                  <th class="num">标准人力${standardCountLabel}</th>
                  <th class="num">标准人力占比</th>
                  <th class="num">期交保费</th>
                  <th class="num">标准人力贡献</th>
                  <th class="num">贡献占比</th>
                </tr>
              </thead>
              <tbody>${standardOrgLineRows}</tbody>
            </table>
          </div>
        </div>
        <div class="team-insight-note" style="margin-top:8px;">
          标准人力口径：OTO 为月末在职且当月折算保费/标准保费≥2万元；证保为月末在职且当月折算保费/标准保费≥3万元。标准人力贡献按对应人员期交保费统计；季度/年度按所选月份人月汇总。
        </div>
        <div class="team-insight-note" style="margin-top:12px;">
          口径：月度仅纳入当月月末在职人员；季度/年度纳入期间内任一统计月月末在职过的人员，同一期间内同一人员只计 1 人；P 值人数为达到该分位阈值及以上的人数。当前筛选机构数：${selectedOrgCount}。
        </div>
      `;
    }

    function getTeamAggregated(year, metric) {
      const selectedKeys = Object.keys(selectedTeamSeries).filter(k => selectedTeamSeries[k]);
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      const hasOrgFilter = selectedOrgs.length > 0 && selectedOrgs.length < ORG_LIST_TEAM.length;
      const useOrgData = hasOrgFilter && teamOrgData[year];
      const data = teamMock[year];
      const result = [];
      for (let i = 0; i < 12; i++) {
        if (Number(year) === DEFAULT_DASHBOARD_YEAR_NUM && i >= getLatestMonthForYear(String(year))) { result.push(null); continue; }
        let totalHeadcount = 0, totalActive = 0, totalPremium = 0;
        if (useOrgData) {
          for (const org of selectedOrgs) {
            const orgD = teamOrgData[year][org];
            if (!orgD) continue;
            for (const key of selectedKeys) {
              totalHeadcount += (orgD.headcount[key][i] || 0);
              totalActive += (orgD.activeHeadcount[key][i] || 0);
              totalPremium += (orgD.premium[key][i] || 0);
            }
          }
        } else {
          for (const key of selectedKeys) {
            totalHeadcount += data.headcount[key][i];
            totalActive += data.activeHeadcount[key][i];
            totalPremium += data.premium[key][i];
          }
        }
        if (metric === 'headcount') result.push(totalHeadcount);
        else if (metric === 'activity') result.push(totalHeadcount > 0 ? Math.round(totalActive / totalHeadcount * 1000) / 10 : 0);
        else if (metric === 'perCapitaPremium') result.push(totalHeadcount > 0 ? Math.round(totalPremium / totalHeadcount * 10) / 10 : 0);
        else if (metric === 'perCapitaCapacity') result.push(totalActive > 0 ? Math.round(totalPremium / totalActive * 10) / 10 : 0);
      }
      return result;
    }

    function getTeamOption() {
      const metric = currentTeamMetric;
      const year = parseInt(selectedTeamYear);
      const prevYear = year - 1;
      const unit = teamMetricUnits[metric];
      const isPercent = metric === 'activity';

      if (currentTeamDim === 'year') {
        const currentData = getTeamAggregated(year, metric);
        const seriesList = [
          { name: year + '年', type: 'line', data: currentData, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, itemStyle: { color: '#3b82f6' } }
        ];
        if (teamMock[prevYear]) {
          const prevData = getTeamAggregated(prevYear, metric);
          seriesList.push({ name: prevYear + '年', type: 'line', data: prevData, smooth: true, symbol: 'none', lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#94a3b8' } });
        }
        return {
          tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' },
            formatter: params => {
              let s = params[0].name + '<br/>';
              params.forEach(p => { if (p.value !== null && p.value !== undefined) s += `${p.marker} ${p.seriesName}: ${p.value}${unit}<br/>`; });
              return s;
            }
          },
          legend: { data: seriesList.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
          grid: { left: 50, right: 20, top: 20, bottom: 40 },
          xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
          yAxis: { type: 'value', name: unit, axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8', formatter: isPercent ? '{value}%' : '{value}' } },
          series: seriesList
        };
      }

      // quarter mode
      const quarter = selectedTeamQuarter;
      const qMonths = { 'Q1': [0,1,2], 'Q2': [3,4,5], 'Q3': [6,7,8], 'Q4': [9,10,11] }[quarter];
      const qMonthNames = qMonths.map(i => months[i]);
      const currentFull = getTeamAggregated(year, metric);
      const currentData = qMonths.map(i => currentFull[i]);

      const seriesList = [
        { name: year + '年' + quarter, type: 'line', data: currentData, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, itemStyle: { color: '#3b82f6' } }
      ];

      if (teamMock[prevYear]) {
        const prevFull = getTeamAggregated(prevYear, metric);
        const prevData = qMonths.map(i => prevFull[i]);
        seriesList.push({ name: prevYear + '年' + quarter, type: 'line', data: prevData, smooth: true, symbol: 'none', lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#94a3b8' } });
      }

      return {
        tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' },
          formatter: params => {
            let s = params[0].name + '<br/>';
            params.forEach(p => { if (p.value !== null && p.value !== undefined) s += `${p.marker} ${p.seriesName}: ${p.value}${unit}<br/>`; });
            return s;
          }
        },
        legend: { data: seriesList.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
        grid: { left: 50, right: 20, top: 20, bottom: 40 },
        xAxis: { type: 'category', data: qMonthNames, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
        yAxis: { type: 'value', name: unit, axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8', formatter: isPercent ? '{value}%' : '{value}' } },
        series: seriesList
      };
    }

    teamChart.setOption(getTeamOption());
    refreshTeamEnhancedPanel();

    async function switchTeamYear(value) {
      selectedTeamYear = value;
      await loadYearFromApi(value, { updateKpi: false, updateProduct: false });
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function switchTeamMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamMetric = metric;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function switchTeamDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamDim = dim;
      document.getElementById('teamQuarterSelect').style.display = dim === 'quarter' ? 'inline-block' : 'none';
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function switchTeamQuarter(value) {
      selectedTeamQuarter = value;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function toggleTeamSeries(key, checked) {
      selectedTeamSeries[key] = checked;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }

    function toggleTeamOrg(key, checked) {
      if (key === 'all') {
        ORG_LIST_TEAM.forEach(o => { selectedTeamOrgs[o] = checked; });
        document.querySelectorAll('#teamOrgChecks input[type="checkbox"]').forEach((input, idx) => {
          if (idx > 0) input.checked = checked;
        });
      } else {
        selectedTeamOrgs[key] = checked;
        const allChecked = ORG_LIST_TEAM.every(o => selectedTeamOrgs[o]);
        const allInput = document.querySelector('#teamOrgChecks input[type="checkbox"]');
        if (allInput) allInput.checked = allChecked;
      }
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }

