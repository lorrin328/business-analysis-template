// payperiod-chart.js — 交期结构图表
(function (window) {
    const payPeriodChart = echarts.init(document.getElementById('payPeriodChart'));

    function getPayPeriodPieOption(type) {
      const data = type === 'count' ? payPeriodData.count : payPeriodData.premium;
      if (!data || data.length === 0) {
        return {
          title: { text: '暂无交期结构数据', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
          series: [{ type: 'pie', data: [], radius: ['40%', '70%'], center: ['35%', '50%'] }]
        };
      }
      const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];
      return {
        tooltip: { trigger: 'item', formatter: '{b}: {c}' + (type === 'count' ? '件' : '万') + ' ({d}%)' },
        series: [{
          type: 'pie', radius: ['38%', '66%'], center: ['50%', '54%'],
          data: data,
          color: colors,
          label: {
            formatter: '{b}\n{d}%',
            color: '#e5e7eb',
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 14,
            textBorderWidth: 0,
            textShadowBlur: 0,
            textShadowColor: 'transparent'
          },
          labelLine: {
            length: 18,
            length2: 14,
            lineStyle: { width: 1.5 },
            smooth: false
          },
          labelLayout: { hideOverlap: true },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.2)' } }
        }]
      };
    }

    function applyPayPeriodFallback(year) {
      payPeriodData.premium = [];
      payPeriodData.count = [];
      const chart = payPeriodChart;
      if (chart) chart.setOption(getPayPeriodPieOption('premium'), true);
    }

    function renderPayPeriodChart() {
      const type = payPeriodFilters.currentPieType;
      payPeriodChart.setOption(getPayPeriodPieOption(type), true);
    }

    function switchPayPeriodPie(btn, type) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      payPeriodFilters.currentPieType = type;
      renderPayPeriodChart();
    }

    function _buildPeriodMonths() {
      const dim = payPeriodFilters.timeDim;
      const sub = payPeriodFilters.subPeriod;
      if (dim === 'year' || sub === 'all') return null;
      if (dim === 'quarter') { const q = parseInt(sub.replace('Q','')); return Array.from({length:3},(_,i)=>(q-1)*3+i+1); }
      return [parseInt(sub)];
    }

    function buildPayPeriodQuery(year) {
      const params = new URLSearchParams();
      const bts = []; if (payPeriodFilters.transform) bts.push('转型'); if (payPeriodFilters.jingdai) bts.push('经代');
      if (bts.length < 2) params.set('businessTypes', bts.join(','));
      if (payPeriodFilters.transform) {
        const chs = Object.entries(payPeriodFilters.channels).filter(([,v])=>v).map(([k])=>k);
        if (chs.length < 3) params.set('channels', chs.join(','));
        const orgs = payPeriodFilters.orgs['all'] ? null : Object.entries(payPeriodFilters.orgs).filter(([k,v])=>k!=='all'&&v).map(([k])=>k);
        if (orgs && orgs.length < ORG_LIST.length) params.set('orgs', orgs.join(','));
      }
      if (payPeriodFilters.jingdai && payPeriodFilters.orgsInitialized) {
        const jdOrgs = Object.entries(payPeriodFilters.jingdaiOrgs).filter(([,v])=>v).map(([k])=>k);
        if (jdOrgs.length > 0 && jdOrgs.length < Object.keys(payPeriodFilters.jingdaiOrgs).length) params.set('jingdaiOrgs', jdOrgs.join(','));
      }
      const months = _buildPeriodMonths();
      if (months && months.length === 1) params.set('month', months[0]);
      else if (months && months.length > 1) params.set('months', months.join(','));
      if (payPeriodFilters.metric !== 'qj') params.set('metric', payPeriodFilters.metric);
      return `/api/payment-period/${year}?${params.toString()}`;
    }

    async function fetchPayPeriodData(year) {
      try {
        const d = unwrapApiResponse(await fetchJson(buildPayPeriodQuery(year)));
        payPeriodData.premium = d.premium || [];
        payPeriodData.count = d.count || [];
        if (d.jingdai_orgs && d.jingdai_orgs.length > 0) {
          renderPayPeriodJingdaiOrgs(d.jingdai_orgs);
        }
      } catch (e) { applyPayPeriodFallback(year); }
      renderPayPeriodChart();
    }

    function refreshPayPeriodChart() { fetchPayPeriodData(payPeriodFilters.year); }

    function togglePayPeriodBiz(type, checked) {
      payPeriodFilters[type === '转型' ? 'transform' : 'jingdai'] = checked;
      document.getElementById('payPeriodTransformRow').style.display = payPeriodFilters.transform ? 'flex' : 'none';
      document.getElementById('payPeriodTransformOrgRow').style.display = payPeriodFilters.transform ? 'flex' : 'none';
      document.getElementById('payPeriodJingdaiOrgRow').style.display = payPeriodFilters.jingdai ? 'flex' : 'none';
      refreshPayPeriodChart();
    }

    function togglePayPeriodChannel(ch, checked) {
      payPeriodFilters.channels[ch] = checked;
      refreshPayPeriodChart();
    }

    function togglePayPeriodOrg(org, checked) {
      if (org === 'all') {
        payPeriodFilters.orgs['all'] = checked;
        ORG_LIST.forEach(o => payPeriodFilters.orgs[o] = checked);
        document.querySelectorAll('#payPeriodTransformOrgChecks [data-org]:not([data-org="all"])').forEach(cb => cb.checked = checked);
      } else {
        payPeriodFilters.orgs[org] = checked;
        const allChecked = ORG_LIST.every(o => payPeriodFilters.orgs[o]);
        payPeriodFilters.orgs['all'] = allChecked;
        const allCb = document.querySelector('#payPeriodTransformOrgChecks [data-org="all"]');
        if (allCb) allCb.checked = allChecked;
      }
      refreshPayPeriodChart();
    }

    function togglePayPeriodJingdaiOrg(org, checked) {
      payPeriodFilters.jingdaiOrgs[org] = checked;
      refreshPayPeriodChart();
    }

    function switchPayPeriodDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      payPeriodFilters.timeDim = dim;
      const sub = document.getElementById('payPeriodSubSelect');
      if (dim === 'year') { sub.style.display = 'none'; payPeriodFilters.subPeriod = 'all'; }
      else if (dim === 'quarter') {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全部</option>'+['Q1','Q2','Q3','Q4'].map(q => `<option value="${q}">${q}</option>`).join('');
        payPeriodFilters.subPeriod = 'all';
      } else {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全年</option>'+Array.from({length:12},(_,i)=>`<option value="${i+1}">${i+1}月</option>`).join('');
        payPeriodFilters.subPeriod = 'all';
      }
      refreshPayPeriodChart();
    }

    function switchPayPeriodSub(value) { payPeriodFilters.subPeriod = value; refreshPayPeriodChart(); }
    function switchPayPeriodYear(value) { payPeriodFilters.year = value; refreshPayPeriodChart(); }

    function switchPayPeriodMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      payPeriodFilters.metric = metric;
      refreshPayPeriodChart();
    }

    function renderPayPeriodJingdaiOrgs(orgs) {
      const container = document.getElementById('payPeriodJingdaiOrgChecks');
      if (!orgs || orgs.length === 0) { container.innerHTML = ''; return; }
      container.innerHTML = orgs.map(org => {
        const checked = payPeriodFilters.orgsInitialized ? (payPeriodFilters.jingdaiOrgs[org] !== false) : true;
        if (!payPeriodFilters.orgsInitialized) payPeriodFilters.jingdaiOrgs[org] = true;
        return `<label class="check-label"><input type="checkbox" ${checked ? 'checked' : ''} data-org="${org}" onchange="togglePayPeriodJingdaiOrg(this.dataset.org, this.checked)"> <span>${org}</span></label>`;
      }).join('');
      payPeriodFilters.orgsInitialized = true;
    }

    // ---------- Chart 3: Team Trend ----------
    let currentTeamMetric = 'headcount';
    let currentTeamDim = 'year';
    let selectedTeamYear = '2026';
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

    function getTeamAggregated(year, metric) {
      const selectedKeys = Object.keys(selectedTeamSeries).filter(k => selectedTeamSeries[k]);
      const selectedOrgs = Object.keys(selectedTeamOrgs).filter(k => selectedTeamOrgs[k]);
      const hasOrgFilter = selectedOrgs.length > 0 && selectedOrgs.length < ORG_LIST_TEAM.length;
      const useOrgData = hasOrgFilter && teamOrgData[year];
      const data = teamMock[year];
      const result = [];
      for (let i = 0; i < 12; i++) {
        if (year === 2026 && i >= 5) { result.push(null); continue; }
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

    async function switchTeamYear(value) {
      selectedTeamYear = value;
      await loadYearFromApi(value, { updateKpi: false, updateProduct: false });
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
    }
    function switchTeamMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamMetric = metric;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
    }
    function switchTeamDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTeamDim = dim;
      document.getElementById('teamQuarterSelect').style.display = dim === 'quarter' ? 'inline-block' : 'none';
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
    }
    function switchTeamQuarter(value) {
      selectedTeamQuarter = value;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
    }
    function toggleTeamSeries(key, checked) {
      selectedTeamSeries[key] = checked;
      teamChart.clear();
      teamChart.setOption(getTeamOption(), true);
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
    }

    // ---------- Upload Handler ----------

  window.payPeriodChart = payPeriodChart;
  window.getPayPeriodOption = getPayPeriodOption;
  window.refreshPayPeriodChart = refreshPayPeriodChart;
  window.buildPayPeriodQuery = buildPayPeriodQuery;
  window.payPeriodFilters = payPeriodFilters;
  window.fetchPayPeriodData = fetchPayPeriodData;`n  window.switchPayPeriodYear = switchPayPeriodYear;`n})(window);


