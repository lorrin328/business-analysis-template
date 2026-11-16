(function () {
  const state = {
    data: null, tab: 'overview', charts: {},
    regular: { search: '', org: '', broker: '', grade: '', status: '', tier: '', sort: 'premiumWan', asc: false },
    followup: { org: '', broker: '' }
  };
  let loadSequence = 0;
  const el = id => document.getElementById(id);
  const user = () => window.getCurrentUser?.() || null;
  const can = key => user()?.role === 'admin' || user()?.permissions?.[key] === true;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
  const number = (value, digits = 2) => value == null ? '—' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const integer = value => number(value, 0);
  const rate = value => value == null ? '—' : `${(Number(value) * 100).toFixed(1)}%`;
  const change = value => value == null ? '—' : `${value > 1 ? '+' : ''}${rate(value - 1)}`;
  const changeClass = value => value == null || value === 1 ? '' : value > 1 ? 'up' : 'down';

  function rebuildPeriodOptions(preferredValue) {
    const type = el('periodType').value;
    const label = el('periodValueLabel');
    label.classList.toggle('hidden', type === 'year');
    if (type === 'year') {
      el('periodValue').innerHTML = '';
      return;
    }
    const cutoff = el('asOfInput').value;
    const month = cutoff ? Number(cutoff.slice(5, 7)) : new Date().getMonth() + 1;
    const selected = Number(preferredValue || (type === 'quarter' ? Math.ceil(month / 3) : month));
    el('periodValueCaption').textContent = type === 'quarter' ? '季度' : '月份';
    el('periodValue').innerHTML = Array.from({ length: type === 'quarter' ? 4 : 12 }, (_, index) => {
      const value = index + 1;
      const text = type === 'quarter' ? `Q${value}` : `${value}月`;
      return `<option value="${value}" ${value === selected ? 'selected' : ''}>${text}</option>`;
    }).join('');
  }

  function requireAccess() {
    if (!window.getAuthToken?.() || !user()) {
      window.location.href = '/';
      return false;
    }
    el('currentUser').textContent = `${user().username} · ${user().roleLabel || user().role}`;
    if (!can('branch_analysis')) {
      el('accessDenied').classList.remove('hidden');
      return false;
    }
    el('pageMain').classList.remove('hidden');
    return true;
  }

  function panel(title, subtitle, body) {
    return `<section class="panel"><div class="panel-head"><div><h2>${esc(title)}</h2>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div></div><div class="panel-body">${body}</div></section>`;
  }

  function table(headers, rows, numeric = []) {
    if (!rows.length) return '<div class="empty">暂无数据</div>';
    return `<div class="table-wrap"><table><thead><tr>${headers.map((item, index) =>
      `<th class="${numeric.includes(index) ? 'num' : ''}">${item}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(row => `<tr>${row.map((item, index) =>
        `<td class="${numeric.includes(index) ? 'num' : ''}">${item}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function statusBadge(status) {
    const cls = { '持续经营': 'live', '新增/恢复': 'new', '待唤醒': 'lost', '未活动': 'off' }[status] || 'off';
    return `<span class="badge ${cls}">${esc(status)}</span>`;
  }

  function chart(id, option) {
    const node = el(id);
    if (!node || !window.echarts) return;
    const instance = window.echarts.init(node);
    state.charts[id] = instance;
    instance.setOption(option);
  }

  function clearCharts() {
    Object.values(state.charts).forEach(instance => instance.dispose());
    state.charts = {};
  }
  window.addEventListener('resize', () => Object.values(state.charts).forEach(instance => instance.resize()));

  function renderKpis() {
    const s = state.data.summary;
    const emphasis = s.largeShare >= 0.5 ? 'warn' : '';
    const cards = [
      ['证保净期交', `${number(s.premiumWan)}万`, `同比 ${change(s.premiumChange)} · ${integer(s.policies)}件`, changeClass(s.premiumChange)],
      ['常规网点活动率', rate(s.regularActivityRate), `${integer(s.activeRegular)}个出单 / ${integer(s.regularStock)}个常规网点`, ''],
      ['常规期交', `${number(s.regularPlatformWan)}万`, `净负冲正 ${number(s.netNegativePremiumWan)}万`, ''],
      ['超大单占比', rate(s.largeShare), `${number(s.largePremiumWan)}万 · ${integer(s.largePolicies)}件`, emphasis],
      ['本期及上年同期均出单', `${integer(s.continuedRegular)}个`, '按常规网点统计', ''],
      ['10年及以上交期占比', rate(s.longTerm10yShare), `已知交期覆盖 ${rate(s.termCoverage)}`, '']
    ];
    el('kpiGrid').innerHTML = cards.map(([label, value, meta, cls]) => `<article class="kpi">
      <div class="kpi-label">${label}</div><div class="kpi-value ${cls}">${value}</div><div class="kpi-meta">${meta}</div>
    </article>`).join('');
    el('scopeNotice').textContent = `常规网点 ${integer(s.regularStock)} 个纳入活动率统计，转介绍网点 ${integer(s.referralStockExcluded)} 个单列。`;
  }

  function renderOverview() {
    const data = state.data;
    const brokerRows = data.brokers.map(b => [
      esc(b.broker), integer(b.stock), integer(b.active), rate(b.activityRate),
      number(b.premiumWan), number(b.regularPremiumWan), rate(b.largeShare), integer(b.policies), integer(b.sellers)
    ]);
    const levelRows = data.levels.map(item => [
      esc(item.label), integer(item.stock), integer(item.active), rate(item.activityRate), number(item.premiumWan)
    ]);
    const projectRows = data.projects.map(item => [
      esc(item.label), integer(item.stock), integer(item.active), rate(item.activityRate), number(item.premiumWan)
    ]);
    const loc = data.insights.localityComparison;
    const followups = `<div class="callouts">
      <div class="callout"><b>同期出单、本期未出单</b><p>${integer(data.insights.dormantAlerts.length)} 个网点</p></div>
      <div class="callout"><b>超大单贡献集中</b><p>${integer(data.insights.largeRelianceAlerts.length)} 个网点</p></div>
      <div class="callout"><b>名称待匹配</b><p>${integer(data.quality.unmatchedBranches.length)} 项明细</p></div>
    </div><div class="toolbar followup-link"><button class="button primary" data-open-tab="followup">查看督导清单</button></div>`;
    const localityRows = Object.entries({ local: '本地', remote: '异地' }).map(([key, label]) => [
      label, integer(loc[key].stock), integer(loc[key].active), rate(loc[key].activityRate),
      number(loc[key].premiumWan), number(loc[key].avgBranchPremiumWan)
    ]);
    return panel('机构督导', '', followups) +
      `<div class="grid-2">
        ${panel('月度保费构成与出单网点', '月度按当月投保单号去重。折线仅统计常规网点。', '<div id="trendChart" class="chart-box"></div>')}
        ${panel('头部网点贡献', `前${integer(data.pareto.pareto20PercentCount)}个网点累计占比 ${rate(data.pareto.pareto20PercentShare)}。按净期交为正的常规网点计算。`,
          data.pareto.series.length ? '<div id="paretoChart" class="chart-box"></div>' : '<div class="empty">常规网点暂无正净期交</div>')}
      </div>
      ${panel('券商主体表现', '按常规网点名单归属汇总。', table(
        ['券商主体', '常规网点', '出单网点', '活动率', '净期交（万）', '常规期交（万）', '超大单占比', '件数', '券商人员'],
        brokerRows, [1, 2, 3, 4, 5, 6, 7, 8]))}
      <div class="grid-2">
        ${panel('网点参数等级', '等级取自参考表。', table(
          ['等级', '常规网点', '出单网点', '活动率', '净期交（万）'], levelRows, [1, 2, 3, 4]))}
        ${panel('本地及异地表现', '按参考表本地或异地标签统计。', table(
          ['归属', '常规网点', '出单网点', '活动率', '净期交（万）', '网均净期交（万）'], localityRows, [1, 2, 3, 4, 5]))}
      </div>
      ${panel('机构类项目表现', '按参考表的机构类项目汇总常规网点。', table(
        ['项目', '常规网点', '出单网点', '活动率', '净期交（万）'], projectRows, [1, 2, 3, 4]))}`;
  }

  function initOverviewCharts() {
    const trend = state.data.monthlyTrend;
    const breakdown = [
      ['常规期交', 'regularWan', '#2f80ed'],
      ['超大单', 'largeWan', '#d49119'],
      ['无单号正额', 'unclassifiedPositiveWan', '#8696ad'],
      ['净负冲正', 'netNegativeWan', '#c33b32']
    ].filter(([, key], index) => index < 2 || trend.some(item => item[key] !== 0));
    chart('trendChart', {
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 64, right: 55, top: 32, bottom: 65 },
      xAxis: { type: 'category', data: trend.map(item => item.month), axisLabel: { hideOverlap: true } },
      yAxis: [{ type: 'value', name: '保费（万元）' }, { type: 'value', name: '出单网点（个）', minInterval: 1 }],
      series: [
        ...breakdown.map(([name, key, color]) => ({
          name, type: 'bar', stack: 'premium', data: trend.map(item => item[key]), itemStyle: { color }, barMaxWidth: 32
        })),
        { name: '净期交', type: 'line', data: trend.map(item => item.totalWan), itemStyle: { color: '#18385f' } },
        { name: '常规出单网点', type: 'line', yAxisIndex: 1, data: trend.map(item => item.activeBranches), itemStyle: { color: '#138a63' } }
      ]
    });
    const pareto = state.data.pareto.series;
    if (pareto.length) {
      chart('paretoChart', {
        tooltip: { trigger: 'axis', formatter: params => {
          const item = pareto[params[0].dataIndex];
          return `${esc(item.branch)}<br>净期交 ${number(item.premiumWan)}万<br>累计占比 ${rate(item.cumShare)}`;
        } },
        legend: { bottom: 0 },
        grid: { left: 60, right: 60, top: 32, bottom: 60 },
        xAxis: { type: 'category', data: pareto.map(item => `第${item.rank}名`), axisLabel: { hideOverlap: true } },
        yAxis: [
          { type: 'value', name: '净期交（万元）' },
          { type: 'value', name: '累计占比', max: 1, axisLabel: { formatter: rate }, splitLine: { show: false } }
        ],
        series: [
          { name: '网点净期交', type: 'bar', data: pareto.map(item => item.premiumWan), itemStyle: { color: '#18385f' } },
          { name: '累计占比', type: 'line', yAxisIndex: 1, data: pareto.map(item => item.cumShare), itemStyle: { color: '#c33b32' } }
        ]
      });
    }
  }

  function renderMatrix() {
    const data = state.data;
    const tierRows = data.tiers.map(item => [
      esc(item.label), integer(item.count), rate(item.countRate), number(item.premiumWan)
    ]);
    const tierPanel = panel('网点净期交分档', `${data.meta.periodLabel} · ${data.meta.periodStart} 至 ${data.meta.asOf}`,
      table(['净期交区间', '网点数', '数量占比', '净期交（万）'], tierRows, [1, 2, 3]));
    const window = data.meta.matrixWindow;
    if (!window) {
      const rows = data.regularBranches.filter(item => item.policies > 0).sort((a, b) => b.activeDays - a.activeDays || b.premiumWan - a.premiumWan);
      return panel('当月出单网点', `${data.meta.periodStart} 至 ${data.meta.asOf}，共 ${integer(rows.length)} 个常规网点出单。`,
        table(['证券网点', '券商', '出单天数', '件数', '净期交（万）'], rows.map(item => [
          esc(item.branch), esc(item.parent), integer(item.activeDays), integer(item.policies), number(item.premiumWan)
        ]), [2, 3, 4])) + tierPanel;
    }
    const dates = `${window.start} 至 ${window.end}`;
    if (!window.available) {
      return panel('近三个月网点矩阵', dates, '<div class="empty">基表尚未覆盖三个完整自然月</div>') + tierPanel;
    }
    return panel('近三个月网点矩阵',
      `${dates} · 观察分界为净期交${window.premiumThresholdWan}万元、${window.activeMonthsThreshold}个出单月。横轴为出单月数，纵轴为净期交。`,
      '<div id="quadrantChart" class="chart-box-lg"></div>') + tierPanel;
  }

  function initMatrixChart() {
    const window = state.data.meta.matrixWindow;
    if (!window?.available || !state.data.quadrant.length) return;
    const points = state.data.quadrant;
    const colors = { I: '#138a63', II: '#c77816', III: '#2f80ed', IV: '#8c98a5' };
    chart('quadrantChart', {
      tooltip: { trigger: 'item', formatter: params => {
        const point = points[params.dataIndex];
        return `<b>${esc(point.branch)}</b><br>${esc(point.parent)}<br>${esc(point.quadrantLabel)}<br>净期交 ${number(point.premiumWan)}万<br>出单 ${integer(point.activeMonths)}个月 · ${integer(point.policies)}件`;
      } },
      grid: { left: 65, right: 35, top: 35, bottom: 50 },
      xAxis: { type: 'value', name: '出单月数', nameLocation: 'middle', nameGap: 26, min: 0, max: 3,
        interval: 1, axisLabel: { formatter: value => Number.isInteger(value) ? value : '' },
        splitLine: { show: false } },
      yAxis: { type: 'value', name: '净期交（万元）', max: value => Math.max(value.max, window.premiumThresholdWan * 1.1) },
      series: [{
        type: 'scatter', clip: false,
        symbolSize: value => Math.max(8, Math.min(44, Math.sqrt(value[2]) * 7)),
        data: points.map(point => ({
          value: [point.activeMonths, point.premiumWan, point.policies],
          itemStyle: { color: colors[point.quadrant] }
        })),
        markLine: {
          silent: true, lineStyle: { color: '#8797a9', type: 'dashed' },
          data: [{ xAxis: window.activeMonthsThreshold }, { yAxis: window.premiumThresholdWan }]
        }
      }]
    });
  }

  function options(values, chosen) {
    return values.map(([value, label]) => `<option value="${esc(value)}" ${String(value) === chosen ? 'selected' : ''}>${esc(label)}</option>`).join('');
  }

  function selectFilter(key, label, values, chosen) {
    return `<label>${esc(label)}<select data-field="${key}">${options([['', '全部'], ...values], chosen)}</select></label>`;
  }

  function choices(values) {
    return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN')).map(value => [value, value]);
  }

  const regularColumns = [
    ['periodStatus', '状态', item => statusBadge(item.status)],
    ['grade', '参考等级', item => esc(item.grade || '—')],
    ['tier', '净期交区间', item => esc(item.tierName)],
    ['parent', '券商主体', item => esc(item.parent || '—')],
    ['project', '机构类项目', item => esc(item.project || '—')],
    ['org', '太平机构', item => esc(item.org || item.previousOrg || '—')],
    ['branch', '证券网点', item => esc(item.branch)],
    ['city', '城市', item => esc(item.city || '—')],
    ['premiumWan', '净期交（万）', item => number(item.premiumWan), true],
    ['regularPremiumWan', '常规期交（万）', item => number(item.regularPremiumWan), true],
    ['largePremiumWan', '超大单（万）', item => number(item.largePremiumWan), true],
    ['netNegativePremiumWan', '净负冲正（万）', item => number(item.netNegativePremiumWan), true],
    ['premiumChange', '同比', item => `<span class="${changeClass(item.premiumChange)}">${change(item.premiumChange)}</span>`, true],
    ['policies', '件数', item => integer(item.policies), true],
    ['averageCaseWan', '件均（万）', item => number(item.averageCaseWan), true],
    ['longTerm10yShare', '10年及以上交期占比', item => `<span title="已知交期覆盖 ${rate(item.termCoverage)}">${rate(item.longTerm10yShare)}</span>`, true],
    ['externalSellers', '券商人员', item => integer(item.externalSellers), true],
    ['internalAgents', '太平人员', item => integer(item.internalAgents), true],
    ['activeDays', '出单天数', item => integer(item.activeDays), true],
    ['activeMonths', '出单月数', item => integer(item.activeMonths), true]
  ];

  function renderRegular() {
    const items = state.data.regularBranches;
    const filter = state.regular;
    const toolbar = `<div class="toolbar" id="regularFilters">
      <label>搜索网点<input aria-label="搜索网点" data-field="search" id="branchSearch" value="${esc(filter.search)}" placeholder="网点、机构、券商、项目或城市"></label>
      ${selectFilter('org', '太平机构', choices(items.flatMap(item => item.orgs)), filter.org)}
      ${selectFilter('broker', '券商主体', choices(items.map(item => item.parent)), filter.broker)}
      ${selectFilter('grade', '参考等级', choices(items.map(item => item.grade)), filter.grade)}
      ${selectFilter('status', '状态', choices(['持续经营', '新增/恢复', '待唤醒', '未活动']), filter.status)}
      ${selectFilter('tier', '净期交区间', state.data.tiers.map(item => [item.tierId, item.label]), filter.tier)}
      <span class="meta filter-count" id="regularCount"></span>
    </div>`;
    return toolbar + panel('常规网点明细',
      '按期内净正保单识别活动网点，券商及太平人员均按出单工号去重。',
      '<div id="regularResults"></div>');
  }

  function renderRegularResults() {
    const f = state.regular;
    const search = f.search.trim().toLowerCase();
    const items = state.data.regularBranches.filter(item =>
      (!search || [item.branch, item.parent, item.project, item.subproject, item.city, ...item.orgs].join(' ').toLowerCase().includes(search)) &&
      (!f.org || item.orgs.includes(f.org)) && (!f.broker || item.parent === f.broker) &&
      (!f.grade || item.grade === f.grade) && (!f.status || item.status === f.status) && (!f.tier || String(item.tier) === f.tier)
    );
    items.sort((a, b) => {
      const left = a[f.sort], right = b[f.sort];
      if (left == null || right == null) return Number(left == null) - Number(right == null);
      return (left - right) * (f.asc ? 1 : -1);
    });
    el('regularCount').textContent = `显示 ${integer(items.length)} / ${integer(state.data.summary.regularStock)} 个网点`;
    const headers = regularColumns.map(([key, label, , numeric]) => numeric ?
      `<button class="sort-button" data-sort-key="${key}" aria-label="按${label}排序">${label}${f.sort === key ? f.asc ? ' ↑' : ' ↓' : ''}</button>` : label);
    el('regularResults').innerHTML = table(headers, items.map(item => regularColumns.map(([, , format]) => format(item))),
      regularColumns.flatMap(([, , , numeric], index) => numeric ? [index] : []));
  }

  function followupItems(items, orgs, brokerOf) {
    const f = state.followup;
    return items.filter(item => (!f.org || orgs(item).includes(f.org)) && (!f.broker || brokerOf(item) === f.broker));
  }

  function renderFollowup() {
    const { data, followup } = state;
    const dormant = data.insights.dormantAlerts;
    const reliance = data.insights.largeRelianceAlerts;
    const unmatched = data.quality.unmatchedBranches;
    const unknownBroker = '未确认券商';
    const selectOrg = choices([...dormant.flatMap(item => item.previousOrgs), ...reliance.flatMap(item => item.currentOrgs), ...unmatched.flatMap(item => item.orgs)]);
    const selectBroker = choices([...dormant, ...reliance].map(item => item.parent || unknownBroker).concat(unmatched.length ? [unknownBroker] : []));
    return `<div class="toolbar" id="followupFilters">
      ${selectFilter('org', '太平机构', selectOrg, followup.org)}
      ${selectFilter('broker', '券商主体', selectBroker, followup.broker)}
    </div><div id="followupResults"></div>`;
  }

  function renderFollowupResults() {
    const data = state.data;
    const meta = data.meta;
    const unknownBroker = '未确认券商';
    const brokerOf = item => item.parent || unknownBroker;
    const dormant = followupItems(data.insights.dormantAlerts, item => item.previousOrgs, brokerOf);
    const reliance = followupItems(data.insights.largeRelianceAlerts, item => item.currentOrgs, brokerOf);
    const unmatched = followupItems(data.quality.unmatchedBranches, item => item.orgs, () => unknownBroker);
    const current = `${meta.periodStart} 至 ${meta.asOf}`;
    const previous = `${meta.previousPeriodStart} 至 ${meta.previousAsOf}`;
    el('followupResults').innerHTML =
      panel(`同期出单、本期未出单（${dormant.length}）`, `本期 ${current}，上年同期 ${previous}。按上年同期明细机构筛选。`,
        table(['网点', '券商', '上年同期太平机构', '上年同期净期交（万）', '上年同期件数', '本期净期交（万）', '本期件数'],
          dormant.map(item => [esc(item.branch), esc(brokerOf(item)), esc(item.previousOrg || '—'),
            number(item.previousPremiumWan), integer(item.previousPolicies), number(item.premiumWan), integer(item.policies)]), [3, 4, 5, 6])) +
      panel(`超大单贡献集中（${reliance.length}）`, '观察条件为期内净期交至少50万元、超大单占可识别正净保费至少70%。',
        table(['网点', '券商', '本期太平机构', '净期交（万）', '超大单（万）', '超大单件数', '占比'],
          reliance.map(item => [esc(item.branch), esc(brokerOf(item)), esc(item.org || '—'), number(item.premiumWan),
            number(item.largePremiumWan), integer(item.largePolicies), rate(item.largeShare)]), [3, 4, 5, 6])) +
      panel(`名称待匹配（${unmatched.length}）`, '业绩明细网点名称与参考表无法精确匹配，含网点名称缺失。',
        table(['基表网点名称', '本期太平机构', '净期交（万）', '可识别件数'], unmatched.map(item =>
          [esc(item.branch), esc(item.orgs.join('、') || '—'), number(item.premiumWan), integer(item.policies)]), [2, 3]));
  }

  function renderReferral() {
    const s = state.data.summary;
    const rows = state.data.referralBranches.map(item => [
      esc(item.referenceId), esc(item.branch), esc(item.parent), esc(item.province), esc(item.city),
      esc(item.project), esc(item.subproject), esc(item.locality)
    ]);
    const note = `转介绍归属主体及可识别子网点汇总净期交 ${number(s.referralPremiumWan)} 万元，${integer(s.referralPolicies)} 件，${integer(s.referralSellers)} 名券商销售人员。其中已纳入常规网点匹配额 ${number(s.referralOverlapPremiumWan)} 万元，匹配合计只计一次。`;
    return `<div class="notice">${note}</div>` + panel(`转介绍网点名录（${integer(s.referralStockExcluded)}个）`,
      '按参考表展示网点归属，保费按业绩底表可识别的网点归属统计。', table(
        ['编号', '转介绍网点', '归属主体', '省', '市', '机构类项目', '项目细分', '本地/异地'], rows));
  }

  function renderQuality() {
    const { quality: q, summary: s, meta } = state.data;
    const batch = meta.referenceBatch || {};
    const labels = {
      regularCount: '常规网点数', referralCount: '转介绍网点数', activity: '活动网点',
      policyCount: '保单去重与缺失', referralPerformance: '转介绍业绩', dataCutoff: '数据截止日',
      regularPlatform: '净期交保费勾稽', largePolicy: '超大单', paymentTerm: '缴费年限',
      paretoConcentration: '头部网点占比', capacityTiers: '产能分档与矩阵', matching: '名称匹配与机构归属'
    };
    const definitions = Object.entries(q.definitions).map(([key, value]) => `<div><b>${esc(labels[key] || key)}</b><br><span class="meta">${esc(value)}</span></div>`).join('');
    const terms = [
      ['净期交', number(s.premiumWan, 4)], ['常规期交', number(s.regularPlatformWan, 4)],
      ['超大单', number(s.largePremiumWan, 4)], ['净负冲正', number(s.netNegativePremiumWan, 4)],
      ['无单号正额', number(s.unclassifiedPositivePremiumWan, 4)],
      ['交期未知的可识别正净额', number(s.unknownTermPositivePremiumWan, 4)],
      ['待匹配网点净期交', number(s.unmatchedPremiumWan, 4)]
    ];
    return `<div class="grid-2">
      ${panel('统计口径', '', `<div class="definition">${definitions}</div>`)}
      <div>${panel('保费与数据质量', `缺单号明细 ${integer(q.missingPolicyRows)} 行。名称匹配率 ${rate(s.matchedPremiumRate)}。`, table(['项目', '万元'], terms, [1]))}
        ${panel('参考表批次', '', table(['批次', '文件', '常规网点', '转介绍网点'],
          [[integer(batch.id), esc(batch.fileName || '—'), integer(q.regularRows), integer(q.referralRows)]], [0, 2, 3]))}</div>
    </div>`;
  }

  function render() {
    if (!state.data) return;
    clearCharts();
    renderKpis();
    const renderers = { overview: renderOverview, matrix: renderMatrix, followup: renderFollowup, regular: renderRegular, referral: renderReferral, quality: renderQuality };
    el('content').innerHTML = renderers[state.tab]();
    if (state.tab === 'overview') initOverviewCharts();
    if (state.tab === 'matrix') initMatrixChart();
    if (state.tab === 'regular') renderRegularResults();
    if (state.tab === 'followup') renderFollowupResults();
  }

  async function load() {
    const sequence = ++loadSequence;
    const year = el('yearInput').value;
    const asOf = el('asOfInput').value;
    const periodType = el('periodType').value;
    const periodValue = el('periodValue').value;
    const query = new URLSearchParams();
    if (year) query.set('year', year);
    if (asOf) query.set('asOf', asOf);
    query.set('periodType', periodType);
    if (periodType !== 'year' && periodValue) query.set('periodValue', periodValue);
    clearCharts();
    state.data = null;
    el('kpiGrid').innerHTML = '';
    el('scopeNotice').textContent = '';
    el('content').innerHTML = '<div class="panel empty">正在读取当前筛选范围…</div>';
    el('sourceLine').textContent = '正在读取数据…';
    try {
      const payload = await window.fetchJson(`/api/branch-analysis/overview?${query}`);
      if (sequence !== loadSequence) return;
      state.data = window.unwrapApiResponse(payload);
      const meta = state.data.meta;
      const periodChanged = state.periodKey !== query.toString();
      if (periodChanged) {
        state.followup = { org: '', broker: '' };
        Object.assign(state.regular, { org: '', broker: '', grade: '', status: '', tier: '' });
      }
      state.periodKey = query.toString();
      el('yearInput').value = meta.year;
      if (!el('asOfInput').value) el('asOfInput').value = meta.performanceCutoff;
      el('periodType').value = meta.periodType;
      rebuildPeriodOptions(meta.periodValue);
      const lastBranchDate = meta.lastBranchBusinessDate
        ? `证保末笔明细 ${meta.lastBranchBusinessDate}`
        : '本期无证保明细';
      el('sourceLine').textContent = `数据截至 ${state.data.meta.performanceCutoff} · ${meta.periodLabel} ${meta.periodStart} 至 ${meta.asOf} · ${lastBranchDate} · 同比 ${meta.previousPeriodStart} 至 ${meta.previousAsOf}`;
      el('filterState').textContent = '当前结果对应已应用筛选';
      render();
    } catch (error) {
      if (sequence !== loadSequence) return;
      state.data = null;
      el('kpiGrid').innerHTML = '';
      el('scopeNotice').textContent = '';
      el('sourceLine').textContent = '读取失败';
      el('filterState').textContent = '当前筛选读取失败';
      el('content').innerHTML = `<div class="panel empty">${esc(error.message)}</div>`;
    }
  }

  function openTab(tab) {
    state.tab = tab;
    document.querySelectorAll('#tabs [data-tab]').forEach(button => {
      const selected = button.dataset.tab === tab;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-selected', String(selected));
    });
    render();
  }

  function bind() {
    el('backBtn').addEventListener('click', () => { window.location.href = '/'; });
    el('refreshBtn').addEventListener('click', load);
    document.querySelector('.filters').addEventListener('change', () => { el('filterState').textContent = '筛选已修改，请点击应用'; });
    el('periodType').addEventListener('change', () => rebuildPeriodOptions());
    el('asOfInput').addEventListener('change', () => rebuildPeriodOptions(el('periodValue').value));
    el('yearInput').addEventListener('change', () => {
      const cutoff = el('asOfInput').value;
      const year = el('yearInput').value;
      if (cutoff && year) {
        const month = Number(cutoff.slice(5, 7));
        const day = Math.min(Number(cutoff.slice(8, 10)), new Date(Number(year), month, 0).getDate());
        el('asOfInput').value = `${year}${cutoff.slice(4, 8)}${String(day).padStart(2, '0')}`;
      }
      rebuildPeriodOptions(el('periodValue').value);
    });
    el('tabs').addEventListener('click', event => {
      const button = event.target.closest('[data-tab]');
      if (button) openTab(button.dataset.tab);
    });
    el('content').addEventListener('click', event => {
      const destination = event.target.closest('[data-open-tab]');
      if (destination) {
        openTab(destination.dataset.openTab);
        el('content').querySelector('select')?.focus();
        return;
      }
      const sort = event.target.closest('[data-sort-key]');
      if (sort) {
        const key = sort.dataset.sortKey;
        state.regular.asc = state.regular.sort === key && !state.regular.asc;
        state.regular.sort = key;
        renderRegularResults();
        el('regularResults').querySelector(`[data-sort-key="${key}"]`)?.focus();
      }
    });
    const applyFilter = event => {
      const key = event.target.dataset.field;
      if (!key || event.isComposing) return;
      if (event.target.closest('#regularFilters')) {
        state.regular[key] = event.target.value;
        renderRegularResults();
      }
      if (event.target.closest('#followupFilters')) {
        state.followup[key] = event.target.value;
        renderFollowupResults();
      }
    };
    el('content').addEventListener('input', applyFilter);
    el('content').addEventListener('compositionend', applyFilter);
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requireAccess()) return;
    rebuildPeriodOptions();
    bind();
    load();
  });
})();
