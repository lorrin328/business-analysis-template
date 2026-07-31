// team-analysis.js — team trend chart state and rendering
    // ---------- Chart 3: Team Trend ----------
    let currentTeamMetric = 'headcount';
    let currentTeamDim = 'year';
    let selectedTeamYear = DEFAULT_DASHBOARD_YEAR;
    const selectedTeamMonths = {
      quarter: [],
      month: []
    };
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
    let teamEnhancedRequestSerial = 0;
    let selectedTeamEnhancedPeriodType = 'month';
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

    function getTeamMaxMonth() {
      const latest = latestTeamMonthIndex(String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR)) + 1;
      return latest || (
        typeof getLatestMonthForYear === 'function'
          ? getLatestMonthForYear(String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR))
          : 12
      );
    }

    function getSelectedTeamMonths(dimension = currentTeamDim) {
      if (dimension === 'year') return [];
      const selected = MonthMultiSelect.normalizeMonths(selectedTeamMonths[dimension], getTeamMaxMonth());
      if (selected.length > 0) return selected;
      const fallback = MonthMultiSelect.defaultMonths(dimension, getTeamMaxMonth());
      selectedTeamMonths[dimension] = fallback;
      return fallback;
    }

    function renderTeamMonthFilter() {
      const container = document.getElementById('teamMonthMultiSelect');
      if (!container) return;
      if (currentTeamDim === 'year') {
        container.hidden = true;
        return;
      }
      selectedTeamMonths[currentTeamDim] = MonthMultiSelect.render(container, {
        dimension: currentTeamDim,
        maxMonth: getTeamMaxMonth(),
        selectedMonths: getSelectedTeamMonths(currentTeamDim),
        onChange: months => {
          selectedTeamMonths[currentTeamDim] = months;
          selectedTeamEnhancedPeriodType = currentTeamDim;
          teamChart.clear();
          teamChart.setOption(getTeamOption(), true);
          refreshTeamEnhancedPanel();
        }
      });
    }

    function renderTeamEnhancedMonthFilter() {
      const container = document.getElementById('teamEnhancedMonthMultiSelect');
      if (!container || selectedTeamEnhancedPeriodType === 'year') return;
      selectedTeamMonths[selectedTeamEnhancedPeriodType] = MonthMultiSelect.render(container, {
        dimension: selectedTeamEnhancedPeriodType,
        maxMonth: getTeamMaxMonth(),
        selectedMonths: getSelectedTeamMonths(selectedTeamEnhancedPeriodType),
        onChange: months => {
          selectedTeamMonths[selectedTeamEnhancedPeriodType] = months;
          currentTeamDim = selectedTeamEnhancedPeriodType;
          renderTeamMonthFilter();
          teamChart.clear();
          teamChart.setOption(getTeamOption(), true);
          refreshTeamEnhancedPanel();
        }
      });
    }

    function buildTeamEnhancedParams() {
      const params = new URLSearchParams({
        year: String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR),
        periodType: selectedTeamEnhancedPeriodType,
        scope: 'all'
      });
      if (selectedTeamEnhancedPeriodType !== 'year') {
        params.set('months', getSelectedTeamMonths(selectedTeamEnhancedPeriodType).join(','));
      }
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
      return MonthMultiSelect.periodLabel(year, data.months || []);
    }

    function renderTeamEnhancedControls(data) {
      const periodType = data?.periodType || selectedTeamEnhancedPeriodType;
      const selectedLines = getSelectedTeamEnhancedBusinessLines();
      const allSelected = selectedLines.length === Object.keys(selectedTeamEnhancedBusinessLines).length;
      const monthControlHtml = periodType === 'year'
        ? ''
        : '<div id="teamEnhancedMonthMultiSelect" class="team-enhanced-month-filter"></div>';
      return `
        <div class="chart-controls team-enhanced-controls">
          <span class="team-enhanced-control-label">统计期间</span>
          <button class="chart-btn ${periodType === 'year' ? 'active' : ''}" data-team-enhanced-period-type="year">年度</button>
          <button class="chart-btn ${periodType === 'quarter' ? 'active' : ''}" data-team-enhanced-period-type="quarter">季度</button>
          <button class="chart-btn ${periodType === 'month' ? 'active' : ''}" data-team-enhanced-period-type="month">月度</button>
          ${monthControlHtml}
          <span class="team-enhanced-control-label">业务模式</span>
          <label class="check-label team-enhanced-check">
            <input type="checkbox" ${allSelected ? 'checked' : ''} data-team-enhanced-line="全部">
            <span>全选</span>
          </label>
          ${Object.keys(selectedTeamEnhancedBusinessLines).map(line => `
            <label class="check-label team-enhanced-check">
              <input type="checkbox" ${selectedTeamEnhancedBusinessLines[line] ? 'checked' : ''} data-team-enhanced-line="${escapeTeamText(line)}">
              <span>${escapeTeamText(line)}</span>
            </label>
          `).join('')}
        </div>
      `;
    }

    function switchTeamEnhancedPeriodType(periodType) {
      selectedTeamEnhancedPeriodType = periodType;
      currentTeamDim = periodType;
      document.querySelectorAll('#teamDimBtns button').forEach(button => {
        button.classList.toggle('active', button.dataset.teamDim === periodType);
      });
      renderTeamMonthFilter();
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
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

    async function fetchTeamEnhancedData(requestSerial) {
      const wrapper = document.getElementById('teamEnhancedPanel');
      teamEnhancedLoading = true;
      if (wrapper && !teamEnhancedData) {
        wrapper.innerHTML = '<div class="structure-empty">正在加载队伍结构与产能分析...</div>';
      }
      try {
        const params = buildTeamEnhancedParams();
        const payload = await window.fetchJson(`/api/team-enhanced-analysis?${params.toString()}`);
        if (requestSerial !== teamEnhancedRequestSerial) return false;
        teamEnhancedData = window.unwrapApiResponse ? window.unwrapApiResponse(payload) : (payload?.data || null);
        return true;
      } catch (error) {
        if (requestSerial === teamEnhancedRequestSerial) {
          console.error('load team enhanced analysis failed', error);
          teamEnhancedData = null;
          return true;
        }
        return false;
      } finally {
        if (requestSerial === teamEnhancedRequestSerial) teamEnhancedLoading = false;
      }
    }

    async function refreshTeamEnhancedPanel() {
      const requestSerial = ++teamEnhancedRequestSerial;
      teamEnhancedData = null;
      const shouldRender = await fetchTeamEnhancedData(requestSerial);
      if (shouldRender) renderTeamEnhancedPanel();
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

    function fmtTeamOptionalPercent(value, digits = 1) {
      return value === null || value === undefined ? '--' : `${fmtTeamNumber(value, digits)}%`;
    }

    function renderHighProductivityBandCell(group, bandLabel) {
      const band = (group?.bands || []).find(item => item.label === bandLabel) || {};
      const headcountShare = fmtTeamOptionalPercent(band.headcountShare);
      const premiumShare = fmtTeamOptionalPercent(band.premiumShare);
      return `
        <div class="primary-text">${fmtTeamNumber(band.count)}人 · ${headcountShare}</div>
        <div class="muted">${fmtTeamNumber(band.qjPremium, 1)}万 · ${premiumShare}</div>
      `;
    }

    function renderHighProductivityRows(groups, bandLabels, emptyText, includeOrg = false) {
      const columns = [
        ...(includeOrg ? [
          { render: row => `<span class="primary-text">${escapeTeamText(row.org || '未列明')}</span>` }
        ] : []),
        { render: row => `<span class="primary-text">${escapeTeamText(row.businessLine || row.label || '未列明')}</span>` },
        ...bandLabels.map(bandLabel => ({
          className: 'num',
          render: row => renderHighProductivityBandCell(row, bandLabel)
        }))
      ];
      return renderRows(groups || [], columns, emptyText);
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
      const highProductivity = data.highProductivity || {};
      const highProductivityBands = highProductivity.definitions?.bands
        || highProductivity.byBusinessLine?.[0]?.bands?.map(item => item.label)
        || ['60万—100万', '100万—150万', '150万—300万', '300万—500万', '500万—1000万', '1000万及以上'];
      const highProductivityHeaders = highProductivityBands
        .map(label => `<th class="num">${escapeTeamText(label)}</th>`)
        .join('');
      const highProductivityLineRows = renderHighProductivityRows(
        highProductivity.byBusinessLine || [],
        highProductivityBands,
        '当前筛选未包含OTO或证保高产能人力'
      );
      const highProductivityOrgLineRows = renderHighProductivityRows(
        highProductivity.byOrgBusinessLine || [],
        highProductivityBands,
        '当前筛选暂无分机构、分模式高产能人力',
        true
      );

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
        <div class="structure-block-title">累计期交保费60万元及以上人力分档</div>
        <div class="structure-table-wrapper" style="margin-top:10px;">
          <table class="structure-table" id="teamHighProductivityBusinessLineTable">
            <thead>
              <tr>
                <th>业务模式</th>
                ${highProductivityHeaders}
              </tr>
            </thead>
            <tbody>${highProductivityLineRows}</tbody>
          </table>
        </div>
        <div class="structure-table-wrapper" style="margin-top:10px;">
          <table class="structure-table" id="teamHighProductivityOrgLineTable">
            <thead>
              <tr>
                <th>机构</th>
                <th>业务模式</th>
                ${highProductivityHeaders}
              </tr>
            </thead>
            <tbody>${highProductivityOrgLineRows}</tbody>
          </table>
        </div>
        <div class="team-insight-note" style="margin-top:8px;">
          仅展示OTO、证保。每格第一行是“人数 · 人数占比”，第二行是“累计期交保费 · 保费占比”；占比分母分别为同一业务模式或同一机构+业务模式的全部月末在职样本人数和累计期交保费。单月按当月累计，多月按所选月份个人累计，同一人员只计1人。
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
          标准人力口径：OTO 为月末在职且当月折算保费/标准保费≥2万元；证保为月末在职且当月折算保费/标准保费≥3万元。2026年产品4281按10年及以上交期处理，标准保费按期交保费全额计入。标准人力贡献按对应人员期交保费统计；多月按所选月份人月汇总。
        </div>
        <div class="team-insight-note" style="margin-top:12px;">
          口径：单月仅纳入当月月末在职人员；多月纳入所选月份内任一月末在职过的人员，同一人员只计 1 人，人员属性取最后一个所选月。当前筛选机构数：${selectedOrgCount}。
        </div>
      `;
      renderTeamEnhancedMonthFilter();
    }

    function bindTeamEnhancedControls() {
      const panel = document.getElementById('teamEnhancedPanel');
      if (!panel || panel.dataset.boundTeamEnhancedControls === 'true') return;
      panel.dataset.boundTeamEnhancedControls = 'true';

      panel.addEventListener('click', event => {
        const button = event.target.closest('button[data-team-enhanced-period-type]');
        if (!button || !panel.contains(button)) return;
        event.preventDefault();
        switchTeamEnhancedPeriodType(button.dataset.teamEnhancedPeriodType);
      });

      panel.addEventListener('change', event => {
        const input = event.target.closest('input[data-team-enhanced-line]');
        if (!input || !panel.contains(input)) return;
        toggleTeamEnhancedBusinessLine(input.dataset.teamEnhancedLine, input.checked);
      });
    }

    function getTeamAggregated(year, metric) {
      const selectedKeys = Object.keys(selectedTeamSeries).filter(k => selectedTeamSeries[k]);
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      const hasOrgFilter = selectedOrgs.length > 0 && selectedOrgs.length < ORG_LIST_TEAM.length;
      const useOrgData = hasOrgFilter && teamOrgData[year];
      const data = teamMock[year];
      if (!data && !useOrgData) return Array(12).fill(null);
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

      const selectedMonths = getSelectedTeamMonths(currentTeamDim);
      const selectedIndexes = selectedMonths.map(month => month - 1);
      const selectedMonthNames = selectedIndexes.map(index => months[index]);
      const periodText = selectedMonths.join('、') + '月';
      const currentFull = getTeamAggregated(year, metric);
      const currentData = selectedIndexes.map(index => currentFull[index]);

      const seriesList = [
        { name: year + '年' + periodText, type: 'line', data: currentData, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, itemStyle: { color: '#3b82f6' } }
      ];

      if (teamMock[prevYear]) {
        const prevFull = getTeamAggregated(prevYear, metric);
        const prevData = selectedIndexes.map(index => prevFull[index]);
        seriesList.push({ name: prevYear + '年' + periodText, type: 'line', data: prevData, smooth: true, symbol: 'none', lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#94a3b8' } });
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
        xAxis: { type: 'category', data: selectedMonthNames, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
        yAxis: { type: 'value', name: unit, axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8', formatter: isPercent ? '{value}%' : '{value}' } },
        series: seriesList
      };
    }

    teamChart.setOption(getTeamOption());
    bindTeamEnhancedControls();
    refreshTeamEnhancedPanel();

    async function switchTeamYear(value) {
      selectedTeamYear = value;
      await loadYearFromApi(value, { updateKpi: false, updateProduct: false });
      renderTeamMonthFilter();
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function switchTeamMetric(btn, metric) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      currentTeamMetric = metric;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }
    function switchTeamDim(btn, dim) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      currentTeamDim = dim;
      selectedTeamEnhancedPeriodType = dim;
      renderTeamMonthFilter();
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
        document.querySelectorAll('#teamOrgChecks input[data-team-org]:not([data-team-org="all"])').forEach(input => {
          input.checked = checked;
        });
      } else {
        selectedTeamOrgs[key] = checked;
        const allChecked = ORG_LIST_TEAM.every(o => selectedTeamOrgs[o]);
        const allInput = document.querySelector('#teamOrgChecks input[data-team-org="all"]');
        if (allInput) allInput.checked = allChecked;
      }
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      refreshTeamEnhancedPanel();
    }

    function bindTeamTrendControls() {
      const yearSelect = document.getElementById('teamYearSelect');
      if (yearSelect && yearSelect.dataset.boundTeamYear !== 'true') {
        yearSelect.dataset.boundTeamYear = 'true';
        yearSelect.addEventListener('change', () => switchTeamYear(yearSelect.value));
      }

      const metricBtns = document.getElementById('teamMetricBtns');
      if (metricBtns && metricBtns.dataset.boundTeamMetrics !== 'true') {
        metricBtns.dataset.boundTeamMetrics = 'true';
        metricBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-team-metric]');
          if (!button || !metricBtns.contains(button)) return;
          event.preventDefault();
          switchTeamMetric(button, button.dataset.teamMetric);
        });
      }

      const dimBtns = document.getElementById('teamDimBtns');
      if (dimBtns && dimBtns.dataset.boundTeamDims !== 'true') {
        dimBtns.dataset.boundTeamDims = 'true';
        dimBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-team-dim]');
          if (!button || !dimBtns.contains(button)) return;
          event.preventDefault();
          switchTeamDim(button, button.dataset.teamDim);
        });
      }

      const seriesChecks = document.getElementById('teamSeriesChecks');
      if (seriesChecks && seriesChecks.dataset.boundTeamSeries !== 'true') {
        seriesChecks.dataset.boundTeamSeries = 'true';
        seriesChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-team-series]');
          if (!input || !seriesChecks.contains(input)) return;
          toggleTeamSeries(input.dataset.teamSeries, input.checked);
        });
      }

      const orgChecks = document.getElementById('teamOrgChecks');
      if (orgChecks && orgChecks.dataset.boundTeamOrgs !== 'true') {
        orgChecks.dataset.boundTeamOrgs = 'true';
        orgChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-team-org]');
          if (!input || !orgChecks.contains(input)) return;
          toggleTeamOrg(input.dataset.teamOrg, input.checked);
        });
      }
    }

    bindTeamTrendControls();
    renderTeamMonthFilter();
