const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness() {
  const elements = new Map(['aliasCoverageNotice', 'aliasCoverageMessage', 'aliasCoverageScope'].map(id => [id, {
    textContent: '', hiddenByClass: true,
    classList: { toggle(key, value) { elements.get(id).hiddenByClass = value; } },
  }]));
  const window = {};
  const source = fs.readFileSync(path.join(__dirname, '../js/customer-analysis.js'), 'utf8')
    .replace('  init();', '  window.renderCoverageForTest = renderAliasCoverage;');
  vm.runInNewContext(source, { window, document: { getElementById: id => elements.get(id) } });
  return { show: window.renderCoverageForTest, elements };
}

test('coverage warning shows backend wording and explicit scope as text', () => {
  const h = harness();
  h.show({ aliasCoverage: { status: 'warning', message: '未关联业绩保留，不能进入新老客结论。<b>原始文本</b>',
    scope: '当前所选期间、业务线、机构及保单范围' } });
  assert.equal(h.elements.get('aliasCoverageNotice').hiddenByClass, false);
  assert.equal(h.elements.get('aliasCoverageMessage').textContent, '未关联业绩保留，不能进入新老客结论。<b>原始文本</b>');
  assert.equal(h.elements.get('aliasCoverageScope').textContent, '适用范围：当前所选期间、业务线、机构及保单范围');
  h.show({ aliasCoverage: { status: 'warning', message: '存在未关联业绩。', scope: '全量客户事实表；未关联业绩不进入新客追踪' } });
  assert.match(h.elements.get('aliasCoverageScope').textContent, /全量客户事实表/);
});

test('normal, missing or loading coverage clears any prior warning', () => {
  const h = harness();
  for (const quality of [null, {}, { aliasCoverage: { status: 'ok', message: '' } },
    { aliasCoverage: { status: 'warning', message: ' ' } }]) {
    h.show({ aliasCoverage: { status: 'warning', message: '前次提示', scope: '前次范围' } });
    h.show(quality);
    assert.equal(h.elements.get('aliasCoverageNotice').hiddenByClass, true);
    assert.equal(h.elements.get('aliasCoverageMessage').textContent, '');
    assert.equal(h.elements.get('aliasCoverageScope').textContent, '');
  }
});
