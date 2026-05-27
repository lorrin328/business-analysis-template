(function () {
  let currentBatchId = null;
  const state = {
    persons: [],
    orgs: [],
    exceptions: [],
    trend: [],
    audit: null,
    filters: {
      orgs: { keyword: '', businessLine: 'all' },
      persons: { keyword: '', org: 'all', businessLine: 'all', level: 'all', newStar: false },
      warnings: { keyword: '', org: 'all', type: 'all' },
      exceptions: { keyword: '', org: 'all', severity: 'all', type: 'all' },
    },
  };

  const COLUMN_LABELS = {
    rank: '排名',
    org: '机构',
    business_line: '业务模式',
    tracked_headcount: '跟踪人力',
    member_count: '会员人数',
    member_rate: '会员率',
    avg_diamond: '人均钻石',
    monthly_gain_count: '本月获钻',
    monthly_deduct_count: '本月扣减',
    total_diamond: '累计钻石',
    estimated_reward: '预计奖励',
    staff_code: '人员代码',
    staff_name: '人员姓名',
    membership_level: '会员等级',
    diamond_balance: '当前钻石',
    total_gain: '累计获钻',
    total_deduct: '累计扣减',
    qualified_months: '达标月份',
    is_new_star: '新星人力',
    severity: '等级',
    exception_type: '异常类型',
    policy_no: '保单号',
    message: '异常说明',
    suggested_action: '建议动作',
    month: '月份',
    gainCount: '获钻人数',
    deductCount: '扣减人数',
    memberCount: '会员人数',
    level: '会员等级',
    count: '人数',
  };

  const EXCEPTION_TYPE_LABELS = {
    negative_premium: '负数保费',
    missing_staff_code: '缺少人员代码',
    missing_staff_name: '缺少人员姓名',
    missing_policy_no: '缺少保单号',
    missing_entry_month: '缺少入职月份',
    fallback_period: '归属月份降级',
    insufficient_fields: '字段不足',
  };

  const SEVERITY_LABELS = {
    info: '提示',
    warning: '预警',
    error: '错误',
  };

  const NUMERIC_COLUMNS = new Set([
    'rank',
    'tracked_headcount',
    'member_count',
    'monthly_gain_count',
    'monthly_deduct_count',
    'total_diamond',
    'estimated_reward',
    'diamond_balance',
    'total_gain',
    'total_deduct',
    'qualified_months',
    'gainCount',
    'deductCount',
    'memberCount',
    'count',
  ]);

  function hasPermission(key) {
    const user = window.getCurrentUser?.();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function setStatus(message, cls = 'muted') {
    const el = document.getElementById('honorStatus');
    if (!el) return;
    el.textContent = message || '';
    el.className = `status-pill ${cls}`;
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

  function numberText(v, digits = 0) {
    if (v === null || v === undefined || v === '') return '-';
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    return n.toLocaleString('zh-CN', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function percentText(v) {
    if (v === null || v === undefined || v === '') return '-';
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    return `${(n * 100).toFixed(1)}%`;
  }

  function typeText(v) {
    return EXCEPTION_TYPE_LABELS[v] || v || '-';
  }

  function severityText(v) {
    return SEVERITY_LABELS[v] || v || '-';
  }

  function formatCell(key, value) {
    if (value === null || value === undefined || value === '') return '-';
    if (key === 'member_rate') return percentText(value);
    if (key === 'avg_diamond') return `${numberText(value, 1)}颗`;
    if (key === 'estimated_reward') return `${numberText(value, 0)}元`;
    if (key === 'is_new_star') return Number(value) ? '是' : '否';
    if (key === 'month') return `${value}月`;
    if (key === 'exception_type') return typeText(value);
    if (key === 'severity') return severityText(value);
    if (NUMERIC_COLUMNS.has(key)) return numberText(value, 0);
    return value;
  }

  function cardValue(v, suffix = '', digits = 0) {
    if (v === null || v === undefined || v === '') return '-';
    return `${numberText(v, digits)}${suffix}`;
  }

  function optionValues(rows, key) {
    return [...new Set((rows || []).map(row => row[key]).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'));
  }

  function matchesKeyword(row, keyword, keys) {
    if (!keyword) return true;
    const text = keyword.trim().toLowerCase();
    return keys.some(key => String(row[key] || '').toLowerCase().includes(text));
  }

  function renderCards(overview = {}) {
    const cards = [
      ['当前跟踪人力', cardValue(overview.tracked_headcount, '人')],
      ['会员人数', cardValue(overview.member_count, '人')],
      ['会员率', percentText(overview.member_rate || 0)],
      ['资深及以上', cardValue(overview.senior_plus_count, '人')],
      ['本月获钻人数', cardValue(overview.monthly_gain_count, '人')],
      ['本月扣减人数', cardValue(overview.monthly_deduct_count, '人')],
      ['累计钻石', cardValue(overview.total_diamond, '颗')],
      ['新星人力', cardValue(overview.new_star_count, '人')],
      ['预计季度奖励', cardValue(overview.estimated_reward, '元')],
      ['异常数量', cardValue(overview.exception_count, '条')],
    ];
    document.getElementById('honorCards').innerHTML = cards.map(([label, val]) => `
      <div class="card"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(val)}</div></div>
    `).join('');
  }

  function renderTable(targetId, rows, columns, title = '', options = {}) {
    const el = document.getElementById(targetId);
    const toolbar = options.toolbar || '';
    const note = options.note ? `<div class="panel-note">${escapeHtml(options.note)}</div>` : '';
    if (!rows || !rows.length) {
      el.innerHTML = `${title ? `<div class="panel-title">${escapeHtml(title)}</div>` : ''}${note}${toolbar}<div class="empty">暂无数据</div>`;
      return;
    }
    const keys = columns || Object.keys(rows[0]);
    el.innerHTML = `
      ${title ? `<div class="panel-title">${escapeHtml(title)}</div>` : ''}
      ${note}
      ${toolbar}
      <div class="table-wrap">
        <table>
          <thead><tr>${keys.map(k => `<th class="${NUMERIC_COLUMNS.has(k) || k === 'member_rate' || k === 'avg_diamond' ? 'num' : ''}">${escapeHtml(COLUMN_LABELS[k] || k)}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.map(row => `<tr>${keys.map(k => `<td class="${NUMERIC_COLUMNS.has(k) || k === 'member_rate' || k === 'avg_diamond' ? 'num' : ''}">${escapeHtml(formatCell(k, row[k]))}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderSelect(id, label, value, values, allLabel = '全部') {
    return `
      <label>${escapeHtml(label)}
        <select id="${escapeHtml(id)}">
          <option value="all"${value === 'all' ? ' selected' : ''}>${escapeHtml(allLabel)}</option>
          ${values.map(v => `<option value="${escapeHtml(v)}"${String(value) === String(v) ? ' selected' : ''}>${escapeHtml(v)}</option>`).join('')}
        </select>
      </label>`;
  }

  function renderLabeledSelect(id, label, value, entries, allLabel = '全部') {
    return `
      <label>${escapeHtml(label)}
        <select id="${escapeHtml(id)}">
          <option value="all"${value === 'all' ? ' selected' : ''}>${escapeHtml(allLabel)}</option>
          ${entries.map(([raw, text]) => `<option value="${escapeHtml(raw)}"${String(value) === String(raw) ? ' selected' : ''}>${escapeHtml(text)}</option>`).join('')}
        </select>
      </label>`;
  }

  function renderKeyword(id, label, value, placeholder) {
    return `<label>${escapeHtml(label)}<input id="${escapeHtml(id)}" value="${escapeHtml(value || '')}" placeholder="${escapeHtml(placeholder)}"></label>`;
  }

  function bindFilter(id, callback) {
    document.getElementById(id)?.addEventListener('input', callback);
    document.getElementById(id)?.addEventListener('change', callback);
  }

  function renderFilterBar(target, html) {
    return `<div class="filter-bar" data-filter-target="${escapeHtml(target)}">${html}</div>`;
  }

  function rankedOrgRows() {
    return [...state.orgs]
      .sort((a, b) => Number(b.member_rate || 0) - Number(a.member_rate || 0) || Number(b.total_diamond || 0) - Number(a.total_diamond || 0))
      .map((row, idx) => ({ rank: idx + 1, ...row }));
  }

  function renderOrgInsights(rows) {
    if (!rows.length) return '';
    const totalHeadcount = rows.reduce((sum, row) => sum + Number(row.tracked_headcount || 0), 0);
    const totalMembers = rows.reduce((sum, row) => sum + Number(row.member_count || 0), 0);
    const totalDeduct = rows.reduce((sum, row) => sum + Number(row.monthly_deduct_count || 0), 0);
    const best = [...rows].sort((a, b) => Number(b.member_rate || 0) - Number(a.member_rate || 0))[0];
    const risk = [...rows].sort((a, b) => Number(b.monthly_deduct_count || 0) - Number(a.monthly_deduct_count || 0))[0];
    return `
      <div class="insight-grid">
        <div class="insight"><span>筛选范围人力</span><strong>${escapeHtml(cardValue(totalHeadcount, '人'))}</strong></div>
        <div class="insight"><span>筛选范围会员率</span><strong>${escapeHtml(percentText(totalHeadcount ? totalMembers / totalHeadcount : 0))}</strong></div>
        <div class="insight"><span>会员率领先</span><strong>${escapeHtml(best ? `${best.org}-${best.business_line} ${percentText(best.member_rate)}` : '-')}</strong></div>
        <div class="insight"><span>扣减关注</span><strong>${escapeHtml(risk ? `${risk.org}-${risk.business_line} ${numberText(risk.monthly_deduct_count)}人` : '-')}</strong></div>
      </div>`;
  }

  function renderOrgs() {
    const f = state.filters.orgs;
    const rows = rankedOrgRows().filter(row => (
      matchesKeyword(row, f.keyword, ['org', 'business_line'])
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
    ));
    const toolbar = renderFilterBar('orgs', [
      renderKeyword('orgKeyword', '快速筛选', f.keyword, '机构/业务模式'),
      renderSelect('orgBusinessLine', '业务模式', f.businessLine, optionValues(state.orgs, 'business_line')),
    ].join(''));
    const el = document.getElementById('orgs');
    const columns = ['rank', 'org', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'avg_diamond', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond', 'estimated_reward'];
    renderTable('orgs', rows, columns, '机构会员与星钻汇总', { toolbar, note: '按会员率降序展示，便于快速识别领先机构和扣减压力机构。' });
    el.insertAdjacentHTML('afterbegin', renderOrgInsights(rows));
    bindFilter('orgKeyword', () => { state.filters.orgs.keyword = document.getElementById('orgKeyword').value; renderOrgs(); });
    bindFilter('orgBusinessLine', () => { state.filters.orgs.businessLine = document.getElementById('orgBusinessLine').value; renderOrgs(); });
  }

  function renderPersons() {
    const f = state.filters.persons;
    const rows = state.persons.filter(row => (
      matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'org'])
      && (f.org === 'all' || row.org === f.org)
      && (f.businessLine === 'all' || row.business_line === f.businessLine)
      && (f.level === 'all' || row.membership_level === f.level)
      && (!f.newStar || Number(row.is_new_star) === 1)
    )).sort((a, b) => Number(b.diamond_balance || 0) - Number(a.diamond_balance || 0));
    const toolbar = renderFilterBar('persons', [
      renderKeyword('personSearch', '人员筛选', f.keyword, '姓名/代码/机构'),
      renderSelect('personOrg', '机构', f.org, optionValues(state.persons, 'org')),
      renderSelect('personBusinessLine', '业务模式', f.businessLine, optionValues(state.persons, 'business_line')),
      renderSelect('personLevel', '会员等级', f.level, optionValues(state.persons, 'membership_level')),
      `<label class="check-label"><input id="personNewStar" type="checkbox"${f.newStar ? ' checked' : ''}>仅看新星</label>`,
    ].join(''));
    renderTable('persons', rows, ['org', 'business_line', 'staff_code', 'staff_name', 'membership_level', 'diamond_balance', 'total_gain', 'total_deduct', 'qualified_months', 'is_new_star'], '人员星钻汇总', { toolbar, note: '支持按姓名、人员代码、机构、业务模式和会员等级筛选，便于下钻到个人。' });
    bindFilter('personSearch', () => { state.filters.persons.keyword = document.getElementById('personSearch').value; renderPersons(); });
    bindFilter('personOrg', () => { state.filters.persons.org = document.getElementById('personOrg').value; renderPersons(); });
    bindFilter('personBusinessLine', () => { state.filters.persons.businessLine = document.getElementById('personBusinessLine').value; renderPersons(); });
    bindFilter('personLevel', () => { state.filters.persons.level = document.getElementById('personLevel').value; renderPersons(); });
    bindFilter('personNewStar', () => { state.filters.persons.newStar = document.getElementById('personNewStar').checked; renderPersons(); });
  }

  function renderExceptions(targetId, rows, title, severityFilter = null) {
    const key = targetId === 'warnings' ? 'warnings' : 'exceptions';
    const f = state.filters[key];
    const filtered = rows.filter(row => (
      (!severityFilter || row.severity !== severityFilter)
      && matchesKeyword(row, f.keyword, ['staff_code', 'staff_name', 'policy_no', 'message', 'suggested_action'])
      && (f.org === 'all' || row.org === f.org)
      && (!f.severity || f.severity === 'all' || row.severity === f.severity)
      && (f.type === 'all' || row.exception_type === f.type)
    ));
    const prefix = key === 'warnings' ? 'warning' : 'exception';
    const controls = [
      renderKeyword(`${prefix}Search`, '快速筛选', f.keyword, '姓名/代码/保单/说明'),
      renderSelect(`${prefix}Org`, '机构', f.org, optionValues(rows, 'org')),
    ];
    if (key === 'exceptions') controls.push(renderLabeledSelect(`${prefix}Severity`, '等级', f.severity, optionValues(rows, 'severity').map(v => [v, severityText(v)])));
    controls.push(renderLabeledSelect(`${prefix}Type`, '类型', f.type, optionValues(rows, 'exception_type').map(v => [v, typeText(v)])));
    const toolbar = renderFilterBar(targetId, controls.join(''));
    const displayRows = filtered.map(row => ({
      ...row,
      severity: severityText(row.severity),
      exception_type: typeText(row.exception_type),
    }));
    renderTable(targetId, displayRows, ['severity', 'exception_type', 'org', 'staff_code', 'staff_name', 'policy_no', 'message', 'suggested_action'], title, {
      toolbar,
      note: key === 'warnings' ? '预警清单优先用于经营跟踪，已补充人员姓名和建议动作。' : '异常清单用于追溯字段不足、负数保费、降级归属等计算约束。',
    });
    bindFilter(`${prefix}Search`, () => { state.filters[key].keyword = document.getElementById(`${prefix}Search`).value; renderWarningsAndExceptions(); });
    bindFilter(`${prefix}Org`, () => { state.filters[key].org = document.getElementById(`${prefix}Org`).value; renderWarningsAndExceptions(); });
    bindFilter(`${prefix}Severity`, () => { state.filters[key].severity = document.getElementById(`${prefix}Severity`).value; renderWarningsAndExceptions(); });
    bindFilter(`${prefix}Type`, () => { state.filters[key].type = document.getElementById(`${prefix}Type`).value; renderWarningsAndExceptions(); });
  }

  function renderWarningsAndExceptions() {
    renderExceptions('warnings', state.exceptions, '预警清单', 'info');
    renderExceptions('exceptions', state.exceptions, '异常清单', null);
  }

  function renderLevels() {
    const levels = {};
    state.persons.forEach(row => { levels[row.membership_level || '未入会'] = (levels[row.membership_level || '未入会'] || 0) + 1; });
    const levelRows = Object.entries(levels)
      .map(([level, count]) => ({ level, count }))
      .sort((a, b) => b.count - a.count);
    renderTable('levels', levelRows, ['level', 'count'], '会员等级分布', { note: '按当前累计钻石对应的会员等级统计人数。' });
  }

  function renderAudit(audit) {
    state.audit = audit;
    const rows = [];
    Object.values(audit.rawTables || {}).forEach(table => {
      (table.fields || []).forEach(field => rows.push({
        表: field.tableName,
        字段: field.requiredField,
        实际字段: field.matchedColumn || '-',
        必需性: field.requiredLevel === 'required' ? '必需' : '可选',
        状态: field.available ? '存在' : '缺失',
        影响: field.impact,
        降级方案: field.fallbackStrategy,
      }));
    });
    renderTable('audit', rows, ['表', '字段', '实际字段', '必需性', '状态', '影响', '降级方案'], '数据适配检查明细', {
      note: '这一页用于说明当前已导入数据能否支撑星钻计算，不是经营结果页。字段缺失时，系统只计算可支撑部分，并把不可确定事项写入异常清单。',
    });
    const ruleRows = (audit.ruleAssessment || []).map(r => ({ 规则: r.rule, 分级: r.grade, 说明: r.note }));
    document.getElementById('overview').innerHTML = `
      <div class="panel-title">星钻跟踪总览</div>
      <div class="summary-strip">
        <div class="summary-note"><strong>数据适配：</strong><span class="${audit.canReuseExistingData ? 'ok' : 'bad'}">${audit.canReuseExistingData ? '可复用现有数据' : '暂不可复用'}</span></div>
        <div class="summary-note"><strong>必需字段覆盖：</strong>${escapeHtml(audit.requiredCoverage.available)}/${escapeHtml(audit.requiredCoverage.total)}</div>
        <div class="summary-note"><strong>可选字段覆盖：</strong>${escapeHtml(audit.optionalCoverage.available)}/${escapeHtml(audit.optionalCoverage.total)}</div>
        <div class="summary-note"><strong>新增上传：</strong>${escapeHtml(audit.needsHonorUpload ? '需要补充上传' : '本阶段不需要')}</div>
      </div>
      <p class="muted">${escapeHtml(audit.minimumScope)}</p>
      <div id="ruleAssessment"></div>
    `;
    renderTable('ruleAssessment', ruleRows, ['规则', '分级', '说明'], '规则可计算性');
  }

  async function loadBatch(batchId) {
    if (!batchId) return;
    currentBatchId = batchId;
    const [summary, orgs, persons, exceptions, trend] = await Promise.all([
      api(`/api/honor/summary?batchId=${batchId}`),
      api(`/api/honor/orgs?batchId=${batchId}`),
      api(`/api/honor/persons?batchId=${batchId}`),
      api(`/api/honor/exceptions?batchId=${batchId}`),
      api(`/api/honor/trend?batchId=${batchId}`),
    ]);
    renderCards(summary.overview || {});
    state.orgs = orgs.rows || [];
    state.persons = persons.rows || [];
    state.exceptions = exceptions.rows || [];
    state.trend = trend.rows || [];
    renderOrgs();
    renderPersons();
    renderWarningsAndExceptions();
    renderTable('trend', state.trend, ['month', 'gainCount', 'deductCount', 'memberCount'], '月度获钻 / 扣减趋势', { note: '展示批次内月度获钻、扣减和会员人数变化。' });
    renderLevels();
  }

  async function runAudit() {
    setStatus('数据适配检查中...');
    const audit = await api('/api/honor/field-audit');
    currentBatchId = audit.batchId;
    renderAudit(audit);
    setStatus(`数据适配检查完成，批次 ${currentBatchId}`, 'ok');
  }

  async function loadLatestOrAudit() {
    const year = Number(document.getElementById('honorYear').value || 2026);
    const month = Number(document.getElementById('honorMonth').value || 12);
    try {
      const summary = await api(`/api/honor/summary?year=${year}&month=${month}`);
      const batchId = summary.batch?.id;
      if (batchId) {
        await loadBatch(batchId);
        setStatus(`已加载最近星钻批次 ${batchId}`, 'ok');
        document.getElementById('overview').innerHTML = `
          <div class="panel-title">星钻跟踪总览</div>
          <div class="panel-note">当前展示最近一次星钻计算结果。如需检查数据字段覆盖情况，请点击“数据适配检查”。</div>
          <div class="summary-strip">
            <div class="summary-note"><strong>当前批次：</strong>${escapeHtml(batchId)}</div>
            <div class="summary-note"><strong>规则版本：</strong>${escapeHtml(summary.batch?.rule_version || '-')}</div>
            <div class="summary-note"><strong>数据来源：</strong>${escapeHtml(summary.batch?.data_source_mode || 'existing_data')}</div>
            <div class="summary-note"><strong>异常数量：</strong>${escapeHtml(summary.overview?.exception_count ?? '-')}</div>
          </div>`;
        return;
      }
    } catch (_) {
      // No calculation batch exists yet; fall back to field audit so the page still explains data readiness.
    }
    await runAudit();
  }

  async function recalculate() {
    setStatus('星钻重算中...');
    const year = Number(document.getElementById('honorYear').value || 2026);
    const month = Number(document.getElementById('honorMonth').value || 12);
    const result = await api('/api/honor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year, month, scope: 'all', force: true }),
    });
    await loadBatch(result.batchId);
    setStatus(`重算完成，批次 ${result.batchId}，人员 ${result.personCount}，异常 ${result.exceptionCount}`, 'ok');
  }

  function exportExcel() {
    if (!currentBatchId) {
      setStatus('请先执行重算，再导出。', 'warn');
      return;
    }
    window.location.href = `/api/honor/export?batchId=${currentBatchId}`;
  }

  function bind() {
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
      });
    });
    document.getElementById('auditBtn')?.addEventListener('click', () => runAudit().catch(e => setStatus(e.message, 'bad')));
    document.getElementById('recalcBtn')?.addEventListener('click', () => recalculate().catch(e => setStatus(e.message, 'bad')));
    document.getElementById('exportBtn')?.addEventListener('click', exportExcel);
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requireLogin()) return;
    bind();
    renderCards({});
    loadLatestOrAudit().catch(e => setStatus(e.message, 'bad'));
  });
})();
