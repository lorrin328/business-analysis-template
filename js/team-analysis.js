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
      const params = new URLSearchParams({ year: String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR), scope: 'all' });
      const selectedKeys = Object.keys(selectedTeamSeries).filter(k => selectedTeamSeries[k]);
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      if (selectedKeys.length === 0) {
        params.set('businessLines', '__none__');
      } else if (selectedKeys.length < Object.keys(selectedTeamSeries).length) {
        params.set('businessLines', selectedKeys.join(','));
      }
      if (selectedOrgs.length === 0) {
        params.set('orgs', '__none__');
      } else if (selectedOrgs.length < ORG_LIST_TEAM.length) {
        params.set('orgs', selectedOrgs.join(','));
      }
      return params;
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
        const resp = await fetch(`/api/team-enhanced-analysis?${params.toString()}`);
        if (!resp.ok) throw new Error(`team enhanced api ${resp.status}`);
        const payload = await resp.json();
        teamEnhancedData = payload?.data || null;
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
        { className: 'num', render: row => `${fmtTeamNumber(row.p50, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.avg, 2)}万` }
      ], '暂无分位数数据');
      const trendRows = renderRows((data.trend || []).slice(-6), [
        { render: row => `${row.month}月` },
        { className: 'num', render: row => `${fmtTeamNumber(row.sampleCount)}人` },
        { className: 'num', render: row => `${fmtTeamNumber(row.zeroRate, 1)}%` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p50, 2)}万` },
        { className: 'num', render: row => `${fmtTeamNumber(row.p75, 2)}万` }
      ], '暂无趋势数据');

      wrapper.innerHTML = `
        <div class="team-insight-grid">
          <div class="team-insight-card">
            <div class="team-insight-label">统计月份</div>
            <div class="team-insight-value">${year}年${data.month}月</div>
            <div class="team-insight-note">人员月度原始表口径</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">样本人数</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.sampleCount)}人</div>
            <div class="team-insight-note">当前筛选范围</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">零/负产能占比</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.zeroRate, 1)}%</div>
            <div class="team-insight-note">产能≤0人员 / 样本人数</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">P50 中位数</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.p50, 2)}万</div>
            <div class="team-insight-note">保留零/负产能人员</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">P75 骨干门槛</div>
            <div class="team-insight-value">${fmtTeamNumber(summary.p75, 2)}万</div>
            <div class="team-insight-note">人员月产能上四分位</div>
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
                  <th class="num">P50</th>
                  <th class="num">P75</th>
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
                  <th class="num">P50</th>
                  <th class="num">P75</th>
                </tr>
              </thead>
              <tbody>${trendRows}</tbody>
            </table>
          </div>
        </div>
        <div class="team-insight-note" style="margin-top:12px;">
          口径：以人力原始表人员月度记录为基准，按同一人员、同一年月左关联保单明细，保留零/负产能人员；经代无队伍人力基表，不进入本模块。当前筛选机构数：${selectedOrgCount}。
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

