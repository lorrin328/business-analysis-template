(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const fields = ['annualIncome', 'otherDeductions', 'pensionDeduction', 'healthDeduction'];
  const money = cents => (cents / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const rate = scenario => scenario.taxable === 0 ? '无应税所得' : `${scenario.rate}%`;
  let current = null;
  let started = false;

  function paragraph(parent, message) {
    const node = document.createElement('p');
    node.textContent = message;
    parent.appendChild(node);
  }

  function render(result) {
    $('healthSaving').textContent = money(result.healthSaving);
    $('pensionTax').textContent = money(result.pension.tax);
    $('combinedTax').textContent = money(result.combined.tax);
    $('totalSaving').textContent = money(result.totalSaving);
    $('heroNote').textContent = `按税优健康险本年可扣除${money(result.amounts.healthDeduction)}元试算；应纳税额由${money(result.pension.tax)}元降至${money(result.combined.tax)}元。`;
    const rows = $('scenarioRows');
    rows.replaceChildren();
    for (const [name, scenario, highlight] of [
      ['不计个养及税优健康险（基准）', result.baseline, false],
      ['仅计个人养老金', result.pension, false],
      ['仅计税优健康险', result.health, false],
      ['个人养老金＋税优健康险', result.combined, true]
    ]) {
      const row = document.createElement('tr');
      if (highlight) row.className = 'highlight';
      [name, money(scenario.taxable), rate(scenario), money(scenario.tax), money(result.baseline.tax - scenario.tax)].forEach(value => {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.appendChild(cell);
      });
      rows.appendChild(row);
    }
    const a = result.amounts;
    $('formula').replaceChildren();
    paragraph($('formula'), `两项扣除后应纳税所得额＝max（0，${money(a.annualIncome)}－60,000.00－${money(a.otherDeductions)}－${money(a.pensionDeduction)}－${money(a.healthDeduction)}）＝${money(result.combined.taxable)}元。`);
    paragraph($('formula'), `应纳税额＝${money(result.combined.taxable)} × ${result.combined.rate}%－${money(result.combined.quick)}＝${money(result.combined.tax)}元。`);
    paragraph($('formula'), `当年节税拆分：个养${money(result.pensionSaving)}元＋其后税优健康险${money(result.healthSaving)}元＝合计${money(result.totalSaving)}元。`);
    const warnings = $('warnings');
    warnings.replaceChildren();
    if (result.deductionsExceedIncome) paragraph(warnings, '基本减除费用与其他扣除合计已超过收入，应纳税所得额按0计算。请核对是否重复填写6万元或其他扣除。');
    if (result.pension.taxable === 0) paragraph(warnings, '计入个养后已无应纳税所得额，增加税优健康险不会产生额外当年节税。');
    else if (result.healthUnused > 0) paragraph(warnings, `税优健康险扣除中仅${money(result.healthUsed)}元降低了应纳税所得额；其余${money(result.healthUnused)}元在本情景不产生当年节税。`);
    if (result.pension.rate !== result.combined.rate && result.combined.taxable > 0) paragraph(warnings, `税优健康险扣除跨越${result.pension.rate}%与${result.combined.rate}%税档，已按扣除前后税额差计算。`);
    if (a.healthDeduction === 0) paragraph(warnings, '税优健康险可扣除金额为0，本次仅测算个人养老金扣除的影响。');
    paragraph(warnings, '个养领取时另按3%计税。以上为当年应纳税额差，不是实际退税额、产品收益或最终净收益。');
    $('results').hidden = false;
    $('emptyState').hidden = true;
  }

  function update(focusError = false) {
    const input = Object.fromEntries(fields.map(field => [field, $(field).value]));
    const result = window.TaxCalculator.calculate(input);
    current = null;
    $('copyStatus').textContent = '';
    for (const field of fields) {
      const error = result.errors?.[field];
      $(field).setAttribute('aria-invalid', error ? 'true' : 'false');
      $(`${field}Error`).textContent = error || '';
      $(`${field}Error`).hidden = !error;
    }
    if (!result.valid) {
      $('results').hidden = true;
      $('emptyState').hidden = false;
      $('emptyState').firstElementChild.textContent = '请补全或修正输入';
      $('inputStatus').textContent = '输入不完整或超出范围，暂不显示测算结果。';
      if (result.errors.healthDeduction) $('healthSettings').open = true;
      if (focusError) $(Object.keys(result.errors)[0]).focus();
      return;
    }
    current = result;
    $('inputStatus').textContent = '测算已更新。修改任一金额后会自动重算。';
    render(result);
  }

  function updateAssumption() {
    try { $('healthAssumption').textContent = `全年扣除${money(window.TaxCalculator.parseMoney($('healthDeduction').value, 'healthDeduction'))}元`; }
    catch (_) { $('healthAssumption').textContent = '金额待核对'; }
  }

  $('taxForm').addEventListener('submit', event => { event.preventDefault(); started = true; update(true); });
  fields.forEach(field => $(field).addEventListener('input', () => { updateAssumption(); if (started) update(); }));
  $('exampleButton').addEventListener('click', () => {
    $('annualIncome').value = '300000'; $('otherDeductions').value = '60000';
    $('pensionDeduction').value = '12000'; $('healthDeduction').value = '2400';
    started = true; updateAssumption(); update();
    $('inputStatus').textContent = '当前为演示数据：年收入30万元，其他扣除6万元，个养1.2万元。';
  });
  $('resetButton').addEventListener('click', () => {
    $('taxForm').reset(); current = null; started = false;
    fields.forEach(field => { $(field).removeAttribute('aria-invalid'); $(`${field}Error`).hidden = true; });
    $('results').hidden = true; $('emptyState').hidden = false;
    $('emptyState').firstElementChild.textContent = '填写年收入，开始测算';
    $('inputStatus').textContent = '基本减除费用60,000元已自动计入。';
    $('copyStatus').textContent = ''; updateAssumption(); $('annualIncome').focus();
  });
  $('copyButton').addEventListener('click', async () => {
    if (!current) return;
    const r = current, a = r.amounts;
    const summary = [
      '税优产品年度测算（居民个人综合所得）',
      `年收入额：${money(a.annualIncome)}元；其他税前扣除：${money(a.otherDeductions)}元；基本减除费用：60,000.00元。`,
      `个养扣除：${money(a.pensionDeduction)}元；税优健康险本年可扣除金额（情景假设）：${money(a.healthDeduction)}元。`,
      `基准应纳税额：${money(r.baseline.tax)}元；仅扣个养后：${money(r.pension.tax)}元；两项扣除后：${money(r.combined.tax)}元。`,
      `当年节税：个养${money(r.pensionSaving)}元，之后增加税优健康险${money(r.healthSaving)}元，两项合计${money(r.totalSaving)}元。`,
      `税优健康险实际降低应纳税所得额${money(r.healthUsed)}元；${money(r.healthUnused)}元在本情景不产生当年节税。`,
      '不代表退税额、产品收益或最终净收益。个养领取时另按3%计税；税优健康险须核实税优识别码、凭证及有效扣除月份。经营所得、单独计税奖金和特殊减免等不适用。',
      '政策核验：2026-08-31；计算口径以税务机关核定为准。',
      '个人所得税法：https://www.chinatax.gov.cn/n810219/n810744/n3752930/n3752974/c3970366/content.html',
      '个人养老金：https://fgk.chinatax.gov.cn/zcfgk/c102416/c5237110/content.html',
      '税优健康险：https://shanghai.chinatax.gov.cn/zcfw/zcfgk/grsds/201705/t432115.html'
    ].join('\n');
    try {
      await navigator.clipboard.writeText(summary);
      $('copyStatus').textContent = '摘要已复制，含口径与风险提示。';
    } catch (_) { $('copyStatus').textContent = '浏览器未允许复制，请选择页面内容复制，或使用打印。'; }
  });
  $('printButton').addEventListener('click', () => { if (current) window.print(); });
})();
