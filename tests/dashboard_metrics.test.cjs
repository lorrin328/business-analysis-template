const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('js/kpi-cards.js', 'utf8');
function render(value) {
  const elements = {};
  const document = {
    readyState: 'loading', addEventListener() {}, querySelectorAll() { return []; },
    body: { classList: { toggle() {} } },
    getElementById(id) {
      if (['targetTrustBanner', 'targetSourceStatus'].includes(id)) return null;
      return elements[id] ||= { textContent: '', innerHTML: '', title: '' };
    }
  };
  const metric = { value, calculable: value !== null, reason: value === null ? '缺少分母数据' : null,
    cutoff: '2026-06', coveredMonths: 2, yoy: { value: value === null ? null : 0 } };
  const context = { document, console: { error(...args) { throw new Error(args.join(' ')); } },
    loadTargetData() {}, targetSourceLabel: () => '服务端目标', selectedYear: 2026,
    DEFAULT_DASHBOARD_YEAR: 2026, platformMock: {}, teamMock: {}, targetData: { categories: {} },
    apiData: { kpi: { year: 2026, month: 6, qj_premium: { total: 0 }, hr: {},
      metrics: { version: 1, cards: { activity: metric, percapita: metric } } } } };
  context.window = context;
  vm.runInNewContext(source, context);
  context.updateKPICards();
  return elements;
}
const zero = render(0);
assert.equal(zero['kpi-activity-rate'].textContent, '0.0%');
assert.equal(zero['kpi-percapita'].textContent, '0.0万');
assert.match(zero['kpi-activity-sub'].textContent, /同比 \+0.0pp/);
const missing = render(null);
assert.equal(missing['kpi-activity-rate'].textContent, '—');
assert.equal(missing['kpi-percapita'].textContent, '—');
assert.equal(missing['kpi-percapita-sub'].textContent, '缺少分母数据');

const modalContext = { apiData: {}, window: {} };
vm.runInNewContext(fs.readFileSync('js/kpi-modal-content.js', 'utf8'), modalContext);
const base = { year: 2026, period: { label: '2026年5月20日至6月10日' }, metrics: { version: 1, cards: {} } };
const available = { value: .5, calculable: true, numerator: 100, denominator: 200,
  displayDigits: 1, cutoff: '2026-06', precision: 'month', definition: '实绩 / 目标' };
for (const type of ['overall', 'value', 'annuity', 'protection', '10year', 'longterm']) {
  base.metrics.cards[type] = { overall: available, transform: { ...available, value: 0, numerator: 0 },
    jingdai: { ...available, calculable: false, value: null, denominator: null, reason: '未配置正式目标' } };
  modalContext.apiData.kpi = base;
  const result = modalContext.getModalContent(type);
  assert.match(result.body, /50\.0%/);
  assert.match(result.body, /0\.0%/);
  assert.match(result.body, /未配置正式目标/);
  assert.match(result.body, /2026年5月20日至6月10日/);
  assert.doesNotMatch(result.body, /季度累计|年度累计|NaN|null%/);
}
base.metrics.cards.activity = { ...available, value: 0, numerator: 0, yoy: { value: 0, unit: 'pp' },
  byChannel: { OTO: { ...available, value: null, calculable: false, denominator: null, reason: '缺少人力分母' } } };
assert.match(modalContext.getModalContent('activity').body, /\+0\.0pp/);
assert.match(modalContext.getModalContent('activity').body, /缺少人力分母/);
base.metrics.cards.percapita = { ...available, value: 5, numerator: 50, denominator: 10,
  periodPremium: 100, coveredMonths: 2, yoy: { value: 5, unit: '万元/人' }, byChannel: {} };
const pcBody = modalContext.getModalContent('percapita').body;
assert.match(pcBody, /<td>100\.0<\/td><td>2<\/td><td>50\.0<\/td><td>10\.0<\/td><td>5\.0<\/td>/);
assert.match(pcBody, /\+5\.0万元\/人/);
assert.doesNotMatch(pcBody, /季度累计|年度累计/);
modalContext.apiData.kpi = {};
assert.match(modalContext.getModalContent('percapita').body, /请刷新页面/);
