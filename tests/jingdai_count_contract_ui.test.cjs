const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');

const payment = fs.readFileSync('js/payperiod-chart.js', 'utf8');
const product = fs.readFileSync('js/product-analysis.js', 'utf8');
function extract(source, start, end) {
  return source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
}
function paymentContext(basis, countNote = '') {
  const cell = basis === 'mixed'
    ? {premium: 20, count: null, average: null, calculable: false, reason: '混合口径不可计算'}
    : {premium: 20, count: 10, average: 2, calculable: true};
  const elements = {
    payPeriodTableWrapper: {innerHTML: ''},
    payPeriodAverageWrapper: {innerHTML: ''},
    payPeriodAverageScopeNote: {textContent: ''}
  };
  const ctx = vm.createContext({
    document: {getElementById: id => elements[id] || null},
    payPeriodData: {premium: [{name: '未分类', value: 20}], count: basis === 'mixed' ? [] : [{name: '未分类', value: 10}],
      countBasis: basis, countNote, averagePremium: {categories: ['未分类'], scope: '经代',
        rows: [{org: '合成平台', business_mode: '经代', terms: [{category: '未分类', ...cell}], total: cell}],
        summaries: [{org: 'all', business_mode: 'all', terms: [{category: '未分类', ...cell}], total: cell}]}},
    payPeriodFilters: {metric: 'qj', timeDim: 'year', year: 2026},
    payPeriodAverageFilters: {org: 'all', businessMode: 'all'},
    ORG_LIST: [], DEFAULT_DASHBOARD_YEAR: 2026
  });
  vm.runInContext(extract(payment, '    function fmtPayPeriodAmount(', '    function renderPayPeriodChart('), ctx);
  vm.runInContext(extract(payment, '    function getPayPeriodPieOption(', '    function applyPayPeriodFallback('), ctx);
  return {ctx, elements};
}

test('payment legacy notes and average tooltip retain source net counts', () => {
  const {ctx, elements} = paymentContext('source_net');
  ctx.renderPayPeriodTable(); ctx.renderPayPeriodAverageTable();
  assert.match(elements.payPeriodAverageScopeNote.textContent, /承保件数净额/);
  assert.match(elements.payPeriodAverageWrapper.innerHTML, /承保件数净额10件/);
  assert.match(elements.payPeriodTableWrapper.innerHTML, /20\.0万/);
  assert.match(elements.payPeriodTableWrapper.innerHTML, /10件/);
});

test('payment identity notes and tooltips say selected-range distinct policies', () => {
  const {ctx, elements} = paymentContext('policy_identity');
  ctx.renderPayPeriodTable(); ctx.renderPayPeriodAverageTable();
  assert.match(elements.payPeriodAverageScopeNote.textContent, /所选范围投保单号去重数/);
  assert.match(elements.payPeriodAverageScopeNote.textContent, /不等同于净承保件数/);
  assert.match(elements.payPeriodAverageWrapper.innerHTML, /所选范围投保单号去重数10件/);
  assert.doesNotMatch(elements.payPeriodAverageWrapper.innerHTML, /承保件数净额10件/);
  assert.equal(ctx.getPayPeriodPieOption('count').series[0].data[0].value, 10);
});

test('mixed periods explain unavailable count and average without making up values', () => {
  const {ctx, elements} = paymentContext('mixed');
  ctx.renderPayPeriodTable(); ctx.renderPayPeriodAverageTable();
  assert.match(elements.payPeriodAverageScopeNote.textContent, /合并件数及件均不可计算/);
  assert.match(elements.payPeriodAverageWrapper.innerHTML, /混合口径不可计算/);
  assert.match(ctx.getPayPeriodPieOption('count').title.text, /合并件数不可计算/);
  assert.equal(ctx.getPayPeriodPieOption('premium').series[0].data[0].value, 20);
});

test('API metadata wins and API notes remain escaped text in payment scopes', () => {
  const attack = '<img src=x onerror="alert(1)">';
  const {ctx, elements} = paymentContext('source_net', attack);
  ctx.payPeriodData.averagePremium.metadata = {countBasis: 'policy_identity', countNote: attack,
    formula: '保费净额 ÷ 所选范围投保单号去重数'};
  ctx.renderPayPeriodTable(); ctx.renderPayPeriodAverageTable();
  assert.match(elements.payPeriodAverageScopeNote.textContent, /所选范围投保单号去重数/);
  assert.ok(elements.payPeriodAverageScopeNote.textContent.includes(attack));
  assert.doesNotMatch(elements.payPeriodTableWrapper.innerHTML, /<img/);
  assert.match(elements.payPeriodTableWrapper.innerHTML, /&lt;img/);
});

test('product count notes use textContent and product names are escaped in tooltip', () => {
  const attack = '<img src=x onerror="alert(1)">';
  const note = {textContent: '', hidden: true};
  const ctx = vm.createContext({document: {getElementById: id => id === 'productCountBasisNote' ? note : null},
    productData: {premium: [{name: '合成产品', value: 20}], count: [{name: '合成产品', value: 10}],
      countBasis: 'policy_identity', countNote: attack}});
  vm.runInContext(extract(product, '    function getPieOption(type)', '    let currentPieType ='), ctx);
  const option = ctx.getPieOption('count');
  assert.equal(note.textContent, attack); assert.equal(note.hidden, false);
  assert.equal(option.series[0].data[0].value, 10);
  const tooltip = option.tooltip.formatter({name: attack, value: 10, percent: 100});
  assert.doesNotMatch(tooltip, /<img/); assert.match(tooltip, /&lt;img/);
  ctx.productData.countNote = ''; ctx.productData.countBasis = 'mixed'; ctx.renderProductCountBasisNote();
  assert.match(note.textContent, /合并件数及件均不可计算/);
  ctx.productData.countBasis = 'source_net'; ctx.renderProductCountBasisNote();
  assert.match(note.textContent, /承保件数净额/);
});
