const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');
const read = name => fs.readFileSync(`js/${name}.js`, 'utf8');
function extract(source, start, end) {
  const index = source.indexOf(start);
  assert.ok(index >= 0, start);
  const finish = source.indexOf(end, index);
  assert.ok(finish > index, end);
  return source.slice(index, finish);
}
function context(code, props) {
  const ctx = vm.createContext(props);
  vm.runInContext(code, ctx);
  return ctx;
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

test('payment empty business/channel/organization choices remain explicit', () => {
  const filters = { transform: false, jingdai: false, channels: { OTO: false, '证保': false, '蚁桥': false },
    orgs: { all: false, '上海': false }, jingdaiOrgs: { A: false, B: false }, orgsInitialized: true, metric: 'qj' };
  const c = context(extract(read('payperiod-chart'), '    function buildPayPeriodQuery(', '    async function fetchPayPeriodData('), {
    URLSearchParams, payPeriodFilters: filters, ORG_LIST: ['上海'], _buildPeriodMonths: () => [],
    window: { appendDashboardRange(params) { params.set('rangeType', 'day'); params.set('endDate', '2026-05-02'); } }
  });
  const params = () => new URL('http://test' + c.buildPayPeriodQuery(2026)).searchParams;
  assert.equal(params().get('businessTypes'), '__none__');
  filters.transform = true;
  filters.jingdai = true;
  assert.equal(params().get('channels'), '__none__');
  assert.equal(params().get('orgs'), '__none__');
  assert.equal(params().get('jingdaiOrgs'), '__none__');
  assert.equal(params().get('endDate'), '2026-05-02');
});

test('payment requests keep the latest success and ignore stale success and failure', async () => {
  const pending = [], rendered = [], fallback = [];
  const data = {};
  const c = context('let payPeriodRequestSequence=0;\n' + extract(read('payperiod-chart'), '    async function fetchPayPeriodData(', '    function refreshPayPeriodChart('), {
    payPeriodData: data, unwrapApiResponse: x => x, buildPayPeriodQuery: year => String(year),
    fetchJson: () => { const d = deferred(); pending.push(d); return d.promise; },
    renderPayPeriodJingdaiOrgs() {}, renderPayPeriodChart: () => rendered.push(data.premium),
    applyPayPeriodFallback: year => fallback.push(year)
  });
  const first = c.fetchPayPeriodData(2025), second = c.fetchPayPeriodData(2026);
  pending[1].resolve({ premium: [{ name: 'latest', value: 20 }], period: { label: '2026年5月2日' }, precision: 'unavailable',
    calculable: false, sourcePrecision: { '经代': 'unavailable' }, rangeWarnings: ['经代缺少日明细'] });
  await second;
  pending[0].resolve({ premium: [{ name: 'old', value: 10 }] });
  await first;
  assert.equal(data.premium[0].name, 'latest');
  assert.equal(data.period.label, '2026年5月2日');
  assert.equal(data.precision, 'unavailable');
  assert.equal(data.calculable, false);
  assert.equal(data.sourcePrecision['经代'], 'unavailable');
  assert.equal(data.rangeWarnings[0], '经代缺少日明细');
  const third = c.fetchPayPeriodData(2025), fourth = c.fetchPayPeriodData(2026);
  pending[3].resolve({ premium: [{ name: 'newest', value: 30 }] });
  await fourth;
  pending[2].reject(Error('old failure'));
  await third;
  assert.equal(data.premium[0].name, 'newest');
  assert.deepEqual(fallback, []);
  assert.equal(rendered.length, 2);
  const last = c.fetchPayPeriodData(2026);
  pending[4].reject(Error('current failure'));
  await last;
  assert.deepEqual(fallback, [2026]);
  assert.match(data.loadError, /读取失败/);
});

test('payment scope uses the effective service range and discloses month precision', () => {
  const source = read('payperiod-chart');
  const code = extract(source, '      if (scopeNote) {', '      if (filterSummary) {');
  const scope = { textContent: '' };
  const props = {
    scopeNote: scope, payPeriodFilters: { timeDim: 'month', year: 2026 },
    _buildPeriodMonths: () => [5], MonthMultiSelect: { periodLabel: () => '2026年5月' },
    payPeriodData: { period: { label: '2026年5月2日' }, precision: 'month' },
    payload: { scope: '经代' }, countContract: { formula: '保费净额 ÷ 件数', note: '' }
  };
  context(code, props);
  assert.match(scope.textContent, /2026年5月2日/);
  assert.match(scope.textContent, /5月（取交集）/);
  assert.match(scope.textContent, /仅有月级数据/);
});

test('payment partial range prevents pie charts from presenting an incomplete total', () => {
  const data = { premium: [{ name: '已知', value: 10 }, { name: '未知', value: null }],
    count: [{ name: '已知', value: 2 }], calculable: false, countBasis: 'unavailable' };
  const c = context(extract(read('payperiod-chart'), '    function getPayPeriodPieOption(', '    function applyPayPeriodFallback('), { payPeriodData: data });
  for (const type of ['premium', 'count']) {
    const option = c.getPayPeriodPieOption(type);
    assert.equal(option.series[0].data.length, 0);
    assert.match(option.title.text, /数据不完整/);
  }
  data.calculable = true;
  assert.equal(c.getPayPeriodPieOption('premium').series[0].data.length, 0);
});

test('payment table preserves unknown amounts and suppresses shares of incomplete totals', () => {
  const wrapper = { innerHTML: '' };
  const data = { premium: [{ name: '已知', value: 10 }, { name: '未知', value: null }, { name: '真实零', value: 0 }],
    count: [{ name: '已知', value: 2 }, { name: '真实零', value: 0 }], rangeWarnings: ['经代缺少日明细'] };
  const source = read('payperiod-chart');
  const code = extract(source, '    function fmtPayPeriodAmount(', '    function payPeriodCountContract(')
    + extract(source, '    function renderPayPeriodTable(', '    function renderPayPeriodAverageTable(');
  const c = context(code, { document: { getElementById: () => wrapper }, payPeriodData: data,
    payPeriodFilters: { metric: 'qj' }, payPeriodCountContract: () => ({ note: '' }) });
  c.renderPayPeriodTable();
  const unknown = wrapper.innerHTML.match(/<tr>\s*<td[^>]*>未知<\/td>([\s\S]*?)<\/tr>/)[1];
  assert.equal((unknown.match(/>--<\/td>/g) || []).length, 4);
  assert.match(wrapper.innerHTML, /真实零[\s\S]*?0\.0万/);
  assert.doesNotMatch(wrapper.innerHTML, /100\.0%|0\.0%/);
  assert.match(wrapper.innerHTML, /经代缺少日明细/);
  assert.equal(c.fmtPayPeriodAmount(null), '--');
  assert.equal(c.fmtPayPeriodAmount(0), '0.0');
});

function teamContext(overrides = {}) {
  const rows = { headcount: { OTO: [10, null, 0] }, activeHeadcount: { OTO: [0, null, 0] }, premium: { OTO: [0, null, 10] } };
  return context(extract(read('team-analysis'), '    function getTeamAggregated(', '    function getTeamOption('), {
    selectedTeamSeries: { OTO: true }, selectedTeamOrgs: { '上海': true, '湖北': true }, ORG_LIST_TEAM: ['上海', '湖北'],
    teamOrgData: {}, teamMock: { 2026: rows }, ...overrides
  });
}

test('team empty organization selection never displays national totals', () => {
  const c = teamContext({ selectedTeamOrgs: { '上海': false, '湖北': false } });
  assert.ok(c.getTeamAggregated(2026, 'headcount').every(value => value === null));
});

test('team partial organization selection without organization source stays unavailable', () => {
  const c = teamContext({ selectedTeamOrgs: { '上海': true, '湖北': false } });
  assert.ok(c.getTeamAggregated(2026, 'headcount').every(value => value === null));
});

test('team metrics distinguish observed zero, missing source and invalid denominator', () => {
  const c = teamContext();
  assert.equal(c.getTeamAggregated(2026, 'headcount')[0], 10);
  assert.equal(c.getTeamAggregated(2026, 'activity')[0], 0);
  assert.equal(c.getTeamAggregated(2026, 'perCapitaPremium')[0], 0);
  assert.equal(c.getTeamAggregated(2026, 'perCapitaCapacity')[0], null);
  assert.equal(c.getTeamAggregated(2026, 'headcount')[1], null);
  assert.equal(c.getTeamAggregated(2026, 'activity')[1], null);
  assert.equal(c.getTeamAggregated(2026, 'activity')[2], null);
  assert.equal(c.getTeamAggregated(2026, 'perCapitaPremium')[2], null);
});

test('team months follow human resource coverage rather than platform premium last month', () => {
  const c = teamContext({ teamMock: { 2026: { headcount: { OTO: [10, 12] }, activeHeadcount: { OTO: [2, 3] }, premium: { OTO: [20, 0] } } } });
  assert.equal(c.getTeamAggregated(2026, 'headcount')[1], 12);
});

test('organization all selection remains visibly selected when toggled again', () => {
  const makeLabel = checked => {
    const input = { checked };
    const classes = new Set(checked ? ['active'] : []);
    return { input, classes, querySelector: () => input,
      classList: { add: x => classes.add(x), remove: x => classes.delete(x),
        toggle: (x, on) => on ? classes.add(x) : classes.delete(x) } };
  };
  const all = makeLabel(true), shanghai = makeLabel(false);
  let renders = 0;
  const c = context("let selectedOrgs = ['all']; function getSelected(){return selectedOrgs;}\n" +
    extract(read('org-analysis'), '    function toggleOrgFilter(', '    function switchOrgDim('), {
    document: { querySelectorAll: () => [shanghai] }, renderOrgTable: () => renders++
  });
  c.toggleOrgFilter(all, 'all');
  assert.equal(all.input.checked, true);
  assert.equal(all.classes.has('active'), true);
  assert.deepEqual(Array.from(c.getSelected()), ['all']);
  assert.equal(renders, 1);
});
