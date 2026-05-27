(function () {
  let currentBatchId = null;
  const state = { persons: [], orgs: [], exceptions: [], audit: null };

  const COLUMN_LABELS = {
    org: '机构',
    business_line: '业务模式',
    tracked_headcount: '跟踪人力',
    member_count: '会员人数',
    member_rate: '会员率',
    monthly_gain_count: '本月获钻人数',
    monthly_deduct_count: '本月扣减人数',
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

  const NUMERIC_COLUMNS = new Set([
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

  function formatCell(key, value) {
    if (value === null || value === undefined || value === '') return '-';
    if (key === 'member_rate') return percentText(value);
    if (key === 'estimated_reward') return `${numberText(value, 0)}元`;
    if (key === 'is_new_star') return Number(value) ? '是' : '否';
    if (key === 'month') return `${value}月`;
    if (NUMERIC_COLUMNS.has(key)) return numberText(value, 0);
    return value;
  }

  function cardValue(v, suffix = '', digits = 0) {
    if (v === null || v === undefined || v === '') return '-';
    return `${numberText(v, digits)}${suffix}`;
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
      <div class="card"><div class="label">${label}</div><div class="value">${val}</div></div>
    `).join('');
  }

  function renderTable(targetId, rows, columns, title = '') {
    const el = document.getElementById(targetId);
    if (!rows || !rows.length) {
      el.innerHTML = `${title ? `<div class="panel-title">${title}</div>` : ''}<div class="empty">暂无数据</div>`;
      return;
    }
    const keys = columns || Object.keys(rows[0]);
    el.innerHTML = `
      ${title ? `<div class="panel-title">${title}</div>` : ''}
      <div class="table-wrap">
        <table>
          <thead><tr>${keys.map(k => `<th class="${NUMERIC_COLUMNS.has(k) || k === 'member_rate' ? 'num' : ''}">${COLUMN_LABELS[k] || k}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.map(row => `<tr>${keys.map(k => `<td class="${NUMERIC_COLUMNS.has(k) || k === 'member_rate' ? 'num' : ''}">${formatCell(k, row[k])}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>`;
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
    renderTable('audit', rows, ['表', '字段', '实际字段', '必需性', '状态', '影响', '降级方案'], '字段审计明细');
    const ruleRows = (audit.ruleAssessment || []).map(r => ({ 规则: r.rule, 分级: r.grade, 说明: r.note }));
    document.getElementById('overview').innerHTML = `
      <div class="panel-title">数据适配结论</div>
      <div class="summary-strip">
        <div class="summary-note"><strong>复用判断：</strong><span class="${audit.canReuseExistingData ? 'ok' : 'bad'}">${audit.canReuseExistingData ? '可复用现有数据' : '暂不可复用'}</span></div>
        <div class="summary-note"><strong>必需字段覆盖：</strong>${audit.requiredCoverage.available}/${audit.requiredCoverage.total}</div>
        <div class="summary-note"><strong>可选字段覆盖：</strong>${audit.optionalCoverage.available}/${audit.optionalCoverage.total}</div>
        <div class="summary-note"><strong>新增上传：</strong>${audit.needsHonorUpload ? '需要补充上传' : '本阶段不需要'}</div>
      </div>
      <p class="muted">${audit.minimumScope}</p>
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
    renderTable('orgs', state.orgs, ['org', 'business_line', 'tracked_headcount', 'member_count', 'member_rate', 'monthly_gain_count', 'monthly_deduct_count', 'total_diamond', 'estimated_reward'], '机构会员与星钻汇总');
    renderTable('persons', state.persons, ['org', 'business_line', 'staff_code', 'staff_name', 'membership_level', 'diamond_balance', 'total_gain', 'total_deduct', 'qualified_months', 'is_new_star'], '人员星钻汇总');
    renderTable('exceptions', state.exceptions, ['severity', 'exception_type', 'org', 'staff_code', 'policy_no', 'message', 'suggested_action'], '异常清单');
    renderTable('warnings', state.exceptions.filter(r => r.severity !== 'info'), ['severity', 'exception_type', 'org', 'staff_code', 'message'], '预警清单');
    renderTable('trend', trend.rows || [], ['month', 'gainCount', 'deductCount', 'memberCount'], '月度获钻 / 扣减趋势');
    const levels = {};
    state.persons.forEach(row => { levels[row.membership_level] = (levels[row.membership_level] || 0) + 1; });
    const levelRows = Object.entries(levels).map(([level, count]) => ({ level, count }));
    renderTable('levels', levelRows, ['level', 'count'], '会员等级分布');
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
