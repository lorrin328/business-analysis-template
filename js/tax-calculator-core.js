/* 居民个人年度综合所得；金额内部使用整数分。政策口径见 docs/TAX_CALCULATOR.md。 */
(function (root, factory) {
  const calculator = factory();
  if (typeof module === 'object' && module.exports) module.exports = calculator;
  else root.TaxCalculator = calculator;
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  const BASIC_DEDUCTION = 6000000;
  const BRACKETS = Object.freeze([
    { ceiling: 3600000, rate: 3, quick: 0 },
    { ceiling: 14400000, rate: 10, quick: 252000 },
    { ceiling: 30000000, rate: 20, quick: 1692000 },
    { ceiling: 42000000, rate: 25, quick: 3192000 },
    { ceiling: 66000000, rate: 30, quick: 5292000 },
    { ceiling: 96000000, rate: 35, quick: 8592000 },
    { ceiling: Infinity, rate: 45, quick: 18192000 }
  ].map(Object.freeze));
  const FIELDS = Object.freeze({
    annualIncome: { label: '年收入', max: 1000000000 },
    otherDeductions: { label: '其他税前扣除', max: 1000000000 },
    pensionDeduction: { label: '个人养老金扣除', max: 12000 },
    healthDeduction: { label: '税优健康险本年可扣除金额', max: 2400 }
  });

  function parseMoney(value, field) {
    const rule = FIELDS[field];
    const source = typeof value === 'number' || typeof value === 'string' ? String(value).trim() : '';
    if (!rule) throw new Error('未知金额字段');
    if (!source) throw new Error(`请填写${rule.label}，无此项请填0`);
    if (!/^\d+(\.\d{1,2})?$/.test(source)) throw new Error(`${rule.label}须为非负金额，最多保留两位小数`);
    const [whole, fraction = ''] = source.split('.');
    const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    if (!Number.isSafeInteger(cents) || cents > rule.max * 100) {
      throw new Error(`${rule.label}不能超过${rule.max.toLocaleString('zh-CN')}元`);
    }
    return cents;
  }

  function taxOn(taxableCents) {
    if (!Number.isSafeInteger(taxableCents) || taxableCents < 0 || taxableCents > 100000000000) {
      throw new Error('应纳税所得额超出计算范围');
    }
    const bracket = BRACKETS.find(item => taxableCents <= item.ceiling);
    return {
      taxable: taxableCents,
      tax: Math.max(0, Math.round(taxableCents * bracket.rate / 100) - bracket.quick),
      rate: taxableCents === 0 ? 0 : bracket.rate,
      quick: bracket.quick
    };
  }

  function calculate(input) {
    const amounts = {};
    const errors = {};
    for (const field of Object.keys(FIELDS)) {
      try { amounts[field] = parseMoney(input[field], field); }
      catch (error) { errors[field] = error.message; }
    }
    if (Object.keys(errors).length) return { valid: false, errors };
    const base = Math.max(0, amounts.annualIncome - BASIC_DEDUCTION - amounts.otherDeductions);
    const baseline = taxOn(base);
    const pension = taxOn(Math.max(0, base - amounts.pensionDeduction));
    const health = taxOn(Math.max(0, base - amounts.healthDeduction));
    const combined = taxOn(Math.max(0, base - amounts.pensionDeduction - amounts.healthDeduction));
    return {
      valid: true, amounts, baseline, pension, health, combined,
      pensionSaving: baseline.tax - pension.tax,
      healthSaving: pension.tax - combined.tax,
      totalSaving: baseline.tax - combined.tax,
      healthUsed: pension.taxable - combined.taxable,
      healthUnused: amounts.healthDeduction - (pension.taxable - combined.taxable),
      deductionsExceedIncome: BASIC_DEDUCTION + amounts.otherDeductions > amounts.annualIncome
    };
  }

  return Object.freeze({ calculate, taxOn, parseMoney, BRACKETS, BASIC_DEDUCTION });
});
