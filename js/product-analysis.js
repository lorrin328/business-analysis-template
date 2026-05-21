// product-analysis.js — 产品结构图表
(function (window) {
    // ---------- Chart 2: Product Structure ----------
    const productChart = echarts.init(document.getElementById('productChart'));

    function createCheckboxLabel(labelText, checked, onChange) {
      const label = document.createElement('label');
      label.className = 'check-label';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = checked !== false;
      input.dataset.org = String(labelText || '');
      input.addEventListener('change', () => onChange(input.dataset.org, input.checked));
      const span = document.createElement('span');
      span.textContent = String(labelText || '');
      label.appendChild(input);
      label.appendChild(document.createTextNode(' '));
      label.appendChild(span);
      return label;
    }

    function getPieOption(type) {
      const data = productData[type] || [];
      if (data.length === 0) {
        return {
          title: { text: '暂无产品结构数据', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
          series: []
        };
      }
      return {
        tooltip: {
          trigger: 'item',
          backgroundColor: '#1e293b',
          borderColor: '#334155',
          textStyle: { color: '#f1f5f9' },
          formatter: '{b}: {c}万 ({d}%)'
        },
        legend: {
          type: 'scroll',
          orient: 'horizontal',
          left: 'center',
          bottom: 4,
          width: '86%',
          height: 44,
          textStyle: { color: '#94a3b8', fontSize: 10 },
          itemWidth: 9,
          itemHeight: 9,
          itemGap: 10,
          pageIconColor: '#60a5fa',
          pageIconInactiveColor: '#475569',
          pageTextStyle: { color: '#94a3b8' }
        },
        series: [{
          type: 'pie',
          radius: ['36%', '62%'],
          center: ['50%', '42%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#1e293b', borderWidth: 2 },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 13,
              fontWeight: 600,
              color: '#f8fafc',
              textBorderWidth: 0,
              textShadowBlur: 0
            }
          },
          data,
          color: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4']
        }]
      };
    }
    let currentPieType = 'premium';
    productChart.setOption(getPieOption(currentPieType));

    function switchPie(btn, type) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPieType = type;
      productChart.setOption(getPieOption(type), true);
    }

    function toggleProductSource(source, checked) {
      productFilters[source] = checked;
      const row = document.getElementById(source === 'transform' ? 'productTransformRow' : 'productJingdaiRow');
      if (row) row.style.display = checked ? 'flex' : 'none';
      refreshProductChart();
    }

    function toggleProductTransform(line, checked) {
      productFilters.transformLines[line] = checked;
      refreshProductChart();
    }

    function toggleProductJingdaiOrg(org, checked) {
      productFilters.jingdaiOrgs[org] = checked;
      refreshProductChart();
    }

    // ---------- Product Structure Enhancement ----------
    productFilters.orgs = { 'all': true };
    ORG_LIST.forEach(o => productFilters.orgs[o] = true);
    productFilters.timeDim = 'year';
    productFilters.subPeriod = 'all';
    productFilters.metric = 'qj';

    function toggleProductOrg(org, checked) {
      if (org === 'all') {
        productFilters.orgs['all'] = checked;
        ORG_LIST.forEach(o => productFilters.orgs[o] = checked);
        const allLabel = document.querySelector('#productOrgChecks [data-org="all"]');
        document.querySelectorAll('#productOrgChecks [data-org]:not([data-org="all"])').forEach(cb => cb.checked = checked);
      } else {
        productFilters.orgs[org] = checked;
        const allChecked = ORG_LIST.every(o => productFilters.orgs[o]);
        productFilters.orgs['all'] = allChecked;
        const allLabel = document.querySelector('#productOrgChecks [data-org="all"]');
        if (allLabel) allLabel.checked = allChecked;
      }
      refreshProductChart();
    }

    function switchProductDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      productFilters.timeDim = dim;
      const sub = document.getElementById('productSubSelect');
      if (dim === 'year') { sub.style.display = 'none'; productFilters.subPeriod = 'all'; }
      else if (dim === 'quarter') {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全部</option>'+['Q1','Q2','Q3','Q4'].map(q => `<option value="${q}">${q}</option>`).join('');
        productFilters.subPeriod = 'all';
      } else {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全年</option>'+Array.from({length:12},(_,i)=>`<option value="${i+1}">${i+1}月</option>`).join('');
        productFilters.subPeriod = 'all';
      }
      refreshProductChart();
    }

    function switchProductSub(value) {
      productFilters.subPeriod = value;
      refreshProductChart();
    }

    function switchProductMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      productFilters.metric = metric;
      refreshProductChart();
    }

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
      year: '2026',
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


  window.productChart = productChart;
  window.getPieOption = getPieOption;
  window.switchPie = switchPie;
  window.refreshProductChart = refreshProductChart;
  window.buildProductQuery = buildProductQuery;
  window.currentPieType = currentPieType;`n})(window);


