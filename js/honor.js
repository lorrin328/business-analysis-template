(function () {
  let currentBatchId = null;
  let dashboardRequestSeq = 0;
  const state = {
    dashboard: null,
    audit: null,
    periods: [],
    filters: {
      tracking: { keyword: '', org: 'all', businessLine: 'all', roleType: 'all' },
      orgs: { keyword: '', businessLine: 'all' },
      projects: { businessLine: 'all' },
      specialists: { keyword: '', org: 'all', businessLine: 'all' },
      managers: { keyword: '', roleType: 'all', businessLine: 'all' },
      specialistHistory: { keyword: '', org: 'all', businessLine: 'all' },
      managerHistory: { keyword: '', org: 'all', businessLine: 'all', roleType: 'all' },
      warnings: { keyword: '', org: 'all', businessLine: 'all', type: 'all' },
      persons: { keyword: '', org: 'all', businessLine: 'all', roleType: 'all', level: 'all' },
      analysis: { keyword: '', businessLine: 'all' },
    },
  };

  const LABELS = {
    rank: '排名',
    dimension: '维度',
    org: '机构',
    business_line: '项目',
    role_type: '层级',
    staff_category: '外勤岗位类别',
    staff_code: '人员代码',
    staff_name: '人员姓名',
    manager_code: '主管/经理代码',
    manager_name: '主管/经理姓名',
    team_code: '团队代码',
    team_scope: '团队层级',
    data_note: '数据说明',
    tracked_headcount: '追踪人力',
    member_count: '会员人数',
    total_members: '会员数',
    oto_members: 'OTO会员',
    zhengbao_members: '证保会员',
    personal_members: '个人会员',
    specialist_members: '专员会员',
    supervisor_members: '主管会员',
    manager_members: '经理会员',
    management_members: '管理职会员',
    management_track_members: '管理职团队轨道会员',
    new_member_count: '新晋人数',
    promotion_count: '晋升人数',
    personal_member_count: '个人会员',
    management_staff_member_count: '管理职会员',
    supervisor_member_count: '主管会员',
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
    qualified_months: '累计获钻次数',
    is_new_star: '新星人力',
    warning_type: '预警类型',
    month: '月份',
    diamond_delta: '本月变化',
    standard_premium: '标保(万)',
    qj_premium: '期交保费(万)',
    team_qj_premium: '团队期交(万)',
    team_standard_premium: '团队标保(万)',
    team_tracked_headcount: '团队人力',
    star_manpower_count: '团队会员人数',
    specialist_member_count: '专员级会员',
    manager_member_count: '管理职会员',
    team_diamond_balance: '团队钻石',
    manager_diamond_balance: '管理职钻石',
    longterm_policy_count: '长险件数',
    tracking_policy_count: '当月件数',
    monthly_qualified: '当月达标',
    previous_level: '上月等级',
    current_level: '本月等级',
    standard_premium_gap: '标保差额(万)',
    premium_threshold: '达标标保(万)',
    premium_gap: '还差标保(万)',
    longterm_gap: '还缺长险件',
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
    'specialist_member_count', 'manager_member_count', 'team_diamond_balance',
    'manager_diamond_balance', 'longterm_policy_count', 'standard_premium_gap',
    'premium_threshold', 'premium_gap', 'longterm_gap',
    'count', 'gain_count', 'deduct_count', 'qualified_count',
    'total_members', 'oto_members', 'zhengbao_members', 'personal_members', 'specialist_members',
    'supervisor_members', 'manager_members', 'management_members',
    'management_track_members', 'management_staff_member_count',
    'new_member_count', 'promotion_count', 'personal_member_count',
    'supervisor_member_count', 'monthly_qualified', 'tracking_policy_count',
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
    if (!resp.ok) {
      let message = `${path} ${resp.status}`;
      try {
        const errorPayload = await resp.json();
        message = errorPayload.detail || errorPayload.message || message;
      } catch (_error) {
        // Keep the HTTP fallback when the response is not JSON.
      }
      throw new Error(message);
    }
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
    if (['standard_premium', 'qj_premium', 'team_qj_premium', 'team_standard_premium', 'standard_premium_gap', 'premium_threshold', 'premium_gap'].includes(key)) return value === '' ? '-' : numberText(Number(value || 0) / 10000, 2);
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

  function renderMetricCards(data = {}) {
    const overview = data.overview || {};
    const tracking = data.tracking || {};
    const trackingOverview = tracking.overview || {};
    const progress = data.qualificationProgress || {};
    const gapNote = progress.unqualifiedCount === undefined
      ? '读取当月达标情况'
      : `标保还差 ${numberText(Number(progress.premiumGapTotal || 0) / 10000, 2)}万；${numberText(progress.missingLongtermCount)}人还缺长险件`;
    const cards = [
      ['会员总数', numberText(trackingOverview.total_members ?? overview.member_count), `会员率 ${percentText(overview.member_rate)}`, 'result'],
      ['累计钻石', numberText(overview.total_diamond), '当前统计期', 'result'],
      ['本月新入会', numberText(trackingOverview.new_member_count), '首次达到会员标准', 'result'],
      ['本月晋级', numberText(trackingOverview.promotion_count), '会员等级提升', 'result'],
      ['本月未达标', numberText(progress.unqualifiedCount), gapNote, 'attention'],
    ];
    document.getElementById('honorCards').innerHTML = cards.map(([label, value, note, tone]) => `
      <article class="metric-card" data-tone="${tone}">
        <div class="metric-label">${escapeHtml(label)}</div>
        <div class="metric-value">${escapeHtml(value)}</div>
        <div class="metric-note">${escapeHtml(note)}</div>
      </article>`).join('');
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

  function renderBarList(targetId, rows, labelKey, valueKey, valueFormatter = numberText, limit = 8) {
    const target = document.getElementById(targetId);
    const max = Math.max(...rows.map(row => Number(row[valueKey] || 0)), 0);
    if (!rows.length || max <= 0) {
      target.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }
    target.innerHTML = rows.slice(0, limit).map(row => {
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

  function renderTracking() {
    const data = state.dashboard || {};
    const tracking = data.tracking || {};
    const overview = tracking.overview || {};
    const orgMembers = tracking.orgMembers || [];
    const newMembers = tracking.newMembers || [];
    const promotions = tracking.promotions || [];
    const progress = data.qualificationProgress || {};
    const sourceNote = tracking.trackingMode || (tracking.sourceCutoff ? `数据截至 ${tracking.sourceCutoff}` : '最终结果');
    const progressNote = data.batch?.resultNote || (tracking.sourceCutoff ? '以下为过程值，会随新单、入账和回销状态变化。' : '以下为最终结果。');
    document.getElementById('tracking').innerHTML = `
      <div class="panel-head">
        <div><h2>本月概况</h2><p>${escapeHtml(tracking.periodLabel || '-')} · ${escapeHtml(sourceNote)}</p></div>
      </div>
      <section class="structure-strip" aria-label="会员结构">
        <div class="structure-item"><span>OTO会员</span><strong>${numberText(overview.oto_members)}</strong></div>
        <div class="structure-item"><span>证保会员</span><strong>${numberText(overview.zhengbao_members)}</strong></div>
        <div class="structure-item"><span>专员会员</span><strong>${numberText(overview.specialist_members ?? overview.personal_members)}</strong></div>
        <div class="structure-item"><span>管理职会员</span><strong>${numberText(overview.management_members)}</strong></div>
      </section>
      <section class="panel-block detail-section">
        <h2>当月个人达标进度</h2>
        <p class="panel-note">${escapeHtml(progressNote)}主管、经理按团队规则计算，不并入个人差额。</p>
        <div class="structure-strip">
          <div class="structure-item"><span>个人追踪</span><strong>${numberText(progress.trackedCount)}</strong></div>
          <div class="structure-item"><span>已达标</span><strong>${numberText(progress.qualifiedCount)}</strong></div>
          <div class="structure-item"><span>未达标</span><strong>${numberText(progress.unqualifiedCount)}</strong></div>
          <div class="structure-item"><span>标保合计还差</span><strong>${numberText(Number(progress.premiumGapTotal || 0) / 10000, 2)}万</strong></div>
          <div class="structure-item"><span>还缺长险件</span><strong>${numberText(progress.missingLongtermCount)}人</strong></div>
        </div>
      </section>
      <div class="dashboard-grid">
        <section class="panel-block">
          <h2>机构会员</h2>
          <div id="trackingOrgBars"></div>
        </section>
        <section class="panel-block">
          <h2>本月贡献前三</h2>
          <div id="trackingTopContributors"></div>
        </section>
        <section class="panel-block wide">
          <h2>本月新入会</h2>
          <div id="trackingNewMembers"></div>
        </section>
        <section class="panel-block wide">
          <h2>本月晋级</h2>
          <div id="trackingPromotions"></div>
        </section>
      </div>`;
    renderBarList('trackingOrgBars', orgMembers, 'org', 'member_count', numberText, 12);
    renderTopContributors('trackingTopContributors', tracking.topContributors || []);
    renderMiniTable('trackingNewMembers', newMembers, ['rank', 'org', 'staff_name', 'business_line', 'role_type', 'membership_level', 'diamond_balance'], '本月暂无新入会会员');
    renderMiniTable('trackingPromotions', promotions, ['rank', 'org', 'staff_name', 'business_line', 'role_type', 'previous_level', 'membership_level'], '本月暂无晋级会员');
  }

  function renderTopContributors(targetId, rows) {
    const target = document.getElementById(targetId);
    if (!target) return;
    if (!rows.length) {
      target.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }
    target.innerHTML = `<div class="top-contributors">${rows.map(row => `
      <article class="top-person">
        <div class="avatar-mark">${escapeHtml(String(row.staff_name || '-').slice(-2))}</div>
        <div class="top-person-main">
          <div class="top-person-name">${escapeHtml(row.org || '')} ${escapeHtml(row.staff_name || '-')}</div>
          <div class="top-person-stats">
            <span><strong>${numberText(row.tracking_policy_count ?? row.longterm_policy_count)}</strong>件</span>
            <span><strong>${numberText(Number(row.standard_premium || 0) / 10000, 0)}</strong>万</span>
          </div>
        </div>
      </article>
    `).join('')}</div>`;
  }

  function renderOverview() {
    const data = state.dashboard || {};
    const overview = data.overview || {};
    const orgs = data.orgs || [];
    const projects = data.projects || [];
    const orgMemberStructure = data.orgMemberStructure || [];
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
          <h2>各机构会员结构</h2>
          <div id="overviewOrgMembers"></div>
        </section>
        <section class="panel-block wide">
          <h2>月度降级预警</h2>
          <div id="overviewWarnings"></div>
        </section>
      </div>`;
    renderMiniTable('overviewProjects', projects, ['rank', 'dimension', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count']);
    renderMiniTable('overviewOrgMembers', orgMemberStructure, ['rank', 'org', 'member_count', 'specialist_member_count', 'manager_member_count']);
    renderMiniTable('overviewWarnings', warnings, ['warning_type', 'org', 'business_line', 'staff_name', 'previous_level', 'current_level', 'standard_premium_gap', 'suggested_action']);
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
    const orgRows = state.dashboard?.projectOrgs || [];
    const f = state.filters.projects;
    const filtered = rows.filter(row => f.businessLine === 'all' || row.dimension === f.businessLine || row.business_line === f.businessLine);
    const orgFiltered = orgRows.filter(row => f.businessLine === 'all' || row.dimension === f.businessLine || row.business_line === f.businessLine);
    document.getElementById('projects').innerHTML = `
      <div class="panel-head">
        <div><h2>项目分析</h2><p>先看 OTO、证保整体表现，再下钻到项目下各机构的会员转化、获钻和扣减情况。</p></div>
        <div class="filter-bar">${selectControl('projectBusinessLine', '项目', f.businessLine, optionValues(rows, 'dimension'))}</div>
      </div>
      <div class="panel-block"><h3>项目整体表现</h3><div id="projectTable"></div></div>
      <div class="panel-block detail-section"><h3>项目下机构表现</h3><div id="projectOrgTable"></div></div>`;
    renderTable('projectTable', filtered, ['rank', 'dimension', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'estimated_reward']);
    renderTable('projectOrgTable', orgFiltered, ['rank', 'business_line', 'org', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond', 'estimated_reward']);
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
      <div class="panel-block"><h3>机构 / 项目整体表现</h3><div id="specialistTable"></div></div>
      <div class="panel-block detail-section"><h3>人员历史月度明细</h3><div id="specialistHistoryFilters"></div><div id="specialistHistoryTable"></div></div>`;
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
      <div class="panel-block"><h3>管理职整体表现</h3><div id="managerTable"></div></div>
      <div class="panel-block detail-section"><h3>主管 / 经理历史团队表现</h3><div id="managerHistoryFilters"></div><div id="managerHistoryTable"></div></div>`;
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
    const filters = document.getElementById('specialistHistoryFilters');
    if (filters) filters.innerHTML = `
      <div class="filter-bar compact-history-filter">
        ${searchControl('specialistHistoryKeyword', '人员', f.keyword, '代码/姓名/机构')}
        ${selectControl('specialistHistoryOrg', '机构', f.org, optionValues(rows, 'org'))}
        ${selectControl('specialistHistoryBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
      </div>`;
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
    const filters = document.getElementById('managerHistoryFilters');
    if (filters) filters.innerHTML = `
      <div class="filter-bar compact-history-filter">
        ${searchControl('managerHistoryKeyword', '主管/经理', f.keyword, '代码/姓名/团队')}
        ${selectControl('managerHistoryOrg', '机构', f.org, optionValues(rows, 'org'))}
        ${selectControl('managerHistoryBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
        ${selectControl('managerHistoryRoleType', '层级', f.roleType, optionValues(rows, 'role_type'))}
      </div>`;
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
        <div><h2>月度预警</h2><p>优先展示本月较上月发生等级下降的人员，并列明降级原因和标保差额。</p></div>
        <div class="filter-bar">
          ${searchControl('warningKeyword', '筛选', f.keyword, '姓名/代码/机构/动作')}
          ${selectControl('warningOrg', '机构', f.org, optionValues(rows, 'org'))}
          ${selectControl('warningBusinessLine', '项目', f.businessLine, optionValues(rows, 'business_line'))}
          ${selectControl('warningType', '类型', f.type, optionValues(rows, 'warning_type'))}
        </div>
      </div>
      <div id="warningTable"></div>`;
    renderTable('warningTable', filtered, ['warning_type', 'month', 'org', 'business_line', 'staff_code', 'staff_name', 'role_type', 'previous_level', 'current_level', 'diamond_balance', 'diamond_delta', 'standard_premium', 'standard_premium_gap', 'longterm_policy_count', 'suggested_action']);
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

  function renderAnalysis() {
    const orgRows = state.dashboard?.orgs || [];
    const projectRows = state.dashboard?.projects || [];
    const f = state.filters.analysis;
    const businessLines = [...new Set([
      ...orgRows.map(row => row.business_line),
      ...projectRows.map(row => row.dimension || row.business_line),
    ].filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'));
    const filteredOrgs = orgRows.filter(row => (
      matchesKeyword(row, f.keyword, ['org', 'business_line'])
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    const filteredProjects = projectRows.filter(row => (
      matchesKeyword(row, f.keyword, ['dimension', 'business_line'])
      && (f.businessLine === 'all' || row.dimension === f.businessLine || row.business_line === f.businessLine)
    ));
    document.getElementById('analysis').innerHTML = `
      <div class="panel-head">
        <div><h2>机构与项目</h2><p>比较 OTO、证保及各机构的会员、获钻和扣钻情况。</p></div>
        <div class="filter-bar">
          ${searchControl('analysisKeyword', '筛选', f.keyword, '机构/项目')}
          ${selectControl('analysisBusinessLine', '项目', f.businessLine, businessLines)}
        </div>
      </div>
      <div class="section-stack">
        <section class="panel-block">
          <h3>机构表现</h3>
          <div class="result-count">共 ${numberText(filteredOrgs.length)} 条</div>
          <div id="analysisOrgTable"></div>
        </section>
        <section class="panel-block">
          <h3>项目表现</h3>
          <div class="result-count">共 ${numberText(filteredProjects.length)} 条</div>
          <div id="analysisProjectTable"></div>
        </section>
      </div>`;
    renderTable('analysisOrgTable', filteredOrgs, ['rank', 'org', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count', 'estimated_reward']);
    renderTable('analysisProjectTable', filteredProjects, ['rank', 'dimension', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count', 'estimated_reward']);
    bindFilter('analysisKeyword', 'input', () => {
      state.filters.analysis.keyword = document.getElementById('analysisKeyword').value;
      renderAnalysis();
    });
    bindFilter('analysisBusinessLine', 'change', () => {
      state.filters.analysis.businessLine = document.getElementById('analysisBusinessLine').value;
      renderAnalysis();
    });
  }

  function renderPeople() {
    const tracking = state.dashboard?.tracking || {};
    const roster = tracking.memberRoster || [];
    const warnings = state.dashboard?.warnings || [];
    const gapRows = state.dashboard?.qualificationProgress?.rows || [];
    const specialistHistory = state.dashboard?.specialistHistory || [];
    const managerHistory = state.dashboard?.managerHistory || [];
    const f = state.filters.persons;
    const allRows = [...roster, ...gapRows, ...warnings, ...specialistHistory, ...managerHistory];
    const filteredRoster = roster.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || row.role_type === f.roleType)
      && (f.level === 'all' || row.membership_level === f.level)
    ));
    const filteredWarnings = warnings.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org', 'suggested_action'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || row.role_type === f.roleType)
    ));
    const filteredGapRows = gapRows.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || f.roleType === '个人')
    ));
    const filteredSpecialists = specialistHistory.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    const filteredManagers = managerHistory.filter(row => (
      matchesKeyword(row, f.keyword, ['manager_code', 'manager_name', 'org', 'team_code'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.roleType === 'all' || row.role_type === f.roleType)
    ));
    document.getElementById('people').innerHTML = `
      <div class="panel-head">
        <div><h2>人员追踪</h2><p>先看当月未达标及具体差额，再查看等级变化、数据待核对项和历史表现。</p></div>
      </div>
      <div class="filter-bar">
        ${searchControl('peopleKeyword', '人员', f.keyword, '姓名/代码/机构')}
        ${selectControl('peopleOrg', '机构', f.org, optionValues(allRows, 'org'))}
        ${selectControl('peopleBusinessLine', '项目', f.businessLine, optionValues(allRows, 'business_line'))}
        ${selectControl('peopleRoleType', '层级', f.roleType, optionValues(allRows, 'role_type'))}
        ${selectControl('peopleLevel', '会员等级', f.level, optionValues(roster, 'membership_level'))}
      </div>
      <div class="section-stack">
        <details open>
          <summary>本月未达标（${numberText(filteredGapRows.length)}）</summary>
          <div id="peopleGapTable"></div>
        </details>
        <details>
          <summary>等级变化与数据待核对（${numberText(filteredWarnings.length)}）</summary>
          <div id="peopleWarningTable"></div>
        </details>
        <details>
          <summary>会员名单（${numberText(filteredRoster.length)}）</summary>
          <div id="peopleRosterTable"></div>
        </details>
        <details>
          <summary>专员历史（${numberText(filteredSpecialists.length)}）</summary>
          <div id="peopleSpecialistTable"></div>
        </details>
        <details>
          <summary>主管和经理历史（${numberText(filteredManagers.length)}）</summary>
          <div id="peopleManagerTable"></div>
        </details>
      </div>`;
    renderTable('peopleGapTable', filteredGapRows, ['org', 'business_line', 'staff_code', 'staff_name', 'membership_level', 'standard_premium', 'premium_threshold', 'premium_gap', 'longterm_policy_count', 'longterm_gap'], '当前筛选范围内没有未达标人员');
    renderTable('peopleWarningTable', filteredWarnings, ['warning_type', 'org', 'business_line', 'staff_name', 'role_type', 'previous_level', 'current_level', 'standard_premium_gap', 'suggested_action'], '当前筛选范围内没有等级变化或数据待核对项');
    renderTable('peopleRosterTable', filteredRoster, ['rank', 'staff_code', 'staff_name', 'org', 'business_line', 'role_type', 'membership_level', 'diamond_balance', 'tracking_policy_count', 'qualified_months']);
    renderTable('peopleSpecialistTable', filteredSpecialists, ['org', 'business_line', 'staff_code', 'staff_name', 'month', 'standard_premium', 'longterm_policy_count', 'diamond_delta', 'diamond_balance', 'membership_level']);
    renderTable('peopleManagerTable', filteredManagers, ['org', 'business_line', 'role_type', 'manager_code', 'manager_name', 'month', 'team_tracked_headcount', 'star_manpower_count', 'team_diamond_balance', 'manager_diamond_balance', 'monthly_gain_count', 'monthly_deduct_count']);
    bindFilter('peopleKeyword', 'input', () => { state.filters.persons.keyword = document.getElementById('peopleKeyword').value; renderPeople(); });
    bindFilter('peopleOrg', 'change', () => { state.filters.persons.org = document.getElementById('peopleOrg').value; renderPeople(); });
    bindFilter('peopleBusinessLine', 'change', () => { state.filters.persons.businessLine = document.getElementById('peopleBusinessLine').value; renderPeople(); });
    bindFilter('peopleRoleType', 'change', () => { state.filters.persons.roleType = document.getElementById('peopleRoleType').value; renderPeople(); });
    bindFilter('peopleLevel', 'change', () => { state.filters.persons.level = document.getElementById('peopleLevel').value; renderPeople(); });
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
    document.getElementById('auditResult').innerHTML = `
      <div class="panel-head">
        <div><h2>数据检查结果</h2><p>检查源表字段是否完整，供重新测算前核对使用。</p></div>
      </div>
      <div class="summary-strip">
        <div class="summary-note"><strong>现有数据：</strong>${audit.canReuseExistingData ? '可以使用' : '需要补充'}</div>
        <div class="summary-note"><strong>必需字段覆盖：</strong>${audit.requiredCoverage?.available || 0}/${audit.requiredCoverage?.total || 0}</div>
        <div class="summary-note"><strong>可选字段覆盖：</strong>${audit.optionalCoverage?.available || 0}/${audit.optionalCoverage?.total || 0}</div>
        <div class="summary-note"><strong>是否需要补充数据：</strong>${audit.needsHonorUpload ? '需要' : '不需要'}</div>
      </div>
      <div id="auditTable"></div>`;
    renderTable('auditTable', rows, ['tableName', 'requiredField', 'matchedColumn', 'requiredLevel', 'available', 'impact', 'fallbackStrategy']);
  }

  function renderAll() {
    const data = state.dashboard || {};
    renderMetricCards(data);
    renderTracking();
    renderAnalysis();
    renderPeople();
    const batch = data.batch || {};
    const resultLabel = batch.resultLabel || cutoffLabel(batch.year, batch.month, batch);
    const batchSummary = document.getElementById('batchSummary');
    if (batchSummary) {
      batchSummary.innerHTML = `<strong>当前数据：</strong>${escapeHtml(`${batch.year || '-'}年${resultLabel}`)}；规则版本 ${escapeHtml(batch.rule_version || '-') }；批次 ${escapeHtml(batch.id || '-')}`;
    }
  }

  function cutoffLabel(year, month, version) {
    if (version?.resultLabel) return version.resultLabel;
    const cutoff = typeof version === 'object' ? version?.sourceCutoff || version?.source_cutoff : version;
    if (!cutoff) return `${month}月最终结果`;
    const parts = String(cutoff).split('-').map(Number);
    if (parts[0] === Number(year) && parts[1] === Number(month)) {
      return `截至${parts[1]}月${parts[2]}日（过程）`;
    }
    return `后续状态更新至${parts[1]}月${parts[2]}日`;
  }

  function renderPeriodNote(batch) {
    const target = document.getElementById('honorPeriodNote');
    if (!target || !batch) return;
    const resultLabel = batch.resultLabel || cutoffLabel(batch.year, batch.month, batch);
    const resultNote = batch.resultNote || '';
    target.textContent = `${batch.year}年${resultLabel}。${resultNote}`;
  }

  function selectedPeriod() {
    const year = Number(document.getElementById('honorYear')?.value || 0);
    const month = Number(document.getElementById('honorMonth')?.value || 0);
    return state.periods.find(item => Number(item.year) === year && Number(item.month) === month) || null;
  }

  function renderPeriodAction() {
    const target = document.getElementById('honorPeriodAction');
    if (!target) return;
    const period = selectedPeriod();
    target.classList.remove('visible');
    target.innerHTML = '';
    if (!period) return;

    const availability = period.dataAvailability || {};
    const channelCutoffs = availability.channelCutoffs || {};
    const activityNote = ['OTO', '证保']
      .filter(line => channelCutoffs[line])
      .map(line => `${line}最近出单${formatShortDate(channelCutoffs[line])}`)
      .join('，');
    if (period.latestDataCutoff && !period.latestDataBatchAvailable) {
      const cutoff = formatDateLabel(period.latestDataCutoff);
      const missingLines = availability.missingStaffChannels || [];
      if (!availability.canCalculate) {
        const reason = missingLines.length
          ? `${missingLines.join('、')}当月人力数据尚未就绪`
          : '数据截止日异常';
        target.innerHTML = `<span>业绩数据已到${escapeHtml(cutoff)}，但${escapeHtml(reason)}，暂不能生成星钻过程结果。</span>`;
        target.classList.add('visible');
        return;
      }
      const button = hasPermission('honor_recalculate')
        ? `<button id="createLatestDataBatchBtn" class="primary" type="button">生成截至${escapeHtml(formatShortDate(period.latestDataCutoff))}数据</button>`
        : '';
      const permissionNote = button ? '' : ' 请由有重算权限的管理员更新。';
      target.innerHTML = `<span>业绩数据已更新至${escapeHtml(cutoff)}，星钻尚未生成同口径过程结果。生成后可查看还差标保和还缺长险件。${escapeHtml(activityNote ? ` ${activityNote}。` : '')}${escapeHtml(permissionNote)}</span>${button}`;
      target.classList.add('visible');
      document.getElementById('createLatestDataBatchBtn')?.addEventListener('click', () => {
        createLatestDataBatch().catch(err => setStatus(err.message, 'bad'));
      });
      return;
    }
    if (period.latestDataBatchAvailable && period.latestDataCutoff) {
      const selectedBatchId = Number(document.getElementById('honorBatch')?.value || 0);
      const viewingLatest = selectedBatchId === Number(period.latestDataBatchId);
      const prefix = viewingLatest
        ? `当前星钻结果已按最新业绩数据计算至${formatDateLabel(period.latestDataCutoff)}。`
        : `最新过程结果已计算至${formatDateLabel(period.latestDataCutoff)}；当前查看的是历史版本。`;
      target.innerHTML = `<span>${escapeHtml(prefix)}${escapeHtml(activityNote ? `${activityNote}。` : '')}</span>`;
      target.classList.add('visible');
      return;
    }
    if (period.finalAvailable) return;

    const finalDate = formatDateLabel(period.finalReadyOn);
    if (period.monthEndSnapshotAvailable) {
      target.innerHTML = `<span>月末快照已生成；最终结果需等45天回销观察结束，最早于${escapeHtml(finalDate)}生成。</span>`;
      target.classList.add('visible');
      return;
    }
    if (!period.canCreateMonthEndSnapshot) return;

    const monthEnd = formatDateLabel(period.monthEnd);
    const button = hasPermission('honor_recalculate')
      ? '<button id="createMonthEndSnapshotBtn" class="primary" type="button">生成月末快照</button>'
      : '';
    target.innerHTML = `<span>尚未生成${escapeHtml(monthEnd)}月末快照。该版本覆盖整月业绩，但仍需等待回销观察。</span>${button}`;
    target.classList.add('visible');
    document.getElementById('createMonthEndSnapshotBtn')?.addEventListener('click', () => {
      createMonthEndSnapshot().catch(err => setStatus(err.message, 'bad'));
    });
  }

  function formatDateLabel(value) {
    const parts = String(value || '').split('-').map(Number);
    if (parts.length !== 3 || parts.some(item => !Number.isFinite(item))) return value || '-';
    return `${parts[0]}年${parts[1]}月${parts[2]}日`;
  }

  function formatShortDate(value) {
    const parts = String(value || '').split('-').map(Number);
    if (parts.length !== 3 || parts.some(item => !Number.isFinite(item))) return value || '-';
    return `${parts[1]}月${parts[2]}日`;
  }

  function renderBatchOptions(preferredBatchId = null) {
    const year = Number(document.getElementById('honorYear').value);
    const month = Number(document.getElementById('honorMonth').value);
    const period = state.periods.find(item => Number(item.year) === year && Number(item.month) === month);
    const batchSelect = document.getElementById('honorBatch');
    const versions = period?.versions || [];
    batchSelect.innerHTML = versions.length
      ? versions.map(version => `<option value="${escapeHtml(version.batchId)}">${escapeHtml(cutoffLabel(year, month, version))}</option>`).join('')
      : `<option value="">${period?.latestDataCutoff ? `待生成截至${escapeHtml(formatShortDate(period.latestDataCutoff))}数据` : '暂无结果'}</option>`;
    const selected = versions.some(item => Number(item.batchId) === Number(preferredBatchId))
      ? Number(preferredBatchId)
      : Number(period?.recommendedBatchId || versions[0]?.batchId || 0);
    if (selected) batchSelect.value = String(selected);
    renderPeriodAction();
    return selected;
  }

  function renderPendingPeriod(period) {
    state.dashboard = null;
    currentBatchId = null;
    renderMetricCards({});
    ['tracking', 'analysis', 'people'].forEach(id => {
      const target = document.getElementById(id);
      if (target) target.innerHTML = '<div class="empty">请先生成所选月份的最新过程数据。</div>';
    });
    const cutoff = formatDateLabel(period?.latestDataCutoff);
    const asOfInput = document.getElementById('honorAsOf');
    if (asOfInput) {
      asOfInput.value = period?.latestDataCutoff || '';
      asOfInput.max = period?.latestDataCutoff || '';
    }
    const periodNote = document.getElementById('honorPeriodNote');
    if (periodNote) periodNote.textContent = `${period?.year || '-'}年${period?.month || '-'}月业绩数据已到${cutoff}，尚无同口径星钻测算结果。`;
    const batchSummary = document.getElementById('batchSummary');
    if (batchSummary) batchSummary.innerHTML = '<strong>当前数据：</strong>尚未生成所选月份过程结果。';
    renderPeriodAction();
  }

  function renderMonthOptions(preferredMonth = null) {
    const year = Number(document.getElementById('honorYear').value);
    const monthSelect = document.getElementById('honorMonth');
    const months = state.periods
      .filter(item => Number(item.year) === year)
      .map(item => Number(item.month))
      .sort((a, b) => a - b);
    monthSelect.innerHTML = months.length
      ? months.map(month => `<option value="${month}">${month}月</option>`).join('')
      : '<option value="">暂无结果</option>';
    const selected = months.includes(Number(preferredMonth)) ? Number(preferredMonth) : months[months.length - 1];
    if (selected) monthSelect.value = String(selected);
    return selected;
  }

  async function loadAvailablePeriods(preferredBatchId = null) {
    const payload = await api('/api/honor/periods');
    state.periods = payload.periods || [];
    const yearSelect = document.getElementById('honorYear');
    const currentYear = Number(yearSelect.value);
    const years = payload.years || [];
    yearSelect.innerHTML = years.length
      ? years.map(year => `<option value="${escapeHtml(year)}">${escapeHtml(year)}年</option>`).join('')
      : '<option value="">暂无结果</option>';
    const preferredPeriod = preferredBatchId
      ? state.periods.find(item => (item.versions || []).some(version => Number(version.batchId) === Number(preferredBatchId)))
      : null;
    const selectedYear = preferredPeriod?.year || (years.includes(currentYear) ? currentYear : years[0]);
    if (selectedYear) yearSelect.value = String(selectedYear);
    const selectedMonth = renderMonthOptions(preferredPeriod?.month);
    const selectedBatchId = renderBatchOptions(preferredBatchId);
    if (!selectedMonth) {
      setStatus('暂无可查看的星钻测算结果', 'warn');
      return;
    }
    if (!selectedBatchId) {
      const period = selectedPeriod();
      renderPendingPeriod(period);
      setStatus(period?.latestDataCutoff ? `${selectedMonth}月数据待生成` : '暂无可查看的星钻测算结果', 'warn');
      return;
    }
    await loadDashboard(selectedBatchId);
  }

  async function loadDashboard(batchId) {
    const requestSeq = ++dashboardRequestSeq;
    const query = `batchId=${encodeURIComponent(batchId)}`;
    const data = await api(`/api/honor/dashboard?${query}`);
    if (requestSeq !== dashboardRequestSeq) return;
    state.dashboard = data;
    currentBatchId = data.batch?.id || batchId || currentBatchId;
    if (data.batch?.year) document.getElementById('honorYear').value = data.batch.year;
    if (data.batch?.month) document.getElementById('honorMonth').value = data.batch.month;
    document.getElementById('honorAsOf').value = data.batch?.source_cutoff || '';
    document.getElementById('honorBatch').value = String(currentBatchId);
    renderAll();
    renderPeriodNote(data.batch);
    renderPeriodAction();
    const resultLabel = data.batch?.resultLabel || cutoffLabel(data.batch?.year, data.batch?.month, data.batch);
    setStatus(`${data.batch?.year || '-'}年${resultLabel}`, 'ok');
  }

  async function runAudit() {
    setStatus('正在检查数据...');
    const audit = await api('/api/honor/field-audit');
    currentBatchId = audit.batchId;
    renderAudit(audit);
    setStatus('数据检查完成', 'ok');
  }

  async function recalculate() {
    const year = Number(document.getElementById('honorYear').value || 2026);
    const month = Number(document.getElementById('honorMonth').value || 12);
    const asOf = document.getElementById('honorAsOf')?.value || '';
    setStatus('正在重新测算...');
    const result = await api('/api/honor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year, month, asOf, scope: 'all', force: true }),
    });
    await loadAvailablePeriods(result.batchId);
    setStatus(`${result.resultLabel || '测算完成'}：${result.personCount}人，${result.exceptionCount}条待核对记录`, 'ok');
  }

  async function createMonthEndSnapshot() {
    const period = selectedPeriod();
    if (!period?.monthEnd) throw new Error('无法确定所选月份的月末日期');
    setStatus('正在生成月末快照...');
    const result = await api('/api/honor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year: period.year, month: period.month, asOf: period.monthEnd, scope: 'all', force: true }),
    });
    await loadAvailablePeriods(result.batchId);
    setStatus(`${result.resultLabel || '月末快照'}生成完成：${result.personCount}人，${result.exceptionCount}条待核对记录`, 'ok');
  }

  async function createLatestDataBatch() {
    const period = selectedPeriod();
    if (!period?.latestDataCutoff) throw new Error('无法确定最新业绩数据截止日');
    setStatus(`正在生成截至${formatShortDate(period.latestDataCutoff)}的过程数据...`);
    const result = await api('/api/honor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        year: period.year,
        month: period.month,
        asOf: period.latestDataCutoff,
        scope: 'all',
        force: true,
      }),
    });
    await loadAvailablePeriods(result.batchId);
    setStatus(`${result.resultLabel || '过程数据'}生成完成：${result.personCount}人，${result.exceptionCount}条待核对记录`, 'ok');
  }

  function exportExcel() {
    if (!currentBatchId) {
      setStatus('请先加载数据或重新测算后再导出。', 'warn');
      return;
    }
    window.location.href = `/api/honor/export?batchId=${currentBatchId}`;
  }

  function bindTabs() {
    const tabs = Array.from(document.querySelectorAll('.tab[role="tab"]'));
    function activate(tab, focus = false) {
      tabs.forEach(item => {
        const selected = item === tab;
        item.classList.toggle('active', selected);
        item.setAttribute('aria-selected', String(selected));
        item.tabIndex = selected ? 0 : -1;
      });
      document.querySelectorAll('.panel[role="tabpanel"]').forEach(panel => panel.classList.toggle('active', panel.id === tab.dataset.tab));
      if (focus) tab.focus();
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab));
      tab.addEventListener('keydown', event => {
        let nextIndex = null;
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = tabs.length - 1;
        if (nextIndex == null) return;
        event.preventDefault();
        activate(tabs[nextIndex], true);
      });
    });
  }

  function bindActions() {
    document.getElementById('auditBtn')?.addEventListener('click', () => runAudit().catch(err => setStatus(err.message, 'bad')));
    document.getElementById('recalcBtn')?.addEventListener('click', () => recalculate().catch(err => setStatus(err.message, 'bad')));
    document.getElementById('exportBtn')?.addEventListener('click', exportExcel);
    document.getElementById('honorYear')?.addEventListener('change', () => {
      renderMonthOptions();
      const batchId = renderBatchOptions();
      if (batchId) {
        loadDashboard(batchId).catch(err => setStatus(err.message, 'bad'));
      } else {
        renderPendingPeriod(selectedPeriod());
        setStatus(`${document.getElementById('honorMonth').value}月数据待生成`, 'warn');
      }
    });
    document.getElementById('honorMonth')?.addEventListener('change', () => {
      const batchId = renderBatchOptions();
      if (batchId) {
        loadDashboard(batchId).catch(err => setStatus(err.message, 'bad'));
      } else {
        renderPendingPeriod(selectedPeriod());
        setStatus(`${document.getElementById('honorMonth').value}月数据待生成`, 'warn');
      }
    });
    document.getElementById('honorBatch')?.addEventListener('change', event => {
      const batchId = Number(event.target.value || 0);
      if (batchId) loadDashboard(batchId).catch(err => setStatus(err.message, 'bad'));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requireLogin()) return;
    bindTabs();
    bindActions();
    renderMetricCards({});
    loadAvailablePeriods().catch(err => setStatus(err.message, 'bad'));
  });
})();
