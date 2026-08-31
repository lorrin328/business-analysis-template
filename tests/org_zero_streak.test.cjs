const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../js/org-analysis.js'), 'utf8');
const result = (days, status = 'ok', extra = {}) => ({
  days, status, lastPositiveDate: '2026-08-28', startDate: '2026-01-01', reason: '', ...extra,
});
const snapshot = (cutoff, projects = {}, orgs = {}, warning = '') => ({cutoff, projects, orgs, warning});
const data = () => ({
  year: 2026, perf: {}, perf_prev: {}, value: {}, value_prev: {}, longterm: {},
  zeroStreak: {basis: 'qj_premium', dateBasis: 'business_date', unit: '天',
    year: snapshot('2026-08-31', {'上海|OTO': result(3), '上海|证保': result(8)}, {'上海': result(3)}),
    month: {
      '7': snapshot('2026-07-31', {'上海|OTO': result(2)}, {'上海': result(2)}),
      '8': snapshot('2026-08-31', {'上海|OTO': result(3)}, {'上海': result(3)}),
    },
  },
});

function harness(payload = data(), targets = {}) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      innerHTML: '', style: {}, dataset: {}, hidden: false,
      setAttribute() {}, addEventListener() {}, classList: {add() {}, remove() {}},
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    window: {}, document: {readyState: 'loading', addEventListener() {}, getElementById: element,
      querySelectorAll: () => [], querySelector: () => null},
    targetData: {orgTargets: targets}, selectedYear: 2026, DEFAULT_DASHBOARD_YEAR: 2026,
    getLatestMonthForYear: () => 8,
    MonthMultiSelect: {normalizeMonths: months => months, defaultMonths: () => [8], render: (_, options) => options.selectedMonths},
    console, payload,
  });
  vm.runInContext(source, context);
  vm.runInContext('orgKpiData = payload;', context);
  const render = (state = '') => {
    vm.runInContext(`${state}; renderOrgTable();`, context);
    return element('orgTableWrapper').innerHTML;
  };
  return {render, context, element};
}

function tableRows(html) {
  const tbody = html.match(/<tbody>([\s\S]*?)<\/tbody>/)[1];
  return Array.from(tbody.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g), match => ({
    html: match[1],
    cells: Array.from(match[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g), cell => cell[1].trim()),
  }));
}

test('最后指标为连续挂零，收起显示机构整体结果且十家机构完整保留', () => {
  const html = harness().render();
  assert.ok(html.indexOf('连续挂零（天）') > html.indexOf('保障类产品'));
  const rows = tableRows(html);
  assert.equal(rows.length, 14);
  assert.equal(rows.find(row => row.cells[0] === '上海').cells.at(-1), '3');
  assert.equal(rows.find(row => row.cells[0] === '湖北').cells.at(-1), '—');
  assert.equal(rows.at(-1).cells.at(-1), '—');
  assert.match(html, /截至 2026-08-31/);
});

test('展开保留业绩全零的已观察项目，机构小计不累加项目挂零天数', () => {
  const html = harness().render('orgExpanded = true');
  const shanghai = tableRows(html).filter(row => row.cells[0] === '上海');
  assert.deepEqual(shanghai.map(row => [row.cells[1], row.cells.at(-1)]), [['OTO', '3'], ['证保', '8'], ['小计', '3']]);
  assert.match(shanghai[0].html, /本行仅用于挂零追踪/);
  assert.ok(!shanghai.some(row => row.cells[1] === '蚁桥'));
});

test('多选月份和季度采用最后月份快照，切换月份不求和且年度恢复全局截止', () => {
  const h = harness();
  let html = h.render("orgTimeDim = 'month'; orgSelectedMonths.month = [8, 7]");
  assert.equal(tableRows(html).find(row => row.cells[0] === '上海').cells.at(-1), '3');
  assert.match(html, /截至 2026-08-31/);
  html = h.render('orgSelectedMonths.month = [7]');
  assert.equal(tableRows(html).find(row => row.cells[0] === '上海').cells.at(-1), '2');
  assert.match(html, /截至 2026-07-31/);
  html = h.render("orgTimeDim = 'quarter'; orgSelectedMonths.quarter = [7, 8]");
  assert.equal(tableRows(html).find(row => row.cells[0] === '上海').cells.at(-1), '3');
  html = h.render("orgTimeDim = 'year'");
  assert.match(html, /截至 2026-08-31/);
});

