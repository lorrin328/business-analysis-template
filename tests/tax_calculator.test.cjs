const test = require('node:test');
const assert = require('node:assert/strict');
const { calculate, taxOn, parseMoney } = require('../js/tax-calculator-core.js');
const input = (overrides = {}) => ({ annualIncome: '300000', otherDeductions: '60000', pensionDeduction: '12000', healthDeduction: '2400', ...overrides });

test('30万元收入：个养节税2400元，其后健康险节税480元', () => {
  const r = calculate(input());
  assert.equal(r.valid, true);
  assert.equal(r.baseline.tax, 1908000);
  assert.equal(r.pension.tax, 1668000);
  assert.equal(r.combined.tax, 1620000);
  assert.equal(r.pensionSaving, 240000);
  assert.equal(r.healthSaving, 48000);
  assert.equal(r.totalSaving, 288000);
});

test('收入小于等于基本减除费用，不产生节税或负税额', () => {
  for (const income of ['0', '50000', '60000']) {
    const r = calculate(input({ annualIncome: income, otherDeductions: '0' }));
    assert.equal(r.baseline.tax, 0);
    assert.equal(r.combined.tax, 0);
    assert.equal(r.totalSaving, 0);
    assert.equal(r.healthUnused, 240000);
  }
});

test('健康险跨越10%和3%税档，节税142元而非240元', () => {
  const r = calculate(input({ annualIncome: '109000', otherDeductions: '0' }));
  assert.equal(r.pension.taxable, 3700000);
  assert.equal(r.pension.tax, 118000);
  assert.equal(r.combined.tax, 103800);
  assert.equal(r.healthSaving, 14200);
  assert.equal(r.pensionSaving, 120000);
});

test('健康险扣除超过剩余应税所得时，仅剩余部分节税', () => {
  const r = calculate(input({ annualIncome: '73000', otherDeductions: '0' }));
  assert.equal(r.pension.tax, 3000);
  assert.equal(r.combined.tax, 0);
  assert.equal(r.healthSaving, 3000);
  assert.equal(r.healthUsed, 100000);
  assert.equal(r.healthUnused, 140000);
});

test('零扣除不虚构优惠，个养已耗尽所得时健康险节税为零', () => {
  const none = calculate(input({ pensionDeduction: '0', healthDeduction: '0' }));
  assert.equal(none.totalSaving, 0);
  assert.equal(none.baseline.tax, none.combined.tax);
  const exhausted = calculate(input({ annualIncome: '70000', otherDeductions: '0' }));
  assert.equal(exhausted.healthSaving, 0);
  assert.equal(exhausted.pensionSaving, 30000);
});

test('所有年度税档边界与上下1分，匹配逐段累进独立算法', () => {
  const segments = [[3600000,3],[10800000,10],[15600000,20],[12000000,25],[24000000,30],[30000000,35],[Infinity,45]];
  const progressive = value => {
    let remaining = value, numerator = 0;
    for (const [size, rate] of segments) {
      const part = Math.min(remaining, size);
      numerator += part * rate;
      remaining -= part;
      if (!remaining) break;
    }
    return Math.round(numerator / 100);
  };
  for (const threshold of [3600000,14400000,30000000,42000000,66000000,96000000]) {
    for (const offset of [-1,0,1]) assert.equal(taxOn(threshold + offset).tax, progressive(threshold + offset));
  }
  for (let cents = 17; cents < 150000000; cents += 179383) assert.equal(taxOn(cents).tax, progressive(cents));
  assert.equal(taxOn(100000000).tax, 26808000);
});

test('精确解析到分，零值有效，拒绝空白、负数、指数、超限及多余小数', () => {
  assert.equal(parseMoney(' 1200.01 ', 'healthDeduction'), 120001);
  assert.equal(parseMoney('0', 'healthDeduction'), 0);
  assert.equal(parseMoney('1.1', 'healthDeduction'), 110);
  for (const field of ['annualIncome','otherDeductions','pensionDeduction','healthDeduction']) {
    for (const invalid of ['', ' ', '-1', 'NaN', 'Infinity', '1e3', '1,000', '0.001', null, undefined, true, 'abc', '<script>']) {
      const r = calculate(input({ [field]: invalid }));
      assert.equal(r.valid, false, `${field}: ${invalid}`);
      assert.ok(r.errors[field]);
    }
  }
  for (const [field, value] of [['pensionDeduction','12000.01'], ['healthDeduction','2400.01'], ['annualIncome','1000000000.01'], ['otherDeductions','1000000000.01']]) {
    assert.equal(calculate(input({ [field]: value })).valid, false);
  }
});

test('限额内与部分年度扣除按实际金额算，不自动补齐至上限', () => {
  const r = calculate(input({ pensionDeduction: '6000', healthDeduction: '800' }));
  assert.equal(r.healthSaving, 16000);
  assert.equal(r.pensionSaving, 120000);
  assert.equal(r.amounts.healthDeduction, 80000);
});

test('跨税档各情景独立计算，分项顺序拆分保持勾稽', () => {
  for (const annualIncome of ['60000.01','96000','97000','109000','205000','361000','481000','721000','1021000','1000000000']) {
    const r = calculate(input({ annualIncome, otherDeductions: '0' }));
    assert.ok(r.combined.tax <= r.pension.tax && r.pension.tax <= r.baseline.tax);
    assert.ok(r.combined.tax <= r.health.tax && r.health.tax <= r.baseline.tax);
    assert.equal(r.totalSaving, r.pensionSaving + r.healthSaving);
    assert.ok(r.healthSaving <= 108000);
    assert.ok(r.totalSaving <= 648000);
  }
});
