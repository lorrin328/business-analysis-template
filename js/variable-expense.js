(function () {
  const state = { data: null, batches: [], tab: 'overview', query: '' };

  const el = id => document.getElementById(id);
  const user = () => window.getCurrentUser?.() || null;
  const can = key => user()?.role === 'admin' || user()?.permissions?.[key] === true;
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
  const money = value => value == null ? '--' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const number = value => value == null ? '--' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  const rate = value => value == null ? '--' : `${(Number(value) * 100).toFixed(1)}%`;
  const statusText = status => ({ over: '超可用', near: '接近上限', normal: '正常', not_calculable: '不可计算' }[status] || '--');
  const rateCell = metric => `<span class="rate ${escapeHtml(metric?.status || '')}">${rate(metric?.rate)}</span>`;
  const badge = metric => `<span class="badge ${escapeHtml(metric?.status || '')}">${statusText(metric?.status)}</span>`;

  function requireAccess() {
    if (!window.getAuthToken?.() || !user()) {
      window.location.href = '/';
      return false;
    }
    el('currentUser').textContent = `${user().username} · ${user().roleLabel || user().role}`;
    if (!can('variable_expense_view')) {
      el('accessDenied').classList.remove('hidden');
      return false;
    }
    el('pageMain').classList.remove('hidden');
    if (can('variable_expense_upload')) el('uploadPanel').classList.remove('hidden');
    return true;
  }

  async function loadBatches() {
    const payload = await window.fetchJson('/api/variable-expense/batches');
    state.batches = window.unwrapApiResponse(payload) || [];
    const select = el('periodSelect');
    const selected = select.value;
    const periods = [...new Set(state.batches.map(item => item.period))];
    select.innerHTML = '<option value="">最新批次</option>' + periods.map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('');
    if (periods.includes(selected)) select.value = selected;
  }

  async function loadLatest() {
    const period = el('periodSelect').value;
    const payload = await window.fetchJson(`/api/variable-expense/latest${period ? `?period=${encodeURIComponent(period)}` : ''}`);
    state.data = window.unwrapApiResponse(payload);
    render();
  }

  function metricCard(label, metric) {
    return `<article class="kpi">
      <div class="kpi-label">${escapeHtml(label)}</div>
      <div class="kpi-value">${money(metric?.actual)}</div>
      <div class="kpi-meta">可用 ${money(metric?.available)} 万元 · 执行 ${rate(metric?.rate)}</div>
    </article>`;
  }

  function renderKpis() {
    const s = state.data?.summary || {};
    el('kpiGrid').innerHTML = [
      metricCard('转型首期+续期变动', s.transformation),
      metricCard('转型首年变动', s.transformationFirstYear),
      metricCard('经代首年变动', s.agencyVariable),
      metricCard('机构首年变动', s.institutionVariable),
      metricCard('机构业务推动费', s.promotion)
    ].join('');
  }

  function renderOverview() {
    const s = state.data.summary || {};
    const rows = [
      ['转型首年变动', s.transformationFirstYear],
      ['全口径续年变动', s.renewal],
      ['转型首期+续期变动', s.transformation],
      ['经代首年变动', s.agencyVariable],
      ['经代首年固定+变动', s.agencyTotal],
      ['机构首年变动', s.institutionVariable],
      ['机构业务推动费', s.promotion]
    ];
    return panel('核心口径', '金额单位：万元；计算保留原始精度，页面显示两位小数。', table(
      ['口径', '可用', '动支', '执行率', '结余', '状态'],
      rows.map(([label, item]) => [
        escapeHtml(label), money(item?.available), money(item?.actual), rateCell(item),
        `<span class="${(item?.balance ?? 0) < 0 ? 'negative' : ''}">${money(item?.balance)}</span>`, badge(item)
      ]),
      [1, 2, 3, 4]
    ));
  }

  function renderOrganization() {
    const details = state.data.details || {};
    const modeRows = (details.modes || []).map(item => [
      escapeHtml(item.mode), money(item.available), money(item.actual), rateCell(item),
      `<span class="${(item.balance ?? 0) < 0 ? 'negative' : ''}">${money(item.balance)}</span>`, badge(item)
    ]);
    const orgRows = (details.institutions || []).map(item => [
      escapeHtml(item.org), money(item.premium), number(item.monthlyHeadcount), number(item.perCapitaPremium),
      money(item.variable.available), money(item.variable.actual), rateCell(item.variable),
      `<span class="${(item.variable.balance ?? 0) < 0 ? 'negative' : ''}">${money(item.variable.balance)}</span>`,
      rate(item.promotion.rate)
    ]);
    return panel('模式执行情况', '公共费用没有正可用额度时，执行率显示“--”。', table(
      ['模式', '可用', '动支', '执行率', '结余', '状态'], modeRows, [1, 2, 3, 4]
    )) + panel('机构执行情况', '机构按变动费用执行率从高到低排列。', table(
      ['机构', '期交保费', '月均人力', '人均期交', '变费可用', '变费动支', '变费执行率', '变费结余', '业推执行率'],
      orgRows, [1, 2, 3, 4, 5, 6, 7, 8]
    ));
  }

  function renderCost() {
    const c = state.data.details?.composition || {};
    const items = [
      ['基本法固定', c.basicLawFixed],
      ['基本法浮动', c.basicLawFloating],
      ['手续费', c.commission],
      ['业务推动费', c.promotion],
      ['其他未归类', c.other]
    ];
    const max = Math.max(...items.map(item => Math.abs(Number(item[1] || 0))), 1);
    const bars = items.map(([label, value]) => `<div class="bar-row">
      <div>${escapeHtml(label)}</div>
      <div class="bar-track"><div class="bar" style="width:${Math.max(0, Math.abs(Number(value || 0)) / max * 100).toFixed(2)}%"></div></div>
      <div class="bar-value">${money(value)}</div>
    </div>`).join('');
    return panel('机构首年变动费用构成', `合计 ${money(c.total)} 万元。`, bars);
  }

  function renderProject() {
    const details = state.data.details || {};
    const query = state.query.trim().toLowerCase();
    const matches = item => !query || Object.values(item).some(value => String(value ?? '').toLowerCase().includes(query));
    const projectRows = (details.projects || []).filter(matches).slice(0, 300).map(item => [
      escapeHtml(item.org), escapeHtml(item.mode), escapeHtml(item.project),
      money(item.available), money(item.actual), rateCell(item),
      `<span class="${(item.balance ?? 0) < 0 ? 'negative' : ''}">${money(item.balance)}</span>`,
      item.comparisonStatus === 'matched' ? '名称匹配' : '口径待映射'
    ]);
    const productRows = (details.products || []).filter(matches).slice(0, 300).map(item => [
      escapeHtml(item.org), escapeHtml(item.mode), escapeHtml(item.productCode),
      escapeHtml(item.product), money(item.annualizedPremium), money(item.available)
    ]);
    const toolbar = `<div class="toolbar"><input id="detailSearch" placeholder="搜索机构、模式、项目或产品" value="${escapeHtml(state.query)}"><span class="source-line">单表最多显示300行</span></div>`;
    return toolbar + panel('项目费用', '项目源表合计尚未与正式汇总完全对齐；名称未完整匹配时仅展示源值，不计算执行率和结余。', table(
      ['机构', '模式', '项目', '可用', '动支', '执行率', '结余', '对照状态'], projectRows, [3, 4, 5, 6]
    )) + panel('产品可用费用', '财务月报未提供可可靠下钻到产品的实际动支，因此不虚构产品执行率。', table(
      ['机构', '模式', '产品代码', '产品及交期', '年化规保', '变动可用'], productRows, [4, 5]
    ));
  }

  function renderQuality() {
    const q = state.data.quality || {};
    const checks = (q.checks || []).map(item => `<div class="quality-item">
      <span>${escapeHtml(item.name)}</span><strong class="${item.passed ? 'quality-ok' : 'quality-bad'}">${item.passed ? '通过' : '未通过'}${item.difference == null ? '' : ` · 差额 ${money(item.difference)}`}</strong>
    </div>`).join('') || '<div class="empty">暂无校验记录</div>';
    const warningRows = (q.warnings || []).map(item => [
      escapeHtml(item.level === 'high' ? '阻断' : '提示'),
      escapeHtml(item.title),
      escapeHtml(item.detail || item.source || '')
    ]);
    const comparisons = state.data.reportComparison?.items || [];
    const comparisonRows = comparisons.map(item => [
      escapeHtml(item.label),
      money(item.workbook?.available), money(item.report?.available), money(item.difference?.available),
      money(item.workbook?.actual), money(item.report?.actual), money(item.difference?.actual),
      `${(Number(item.difference?.rate || 0) * 100).toFixed(2)}个百分点`
    ]);
    return panel('强校验', q.calculationNote || '', `<div class="quality-list">${checks}</div>`) +
      panel('提示事项', '提示不会阻断批次；阻断项不会写入成功批次。', table(['级别', '事项', '说明'], warningRows, [])) +
      (comparisons.length ? panel('年中报告对照', `${escapeHtml(state.data.reportComparison.source)}；当前模块以财务月报为准。`,
        table(['口径', '月报可用', '报告可用', '可用差额', '月报动支', '报告动支', '动支差额', '执行率差'], comparisonRows, [1, 2, 3, 4, 5, 6, 7])) : '');
  }

  function table(headers, rows, numericColumns) {
    if (!rows.length) return '<div class="empty">暂无数据</div>';
    return `<div class="table-wrap"><table><thead><tr>${headers.map((h, i) => `<th class="${numericColumns.includes(i) ? 'num' : ''}">${escapeHtml(h)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(row => `<tr>${row.map((value, i) => `<td class="${numericColumns.includes(i) ? 'num' : ''}">${value}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function panel(title, subtitle, body) {
    return `<section class="panel"><div class="panel-head"><div><h2>${escapeHtml(title)}</h2><p>${subtitle}</p></div></div><div class="panel-body">${body}</div></section>`;
  }

  function render() {
    const batch = state.data?.batch;
    if (!batch) {
      el('sourceLine').textContent = '尚未导入财务月报';
      el('kpiGrid').innerHTML = '';
      el('content').innerHTML = '<div class="panel empty">请由有导入权限的账号上传正式财务月报。</div>';
      return;
    }
    el('sourceLine').textContent = `${batch.period} · ${batch.fileName} · 批次 ${batch.id} · ${batch.importedAt}`;
    renderKpis();
    const warnings = state.data.quality?.warnings || [];
    const notice = el('warningNotice');
    if (warnings.length) {
      notice.textContent = `存在 ${warnings.length} 项提示，请在“数据校验”中查看。当前展示以本批次财务月报为准。`;
      notice.classList.remove('hidden');
    } else {
      notice.classList.add('hidden');
    }
    const renderers = { overview: renderOverview, organization: renderOrganization, cost: renderCost, project: renderProject, quality: renderQuality };
    el('content').innerHTML = renderers[state.tab]();
    el('detailSearch')?.addEventListener('input', event => {
      state.query = event.target.value;
      el('content').innerHTML = renderProject();
      el('detailSearch')?.focus();
      const search = el('detailSearch');
      search?.setSelectionRange(search.value.length, search.value.length);
    });
  }

  async function upload(event) {
    event.preventDefault();
    const file = el('uploadFile').files[0];
    const period = el('uploadPeriod').value;
    if (!file || !period) return;
    const button = el('uploadBtn');
    button.disabled = true;
    el('uploadStatus').textContent = '正在校验财务月报…';
    try {
      const form = new FormData();
      form.append('period', period);
      form.append('workbook', file);
      const response = await window.authFetch(window.apiUrl('/api/variable-expense/upload'), { method: 'POST', body: form });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload.detail;
        throw new Error(typeof detail === 'string' ? detail : (detail?.message || '导入失败'));
      }
      state.data = window.unwrapApiResponse(payload);
      el('uploadStatus').textContent = payload.message || '校验通过，已生成独立统计批次。';
      await loadBatches();
      el('periodSelect').value = state.data.period;
      render();
    } catch (error) {
      el('uploadStatus').textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  function bind() {
    el('backBtn').addEventListener('click', () => { window.location.href = '/'; });
    el('refreshBtn').addEventListener('click', loadLatest);
    el('periodSelect').addEventListener('change', loadLatest);
    el('uploadForm').addEventListener('submit', upload);
    el('tabs').addEventListener('click', event => {
      const button = event.target.closest('[data-tab]');
      if (!button) return;
      state.tab = button.dataset.tab;
      document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item === button));
      render();
    });
  }

  async function init() {
    if (!requireAccess()) return;
    bind();
    try {
      await loadBatches();
      await loadLatest();
    } catch (error) {
      el('content').innerHTML = `<div class="panel empty">${escapeHtml(error.message)}</div>`;
    }
  }

  init();
})();
