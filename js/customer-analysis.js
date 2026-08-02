(function () {
  const state = { data: null, cohortData: null, tab: 'overview', charts: [] };
  const el = id => document.getElementById(id);
  const user = () => window.getCurrentUser?.() || null;
  const can = key => user()?.role === 'admin' || user()?.permissions?.[key] === true;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
  const integer = value => Number(value || 0).toLocaleString('zh-CN');
  const number = (value, digits = 2) => value == null ? '--' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const rate = (value, digits = 1) => value == null ? '--' : `${(Number(value) * 100).toFixed(digits)}%`;
  const chartText = '#465668';
  const chartMuted = '#7b8794';
  const colors = { new: '#2f80ed', existing: '#8b5cf6', active: '#138a63', surrender: '#c33b32' };
  const windowLabels = { first_month: '首现月', twelve_months: '首现后12个月', calendar_year: '首现当年度' };

  function requireAccess() {
    if (!window.getAuthToken?.() || !user()) { window.location.href = '/'; return false; }
    el('currentUser').textContent = `${user().username} · ${user().roleLabel || user().role}`;
    if (!can('customer_analysis')) { el('accessDenied').classList.remove('hidden'); return false; }
    el('pageMain').classList.remove('hidden');
    return true;
  }

  function panel(title, subtitle, body) {
    return `<section class="panel"><div class="panel-head"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div></div><div class="panel-body">${body}</div></section>`;
  }

  function table(headers, rows, numeric = []) {
    if (!rows.length) return '<div class="empty">暂无数据</div>';
    return `<div class="table-wrap"><table><thead><tr>${headers.map((item, i) => `<th class="${numeric.includes(i) ? 'num' : ''}">${esc(item)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((item, i) => `<td class="${numeric.includes(i) ? 'num' : ''}">${item}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function clearCharts() {
    state.charts.forEach(chart => chart.dispose());
    state.charts = [];
  }

  function initChart(id, option) {
    const node = el(id);
    if (!node || !window.echarts) return;
    const chart = window.echarts.init(node);
    chart.setOption(option);
    state.charts.push(chart);
  }

  function axisBase() {
    return { axisLine: { lineStyle: { color: '#c8d1da' } }, axisLabel: { color: chartMuted }, splitLine: { lineStyle: { color: '#edf0f3' } } };
  }

  function rebuildPeriodOptions(preferred) {
    const type = el('periodType').value;
    if (type === 'year') { el('periodValueLabel').classList.add('hidden'); el('periodValue').innerHTML = ''; return; }
    const max = type === 'quarter' ? 4 : 12;
    const selected = Number(preferred || 1);
    el('periodValueCaption').textContent = type === 'quarter' ? '季度' : '月份';
    el('periodValue').innerHTML = Array.from({ length: max }, (_, i) => {
      const value = i + 1;
      return `<option value="${value}" ${value === selected ? 'selected' : ''}>${type === 'quarter' ? `Q${value}` : `${value}月`}</option>`;
    }).join('');
    el('periodValueLabel').classList.remove('hidden');
  }

  function renderKpis() {
    if (state.tab === 'cohort' && state.cohortData) {
      const s = state.cohortData.summary;
      const cards = [
        ['系统新客', integer(s.systemNewCustomers), `筛选范围可追踪 ${integer(s.trackedNewCustomers)}人`],
        ['再次承保客户', integer(s.repeatCustomers), `占可追踪新客 ${rate(s.repeatCustomerRate)}`],
        ['再次承保保单', integer(s.repeatPolicies), `每位可追踪新客 ${number(s.averageRepeatPolicies, 2)}份`],
        ['观察期交', `${number(s.qjPremiumWan)}万`, `首次${number(s.firstQjPremiumWan)}万 · 再次${number(s.repeatQjPremiumWan)}万`],
        ['再次承保期交占比', rate(s.repeatPremiumShare), `再次承保贡献 ${number(s.repeatQjPremiumWan)}万`],
        ['完整观察客户', integer(s.completedObservationCustomers), `完整率 ${rate(s.observationCompletenessRate)} · 未满窗口${integer(s.incompleteObservationCustomers)}人`]
      ];
      el('kpiGrid').innerHTML = cards.map(([label, value, meta]) => `<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-meta">${meta}</div></article>`).join('');
      return;
    }
    const s = state.data.summary;
    const cards = [
      ['期间客户', integer(s.customers), `新客${integer(s.newCustomers)} · 老客${integer(s.existingCustomers)}`],
      ['期交保费', `${number(s.qjPremiumWan)}万`, `新客${number(s.newQjPremiumWan)}万 · 老客${number(s.existingQjPremiumWan)}万`],
      ['新客业绩占比', rate(s.newPremiumShare), `老客占比 ${rate(s.existingPremiumShare)}`],
      ['当前有效保单', integer(s.activePolicies), `有效率 ${rate(s.activeRate)}`],
      ['退保终止', integer(s.surrenderPolicies), `退保率 ${rate(s.surrenderRate)} · 犹豫期撤保${integer(s.coolingOffPolicies)}份`],
      ['保单关联率', rate(s.policyMatchRate, 2), `已关联${integer(s.matchedPolicies)} / ${integer(s.policies)}份`]
    ];
    el('kpiGrid').innerHTML = cards.map(([label, value, meta]) => `<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-meta">${meta}</div></article>`).join('');
  }

  function conclusions() {
    const s = state.data.summary;
    const h = state.data.holdings.summary;
    return `<div class="conclusions">
      <div class="conclusion"><b>新客贡献</b><p>新客${integer(s.newCustomers)}人，贡献期交${number(s.newQjPremiumWan)}万元，占可识别客户业绩${rate(s.newPremiumShare)}。</p></div>
      <div class="conclusion"><b>保单状态</b><p>当前有效${integer(s.activePolicies)}份、退保终止${integer(s.surrenderPolicies)}份；退保率${rate(s.surrenderRate)}。</p></div>
      <div class="conclusion"><b>持单情况</b><p>一客多单${integer(h.multiPolicyCustomers)}人，占已关联客户${rate(h.multiPolicyRate)}；目前有有效保单的客户占${rate(h.activeCustomerRate)}。</p></div>
    </div>`;
  }

  function lineTable() {
    const rows = state.data.lines.map(item => [
      esc(item.businessLine), integer(item.customers), integer(item.newCustomers), integer(item.existingCustomers),
      number(item.qjPremiumWan), number(item.newQjPremiumWan), number(item.existingQjPremiumWan),
      integer(item.activePolicies), rate(item.activeRate), integer(item.surrenderPolicies), rate(item.surrenderRate), rate(item.matchRate)
    ]);
    return table(['业务','客户数','新客','老客','期交(万)','新客期交(万)','老客期交(万)','有效保单','有效率','退保终止','退保率','关联率'], rows, [1,2,3,4,5,6,7,8,9,10,11]);
  }

  function renderOverview() {
    return panel('本期结论', '按当前筛选范围直接汇总。', conclusions()) +
      `<div class="grid-2">${panel('新客与老客期交', '月度新老客按各月月初是否已有承保记录划分。', '<div class="chart" id="premiumTrend"></div>')}${panel('保单当前状态', '状态截止日与上方数据截止日一致。', '<div class="chart" id="statusChart"></div>')}</div>` +
      panel('分业务客户经营', '各业务客户数可能存在跨业务重复；平台客户数按客户去重。', lineTable());
  }

  function renderCustomer() {
    const segments = state.data.segments;
    const rows = [
      ['新客', integer(segments.new.customers), integer(segments.new.policies), number(segments.new.qjPremiumWan), rate(state.data.summary.newPremiumShare)],
      ['老客', integer(segments.existing.customers), integer(segments.existing.policies), number(segments.existing.qjPremiumWan), rate(state.data.summary.existingPremiumShare)]
    ];
    return panel('期间新老客构成', '新客为期间内首次承保；老客为期初已有承保记录。', table(['客户类型','客户数','保单数','期交保费(万)','业绩占比'], rows, [1,2,3,4])) +
      panel('月度客户与业绩', '月度口径用于观察获客与老客经营变化。', '<div class="chart" id="customerTrend"></div>');
  }

  function renderCohort() {
    const data = state.cohortData;
    if (!data) return '<div class="panel empty">正在读取新客经营数据…</div>';
    const s = data.summary;
    const meta = data.meta;
    const windowLabel = windowLabels[meta.observationWindow] || meta.observationWindow;
    const completeness = s.incompleteObservationCustomers
      ? `${integer(s.incompleteObservationCustomers)}名新客尚未走完整个观察窗口，复购率和贡献会随数据更新继续变化。`
      : '本次筛选的新客均已走完整个观察窗口。';
    const conclusion = `<div class="conclusions">
      <div class="conclusion"><b>新客范围</b><p>${esc(meta.periodLabel)}系统首次出现${integer(s.systemNewCustomers)}人；当前业务、机构、保单和产品筛选下，可追踪${integer(s.trackedNewCustomers)}人。</p></div>
      <div class="conclusion"><b>再次承保</b><p>${integer(s.repeatCustomers)}人再次承保${integer(s.repeatPolicies)}份，客户再次承保率${rate(s.repeatCustomerRate)}。</p></div>
      <div class="conclusion"><b>观察完整性</b><p>${esc(windowLabel)}完整观察率${rate(s.observationCompletenessRate)}。${esc(completeness)}</p></div>
    </div>`;
    const lineRows = data.lines.map(item => [
      esc(item.businessLine), integer(item.customers), integer(item.repeatCustomers), rate(item.repeatCustomerRate),
      integer(item.policies), integer(item.repeatPolicies), number(item.qjPremiumWan),
      number(item.repeatQjPremiumWan), rate(item.repeatPremiumShare)
    ]);
    const productRows = data.products.map(item => [
      esc(item.product), esc(item.productType), integer(item.customers), integer(item.policies), number(item.qjPremiumWan),
      integer(item.firstPolicies), number(item.firstQjPremiumWan), integer(item.repeatCustomers),
      integer(item.repeatPolicies), number(item.repeatQjPremiumWan), rate(item.repeatPremiumShare)
    ]);
    return panel('新客经营结论', `首现期间决定新客范围；${windowLabel}决定后续购买观察范围。`, conclusion) +
      `<div class="grid-2">${panel('再次承保节奏', 'M0为首现月；再次承保保单和期交均不含系统首张保单。', '<div class="chart" id="cohortRepeatChart"></div>')}${panel('首现月份表现', '比较各首现月份的新客规模、可追踪人数和再次承保人数。', '<div class="chart" id="cohortMonthChart"></div>')}</div>` +
      `<div class="grid-2">${panel('产品贡献', '展示观察窗口内期交贡献前十产品，并区分再次承保贡献。', '<div class="chart" id="cohortProductChart"></div>')}${panel('分业务表现', '客户跨业务购买时，各业务客户数不可直接相加。', table(['业务','新客','再次承保客户','再次承保率','保单','再次承保保单','期交(万)','再次承保期交(万)','再次承保期交占比'], lineRows, [1,2,3,4,5,6,7,8]))}</div>` +
      panel('新客购买产品', '产品、保费和再次承保均限定为OTO、证保、蚁桥可追踪业绩；按观察期交从高到低排列。', table(['产品','产品类型','新客','保单','期交(万)','首张保单','首张期交(万)','再次承保客户','再次承保保单','再次承保期交(万)','再次承保期交占比'], productRows, [2,3,4,5,6,7,8,9,10]));
  }

  function renderHolding() {
    const h = state.data.holdings;
    const s = h.summary;
    const summary = `<div class="quality-grid">
      <div class="quality-item">一客多单客户<strong>${integer(s.multiPolicyCustomers)}</strong><span class="meta">占已关联客户 ${rate(s.multiPolicyRate)}</span></div>
      <div class="quality-item">人均已知保单<strong>${number(s.averagePolicies, 2)}</strong><span class="meta">共${integer(s.knownPolicies)}份</span></div>
      <div class="quality-item">目前有有效保单<strong>${integer(s.customersWithActivePolicy)}</strong><span class="meta">占已关联客户 ${rate(s.activeCustomerRate)}</span></div>
      <div class="quality-item">首次复购间隔中位数<strong>${s.firstRepeatMedianDays == null ? '--' : number(s.firstRepeatMedianDays, 0) + '天'}</strong><span class="meta">180天内 ${rate(s.firstRepeatWithin180Rate)}</span></div>
    </div>`;
    const notes = table(
      ['观察项','结果','说明'],
      [
        ['已关联客户', integer(s.coveredCustomers), '持单分析的客户范围'],
        ['当前0件有效保单', integer(s.zeroActiveCustomers), '客户清单截止日无有效状态保单'],
        ['人均当前有效保单', number(s.averageActivePolicies, 2), '有效保单数 ÷ 已关联客户数'],
        ['首次复购间隔可计算客户', integer(s.firstRepeatEligibleCustomers), '至少2张保单且承保日期完整']
      ],
      [1]
    );
    return panel('持单情况', '所选期间产生业绩的客户，其在客户清单中的全部已知保单。', summary) +
      `<div class="grid-2">${panel('客户持单数', '按客户全部已知保单数分档。', '<div class="chart compact" id="policyCountChart"></div>')}${panel('客户当前有效保单数', '按客户清单截止日状态分档；0件有效需要单独关注。', '<div class="chart compact" id="activeCountChart"></div>')}</div>` +
      `<div class="grid-2">${panel('首次复购间隔', '按第一张到第二张保单的承保日期间隔统计。', '<div class="chart compact" id="repeatIntervalChart"></div>')}${panel('指标说明', '持单和有效状态分开观察。', notes)}</div>`;
  }

  function renderPolicy() {
    const cohortRows = state.data.cohorts.map(item => [
      integer(item.year), integer(item.total), integer(item.status.active || 0), rate(item.activeRate),
      integer(item.status.surrender || 0), rate(item.surrenderRate), integer(item.status.cooling_off || 0),
      integer((item.status.maturity || 0) + (item.status.short_expiry || 0)), integer(item.status.suspended || 0)
    ]);
    const reasonRows = state.data.terminationReasons.map(item => [esc(item.reason), integer(item.policies)]);
    return `<div class="grid-2">${panel('保单状态分布', '退保、契撤、到期满期、短险逾期和理赔分别统计。', '<div class="chart" id="policyStatusChart"></div>')}${panel('终止原因', '仅展示源清单中的真实终止原因。', '<div class="chart" id="reasonChart"></div>')}</div>` +
      panel('承保年度保单当前状态', '用于观察各承保年度保单截至数据截止日的状态；不替代继续率。', table(['承保年度','保单数','当前有效','有效率','退保终止','退保率','犹豫期撤保','到期/短险逾期','停效'], cohortRows, [0,1,2,3,4,5,6,7,8])) +
      panel('终止原因明细', '按所选期间业绩保单去重统计。', table(['终止原因','保单数'], reasonRows, [1]));
  }

  function renderQuality() {
    const q = state.data.quality;
    const definitions = Object.entries(q.definitions).map(([key, value]) => `<div><b>${esc({ newCustomer:'新客', existingCustomer:'老客', systemCoverage:'系统覆盖范围', policyStatus:'保单状态', surrender:'退保', holdingScope:'持单范围', firstRepeatInterval:'首次复购间隔' }[key] || key)}</b><br><span class="meta">${esc(value)}</span></div>`).join('');
    const stats = `<div class="quality-grid">
      <div class="quality-item">历史业绩明细<strong>${integer(q.performanceRows)}</strong></div>
      <div class="quality-item">客户源记录<strong>${integer(q.customerSourceRows)}</strong></div>
      <div class="quality-item">保单快照<strong>${integer(q.customerPolicyRows)}</strong></div>
      <div class="quality-item">源文本异常记录<strong>${integer(q.sourceTextIssueRows)}</strong></div>
    </div>`;
    return panel('数据覆盖', '早期人员工号中的替换字符来自源CSV，系统保留原值并记录异常数量，不推断缺失字符。', stats) +
      panel('统计口径', '缺少客户关联的业绩单独保留，不归入新客或老客。', `<div class="definition">${definitions}</div>`);
  }

  function drawCharts() {
    if (state.tab === 'cohort' && state.cohortData) {
      const data = state.cohortData;
      const timeline = data.timeline;
      const tooltip = { trigger:'axis', backgroundColor:'#fff', borderColor:'#dfe5eb', textStyle:{ color:chartText } };
      initChart('cohortRepeatChart', {
        tooltip, legend:{ data:['再次承保保单','再次承保期交'],textStyle:{ color:chartMuted } },
        grid:{ left:60,right:65,top:50,bottom:45 },
        xAxis:{ type:'category',data:timeline.map(x => x.monthIndex === 0 ? 'M0' : `M${x.monthIndex}`),...axisBase() },
        yAxis:[{ type:'value',name:'保单',...axisBase() },{ type:'value',name:'万元',...axisBase() }],
        series:[
          { name:'再次承保保单',type:'bar',data:timeline.map(x => x.repeatPolicies),itemStyle:{ color:colors.new } },
          { name:'再次承保期交',type:'line',yAxisIndex:1,smooth:true,data:timeline.map(x => x.repeatQjPremiumWan),itemStyle:{ color:colors.existing } }
        ]
      });
      const cohortMonths = data.cohortMonths;
      initChart('cohortMonthChart', {
        tooltip, legend:{ data:['可追踪新客','再次承保客户'],textStyle:{ color:chartMuted } },
        grid:{ left:60,right:20,top:50,bottom:45 },
        xAxis:{ type:'category',data:cohortMonths.map(x => x.firstAppearanceMonth.slice(5) + '月'),...axisBase() },
        yAxis:{ type:'value',name:'人',...axisBase() },
        series:[
          { name:'可追踪新客',type:'bar',data:cohortMonths.map(x => x.trackedCustomers),itemStyle:{ color:'#89b8ef' } },
          { name:'再次承保客户',type:'bar',data:cohortMonths.map(x => x.repeatCustomers),itemStyle:{ color:colors.existing } }
        ]
      });
      const products = data.products.slice(0, 10).reverse();
      initChart('cohortProductChart', {
        tooltip:{ trigger:'axis',axisPointer:{ type:'shadow' } },
        legend:{ data:['首张期交','再次承保期交'],textStyle:{ color:chartMuted } },
        grid:{ left:165,right:30,top:45,bottom:25 },
        xAxis:{ type:'value',name:'万元',...axisBase() },
        yAxis:{ type:'category',data:products.map(x => x.product),axisLabel:{ color:chartMuted,width:145,overflow:'truncate' },axisLine:{ lineStyle:{ color:'#c8d1da' } } },
        series:[
          { name:'首张期交',type:'bar',stack:'premium',data:products.map(x => x.firstQjPremiumWan),itemStyle:{ color:'#89b8ef' } },
          { name:'再次承保期交',type:'bar',stack:'premium',data:products.map(x => x.repeatQjPremiumWan),itemStyle:{ color:colors.existing } }
        ]
      });
      return;
    }
    const monthly = state.data.monthly;
    const labels = monthly.map(item => item.period.slice(5) + '月');
    const tooltip = { trigger:'axis', backgroundColor:'#fff', borderColor:'#dfe5eb', textStyle:{ color:chartText } };
    initChart('premiumTrend', { tooltip, legend:{ data:['新客期交','老客期交'], textStyle:{ color:chartMuted } }, grid:{ left:60,right:20,top:50,bottom:35 }, xAxis:{ type:'category',data:labels,...axisBase() }, yAxis:{ type:'value',name:'万元',...axisBase() }, series:[
      { name:'新客期交',type:'bar',stack:'total',data:monthly.map(x => x.new?.qjPremiumWan || 0),itemStyle:{ color:colors.new } },
      { name:'老客期交',type:'bar',stack:'total',data:monthly.map(x => x.existing?.qjPremiumWan || 0),itemStyle:{ color:colors.existing } }
    ]});
    const statuses = state.data.statusDistribution;
    const statusOption = { tooltip:{ trigger:'axis',axisPointer:{ type:'shadow' } }, grid:{ left:85,right:40,top:15,bottom:30 }, xAxis:{ type:'value',...axisBase() }, yAxis:{ type:'category',data:statuses.map(x => x.label),axisLabel:{ color:chartMuted },axisLine:{ lineStyle:{ color:'#c8d1da' } } }, series:[{ type:'bar',data:statuses.map(x => x.policies),itemStyle:{ color:params => params.name === '退保' ? colors.surrender : params.name === '有效' ? colors.active : '#7aa6d8' },label:{ show:true,position:'right',color:chartText } }] };
    initChart('statusChart', statusOption);
    initChart('policyStatusChart', statusOption);
    const holdings = state.data.holdings;
    const holdingChart = (id, rows, color) => initChart(id, { tooltip:{ trigger:'axis' }, grid:{ left:55,right:20,top:15,bottom:45 }, xAxis:{ type:'category',data:rows.map(x => x.band),axisLabel:{ color:chartMuted,interval:0 },axisLine:{ lineStyle:{ color:'#c8d1da' } } }, yAxis:{ type:'value',...axisBase() }, series:[{ type:'bar',data:rows.map(x => x.customers),itemStyle:{ color },label:{ show:true,position:'top',color:chartText } }] });
    holdingChart('policyCountChart', holdings.policyCountBands, '#2f80ed');
    holdingChart('activeCountChart', holdings.activePolicyCountBands, '#138a63');
    holdingChart('repeatIntervalChart', holdings.firstRepeatIntervalBands, '#8b5cf6');
    initChart('customerTrend', { tooltip, legend:{ data:['新客客户','老客客户'],textStyle:{ color:chartMuted } }, grid:{ left:60,right:20,top:50,bottom:35 }, xAxis:{ type:'category',data:labels,...axisBase() }, yAxis:{ type:'value',name:'人',...axisBase() }, series:[
      { name:'新客客户',type:'line',smooth:true,data:monthly.map(x => x.new?.customers || 0),itemStyle:{ color:colors.new } },
      { name:'老客客户',type:'line',smooth:true,data:monthly.map(x => x.existing?.customers || 0),itemStyle:{ color:colors.existing } }
    ]});
    const reasons = state.data.terminationReasons.slice(0, 10).reverse();
    initChart('reasonChart', { tooltip:{ trigger:'axis',axisPointer:{ type:'shadow' } }, grid:{ left:150,right:40,top:15,bottom:30 }, xAxis:{ type:'value',...axisBase() }, yAxis:{ type:'category',data:reasons.map(x => x.reason),axisLabel:{ color:chartMuted },axisLine:{ lineStyle:{ color:'#c8d1da' } } }, series:[{ type:'bar',data:reasons.map(x => x.policies),itemStyle:{ color:'#d07a61' },label:{ show:true,position:'right',color:chartText } }] });
  }

  function render() {
    clearCharts();
    renderKpis();
    const renderer = { overview: renderOverview, customer: renderCustomer, cohort: renderCohort, holding: renderHolding, policy: renderPolicy, quality: renderQuality }[state.tab];
    el('content').innerHTML = renderer();
    drawCharts();
  }

  function syncOptions(meta) {
    el('yearInput').innerHTML = meta.availableYears.slice().reverse().map(value => `<option value="${value}" ${value === meta.year ? 'selected' : ''}>${value}</option>`).join('');
    const currentOrg = el('orgInput').value;
    el('orgInput').innerHTML = '<option value="">全部机构</option>' + meta.organizations.map(value => `<option value="${esc(value)}" ${value === currentOrg ? 'selected' : ''}>${esc(value)}</option>`).join('');
    el('periodType').value = meta.periodType;
    rebuildPeriodOptions(meta.periodValue);
  }

  function analysisQuery() {
    const query = new URLSearchParams({ year: el('yearInput').value, periodType: el('periodType').value, policyScope: el('policyScope').value });
    if (el('periodType').value !== 'year') query.set('periodValue', el('periodValue').value);
    if (el('businessLine').value) query.set('businessLine', el('businessLine').value);
    if (el('orgInput').value) query.set('org', el('orgInput').value);
    return query;
  }

  function setOverviewContext() {
    const meta = state.data.meta;
    el('sourceLine').textContent = `${meta.periodLabel} · ${meta.periodStart} 至 ${meta.periodEnd} · 客户状态截止 ${String(meta.sourceCutoff).slice(0, 10)} · 导入批次 ${meta.batchId}`;
    el('scopeNotice').textContent = `新客为系统最早承保日期落在所选期间的客户；老客为期间开始前已有承保记录的客户。保单状态截至${String(meta.sourceCutoff).slice(0, 10)}，不作为13个月或25个月继续率。`;
  }

  function syncCohortOptions(meta) {
    const selected = meta.product === '全部' ? '' : meta.product;
    const options = meta.availableProducts.slice();
    if (selected && !options.includes(selected)) options.unshift(selected);
    el('productInput').innerHTML = '<option value="">全部产品</option>' + options.map(value => `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(value)}</option>`).join('');
    el('observationWindow').value = meta.observationWindow;
  }

  async function loadOverview() {
    const query = analysisQuery();
    el('sourceLine').textContent = '正在读取生产数据…';
    const payload = await window.fetchJson(`/api/customer-analysis/overview?${query}`);
    state.data = window.unwrapApiResponse(payload);
    syncOptions(state.data.meta);
    setOverviewContext();
    render();
  }

  async function loadCohort() {
    const query = analysisQuery();
    query.set('observationWindow', el('observationWindow').value);
    if (el('productInput').value) query.set('product', el('productInput').value);
    state.cohortData = null;
    el('sourceLine').textContent = '正在读取新客经营数据…';
    render();
    const payload = await window.fetchJson(`/api/customer-analysis/new-customer-cohort?${query}`);
    state.cohortData = window.unwrapApiResponse(payload);
    syncCohortOptions(state.cohortData.meta);
    const meta = state.cohortData.meta;
    el('sourceLine').textContent = `${meta.periodLabel}新客 · ${windowLabels[meta.observationWindow]} · 数据截止 ${String(meta.sourceCutoff).slice(0, 10)} · 导入批次 ${meta.batchId}`;
    el('scopeNotice').textContent = '新客身份按系统最早承保日期确定；产品、保费和再次承保只统计OTO、证保、蚁桥可追踪业绩。业务、机构、长险和产品筛选作用于观察窗口内的业绩保单。';
    render();
  }

  function showError(error) {
    clearCharts();
    el('sourceLine').textContent = '读取失败';
    el('content').innerHTML = `<div class="panel empty">${esc(error.message)}</div>`;
  }

  function bind() {
    el('backBtn').addEventListener('click', () => { window.location.href = '/'; });
    el('refreshBtn').addEventListener('click', () => (state.tab === 'cohort' ? loadCohort() : loadOverview()).catch(showError));
    el('periodType').addEventListener('change', () => rebuildPeriodOptions());
    el('tabs').addEventListener('click', event => {
      const button = event.target.closest('[data-tab]');
      if (!button) return;
      state.tab = button.dataset.tab;
      document.querySelectorAll('.tab').forEach(item => { const selected = item === button; item.classList.toggle('active', selected); item.setAttribute('aria-selected', String(selected)); });
      document.querySelectorAll('.cohort-only').forEach(item => item.classList.toggle('hidden', state.tab !== 'cohort'));
      if (state.tab === 'cohort') {
        loadCohort().catch(showError);
      } else {
        setOverviewContext();
        render();
      }
    });
    window.addEventListener('resize', () => state.charts.forEach(chart => chart.resize()));
  }

  async function init() {
    if (!requireAccess()) return;
    bind();
    rebuildPeriodOptions();
    try { await loadOverview(); } catch (error) { showError(error); }
  }
  init();
})();
