(function () {
  const state = { data: null, charts: {} };
  const el = id => document.getElementById(id);
  const user = () => window.getCurrentUser?.() || null;
  const can = key => user()?.role === 'admin' || user()?.permissions?.[key] === true;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
  const number = (value, digits = 2) => Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: digits, maximumFractionDigits: digits
  });
  const integer = value => Number(value || 0).toLocaleString('zh-CN');
  const rate = value => value == null ? '--' : `${(Number(value) * 100).toFixed(1)}%`;

  function requireAccess() {
    if (!window.getAuthToken?.() || !user()) {
      window.location.href = '/';
      return false;
    }
    el('currentUser').textContent = `${user().username} · ${user().roleLabel || user().role}`;
    if (!can('kpi')) {
      el('accessDenied').classList.remove('hidden');
      return false;
    }
    el('pageMain').classList.remove('hidden');
    return true;
  }

  function checkbox(value, label, checked, type) {
    return `<label class="check"><input type="checkbox" data-filter="${type}" value="${esc(value)}" ${checked ? 'checked' : ''}>${esc(label)}</label>`;
  }

  function renderFilters() {
    const filters = state.data.filters;
    const years = filters.selectedYears?.length ? filters.selectedYears : filters.availableYears;
    const months = filters.selectedMonths?.length ? filters.selectedMonths : filters.availableMonths;
    const orgs = filters.selectedOrgs?.length ? filters.selectedOrgs : filters.availableOrgs;
    el('yearChecks').innerHTML = filters.availableYears.map(item => checkbox(item, `${item}年`, years.includes(item), 'years')).join('') || '<span class="meta">暂无可选年度</span>';
    el('monthChecks').innerHTML = Array.from({ length: 12 }, (_, index) => index + 1).map(item => checkbox(item, `${item}月`, months.includes(item), 'months')).join('');
    el('orgChecks').innerHTML = filters.availableOrgs.map(item => checkbox(item, item, orgs.includes(item), 'orgs')).join('') || '<span class="meta">暂无可选机构</span>';
  }

  function selected(type) {
    return Array.from(document.querySelectorAll(`input[data-filter="${type}"]:checked`)).map(input => input.value);
  }

  function table(headers, rows, numeric = []) {
    if (!rows.length) return '<div class="empty">当前筛选范围暂无数据</div>';
    return `<div class="table-wrap"><table><thead><tr>${headers.map((item, index) => `<th class="${numeric.includes(index) ? 'num' : ''}">${esc(item)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((item, index) => `<td class="${numeric.includes(index) ? 'num' : ''}">${item}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderKpis() {
    const s = state.data.summary;
    const cards = [
      ['职拓期交保费', `${number(s.qjPremium)}万`, '是否职拓=是'],
      ['职拓年化规保', `${number(s.gmPremium)}万`, '源数据净额'],
      ['承保件数', `${integer(s.policyCount)}件`, '承保件数净额'],
      ['销售人员', `${integer(s.staffCount)}人`, '按人员工号去重'],
      ['职拓产品', `${integer(s.productCount)}个`, '按产品名称去重'],
      ['覆盖机构', `${integer(s.orgCount)}家`, '按当前筛选范围']
    ];
    el('kpiGrid').innerHTML = cards.map(([label, value, meta]) => `<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-meta">${meta}</div></article>`).join('');
  }

  function chart(id, option) {
    const node = el(id);
    if (!node || !window.echarts) return;
    state.charts[id] = state.charts[id] || echarts.init(node);
    state.charts[id].setOption(option, true);
  }

  function renderCharts() {
    const monthly = state.data.monthly;
    chart('monthlyChart', {
      tooltip: { trigger:'axis' },
      legend: { data:['期交保费（万）','承保件数'], bottom:0 },
      grid: { left:58, right:58, top:24, bottom:48 },
      xAxis: { type:'category', data:monthly.map(item => `${item.year}-${String(item.month).padStart(2, '0')}`) },
      yAxis: [{ type:'value', name:'万元' }, { type:'value', name:'件' }],
      series: [
        { name:'期交保费（万）', type:'bar', data:monthly.map(item => item.qjPremium), itemStyle:{ color:'#2f80ed' }, barMaxWidth:38 },
        { name:'承保件数', type:'line', yAxisIndex:1, data:monthly.map(item => item.policyCount), itemStyle:{ color:'#138a63' }, symbolSize:8 }
      ]
    });
    const orgs = state.data.organizations;
    chart('orgChart', {
      tooltip: { trigger:'axis', axisPointer:{ type:'shadow' } },
      grid: { left:80, right:30, top:20, bottom:35, containLabel:true },
      xAxis: { type:'value', name:'万元' },
      yAxis: { type:'category', inverse:true, data:orgs.map(item => item.org) },
      series: [{ type:'bar', data:orgs.map(item => item.qjPremium), itemStyle:{ color:'#0e91a7' }, label:{ show:true, position:'right', formatter:p => number(p.value) } }]
    });
    chart('productTypeChart', {
      tooltip: { trigger:'item', formatter:'{b}<br>{c}万元（{d}%）' },
      legend: { bottom:0, type:'scroll' },
      series: [{ type:'pie', radius:['42%','68%'], center:['50%','45%'], data:state.data.productTypes.map(item => ({ name:item.productType, value:item.qjPremium })), label:{ formatter:'{b}\n{d}%' } }]
    });
    const payments = state.data.paymentPeriods;
    chart('paymentChart', {
      tooltip: { trigger:'axis', axisPointer:{ type:'shadow' } },
      grid: { left:60, right:20, top:20, bottom:45 },
      xAxis: { type:'category', data:payments.map(item => item.paymentPeriod), axisLabel:{ interval:0 } },
      yAxis: { type:'value', name:'万元' },
      series: [{ type:'bar', data:payments.map(item => item.qjPremium), itemStyle:{ color:'#a56600' }, label:{ show:true, position:'top', formatter:p => number(p.value) } }]
    });
  }

  function renderTables() {
    el('orgTable').innerHTML = table(
      ['机构','期交保费(万)','年化规保(万)','占比','件数','销售人员','产品数'],
      state.data.organizations.map(item => [esc(item.org), number(item.qjPremium), number(item.gmPremium), rate(item.share), integer(item.policyCount), integer(item.staffCount), integer(item.productCount)]),
      [1,2,3,4,5,6]
    );
    el('staffTable').innerHTML = table(
      ['人员工号','机构','期交保费(万)','年化规保(万)','件数','产品数','活动月份数'],
      state.data.staff.map(item => [esc(item.staffId), esc(item.orgs || '--'), number(item.qjPremium), number(item.gmPremium), integer(item.policyCount), integer(item.productCount), integer(item.activeMonths)]),
      [2,3,4,5,6]
    );
    el('productTable').innerHTML = table(
      ['产品名称','产品类型','期交保费(万)','年化规保(万)','件数','销售人员'],
      state.data.products.map(item => [esc(item.productName), esc(item.productType), number(item.qjPremium), number(item.gmPremium), integer(item.policyCount), integer(item.staffCount)]),
      [2,3,4,5]
    );
  }

  function render() {
    renderFilters();
    renderKpis();
    renderCharts();
    renderTables();
    const meta = state.data.meta;
    const selectedYears = state.data.filters.selectedYears?.join('、') || '全部年度';
    const selectedMonths = state.data.filters.selectedMonths?.map(item => `${item}月`).join('、') || '全部月份';
    const selectedOrgs = state.data.filters.selectedOrgs?.join('、') || '全部机构';
    const lastBusiness = meta.lastBusinessDate ? ` · 职拓最后出单 ${meta.lastBusinessDate}` : '';
    el('sourceLine').textContent = `业绩基表截至 ${meta.dataCutoff || '--'}${lastBusiness} · ${selectedYears} · ${selectedMonths} · ${selectedOrgs}`;
  }

  async function load(query = '') {
    el('sourceLine').textContent = '正在读取最新基表数据…';
    const payload = await window.fetchJson(`/api/zhituo-analysis/overview${query ? `?${query}` : ''}`);
    state.data = window.unwrapApiResponse(payload);
    render();
  }

  async function applyFilters() {
    const years = selected('years');
    const months = selected('months');
    const orgs = selected('orgs');
    if (!years.length || !months.length || !orgs.length) {
      el('filterMessage').textContent = '年度、月份和机构均至少选择一项。';
      el('filterMessage').classList.add('error');
      return;
    }
    el('filterMessage').textContent = '';
    el('filterMessage').classList.remove('error');
    const query = new URLSearchParams({ years:years.join(','), months:months.join(','), orgs:orgs.join(',') });
    await load(query.toString());
  }

  function selectAll() {
    document.querySelectorAll('.filter-panel input[type="checkbox"]').forEach(input => { input.checked = true; });
    el('filterMessage').textContent = '已选择全部可用范围，点击“应用筛选”刷新。';
    el('filterMessage').classList.remove('error');
  }

  function bind() {
    el('backBtn').addEventListener('click', () => { window.location.href = '/'; });
    el('applyBtn').addEventListener('click', () => applyFilters().catch(showError));
    el('resetBtn').addEventListener('click', selectAll);
    window.addEventListener('resize', () => Object.values(state.charts).forEach(item => item.resize()));
  }

  function showError(error) {
    el('sourceLine').textContent = `读取失败：${error.message || error}`;
    el('sourceLine').classList.add('error');
  }

  async function init() {
    if (!requireAccess()) return;
    bind();
    try { await load(); } catch (error) { showError(error); }
  }

  init();
})();
