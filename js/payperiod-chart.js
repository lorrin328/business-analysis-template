// payperiod-chart.js — payment period chart state and rendering
    // ---------- Payment Period Structure ----------
    const payPeriodData = { premium: [], count: [] };
    const payPeriodFilters = {
      transform: true,
      jingdai: true,
      channels: { 'OTO': true, '证保': true, '蚁桥': true },
      orgs: { 'all': true },
      jingdaiOrgs: {},
      orgsInitialized: false,
      metric: 'qj',
      timeDim: 'year',
      year: DEFAULT_DASHBOARD_YEAR,
      subPeriod: 'all',
      currentPieType: 'premium'
    };
    ORG_LIST.forEach(o => payPeriodFilters.orgs[o] = true);

    // Init org checkboxes for 交期结构
    (function initPayPeriodOrgChecks() {
      const container = document.getElementById('payPeriodTransformOrgChecks');
      ORG_LIST.forEach(org => {
        container.appendChild(createCheckboxLabel(org, true, togglePayPeriodOrg));
      });
      // Also init product org checks
      const prodContainer = document.getElementById('productOrgChecks');
      ORG_LIST.forEach(org => {
        prodContainer.appendChild(createCheckboxLabel(org, true, toggleProductOrg));
      });
    })();

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
      const labels = orgs.map(org => {
        const checked = payPeriodFilters.orgsInitialized ? (payPeriodFilters.jingdaiOrgs[org] !== false) : true;
        if (!payPeriodFilters.orgsInitialized) payPeriodFilters.jingdaiOrgs[org] = true;
        return createCheckboxLabel(org, checked, togglePayPeriodJingdaiOrg);
      });
      container.replaceChildren(...labels);
      payPeriodFilters.orgsInitialized = true;
    }