test('全局自定义范围始终采用year快照，范围起点不截断挂零', () => {
  const payload = data();
  payload.period = {rangeType: 'custom', startDate: '2026-08-30', endDate: '2026-08-31', label: '8月30—31日'};
  payload.zeroStreak.year.orgs['上海'] = result(10);
  const h = harness(payload);
  const html = h.render("orgTimeDim = 'month'; orgSelectedMonths.month = [7]");
  assert.equal(tableRows(html).find(row => row.cells[0] === '上海').cells.at(-1), '10');
  assert.match(html, /截至 2026-08-31/);
  assert.equal(h.element('orgDimBtns').style.pointerEvents, 'none');
});

test('下界、未知和未观察状态忠实显示，零天必须显示0且不依赖净额', () => {
  const payload = data();
  payload.perf = {'上海|OTO': {qj_premium: -10}, '山东|OTO': {qj_premium: 0}};
  payload.zeroStreak.year.projects = {
    '上海|OTO': result(0), '湖北|OTO': result(5, 'lower_bound'),
    '四川|OTO': result(null, 'unknown', {reason: '数据未完整导入'}),
    '山东|OTO': result(null, 'not_observed'),
  };
  const rows = tableRows(harness(payload).render('orgExpanded = true'));
  const project = org => rows.find(row => row.cells[0] === org && row.cells[1] === 'OTO');
  assert.equal(project('上海').cells.at(-1), '0');
  assert.equal(project('上海').cells[3], '-10');
  assert.equal(project('湖北').cells.at(-1), '≥5');
  assert.match(project('湖北').html, /实际连续挂零天数可能更长/);
  assert.equal(project('四川').cells.at(-1), '—');
  assert.match(project('四川').html, /数据未完整导入/);
  assert.equal(project('山东'), undefined);
});

test('兼容旧API和缺失月快照，不把缺失数据当0，也不回退到未来快照', () => {
  const payload = data();
  delete payload.zeroStreak;
  const rows = tableRows(harness(payload).render());
  assert.equal(rows.length, 14);
  assert.ok(rows.every(row => row.cells.at(-1) === '—'));
  const monthRows = tableRows(harness().render("orgTimeDim = 'month'; orgSelectedMonths.month = [6]"));
  assert.ok(monthRows.every(row => row.cells.at(-1) === '—'));
});

test('只为挂零保留的零行不改变原保费、目标或同比汇总', () => {
  const payload = data();
  payload.perf = {'上海|OTO': {qj_premium: 100}};
  payload.perf_prev = {'上海|OTO': {qj_premium: 80}, '湖北|OTO': {qj_premium: 20}};
  const targets = {
    '上海|OTO': {qjPremium: {year: 200}},
    '上海|证保': {qjPremium: {year: 999}},
    '湖北|OTO': {qjPremium: {year: 50}},
  };
  const withStreak = tableRows(harness(payload, targets).render());
  const without = structuredClone(payload);
  delete without.zeroStreak;
  const withoutStreak = tableRows(harness(without, targets).render());
  assert.deepEqual(withStreak.map(row => row.cells.slice(0, -1)), withoutStreak.map(row => row.cells.slice(0, -1)));
  assert.equal(withStreak.at(-1).cells[1], '250');
  assert.equal(withStreak.at(-1).cells[2], '100');
  assert.equal(withStreak.at(-1).cells[4], '0.0%');
});

test('接口口径、截止日和异常说明均转义，不向页面注入HTML或属性', () => {
  const payload = data();
  const unsafe = '\"><img src=x onerror=alert(1)>&\'';
  payload.zeroStreak.year.cutoff = unsafe;
  payload.zeroStreak.year.warning = unsafe;
  payload.zeroStreak.year.orgs['上海'] = result(null, 'unknown', {reason: unsafe, startDate: unsafe, lastPositiveDate: unsafe});
  payload.period = {rangeType: 'custom', label: unsafe};
  const html = harness(payload).render();
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;&amp;&#39;'));
  assert.match(html, /white-space:normal;overflow-wrap:anywhere;max-width:100%/);
});

