(function () {
  const DEFAULT_SCHEME_ID = '2026-org-dev-policy';
  const state = {
    schemes: [],
    currentSchemeId: DEFAULT_SCHEME_ID,
    currentData: null,
    activeTab: 'overview'
  };

  function getUser() {
    return window.getCurrentUser?.() || null;
  }

  function hasPermission(key) {
    const user = getUser();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  function text(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function numberText(value, digits = 0) {
    const n = Number(value || 0);
    return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function moneyText(value) {
    return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }

  function rateText(value) {
    const n = Number(value || 0);
    return `${(n * 100).toFixed(1)}%`;
  }

  function statusPill(value) {
    const textValue = value || '-';
    if (textValue.includes('淘汰')) return `<span class="pill bad">${escapeHtml(textValue)}</span>`;
    if (textValue.includes('维持')) return `<span class="pill ok">${escapeHtml(textValue)}</span>`;
    return `<span class="pill">${escapeHtml(textValue)}</span>`;
  }

  function requireAccess() {
    const user = getUser();
    if (!window.getAuthToken?.() || !user) {
      window.location.href = '/';
      return false;
    }
    text('currentUserName', `${user.username} · ${user.roleLabel || user.role}`);
    if (!hasPermission('scheme_calculation')) {
      document.getElementById('pageMain')?.classList.add('hidden');
      document.getElementById('schemeSelector')?.classList.remove('active');
      document.getElementById('accessDenied')?.classList.remove('hidden');
      return false;
    }
    document.getElementById('pageMain')?.classList.remove('hidden');
    if (!hasPermission('scheme_upload')) {
      document.getElementById('schemeUploadPanel')?.classList.add('hidden');
    }
    return true;
  }

  async function loadOptions() {
    const payload = await window.fetchJson('/api/scheme/options');
    const data = window.unwrapApiResponse(payload);
    state.schemes = data.schemes || [];
    state.currentSchemeId = data.defaultSchemeId || DEFAULT_SCHEME_ID;
    renderSchemeChoices();
  }

  async function loadLatest() {
    const payload = await window.fetchJson(`/api/scheme/latest?schemeId=${encodeURIComponent(state.currentSchemeId)}`);
    state.currentData = window.unwrapApiResponse(payload);
    renderAll();
  }

  function currentScheme() {
    return state.schemes.find(item => item.id === state.currentSchemeId) || state.schemes[0] || {
      id: DEFAULT_SCHEME_ID,
      name: '2026年组发政策',
      period: { start: '2026-07-01', end: '2026-12-31' },
      entryWindow: { start: '2026-07-01', end: '2026-09-30' }
    };
  }

  function schemeButtonHtml(option) {
    const active = option.id === state.currentSchemeId ? ' active' : '';
    const period = option.period ? `${option.period.start} 至 ${option.period.end}` : '';
    return `
      <button class="scheme-choice${active}" data-scheme-id="${escapeHtml(option.id)}">
        <strong>${escapeHtml(option.name)}</strong>
        <span>${escapeHtml(option.scope || '方案测算')}</span>
        <span>${escapeHtml(period)}</span>
      </button>`;
  }

  function renderSchemeChoices() {
    const html = state.schemes.map(schemeButtonHtml).join('') || '<div class="empty">暂无可选方案</div>';
    const list = document.getElementById('schemeList');
    const selectorList = document.getElementById('schemeSelectorList');
    if (list) list.innerHTML = html;
    if (selectorList) selectorList.innerHTML = html;
    document.querySelectorAll('[data-scheme-id]').forEach(button => {
      button.addEventListener('click', () => {
        state.currentSchemeId = button.dataset.schemeId;
        renderSchemeChoices();
      });
    });
    const scheme = currentScheme();
    text('schemeTitle', scheme.name);
    if (scheme.period && scheme.entryWindow) {
      text('schemeMeta', `方案期：${scheme.period.start} 至 ${scheme.period.end}；入司窗口：${scheme.entryWindow.start} 至 ${scheme.entryWindow.end}`);
    }
  }

  function renderKpis(summary) {
    text('kpiTotalTeams', summary.totalTeams ?? '--');
    text('kpiQualifiedTeams', summary.qualifiedTeams ?? '--');
    text('kpiMaintainedTeams', summary.maintainedTeams ?? '--');
    text('kpiEliminatedTeams', summary.eliminatedTeams ?? '--');
    text('kpiTotalAward', summary.totalAward == null ? '--' : moneyText(summary.totalAward));
  }

  function renderWarnings(warnings) {
    text('warningCount', `${warnings.length}项`);
    const list = document.getElementById('warningList');
    if (!list) return;
    if (!warnings.length) {
      list.innerHTML = '<div class="empty">暂无复核提示</div>';
      return;
    }
    list.innerHTML = warnings.map(item => `
      <div class="warning ${item.level === 'high' ? 'high' : ''}">
        <div class="warning-title">${escapeHtml(item.title || '提示')}</div>
        <div>${escapeHtml(item.message || '')}</div>
      </div>`).join('');
  }

  function tableHtml(columns, rows) {
    if (!rows.length) return '<tbody><tr><td class="empty">暂无测算结果。请先选择方案，并通过“方案专用上传”导入对应底稿。</td></tr></tbody>';
    const head = `<thead><tr>${columns.map(col => `<th>${escapeHtml(col.label)}</th>`).join('')}</tr></thead>`;
    const body = rows.map(row => `
      <tr>${columns.map(col => `<td>${col.render ? col.render(row) : escapeHtml(row[col.key])}</td>`).join('')}</tr>`).join('');
    return `${head}<tbody>${body}</tbody>`;
  }

  function renderTable(id, columns, rows) {
    const table = document.getElementById(id);
    if (table) table.innerHTML = tableHtml(columns, rows);
  }

  function sectionRows(section) {
    return (state.currentData?.details?.rows || []).filter(row => row.section === section);
  }

  function monthlyRows(section) {
    return sectionRows(section).flatMap(row => (row.monthly || []).map(month => ({
      section: row.section,
      teamCode: row.teamCode,
      teamName: row.teamName,
      managerName: row.managerName,
      status: row.status,
      ...month
    })));
  }

  function renderOverview(summary) {
    const rows = summary.sections || [];
    renderTable('schemeOverviewTable', [
      { key: 'section', label: '测算类别' },
      { key: 'teamCount', label: '团队数' },
      { key: 'qualifiedTeamCount', label: '达标团队' },
      { key: 'maintainedTeamCount', label: '维持团队' },
      { key: 'eliminatedTeamCount', label: '淘汰团队' },
      { key: 'totalAward', label: '奖励合计', render: row => moneyText(row.totalAward) }
    ], rows);
  }

  function renderMonthlyTable(id, rows, includeSupervisorCount = false) {
    const columns = [
      { key: 'teamCode', label: '团队代码' },
      { key: 'teamName', label: '团队名称' },
      { key: 'managerName', label: '上级经理' },
      { key: 'month', label: '月份' },
      { key: 'schemeMonth', label: '方案月' },
      { key: 'manpower', label: '团队人力', render: row => numberText(row.manpower, 0) },
    ];
    if (includeSupervisorCount) {
      columns.push({ key: 'supervisorCount', label: '主管架构', render: row => numberText(row.supervisorCount, 0) });
    }
    columns.push(
      { key: 'activeRate', label: '开单率', render: row => rateText(row.activeRate) },
      { key: 'standardPremium', label: '首期标保(万)', render: row => numberText(row.standardPremium, 2) },
      { key: 'qualified', label: '团队达标', render: row => row.qualified ? '<span class="pill ok">达标</span>' : '<span class="pill">未达</span>' },
      { key: 'maintained', label: '维持资格', render: row => row.maintained ? '<span class="pill ok">维持</span>' : '<span class="pill">否</span>' },
      { key: 'finalAward', label: '最终奖励', render: row => moneyText(row.finalAward) },
      { key: 'status', label: '当前状态', render: row => statusPill(row.status) }
    );
    renderTable(id, columns, rows);
  }

  function renderPromotionTable() {
    renderTable('schemePromotionTable', [
      { key: 'teamCode', label: '团队代码' },
      { key: 'teamName', label: '团队名称' },
      { key: 'managerName', label: '原经理' },
      { key: 'month', label: '月份' },
      { key: 'manpower', label: '团队人力', render: row => numberText(row.manpower, 0) },
      { key: 'activeRate', label: '开单率', render: row => rateText(row.activeRate) },
      { key: 'standardPremium', label: '首期标保(万)', render: row => numberText(row.standardPremium, 2) },
      { key: 'organizationAward', label: '组织育成奖', render: row => moneyText(row.organizationAward) },
      { key: 'starAward', label: '星钻育成奖', render: row => moneyText(row.starAward) },
      { key: 'finalAward', label: '整体奖励', render: row => moneyText(row.finalAward) },
      { key: 'status', label: '当前状态', render: row => statusPill(row.status) }
    ], monthlyRows('晋升育成'));
  }

  function renderDefinitions() {
    const definitions = state.currentData?.definitions || {};
    const warnings = state.currentData?.warnings || [];
    const rows = Object.entries(definitions).map(([key, value]) => `
      <div class="warning">
        <div class="warning-title">${escapeHtml(key)}</div>
        <div>${escapeHtml(value)}</div>
      </div>`).join('');
    const gapRows = warnings.map(item => `
      <div class="warning ${item.level === 'high' ? 'high' : ''}">
        <div class="warning-title">${escapeHtml(item.title)}</div>
        <div>${escapeHtml(item.message)}</div>
      </div>`).join('');
    const el = document.getElementById('definitionList');
    if (el) el.innerHTML = rows + gapRows || '<div class="empty">暂无口径说明</div>';
  }

  function renderAll() {
    const data = state.currentData || {};
    const summary = data.summary || {};
    renderKpis(summary);
    renderWarnings(data.warnings || []);
    renderOverview(summary);
    renderMonthlyTable('schemeSupervisorTable', monthlyRows('引才奖-主管'));
    renderMonthlyTable('schemeManagerTable', monthlyRows('引才奖-经理'), true);
    renderPromotionTable();
    renderDefinitions();
    if (data.batch) {
      text('batchStatus', `批次 ${data.batch.id}；${data.batch.fileName}；${String(data.batch.importedAt || '').replace('T', ' ').slice(0, 19)}`);
    } else {
      text('batchStatus', '暂无测算批次');
    }
  }

  function switchTab(tab) {
    state.activeTab = tab;
    document.querySelectorAll('[data-scheme-tab]').forEach(button => {
      button.classList.toggle('active', button.dataset.schemeTab === tab);
    });
    const map = {
      overview: 'tabOverview',
      supervisor: 'tabSupervisor',
      manager: 'tabManager',
      promotion: 'tabPromotion',
      definitions: 'tabDefinitions'
    };
    Object.values(map).forEach(id => document.getElementById(id)?.classList.add('hidden'));
    document.getElementById(map[tab])?.classList.remove('hidden');
  }

  async function uploadWorkbook() {
    const file = document.getElementById('schemeTrackingFile')?.files?.[0];
    if (!file) {
      text('uploadStatus', '请选择方案测算 Excel。');
      return;
    }
    text('uploadStatus', '正在导入并测算...');
    const form = new FormData();
    form.append('schemeId', state.currentSchemeId);
    form.append('tracking', file);
    const resp = await window.authFetch(window.apiUrl('/api/scheme/upload'), { method: 'POST', body: form });
    const payload = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      text('uploadStatus', payload.detail || payload.message || '导入失败');
      return;
    }
    state.currentData = window.unwrapApiResponse(payload);
    text('uploadStatus', '导入完成，测算结果已刷新。');
    renderAll();
  }

  function bindActions() {
    document.querySelector('[data-scheme-action="home"]')?.addEventListener('click', () => {
      window.location.href = '/';
    });
    document.querySelector('[data-scheme-action="open-selector"]')?.addEventListener('click', () => {
      document.getElementById('schemeSelector')?.classList.add('active');
    });
    document.getElementById('confirmSchemeBtn')?.addEventListener('click', async () => {
      document.getElementById('schemeSelector')?.classList.remove('active');
      await loadLatest();
    });
    document.getElementById('schemeUploadBtn')?.addEventListener('click', uploadWorkbook);
    document.querySelectorAll('[data-scheme-tab]').forEach(button => {
      button.addEventListener('click', () => switchTab(button.dataset.schemeTab));
    });
  }

  async function init() {
    if (!requireAccess()) return;
    bindActions();
    try {
      await loadOptions();
      await loadLatest();
    } catch (err) {
      text('batchStatus', err.message || '方案数据加载失败');
      renderKpis({});
      renderWarnings([]);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
