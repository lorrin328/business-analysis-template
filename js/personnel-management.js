(function () {
  const TERMS = ['趸交', '3年', '5年', '6年', '10年'];
  const ZB_RATE_DICT = {
    '趸交': { standard: 0.3, favorable: 0.1 },
    '3年': { standard: 2.0, favorable: 0.6 },
    '5年': { standard: 3.0, favorable: 1.0 },
    '6年': { standard: 3.0, favorable: 1.0 },
    '10年': { standard: 4.5, favorable: 2.0 }
  };
  const state = { active: 'oto', zbType: 'standard' };

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

  function moneyText(value, digits = 0) {
    const n = Number(value || 0);
    return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function pctText(value) {
    const n = Number(value || 0);
    return `${n.toFixed(2)}%`;
  }

  function metric(label, value, note) {
    return `
      <div class="metric">
        <div class="metric-label">${label}</div>
        <div class="metric-value">${value}</div>
        ${note ? `<div class="metric-note">${note}</div>` : ''}
      </div>
    `;
  }

  function renderMetrics(containerId, rows) {
    const target = document.getElementById(containerId);
    if (!target) return;
    target.innerHTML = rows.map(row => metric(row.label, row.value, row.note)).join('');
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

  function calculateOto() {
    const production = numberValue('otoProd');
    const coeff = numberValue('otoCoeff', 1) || 1;
    const term = textValue('otoTerm');
    const inst = textValue('otoInst') || 'A类';
    if (!production || !term) {
      renderMetrics('otoResults', emptyOtoRows());
      return;
    }
    const termValue = term === '趸交' ? 1 : parseInt(term, 10);
    const nfyp = production * 10000 * (termValue / 10) * coeff;
    const teamNfyp = nfyp * 4;
    const umNfyp = nfyp * 20;
    const fixed = otoFixed(nfyp, inst);
    const floating = nfyp * otoFloatRate(nfyp);
    const teamBonus = (teamNfyp * otoTeamBonusRate(teamNfyp)) / 4;
    const supShare = otoSupBase(teamNfyp, inst) / 4;
    const mgrBonus = (umNfyp * otoMgrBonusRate(umNfyp)) / 20;
    const mgrShare = otoMgrBase(umNfyp) / 20;
    const total = fixed + floating + teamBonus + supShare + mgrBonus + mgrShare;
    const ratio = production ? total / (production * 10000) * 100 : 0;
    renderMetrics('otoResults', [
      { label: '个人 NFYP', value: moneyText(nfyp) },
      { label: '团队 NFYP', value: moneyText(teamNfyp), note: '按个人 4 倍测算' },
      { label: 'UM 团队 NFYP', value: moneyText(umNfyp), note: '按个人 20 倍测算' },
      { label: '固定收入', value: moneyText(fixed) },
      { label: '浮动收入', value: moneyText(floating) },
      { label: '团队提奖', value: moneyText(teamBonus), note: '团队提奖后按 4 人分摊' },
      { label: '主管基本佣金分摊', value: moneyText(supShare) },
      { label: '经理提奖', value: moneyText(mgrBonus), note: 'UM 提奖后按 20 人分摊' },
      { label: '经理基本佣金分摊', value: moneyText(mgrShare) },
      { label: '成本合计', value: moneyText(total) },
      { label: '费用率', value: pctText(Math.round((ratio + Number.EPSILON) * 100) / 100) }
    ]);
  }

  function emptyOtoRows() {
    return [
      { label: '个人 NFYP', value: '0' },
      { label: '固定收入', value: '0' },
      { label: '浮动收入', value: '0' },
      { label: '成本合计', value: '0' },
      { label: '费用率', value: '0.00%' }
    ];
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

  function zbEffectiveRate() {
    const term = textValue('zbTerm');
    if (!term) return NaN;
    if (state.zbType === 'other') {
      const input = document.querySelector(`[data-term-rate="${term}"]`);
      return Number(input?.value || NaN);
    }
    return ZB_RATE_DICT[term]?.[state.zbType] ?? NaN;
  }

  function calculateZhengbao() {
    const production = numberValue('zbProd');
    const rate = zbEffectiveRate();
    if (!production || !Number.isFinite(rate)) {
      renderMetrics('zbResults', emptyZbRows());
      return;
    }
    const fyc = production * 10000 * (rate / 100);
    const base = zbBase(fyc);
    const perf = zbPerf(fyc);
    const mgr = fyc * 0.4;
    const train = fyc * 0.15;
    const team = fyc * 4;
    const share = (team < 6000 ? 3000 : team < 12000 ? 6000 : team < 28000 ? 8100 : team < 42000 ? 10500 : 12000) * 0.25;
    const total = fyc + base + perf + mgr + train + share;
    const ratio = production ? total / (production * 10000) * 100 : 0;
    renderMetrics('zbResults', [
      { label: 'FYC', value: moneyText(fyc) },
      { label: '当前业务职级', value: zbRank(fyc) },
      { label: '基本佣金', value: moneyText(base) },
      { label: '绩效佣金', value: moneyText(perf) },
      { label: '管理津贴', value: moneyText(mgr) },
      { label: '育成津贴', value: moneyText(train) },
      { label: '经理分摊基本佣金', value: moneyText(share) },
      { label: '成本合计', value: moneyText(total) },
      { label: '基本法费用率', value: pctText(Math.round((ratio + Number.EPSILON) * 100) / 100) }
    ]);
  }

  function emptyZbRows() {
    return [
      { label: 'FYC', value: '0' },
      { label: '当前业务职级', value: '未达标' },
      { label: '基本佣金', value: '0' },
      { label: '绩效佣金', value: '0' },
      { label: '成本合计', value: '0' },
      { label: '基本法费用率', value: '0.00%' }
    ];
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

  function bindEvents() {
    document.querySelectorAll('[data-calculator]').forEach(tab => {
      tab.addEventListener('click', () => switchCalculator(tab.dataset.calculator));
    });
    ['otoProd', 'otoTerm', 'otoInst', 'otoCoeff'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', calculateOto);
      document.getElementById(id)?.addEventListener('change', calculateOto);
    });
    ['zbProd', 'zbTerm'].forEach(id => {
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
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requirePersonnelAccess()) return;
    bindEvents();
    renderZbRateDisplay();
    calculateOto();
    calculateZhengbao();
  });
})();