test('非法天数不能展示为有效统计', () => {
  const payload = data();
  Object.assign(payload.zeroStreak.year.orgs, {
    '上海': result(-1), '湖北': result(1.5), '四川': result('3'),
    '辽宁': result(3, 'unknown'), '山东': result(null),
  });
  assert.ok(tableRows(harness(payload).render()).every(row => row.cells.at(-1) === '—'));
});

test('业务小计固定在合计前，跨机构重算达成率和同比，展开不重复汇总', () => {
  const payload = data();
  payload.perf = {
    '上海|OTO': {qj_premium: 100, product_10year: 20, product_annuity: 30, product_protection: 40},
    '湖北|OTO': {qj_premium: 300, product_10year: 60, product_annuity: 90, product_protection: 120},
    '四川|OTO': {qj_premium: 0},
    '上海|证保': {qj_premium: 50}, '湖北|蚁桥': {qj_premium: -10},
  };
  payload.perf_prev = {'上海|OTO': {qj_premium: 50}, '湖北|OTO': {qj_premium: 250}, '四川|OTO': {qj_premium: 100}};
  payload.value = {'上海|OTO': 10, '湖北|OTO': 30};
  payload.value_prev = {'上海|OTO': 5, '湖北|OTO': 15};
  payload.longterm = {'上海|OTO': 80, '湖北|OTO': 240};
  const targets = {
    '上海|OTO': {qjPremium: {year: 100}, value: {year: 20}, tenYear: {year: 40}, shangbao: {year: 60}, baozhang: {year: 80}},
    '湖北|OTO': {qjPremium: {year: 900}, value: {year: 80}, tenYear: {year: 160}, shangbao: {year: 240}, baozhang: {year: 320}},
  };
  const h = harness(payload, targets);
  const rows = tableRows(h.render());
  assert.deepEqual(rows.slice(-4).map(r => r.cells[0]), ['OTO小计', '证保小计', '蚁桥小计', '合计']);
  assert.deepEqual(rows.at(-4).cells, ['OTO小计','1,000','400','40.0%','0.0%','100','40','40.0%','+100.0%','1,000','320','32.0%','200','80','40.0%','300','120','40.0%','400','160','40.0%','—']);
  assert.equal(rows.at(-2).cells[2], '-10');
  assert.equal(rows.at(-1).cells[2], '440');
  assert.match(rows.at(-4).html, /连续挂零天数不作业务小计/);
  assert.deepEqual(tableRows(h.render('orgExpanded = true')).slice(-4).map(r => r.cells), rows.slice(-4).map(r => r.cells));
  const filtered = tableRows(h.render("selectedOrgs = ['上海']"));
  assert.equal(filtered.at(-4).cells[2], '100');
  assert.equal(filtered.at(-4).cells[3], '100.0%');
  assert.equal(filtered.at(-4).cells[4], '+100.0%');
  assert.equal(filtered.at(-1).cells[2], '150');
  assert.equal(filtered.at(-2).cells[3], '-');
});

test('业务小计遵循月度、季度多选及全局自定义范围，缺目标不伪造达成率', () => {
  const payload = data();
  payload.perf = {'上海|OTO': {year: {qj_premium: 100}, month: {'7': {qj_premium: 30}, '8': {qj_premium: 70}}}};
  payload.perf_prev = {'上海|OTO': {year: {qj_premium: 80}, month: {'7': {qj_premium: 20}, '8': {qj_premium: 60}}}};
  const months = Array(12).fill(0); months[6] = 50; months[7] = 150;
  const h = harness(payload, {'上海|OTO': {qjPremium: {year: 1000, month: months}}});
  const summary = state => tableRows(h.render(state)).at(-4).cells;
  assert.deepEqual(summary("orgTimeDim = 'month'; orgSelectedMonths.month = [7]").slice(1,5), ['50','30','60.0%','+50.0%']);
  assert.deepEqual(summary('orgSelectedMonths.month = [7,8]').slice(1,5), ['200','100','50.0%','+25.0%']);
  assert.deepEqual(summary("orgTimeDim = 'quarter'; orgSelectedMonths.quarter = [7,8]").slice(1,5), ['200','100','50.0%','+25.0%']);
  assert.deepEqual(summary("orgKpiData.period = {rangeType: 'custom', targetMode: 'none'}").slice(1,5), ['-','100','-','+25.0%']);
});
