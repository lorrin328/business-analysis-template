(function () {
  let currentBatchId = null;
  const state = { persons: [], orgs: [], exceptions: [], audit: null };

  function hasPermission(key) {
    const user = window.getCurrentUser?.();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function setStatus(message, cls = 'muted') {
    const el = document.getElementById('honorStatus');
    if (el) {
      el.textContent = message || '';
      el.className = cls;
    }
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

  function value(v, suffix = '') {
    if (v === null || v === undefined || v === '') return '-';
    if (typeof v === 'number') return `${Number.isInteger(v) ? v : v.toFixed(1)}${suffix}`;
    return `${v}${suffix}`;
  }

  function renderCards(overview = {}) {
    const cards = [
      ['当前跟踪人力', value(overview.tracked_headcount, '人')],
      ['会员人数', value(overview.member_count, '人')],
      ['会员率', value((overview.member_rate || 0) * 100, '%')],
      ['资深及以上', value(overview.senior_plus_count, '人')],
      ['本月获钻人数', value(overview.monthly_gain_count, '人')],
      ['本月扣减人数', value(overview.monthly_deduct_count, '人')],
      ['累计钻石', value(overview.total_diamond, '颗')],
      ['新星人力', value(overview.new_star_count, '人')],
      ['预计季度奖励', value(overview.estimated_reward, '元')],
      ['异常数量', value(overview.exception_count, '条')],
    ];
    document.getElementById('honorCards').innerHTML = cards.map(([label, val]) => `
      <div class="card"><div class="label">${label}</div><div class="value">${val}</div></div>
    `).join('');
  }

  function renderTable(targetId, rows, columns) {
    const el = document.getElementById(targetId);
    if (!rows || !rows.length) {
      el.innerHTML = '<div class="muted">暂无数据</div>';
      return;
    }
    const headers = columns || Object.keys(rows[0]);
    el.innerHTML = `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${
      rows.map(row => `<tr>${headers.map(h => `<td>${row[h] ?? '-'}</td>`).join('')}</tr>`).join('')
    }</tbody></table>`;
  }

  function renderAudit(audit) {
    state.audit = audit;
    const rows = [];
    Object.values(audit.rawTables || {}).forEach(table => {
      (table.fields || []).forEach(field => rows.push({
        表: field.tableName,
        字段: field.requiredField,
        实际字段: field.matchedColumn || '-',
        必需性: field.requiredLevel,
        状态: field.available ? '存在' : '缺失',
        影响: field.impact,
        降级方案: field.fallbackStrategy,
      }));
    });
    renderTable('audit', rows, ['表', '字段', '实际字段', '必需性', '状态', '影响', '降级方案']);
    const ruleRows = (audit.ruleAssessment || []).map(r => ({ 规则: r.rule, 分级: r.grade, 说明: r.note }));
    document.getElementById('overview').innerHTML = `
      <p>现有数据复用判断：<strong class="${audit.canReuseExistingData ? 'ok' : 'bad'}">${audit.canReuseExistingData ? '可复用' : '不可复用'}</strong></p>
      <p>必需字段覆盖率：${audit.requiredCoverage.available}/${audit.requiredCoverage.total}</p>
      <p>可选字段覆盖率：${audit.optionalCoverage.available}/${audit.optionalCoverage.total}</p>
      <p>${audit.minimumScope}</p>
      <h3>规则可计算性</h3>
      <div id="ruleAssessment"></div>
    `;
    renderTable('ruleAssessment', ruleRows, ['规则', '分级', '说明']);
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
    renderTable('orgs', state.orgs, ['org', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond', 'estimated_reward']);
    renderTable('persons', state.persons, ['org', 'business_line', 'staff_code', 'staff_name', 'membership_level', 'diamond_balance', 'total_gain', 'total_deduct', 'qualified_months', 'is_new_star']);
    renderTable('exceptions', state.exceptions, ['severity', 'exception_type', 'org', 'staff_code', 'policy_no', 'message', 'suggested_action']);
    renderTable('warnings', state.exceptions.filter(r => r.severity !== 'info'), ['severity', 'exception_type', 'org', 'staff_code', 'message']);
    renderTable('trend', trend.rows || [], ['month', 'gainCount', 'deductCount', 'memberCount']);
    const levels = {};
    state.persons.forEach(row => { levels[row.membership_level] = (levels[row.membership_level] || 0) + 1; });
    renderTable('levels', Object.entries(levels).map(([level, count]) => ({ 等级: level, 人数: count })), ['等级', '人数']);
  }

  async function runAudit() {
    setStatus('字段审计中...');
    const audit = await api('/api/honor/field-audit');
    currentBatchId = audit.batchId;
    renderAudit(audit);
    setStatus(`字段审计完成，批次 ${currentBatchId}`, 'ok');
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
    runAudit().catch(e => setStatus(e.message, 'bad'));
  });
})();
