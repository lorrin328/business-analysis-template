(function () {
  const TERMS = ['趸交', '3年', '5年', '6年', '10年'];
  const DEFAULT_SCENARIOS = [1, 5, 10, 20, 30, 50];
  const ZB_RATE_DICT = {
    '趸交': { standard: 0.3, favorable: 0.1 },
    '3年': { standard: 2.0, favorable: 0.6 },
    '5年': { standard: 3.0, favorable: 1.0 },
    '6年': { standard: 3.0, favorable: 1.0 },
    '10年': { standard: 4.5, favorable: 2.0 }
  };
  const state = { active: 'oto', zbType: 'standard', lastResults: { oto: null, zhengbao: null } };

  function getUser() {
    return window.getCurrentUser?.() || null;
  }

  function hasPermission(key) {
    const user = getUser();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function requirePersonnelAccess() {
    const user = getUser();
    if (!window.getAuthToken?.() || !user) {
      window.location.href = '/';
      return false;
    }
    const name = document.getElementById('currentUserName');
    if (name) name.textContent = `${user.username} · ${user.roleLabel || user.role}`;
    if (!hasPermission('personnel_management')) {
      document.getElementById('pageMain')?.classList.add('hidden');
      document.getElementById('accessDenied')?.classList.remove('hidden');
      return false;
    }
    return true;
  }

  function numberValue(id, fallback = 0) {
    const value = Number(document.getElementById(id)?.value || fallback);
    return Number.isFinite(value) ? value : fallback;
  }

  function textValue(id) {
    return document.getElementById(id)?.value || '';
  }

  function clampCount(value, fallback) {
    const n = Math.floor(Number(value || fallback));
    return Number.isFinite(n) && n > 0 ? n : fallback;
  }

  function parseScenarios(id) {
    const raw = document.getElementById(id)?.value || '';
    const values = raw
      .split(/[\s,，;；、]+/)
      .map(item => Number(item))
      .filter(item => Number.isFinite(item) && item > 0);
    const unique = Array.from(new Set(values.length ? values : DEFAULT_SCENARIOS));
    return unique.sort((a, b) => a - b);
  }

  function termFactor(term) {
    return (term === '趸交' ? 1 : parseInt(term, 10)) / 10;
  }

  function moneyText(value, digits = 0) {
    const n = Number(value || 0);
    return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function pctText(value) {
    const n = Number(value || 0);
    return `${n.toFixed(2)}%`;
  }

  function ratePct(value) {
    return Math.round((Number(value || 0) + Number.EPSILON) * 100) / 100;
  }

  function tableHtml(columns, rows) {
    const head = `<thead><tr>${columns.map(col => `<th>${col.label}</th>`).join('')}</tr></thead>`;
    const body = rows.length
      ? rows.map(row => `<tr>${columns.map(col => `<td>${col.render ? col.render(row[col.key], row) : row[col.key]}</td>`).join('')}</tr>`).join('')
      : `<tr><td colspan="${columns.length}" class="muted">暂无可测算数据</td></tr>`;
    return `${head}<tbody>${body}</tbody>`;
  }

  function renderTable(id, columns, rows) {
    const target = document.getElementById(id);
    if (target) target.innerHTML = tableHtml(columns, rows);
  }

  function otoFixed(nfyp, inst) {
    if (nfyp < 12000) return inst === 'A类' ? 3500 : 3100;
    if (nfyp < 22000) return inst === 'A类' ? 3900 : 3500;
    if (nfyp < 35000) return inst === 'A类' ? 4400 : 4000;
    if (nfyp < 55000) return inst === 'A类' ? 5000 : 4600;
    if (nfyp < 85000) return inst === 'A类' ? 5900 : 5500;
    if (nfyp < 120000) return inst === 'A类' ? 6600 : 6200;
    return inst === 'A类' ? 8200 : 7800;
  }

  function otoFloatRate(nfyp) {
    if (nfyp < 5000) return 0.07;
    if (nfyp < 10000) return 0.11;
    if (nfyp < 15000) return 0.13;
    if (nfyp < 30000) return 0.15;
    if (nfyp < 50000) return 0.165;
    if (nfyp < 80000) return 0.18;
    if (nfyp < 110000) return 0.195;
    if (nfyp < 150000) return 0.21;
    if (nfyp < 200000) return 0.225;
    if (nfyp < 250000) return 0.24;
    return 0.25;
  }

  function otoTeamBonusRate(teamNfyp) {
    if (teamNfyp < 30000) return 0;
    if (teamNfyp < 50000) return 0.016;
    if (teamNfyp < 100000) return 0.023;
    if (teamNfyp < 150000) return 0.026;
    if (teamNfyp < 200000) return 0.029;
    if (teamNfyp < 250000) return 0.032;
    if (teamNfyp < 350000) return 0.035;
    if (teamNfyp < 500000) return 0.038;
    if (teamNfyp < 700000) return 0.041;
    if (teamNfyp < 900000) return 0.044;
    return 0.047;
  }

  function otoSupBase(teamNfyp, inst) {
    if (teamNfyp < 70000) return inst === 'A类' ? 6200 : 5500;
    if (teamNfyp < 120000) return inst === 'A类' ? 6500 : 5800;
    if (teamNfyp < 200000) return inst === 'A类' ? 8100 : 7400;
    if (teamNfyp < 280000) return inst === 'A类' ? 9200 : 8500;
    if (teamNfyp < 400000) return inst === 'A类' ? 10500 : 9800;
    return inst === 'A类' ? 12000 : 11300;
  }

  function otoMgrBonusRate(umNfyp) {
    if (umNfyp < 100000) return 0;
    if (umNfyp < 200000) return 0.006;
    if (umNfyp < 300000) return 0.008;
    if (umNfyp < 500000) return 0.0095;
    if (umNfyp < 700000) return 0.0105;
    if (umNfyp < 1000000) return 0.0115;
    if (umNfyp < 1500000) return 0.0125;
    if (umNfyp < 2000000) return 0.0135;
    return 0.0145;
  }

  function otoMgrBase(umNfyp) {
    if (umNfyp < 450000) return 10400;
    if (umNfyp < 650000) return 11700;
    if (umNfyp < 850000) return 12900;
    if (umNfyp < 1200000) return 15000;
    return 19000;
  }

  function calculateOtoScenario(production, params) {
    const premium = production * 10000;
    const nfyp = premium * termFactor(params.term) * params.coeff;
    const teamNfyp = nfyp * params.teamSize;
    const umNfyp = nfyp * params.umSize;
    const fixed = otoFixed(nfyp, params.inst);
    const floating = nfyp * otoFloatRate(nfyp);
    const specialistTotal = fixed + floating;
    const teamBonus = (teamNfyp * otoTeamBonusRate(teamNfyp)) / params.teamSize;
    const supShare = otoSupBase(teamNfyp, params.inst) / params.teamSize;
    const mgrBonus = (umNfyp * otoMgrBonusRate(umNfyp)) / params.umSize;
    const mgrShare = otoMgrBase(umNfyp) / params.umSize;
    const managementTotal = teamBonus + supShare + mgrBonus + mgrShare;
    const total = specialistTotal + managementTotal;
    return {
      production, premium, nfyp, teamNfyp, umNfyp, fixed, floating,
      specialistTotal, teamBonus, supShare, mgrBonus, mgrShare,
      managementTotal, total, ratio: ratePct(total / premium * 100),
      specialistRatio: ratePct(specialistTotal / premium * 100),
      managementRatio: ratePct(managementTotal / premium * 100)
    };
  }

  function calculateOto() {
    const params = {
      term: textValue('otoTerm') || '10年',
      inst: textValue('otoInst') || 'A类',
      coeff: numberValue('otoCoeff', 1) || 1,
      teamSize: clampCount(numberValue('otoTeamSize', 4), 4),
      umSize: clampCount(numberValue('otoUmSize', 20), 20)
    };
    const rows = parseScenarios('otoScenarios').map(production => calculateOtoScenario(production, params));
    state.lastResults.oto = { params, rows };
    renderOtoTables(rows);
  }

  function zbRank(fyc) {
    if (fyc < 120) return '未达标';
    if (fyc < 1600) return '初级服务顾问';
    if (fyc < 4000) return '中级服务顾问';
    if (fyc < 7500) return '高级服务顾问';
    if (fyc < 9000) return '资深服务顾问';
    if (fyc < 11000) return '高级客户专家';
    if (fyc < 18000) return '资深客户专家';
    return '首席客户专家';
  }

  function zbBase(fyc) {
    if (fyc < 120) return 1500;
    if (fyc < 1600) return 3000;
    if (fyc < 4000) return 4000;
    if (fyc < 7500) return 5000;
    if (fyc < 9000) return 7000;
    if (fyc < 11000) return 8000;
    if (fyc < 18000) return 10000;
    return 12000;
  }

  function zbPerf(fyc) {
    if (fyc < 1600) return 0;
    if (fyc < 4000) return 2000;
    if (fyc < 7500) return 2500;
    if (fyc < 9000) return 4000;
    if (fyc < 11000) return 7000;
    if (fyc < 18000) return 10000;
    return 23000;
  }

  function zbManagerBase(teamFyc) {
    if (teamFyc < 6000) return 3000;
    if (teamFyc < 12000) return 6000;
    if (teamFyc < 28000) return 8100;
    if (teamFyc < 42000) return 10500;
    return 12000;
  }

  function zbManagerRank(teamFyc) {
    if (teamFyc < 6000) return '准经理';
    if (teamFyc < 12000) return '初级经理';
    if (teamFyc < 28000) return '高级经理';
    if (teamFyc < 42000) return '资深经理';
    return '首席经理';
  }

  function zbEffectiveRate() {
    const term = textValue('zbTerm') || '10年';
    if (state.zbType === 'other') {
      const input = document.querySelector(`[data-term-rate="${term}"]`);
      return Number(input?.value || NaN);
    }
    return ZB_RATE_DICT[term]?.[state.zbType] ?? NaN;
  }

  function calculateZhengbaoScenario(production, params) {
    const premium = production * 10000;
    const fyc = premium * (params.rate / 100);
    const base = zbBase(fyc);
    const perf = zbPerf(fyc);
    const specialistTotal = fyc + base + perf;
    const teamFyc = fyc * params.teamSize;
    const mgr = fyc * 0.4;
    const train = fyc * 0.15;
    const share = zbManagerBase(teamFyc) / params.teamSize;
    const managementTotal = mgr + train + share;
    const total = specialistTotal + managementTotal;
    return {
      production, premium, fyc, teamFyc, rank: zbRank(fyc), managerRank: zbManagerRank(teamFyc),
      base, perf, specialistTotal, mgr, train, share, managementTotal,
      total, ratio: ratePct(total / premium * 100),
      specialistRatio: ratePct(specialistTotal / premium * 100),
      managementRatio: ratePct(managementTotal / premium * 100)
    };
  }

  function calculateZhengbao() {
    const params = {
      term: textValue('zbTerm') || '10年',
      type: state.zbType,
      rate: zbEffectiveRate(),
      teamSize: clampCount(numberValue('zbTeamSize', 4), 4)
    };
    const rows = Number.isFinite(params.rate)
      ? parseScenarios('zbScenarios').map(production => calculateZhengbaoScenario(production, params))
      : [];
    state.lastResults.zhengbao = { params, rows };
    renderZhengbaoTables(rows);
  }

  const commonRenderers = {
    money: value => moneyText(value),
    pct: value => pctText(value),
    prod: value => `${moneyText(value, value % 1 === 0 ? 0 : 2)}万`
  };

  function renderOtoTables(rows) {
    renderTable('otoOverallTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'premium', label: '保费规模', render: commonRenderers.money },
      { key: 'nfyp', label: '个人 NFYP', render: commonRenderers.money },
      { key: 'teamNfyp', label: '团队 NFYP', render: commonRenderers.money },
      { key: 'umNfyp', label: 'UM NFYP', render: commonRenderers.money },
      { key: 'total', label: '基本法成本合计', render: commonRenderers.money },
      { key: 'ratio', label: '基本法费用率', render: commonRenderers.pct }
    ], rows);
    renderTable('otoSpecialistTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'nfyp', label: '个人 NFYP', render: commonRenderers.money },
      { key: 'fixed', label: '固定收入', render: commonRenderers.money },
      { key: 'floating', label: '浮动收入', render: commonRenderers.money },
      { key: 'specialistTotal', label: '专员成本小计', render: commonRenderers.money },
      { key: 'specialistRatio', label: '专员成本率', render: commonRenderers.pct }
    ], rows);
    renderTable('otoManagementTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'teamNfyp', label: '团队 NFYP', render: commonRenderers.money },
      { key: 'teamBonus', label: '团队提奖分摊', render: commonRenderers.money },
      { key: 'supShare', label: '主管基本佣金分摊', render: commonRenderers.money },
      { key: 'mgrBonus', label: '经理提奖分摊', render: commonRenderers.money },
      { key: 'mgrShare', label: '经理基本佣金分摊', render: commonRenderers.money },
      { key: 'managementTotal', label: '管理职成本小计', render: commonRenderers.money },
      { key: 'managementRatio', label: '管理职成本率', render: commonRenderers.pct }
    ], rows);
  }

  function renderZhengbaoTables(rows) {
    renderTable('zbOverallTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'premium', label: '保费规模', render: commonRenderers.money },
      { key: 'fyc', label: 'FYC', render: commonRenderers.money },
      { key: 'teamFyc', label: '团队 FYC', render: commonRenderers.money },
      { key: 'total', label: '基本法成本合计', render: commonRenderers.money },
      { key: 'ratio', label: '基本法费用率', render: commonRenderers.pct }
    ], rows);
    renderTable('zbSpecialistTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'rank', label: '专员职级' },
      { key: 'fyc', label: 'FYC', render: commonRenderers.money },
      { key: 'base', label: '基本佣金', render: commonRenderers.money },
      { key: 'perf', label: '绩效佣金', render: commonRenderers.money },
      { key: 'specialistTotal', label: '专员成本小计', render: commonRenderers.money },
      { key: 'specialistRatio', label: '专员成本率', render: commonRenderers.pct }
    ], rows);
    renderTable('zbManagementTable', [
      { key: 'production', label: '人产', render: commonRenderers.prod },
      { key: 'managerRank', label: '管理职级' },
      { key: 'teamFyc', label: '团队 FYC', render: commonRenderers.money },
      { key: 'mgr', label: '管理津贴', render: commonRenderers.money },
      { key: 'train', label: '育成津贴', render: commonRenderers.money },
      { key: 'share', label: '经理基本佣金分摊', render: commonRenderers.money },
      { key: 'managementTotal', label: '管理职成本小计', render: commonRenderers.money },
      { key: 'managementRatio', label: '管理职成本率', render: commonRenderers.pct }
    ], rows);
  }

  function renderZbRateDisplay() {
    const target = document.getElementById('zbRateDisplay');
    const custom = document.getElementById('zbCustomRates');
    if (!target || !custom) return;
    const standard = TERMS.map(term => `${term} ${ZB_RATE_DICT[term].standard.toFixed(1)}%`).join(' / ');
    const favorable = TERMS.map(term => `${term} ${ZB_RATE_DICT[term].favorable.toFixed(1)}%`).join(' / ');
    if (state.zbType === 'other') {
      target.innerHTML = `<label>参考费率</label><div class="section-note" style="margin-top:0;">标准：${standard}<br>费优：${favorable}</div>`;
      custom.classList.remove('hidden');
    } else {
      const current = TERMS.map(term => `${term} ${ZB_RATE_DICT[term][state.zbType].toFixed(1)}%`).join(' / ');
      target.innerHTML = `<label>当前费率</label><div class="section-note" style="margin-top:0;">${current}</div>`;
      custom.classList.add('hidden');
    }
  }

  function switchCalculator(name) {
    state.active = name;
    document.querySelectorAll('[data-calculator]').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.calculator === name);
    });
    document.getElementById('otoCalculator')?.classList.toggle('hidden', name !== 'oto');
    document.getElementById('zhengbaoCalculator')?.classList.toggle('hidden', name !== 'zhengbao');
  }

  function csvEscape(value) {
    const text = String(value ?? '');
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function exportRows(name, result) {
    if (!result?.rows?.length) return;
    const rows = result.rows;
    const sections = [
      ['整体基本法成本', ['人产', '保费规模', '指标', '团队指标', '成本合计', '费用率'],
        rows.map(row => [row.production, row.premium, row.nfyp ?? row.fyc, row.teamNfyp ?? row.teamFyc, row.total, pctText(row.ratio)])],
      ['专员成本明细', ['人产', '职级', '指标', '固定/基本佣金', '浮动/绩效佣金', '小计', '成本率'],
        rows.map(row => [row.production, row.rank || '', row.nfyp ?? row.fyc, row.fixed ?? row.base, row.floating ?? row.perf, row.specialistTotal, pctText(row.specialistRatio)])],
      ['管理职成本明细', ['人产', '管理职级', '团队指标', '团队提奖/管理津贴', '主管分摊/育成津贴', '经理提奖', '经理基本佣金/分摊', '小计', '成本率'],
        rows.map(row => [row.production, row.managerRank || '', row.teamNfyp ?? row.teamFyc, row.teamBonus ?? row.mgr, row.supShare ?? row.train, row.mgrBonus ?? '', row.mgrShare ?? row.share, row.managementTotal, pctText(row.managementRatio)])]
    ];
    const lines = [`${name}基本法测算`, `参数,${csvEscape(JSON.stringify(result.params))}`, ''];
    sections.forEach(([title, headers, dataRows]) => {
      lines.push(title);
      lines.push(headers.map(csvEscape).join(','));
      dataRows.forEach(row => lines.push(row.map(csvEscape).join(',')));
      lines.push('');
    });
    const blob = new Blob([`\uFEFF${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${name}-基本法测算.csv`;
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }

  function bindEvents() {
    document.querySelectorAll('[data-calculator]').forEach(tab => {
      tab.addEventListener('click', () => switchCalculator(tab.dataset.calculator));
    });
    ['otoTerm', 'otoInst', 'otoCoeff', 'otoTeamSize', 'otoUmSize', 'otoScenarios'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', calculateOto);
      document.getElementById(id)?.addEventListener('change', calculateOto);
    });
    ['zbTerm', 'zbTeamSize', 'zbScenarios'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', calculateZhengbao);
      document.getElementById(id)?.addEventListener('change', calculateZhengbao);
    });
    document.querySelectorAll('[data-zb-type]').forEach(btn => {
      btn.addEventListener('click', () => {
        state.zbType = btn.dataset.zbType;
        document.querySelectorAll('[data-zb-type]').forEach(item => item.classList.toggle('active', item === btn));
        renderZbRateDisplay();
        calculateZhengbao();
      });
    });
    document.querySelectorAll('[data-term-rate]').forEach(input => {
      input.addEventListener('input', calculateZhengbao);
    });
    document.querySelectorAll('[data-export]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.export;
        if (type === 'oto') exportRows('OTO', state.lastResults.oto);
        if (type === 'zhengbao') exportRows('证保', state.lastResults.zhengbao);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requirePersonnelAccess()) return;
    bindEvents();
    renderZbRateDisplay();
    calculateOto();
    calculateZhengbao();
  });
})();
