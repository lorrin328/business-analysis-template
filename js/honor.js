(function () {
  let currentBatchId = null;
  const state = {
    dashboard: null,
    audit: null,
    filters: {
      orgs: { keyword: '', businessLine: 'all' },
      projects: { businessLine: 'all' },
      specialists: { keyword: '', org: 'all', businessLine: 'all' },
      managers: { keyword: '', roleType: 'all', businessLine: 'all' },
      specialistHistory: { keyword: '', org: 'all', businessLine: 'all' },
      managerHistory: { keyword: '', org: 'all', businessLine: 'all', roleType: 'all' },
      warnings: { keyword: '', org: 'all', businessLine: 'all', type: 'all' },
      persons: { keyword: '', org: 'all', businessLine: 'all', roleType: 'all', level: 'all' },
    },
  };

  const LABELS = {
    rank: '排名',
    dimension: '维度',
    org: '机构',
    business_line: '项目',
    role_type: '层级',
    staff_code: '人员代码',
    staff_name: '人员姓名',
    manager_code: '主管/经理代码',
    manager_name: '主管/经理姓名',
    team_code: '团队代码',
    team_scope: '团队层级',
    data_note: '数据说明',
    tracked_headcount: '追踪人力',
    member_count: '会员人数',
    member_rate: '会员率',
    avg_diamond: '人均钻石',
    monthly_gain_count: '本月获钻',
    monthly_deduct_count: '本月扣减',
    total_diamond: '累计钻石',
    estimated_reward: '测算奖励',
    membership_level: '会员等级',
    diamond_balance: '当前钻石',
    total_gain: '累计获钻',
    total_deduct: '累计扣减',
    qualified_months: '达标月份',
    is_new_star: '新星人力',
    warning_type: '预警类型',
    month: '月份',
    diamond_delta: '本月变化',
    standard_premium: '标保(万)',
    qj_premium: '期交保费(万)',
    team_qj_premium: '团队期交(万)',
    team_standard_premium: '团队标保(万)',
    team_tracked_headcount: '团队人力',
    star_manpower_count: '星钻人力数',
    team_diamond_balance: '团队钻石',
    manager_diamond_balance: '管理职钻石',
    longterm_policy_count: '长险件数',
    suggested_action: '建议动作',
    level: '会员等级',
    count: '人数',
    share: '占比',
    gain_count: '获钻人数',
    deduct_count: '扣减人数',
    qualified_count: '达标人数',
    qualified_rate: '达标率',
  };

  const NUMBER_COLUMNS = new Set([
    'rank', 'tracked_headcount', 'member_count', 'monthly_gain_count',
    'monthly_deduct_count', 'total_diamond', 'estimated_reward',
    'diamond_balance', 'total_gain', 'total_deduct', 'qualified_months',
    'month', 'diamond_delta', 'standard_premium', 'qj_premium', 'team_qj_premium',
    'team_standard_premium', 'team_tracked_headcount', 'star_manpower_count',
    'team_diamond_balance', 'manager_diamond_balance', 'longterm_policy_count',
    'count', 'gain_count', 'deduct_count', 'qualified_count',
  ]);

  const PERCENT_COLUMNS = new Set(['member_rate', 'share', 'qualified_rate']);

  function hasPermission(key) {
    const user = window.getCurrentUser?.();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function requireLogin() {
    if (!window.getAuthToken?.()) {
      window.location.href = '/';
      return false;
    }
    document.querySelectorAll('[data-permission]').forEach(el => {
      const key = el.getAttribute('data-permission');
      el.style.display = hasPermission(key) ? '' : 'none';
    });
    return true;
  }

  function setStatus(message, cls = 'muted') {
    const el = document.getElementById('honorStatus');
    if (!el) return;
    el.textContent = message || '';
    el.className = `status-pill ${cls}`;
  }

  async function api(path, options = {}) {
    const resp = await window.authFetch(path, options);
    if (!resp.ok) throw new Error(`${path} ${resp.status}`);
    const payload = await resp.json();
    return payload.data || payload;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function numberText(value, digits = 0) {
    if (value === null || value === undefined || value === '') return '-';
    const n = Number(value);
    if (!Number.isFinite(n)) return String(value);
    return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function percentText(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : '-';
  }

  function formatCell(key, value) {
    if (key === 'is_new_star') return Number(value) ? '是' : '否';
    if (PERCENT_COLUMNS.has(key)) return percentText(value);
    if (key === 'avg_diamond') return numberText(value, 1);
    if (['standard_premium', 'qj_premium', 'team_qj_premium', 'team_standard_premium'].includes(key)) return numberText(Number(value || 0) / 10000, 2);
    if (NUMBER_COLUMNS.has(key)) return numberText(value, 0);
    return value ?? '-';
  }

  function optionValues(rows, key) {
    return [...new Set((rows || []).map(row => row[key]).filter(Boolean))]
      .sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'));
  }

  function matchesKeyword(row, keyword, keys) {
    const text = String(keyword || '').trim().toLowerCase();
    if (!text) return true;
    return keys.some(key => String(row[key] || '').toLowerCase().includes(text));
  }

  function renderMetricCards(overview = {}) {
    const cards = [
      ['追踪人力', numberText(overview.tracked_headcount), '覆盖 OTO、证保'],
      ['会员人数', numberText(overview.member_count), `会员率 ${percentText(overview.member_rate)}`],
      ['资深及以上', numberText(overview.senior_plus_count), '重点荣誉人群'],
      ['本月获钻', numberText(overview.monthly_gain_count), '月度达标人力'],
      ['本月扣减', numberText(overview.monthly_deduct_count), '需优先跟进'],
      ['累计钻石', numberText(overview.total_diamond), '当前批次累计'],
      ['新星人力', numberText(overview.new_star_count), '新人荣誉转化'],
      ['测算奖励', `${numberText(overview.estimated_reward)}元`, '非最终发放金额'],
      ['异常数量', numberText(overview.exception_count), '字段与规则异常'],
    ];
    document.getElementById('honorCards').innerHTML = cards.map(([label, value, note]) => `
      <article class="metric-card">
        <div class="metric-label">${escapeHtml(label)}</div>
        <div class="metric-value">${escapeHtml(value)}</div>
        <div class="metric-note">${escapeHtml(note)}</div>
      </article>
    `).join('');
  }

  function renderTable(targetId, rows, columns, emptyText = '暂无数据') {
    const target = document.getElementById(targetId);
    if (!target) return;
    if (!rows || !rows.length) {
      target.innerHTML = `<div class="empty">${escapeHtml(emptyText)}</div>`;
      return;
    }
    target.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr>${columns.map(key => `<th class="${NUMBER_COLUMNS.has(key) || PERCENT_COLUMNS.has(key) ? 'num' : ''}">${escapeHtml(LABELS[key] || key)}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.map(row => `<tr>${columns.map(key => `<td class="${NUMBER_COLUMNS.has(key) || PERCENT_COLUMNS.has(key) ? 'num' : ''}">${escapeHtml(formatCell(key, row[key]))}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderMiniTable(targetId, rows, columns, emptyText = '暂无数据') {
    renderTable(targetId, rows.slice(0, 8), columns, emptyText);
  }

  function renderBarList(targetId, rows, labelKey, valueKey, valueFormatter = numberText) {
    const target = document.getElementById(targetId);
    const max = Math.max(...rows.map(row => Number(row[valueKey] || 0)), 0);
    if (!rows.length || max <= 0) {
      target.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }
    target.innerHTML = rows.slice(0, 8).map(row => {
      const pct = Math.max(3, Number(row[valueKey] || 0) / max * 100);
      return `
        <div class="bar-row">
          <span>${escapeHtml(row[labelKey])}</span>
          <div class="bar-track"><i style="width:${pct.toFixed(1)}%"></i></div>
          <strong>${escapeHtml(valueFormatter(row[valueKey]))}</strong>
        </div>`;
    }).join('');
  }

  function selectControl(id, label, value, values) {
    return `
      <label>${escapeHtml(label)}
        <select id="${escapeHtml(id)}">
          <option value="all"${value === 'all' ? ' selected' : ''}>全部</option>
          ${values.map(v => `<option value="${escapeHtml(v)}"${String(value) === String(v) ? ' selected' : ''}>${escapeHtml(v)}</option>`).join('')}
        </select>
      </label>`;
  }

  function searchControl(id, label, value, placeholder) {
    return `<label>${escapeHtml(label)}<input id="${escapeHtml(id)}" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}"></label>`;
  }

  function bindFilter(id, event, callback) {
    document.getElementById(id)?.addEventListener(event, callback);
  }

  function renderOverview() {
    const data = state.dashboard || {};
    const overview = data.overview || {};
    const orgs = data.orgs || [];
    const projects = data.projects || [];
    const warnings = data.warnings || [];
    const bestOrg = orgs[0];
    const riskOrg = [...orgs].sort((a, b) => Number(b.monthly_deduct_count || 0) - Number(a.monthly_deduct_count || 0))[0];
    document.getElementById('overview').innerHTML = `
      <div class="dashboard-grid">
        <section class="panel-block">
          <h2>经营追踪结论</h2>
          <div class="conclusion-list">
            <div><span>当前会员率</span><strong>${percentText(overview.member_rate)}</strong></div>
            <div><span>机构领先</span><strong>${escapeHtml(bestOrg ? `${bestOrg.org}-${bestOrg.business_line}` : '-')}</strong></div>
            <div><span>扣减关注</span><strong>${escapeHtml(riskOrg ? `${riskOrg.org}-${riskOrg.business_line} ${numberText(riskOrg.monthly_deduct_count)}人` : '-')}</strong></div>
            <div><span>月度预警</span><strong>${numberText(warnings.length)}条</strong></div>
          </div>
        </section>
        <section class="panel-block">
          <h2>项目表现</h2>
          <div id="overviewProjects"></div>
        </section>
        <section class="panel-block wide">
          <h2>机构会员率 Top</h2>
          <div id="overviewOrgBars"></div>
        </section>
        <section class="panel-block wide">
          <h2>月度预警优先处理</h2>
          <div id="overviewWarnings"></div>
        </section>
      </div>`;
    renderMiniTable('overviewProjects', projects, ['rank', 'dimension', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count']);
    renderBarList('overviewOrgBars', orgs, 'org', 'member_rate', percentText);
    renderMiniTable('overviewWarnings', warnings, ['warning_type', 'org', 'business_line', 'staff_name', 'membership_level', 'suggested_action']);
  }

  function renderOrgs() {
    const rows = state.dashboard?.orgs || [];
    const f = state.filters.orgs;
    const filtered = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['org', 'business_line'])
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    document.getElementById('orgs').innerHTML = `
      <div class="panel-head">
        <div><h2>机构追踪</h2><p>按机构和项目跟踪会员转化、获钻、扣减和测算奖励。</p></div>
        <div class="filter-bar">
          ${searchControl('orgKeyword', '筛选', f.keyword, '机构/项目')}
          ${selectControl('orgBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
        </div>
      </div>
      <div id="orgTable"></div>`;
    renderTable('orgTable', filtered, ['rank', 'org', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond', 'estimated_reward']);
    bindFilter('orgKeyword', 'input', () => { state.filters.orgs.keyword = document.getElementById('orgKeyword').value; renderOrgs(); });
    bindFilter('orgBusinessLine', 'change', () => { state.filters.orgs.businessLine = document.getElementById('orgBusinessLine').value; renderOrgs(); });
  }

  function renderProjects() {
    const rows = state.dashboard?.projects || [];
    const f = state.filters.projects;
    const filtered = rows.filter(row => f.businessLine === 'all' || row.dimension === f.businessLine || row.business_line === f.businessLine);
    document.getElementById('projects').innerHTML = `
      <div class="panel-head">
        <div><h2>项目分析</h2><p>项目口径聚焦 OTO、证保，展示会员转化、获钻、扣减和奖励测算。</p></div>
        <div class="filter-bar">${selectControl('projectBusinessLine', '项目', f.businessLine, optionValues(rows, 'dimension'))}</div>
      </div>
      <div class="split-layout">
        <div id="projectTable"></div>
        <div class="panel-block"><h3>项目会员率对比</h3><div id="projectBars"></div></div>
      </div>`;
    renderTable('projectTable', filtered, ['rank', 'dimension', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'estimated_reward']);
    renderBarList('projectBars', filtered, 'dimension', 'member_rate', percentText);
    bindFilter('projectBusinessLine', 'change', () => { state.filters.projects.businessLine = document.getElementById('projectBusinessLine').value; renderProjects(); });
  }

  function renderSpecialists() {
    const rows = state.dashboard?.specialists || [];
    const f = state.filters.specialists;
    const filtered = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['dimension', 'business_line'])
      && (f.org === 'all' || row.dimension === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    document.getElementById('specialists').innerHTML = `
      <div class="panel-head">
        <div><h2>专员级追踪</h2><p>聚焦非管理职人群，识别会员转化、月度扣减和新人荣誉培育情况。</p></div>
        <div class="filter-bar">
          ${searchControl('specialistKeyword', '筛选', f.keyword, '机构/项目')}
          ${selectControl('specialistOrg', '机构', f.org, optionValues(rows, 'dimension'))}
          ${selectControl('specialistBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
        </div>
      </div>
      <div class="split-layout">
        <div><h3>机构 / 项目整体表现</h3><div id="specialistTable"></div></div>
        <div><h3>人员历史月度明细</h3><div id="specialistHistoryTable"></div></div>
      </div>`;
    renderTable('specialistTable', filtered, ['rank', 'dimension', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond']);
    renderSpecialistHistory();
    bindFilter('specialistKeyword', 'input', () => { state.filters.specialists.keyword = document.getElementById('specialistKeyword').value; renderSpecialists(); });
    bindFilter('specialistOrg', 'change', () => { state.filters.specialists.org = document.getElementById('specialistOrg').value; renderSpecialists(); });
    bindFilter('specialistBusinessLine', 'change', () => { state.filters.specialists.businessLine = document.getElementById('specialistBusinessLine').value; renderSpecialists(); });
  }

  function renderManagers() {
    const rows = state.dashboard?.managers || [];
    const f = state.filters.managers;
    const filtered = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['dimension', 'business_line'])
      && (f.roleType === 'all' || row.dimension === f.roleType)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    document.getElementById('managers').innerHTML = `
      <div class="panel-head">
        <div><h2>管理职追踪</h2><p>主管、经理单独看，便于观察团队带动层的会员沉淀和扣减压力。</p></div>
        <div class="filter-bar">
          ${searchControl('managerKeyword', '筛选', f.keyword, '层级/项目')}
          ${selectControl('managerRoleType', '层级', f.roleType, optionValues(rows, 'dimension'))}
          ${selectControl('managerBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
        </div>
      </div>
      <div class="split-layout">
        <div><h3>管理职整体表现</h3><div id="managerTable"></div></div>
        <div><h3>主管 / 经理历史团队表现</h3><div id="managerHistoryTable"></div></div>
      </div>`;
    renderTable('managerTable', filtered, ['rank', 'dimension', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond']);
    renderManagerHistory();
    bindFilter('managerKeyword', 'input', () => { state.filters.managers.keyword = document.getElementById('managerKeyword').value; renderManagers(); });
    bindFilter('managerRoleType', 'change', () => { state.filters.managers.roleType = document.getElementById('managerRoleType').value; renderManagers(); });
    bindFilter('managerBusinessLine', 'change', () => { state.filters.managers.businessLine = document.getElementById('managerBusinessLine').value; renderManagers(); });
  }

  function renderSpecialistHistory() {
    const rows = state.dashboard?.specialistHistory || [];
    const f = state.filters.specialistHistory;
    const base = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (state.filters.specialists.org === 'all' || row.org === state.filters.specialists.org)
      && (state.filters.specialists.businessLine === 'all' || row.business_line === state.filters.specialists.businessLine)
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    const host = document.getElementById('specialistHistoryTable');
    if (!host) return;
    host.insertAdjacentHTML('beforebegin', `
      <div class="filter-bar compact-history-filter">
        ${searchControl('specialistHistoryKeyword', '人员', f.keyword, '代码/姓名/机构')}
        ${selectControl('specialistHistoryOrg', '机构', f.org, optionValues(rows, 'org'))}
        ${selectControl('specialistHistoryBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
      </div>`);
    renderTable('specialistHistoryTable', base, ['org', 'business_line', 'staff_code', 'staff_name', 'month', 'qj_premium', 'standard_premium', 'longterm_policy_count', 'monthly_qualified', 'diamond_delta', 'diamond_balance', 'membership_level']);
    bindFilter('specialistHistoryKeyword', 'input', () => { state.filters.specialistHistory.keyword = document.getElementById('specialistHistoryKeyword').value; renderSpecialists(); });
    bindFilter('specialistHistoryOrg', 'change', () => { state.filters.specialistHistory.org = document.getElementById('specialistHistoryOrg').value; renderSpecialists(); });
    bindFilter('specialistHistoryBusinessLine', 'change', () => { state.filters.specialistHistory.businessLine = document.getElementById('specialistHistoryBusinessLine').value; renderSpecialists(); });
  }

  function renderManagerHistory() {
    const rows = state.dashboard?.managerHistory || [];
    const f = state.filters.managerHistory;
    const base = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['manager_code', 'manager_name', 'org', 'team_code'])
      && (state.filters.managers.roleType === 'all' || row.role_type === state.filters.managers.roleType)
      && (state.filters.managers.businessLine === 'all' || row.business_line === state.filters.managers.businessLine)
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || row.role_type === f.roleType)
    ));
    const host = document.getElementById('managerHistoryTable');
    if (!host) return;
    host.insertAdjacentHTML('beforebegin', `
      <div class="filter-bar compact-history-filter">
        ${searchControl('managerHistoryKeyword', '主管/经理', f.keyword, '代码/姓名/团队')}
        ${selectControl('managerHistoryOrg', '机构', f.org, optionValues(rows, 'org'))}
        ${selectControl('managerHistoryBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
        ${selectControl('managerHistoryRoleType', '层级', f.roleType, optionValues(rows, 'role_type'))}
      </div>`);
    renderTable('managerHistoryTable', base, ['org', 'business_line', 'role_type', 'manager_code', 'manager_name', 'month', 'team_scope', 'team_code', 'team_tracked_headcount', 'star_manpower_count', 'team_qj_premium', 'team_standard_premium', 'team_diamond_balance', 'manager_diamond_balance', 'monthly_gain_count', 'monthly_deduct_count', 'data_note']);
    bindFilter('managerHistoryKeyword', 'input', () => { state.filters.managerHistory.keyword = document.getElementById('managerHistoryKeyword').value; renderManagers(); });
    bindFilter('managerHistoryOrg', 'change', () => { state.filters.managerHistory.org = document.getElementById('managerHistoryOrg').value; renderManagers(); });
    bindFilter('managerHistoryBusinessLine', 'change', () => { state.filters.managerHistory.businessLine = document.getElementById('managerHistoryBusinessLine').value; renderManagers(); });
    bindFilter('managerHistoryRoleType', 'change', () => { state.filters.managerHistory.roleType = document.getElementById('managerHistoryRoleType').value; renderManagers(); });
  }

  function renderWarnings() {
    const rows = state.dashboard?.warnings || [];
    const f = state.filters.warnings;
    const filtered = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org', 'suggested_action'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.type === 'all' || row.warning_type === f.type)
    ));
    document.getElementById('warnings').innerHTML = `
      <div class="panel-head">
        <div><h2>月度预警</h2><p>优先展示扣减、保号、未达标和数据异常，服务月度追踪和机构督导。</p></div>
        <div class="filter-bar">
          ${searchControl('warningKeyword', '筛选', f.keyword, '姓名/代码/机构/动作')}
          ${selectControl('warningOrg', '机构', f.org, optionValues(rows, 'org'))}
          ${selectControl('warningBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
          ${selectControl('warningType', '类型', f.type, optionValues(rows, 'warning_type'))}
        </div>
      </div>
      <div id="warningTable"></div>`;
    renderTable('warningTable', filtered, ['warning_type', 'month', 'org', 'business_line', 'staff_code', 'staff_name', 'role_type', 'membership_level', 'diamond_balance', 'diamond_delta', 'standard_premium', 'longterm_policy_count', 'suggested_action']);
    bindFilter('warningKeyword', 'input', () => { state.filters.warnings.keyword = document.getElementById('warningKeyword').value; renderWarnings(); });
    bindFilter('warningOrg', 'change', () => { state.filters.warnings.org = document.getElementById('warningOrg').value; renderWarnings(); });
    bindFilter('warningBusinessLine', 'change', () => { state.filters.warnings.businessLine = document.getElementById('warningBusinessLine').value; renderWarnings(); });
    bindFilter('warningType', 'change', () => { state.filters.warnings.type = document.getElementById('warningType').value; renderWarnings(); });
  }

  function renderPersons() {
    const rows = state.dashboard?.persons || [];
    const f = state.filters.persons;
    const filtered = rows.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || row.role_type === f.roleType)
      && (f.level === 'all' || row.membership_level === f.level)
    ));
    document.getElementById('persons').innerHTML = `
      <div class="panel-head">
        <div><h2>人员明细</h2><p>用于下钻到个人，支持按机构、项目、层级和会员等级筛选。</p></div>
        <div class="filter-bar">
          ${searchControl('personKeyword', '人员', f.keyword, '姓名/代码/机构')}
          ${selectControl('personOrg', '机构', f.org, optionValues(rows, 'org'))}
          ${selectControl('personBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
          ${selectControl('personRoleType', '层级', f.roleType, optionValues(rows, 'role_type'))}
          ${selectControl('personLevel', '等级', f.level, optionValues(rows, 'membership_level'))}
        </div>
      </div>
      <div id="personTable"></div>`;
    renderTable('personTable', filtered, ['org', 'business_line', 'role_type', 'staff_code', 'staff_name', 'membership_level', 'diamond_balance', 'total_gain', 'total_deduct', 'qualified_months', 'is_new_star']);
    bindFilter('personKeyword', 'input', () => { state.filters.persons.keyword = document.getElementById('personKeyword').value; renderPersons(); });
    bindFilter('personOrg', 'change', () => { state.filters.persons.org = document.getElementById('personOrg').value; renderPersons(); });
    bindFilter('personBusinessLine', 'change', () => { state.filters.persons.businessLine = document.getElementById('personBusinessLine').value; renderPersons(); });
    bindFilter('personRoleType', 'change', () => { state.filters.persons.roleType = document.getElementById('personRoleType').value; renderPersons(); });
    bindFilter('personLevel', 'change', () => { state.filters.persons.level = document.getElementById('personLevel').value; renderPersons(); });
  }

  function renderAudit(audit) {
    state.audit = audit;
    const rows = [];
    Object.values(audit.rawTables || {}).forEach(table => {
      (table.fields || []).forEach(field => rows.push({
        tableName: field.tableName,
        requiredField: field.requiredField,
        matchedColumn: field.matchedColumn || '-',
        requiredLevel: field.requiredLevel === 'required' ? '必需' : '可选',
        available: field.available ? '存在' : '缺失',
        impact: field.impact,
        fallbackStrategy: field.fallbackStrategy,
      }));
    });
    document.getElementById('audit').innerHTML = `
      <div class="panel-head">
        <div><h2>数据审计</h2><p>用于说明现有 Excel 与 raw 表是否支撑荣誉体系计算，不作为经营结果排名。</p></div>
      </div>
      <div class="summary-strip">
        <div class="summary-note"><strong>复用现有数据：</strong>${audit.canReuseExistingData ? '可以' : '不完整'}</div>
        <div class="summary-note"><strong>必需字段覆盖：</strong>${audit.requiredCoverage?.available || 0}/${audit.requiredCoverage?.total || 0}</div>
        <div class="summary-note"><strong>可选字段覆盖：</strong>${audit.optionalCoverage?.available || 0}/${audit.optionalCoverage?.total || 0}</div>
        <div class="summary-note"><strong>是否新增上传：</strong>${audit.needsHonorUpload ? '建议补充' : '本阶段不需要'}</div>
      </div>
      <div id="auditTable"></div>`;
    renderTable('auditTable', rows, ['tableName', 'requiredField', 'matchedColumn', 'requiredLevel', 'available', 'impact', 'fallbackStrategy']);
  }

  function renderAll() {
    const data = state.dashboard || {};
    renderMetricCards(data.overview || {});
    renderOverview();
    renderOrgs();
    renderProjects();
    renderSpecialists();
    renderManagers();
    renderWarnings();
    renderPersons();
  }

  async function loadDashboard(batchId) {
    const query = batchId ? `batchId=${encodeURIComponent(batchId)}` : `year=${document.getElementById('honorYear').value}&month=${document.getElementById('honorMonth').value}`;
    const data = await api(`/api/honor/dashboard?${query}`);
    state.dashboard = data;
    currentBatchId = data.batch?.id || batchId || currentBatchId;
    renderAll();
    setStatus(`已加载批次 ${currentBatchId}`, 'ok');
  }

  async function loadLatestOrAudit() {
    try {
      await loadDashboard(null);
    } catch (_) {
      await runAudit();
    }
  }

  async function runAudit() {
    setStatus('数据适配检查中...');
    const audit = await api('/api/honor/field-audit');
    currentBatchId = audit.batchId;
    renderAudit(audit);
    setStatus(`数据适配检查完成，批次 ${currentBatchId}`, 'ok');
  }

  async function recalculate() {
    const year = Number(document.getElementById('honorYear').value || 2026);
    const month = Number(document.getElementById('honorMonth').value || 12);
    setStatus('星钻重算中...');
    const result = await api('/api/honor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year, month, scope: 'all', force: true }),
    });
    await loadDashboard(result.batchId);
    setStatus(`重算完成，批次 ${result.batchId}，人员 ${result.personCount}，异常 ${result.exceptionCount}`, 'ok');
  }

  function exportExcel() {
    if (!currentBatchId) {
      setStatus('请先执行重算或加载批次后再导出。', 'warn');
      return;
    }
    window.location.href = `/api/honor/export?batchId=${currentBatchId}`;
  }

  function bindTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(item => item.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab)?.classList.add('active');
      });
    });
  }

  function bindActions() {
    document.getElementById('auditBtn')?.addEventListener('click', () => runAudit().catch(err => setStatus(err.message, 'bad')));
    document.getElementById('recalcBtn')?.addEventListener('click', () => recalculate().catch(err => setStatus(err.message, 'bad')));
    document.getElementById('exportBtn')?.addEventListener('click', exportExcel);
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requireLogin()) return;
    bindTabs();
    bindActions();
    renderMetricCards({});
    loadLatestOrAudit().catch(err => setStatus(err.message, 'bad'));
  });
})();
