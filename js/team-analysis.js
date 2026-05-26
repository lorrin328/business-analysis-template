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

    function renderTeamEnhancedPanel() {
      const wrapper = document.getElementById('teamEnhancedPanel');
      if (!wrapper) return;
      const year = String(selectedTeamYear || DEFAULT_DASHBOARD_YEAR);
      const monthIndex = latestTeamMonthIndex(year);
      if (monthIndex < 0) {
        wrapper.innerHTML = '<div class="structure-empty">暂无队伍结构与产能数据</div>';
        return;
      }
      const { byLine, total } = aggregateTeamMonth(year, monthIndex);
      const activityRate = total.headcount > 0 ? total.active / total.headcount * 100 : 0;
      const perCapitaPremium = total.headcount > 0 ? total.premium / total.headcount : 0;
      const perActivePremium = total.active > 0 ? total.premium / total.active : 0;
      const selectedOrgCount = Object.values(selectedTeamOrgs).filter(Boolean).length;
      const lineRows = Object.entries(byLine)
        .filter(([, row]) => row.headcount > 0 || row.premium > 0)
        .map(([line, row]) => {
          const lineActivity = row.headcount > 0 ? row.active / row.headcount * 100 : 0;
          const linePerCapita = row.headcount > 0 ? row.premium / row.headcount : 0;
          return `
            <tr>
              <td class="primary-text">${escapeTeamText(line)}</td>
              <td class="num">${fmtTeamNumber(row.headcount)}人</td>
              <td class="num">${fmtTeamNumber(row.active)}人</td>
              <td class="num">${lineActivity.toFixed(1)}%</td>
              <td class="num">${fmtTeamNumber(row.premium, 1)}万</td>
              <td class="num">${fmtTeamNumber(linePerCapita, 1)}万</td>
            </tr>
          `;
        }).join('');

      wrapper.innerHTML = `
        <div class="team-insight-grid">
          <div class="team-insight-card">
            <div class="team-insight-label">统计月份</div>
            <div class="team-insight-value">${year}年${monthIndex + 1}月</div>
            <div class="team-insight-note">随队伍趋势筛选联动</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">月均在职人力</div>
            <div class="team-insight-value">${fmtTeamNumber(total.headcount)}人</div>
            <div class="team-insight-note">当前筛选范围</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">长险活动率</div>
            <div class="team-insight-value">${activityRate.toFixed(1)}%</div>
            <div class="team-insight-note">活动人力 / 月均在职</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">人均保费</div>
            <div class="team-insight-value">${fmtTeamNumber(perCapitaPremium, 1)}万</div>
            <div class="team-insight-note">期交保费 / 月均在职</div>
          </div>
          <div class="team-insight-card">
            <div class="team-insight-label">人均产能</div>
            <div class="team-insight-value">${fmtTeamNumber(perActivePremium, 1)}万</div>
            <div class="team-insight-note">期交保费 / 活动人力</div>
          </div>
        </div>
        <div class="team-insight-layout">
          <div class="structure-table-wrapper" style="margin-top:0;">
            <table class="structure-table" id="teamEnhancedSummaryTable">
              <thead>
                <tr>
                  <th>业务模式</th>
                  <th class="num">月均在职</th>
                  <th class="num">活动人力</th>
                  <th class="num">活动率</th>
                  <th class="num">期交保费</th>
                  <th class="num">人均保费</th>
                </tr>
              </thead>
              <tbody>${lineRows || '<tr><td colspan="6" class="muted">暂无当前筛选范围数据</td></tr>'}</tbody>
            </table>
          </div>
          <div class="team-analysis-tiles">
            <div class="team-analysis-tile">
              <div class="team-analysis-tile-title">司龄段结构</div>
              <div class="team-analysis-tile-desc">按司龄段、机构、模式观察新人和成熟人员结构趋势。</div>
              <span class="team-analysis-status">需完善人员月度明细统计</span>
            </div>
            <div class="team-analysis-tile">
              <div class="team-analysis-tile-title">产能段结构</div>
              <div class="team-analysis-tile-desc">识别零产能、低产能、中腰部和高产能人员占比。</div>
              <span class="team-analysis-status">需完善人员月度明细统计</span>
            </div>
            <div class="team-analysis-tile">
              <div class="team-analysis-tile-title">P25 / P50 / P75</div>
              <div class="team-analysis-tile-desc">用分位数判断普通人员、底部人员和骨干层真实产能。</div>
              <span class="team-analysis-status">需完善人员产能分布统计</span>
            </div>
          </div>
        </div>
        <div class="team-insight-note" style="margin-top:12px;">
          当前试运行区只读取现有汇总数据，不影响队伍趋势、KPI 和机构维度。司龄段、职等、产能段和分位数需要先完成“每个人每个月”的保费、件数、司龄、职等统计后再正式启用。当前筛选机构数：${selectedOrgCount}。
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
    renderTeamEnhancedPanel();

    async function switchTeamYear(value) {
      selectedTeamYear = value;
      await loadYearFromApi(value, { updateKpi: false, updateProduct: false });
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      renderTeamEnhancedPanel();
    }
    function switchTeamMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamMetric = metric;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      renderTeamEnhancedPanel();
    }
    function switchTeamDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamDim = dim;
      document.getElementById('teamQuarterSelect').style.display = dim === 'quarter' ? 'inline-block' : 'none';
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      renderTeamEnhancedPanel();
    }
    function switchTeamQuarter(value) {
      selectedTeamQuarter = value;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      renderTeamEnhancedPanel();
    }
    function toggleTeamSeries(key, checked) {
      selectedTeamSeries[key] = checked;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
      renderTeamEnhancedPanel();
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
      renderTeamEnhancedPanel();
    }

