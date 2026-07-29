(function () {
  const state = { data: null, tab: 'overview', search: '', grade: '', status: '' };
  const el = id => document.getElementById(id);
  const user = () => window.getCurrentUser?.() || null;
  const can = key => user()?.role === 'admin' || user()?.permissions?.[key] === true;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
  const number = (value, digits = 2) => value == null ? '--' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const integer = value => Number(value || 0).toLocaleString('zh-CN');
  const rate = value => value == null ? '--' : `${(Number(value) * 100).toFixed(1)}%`;
  const change = value => value == null ? '--' : `${value >= 1 ? '+' : ''}${((Number(value) - 1) * 100).toFixed(1)}%`;
  const changeClass = value => value == null ? '' : value >= 1 ? 'up' : 'down';

  function requireAccess() {
    if (!window.getAuthToken?.() || !user()) {
      window.location.href = '/';
      return false;
    }
    el('currentUser').textContent = `${user().username} · ${user().roleLabel || user().role}`;
    if (!can('branch_analysis')) {
      el('accessDenied').classList.remove('hidden');
      return false;
    }
    el('pageMain').classList.remove('hidden');
    return true;
  }

  function panel(title, subtitle, body) {
    return `<section class="panel"><div class="panel-head"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div></div><div class="panel-body">${body}</div></section>`;
  }

  function table(headers, rows, numeric = []) {
    if (!rows.length) return '<div class="empty">暂无数据</div>';
    return `<div class="table-wrap"><table><thead><tr>${headers.map((item, index) => `<th class="${numeric.includes(index) ? 'num' : ''}">${esc(item)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(row => `<tr>${row.map((item, index) => `<td class="${numeric.includes(index) ? 'num' : ''}">${item}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function statusBadge(status) {
    const cls = ({ '持续经营': 'live', '新增/恢复': 'new', '待唤醒': 'lost', '未活动': 'off' })[status] || 'off';
    return `<span class="badge ${cls}">${esc(status)}</span>`;
  }

  function renderKpis() {
    const s = state.data.summary;
    const cards = [
      ['证保期交保费', `${number(s.premiumWan)}万`, `同比 ${change(s.premiumChange)}`, changeClass(s.premiumChange)],
      ['常规活动网点', `${integer(s.activeRegular)} / ${integer(s.regularStock)}`, `活动率 ${rate(s.regularActivityRate)}`, ''],
      ['未活动常规网点', integer(s.inactiveRegular), '需进入唤醒或退出核验', s.inactiveRegular ? 'warn' : ''],
      ['转介绍汇总贡献', `${number(s.referralPremiumWan)}万`, `${integer(s.referralStockExcluded)}个子网点不进入常规网点数`, ''],
      ['券商销售人员', integer(s.externalSellers), `${integer(s.policies)}件 · 件均${number(s.averageCaseWan)}万`, ''],
      ['标准名匹配率', rate(s.matchedPremiumRate), `待匹配${number(s.unmatchedPremiumWan)}万`, s.unmatchedPremiumWan ? 'warn' : '']
    ];
    el('kpiGrid').innerHTML = cards.map(([label, value, meta, cls]) => `<article class="kpi">
      <div class="kpi-label">${label}</div><div class="kpi-value ${cls}">${value}</div><div class="kpi-meta">${meta}</div>
    </article>`).join('');
  }

  function renderOverview() {
    const s = state.data.summary;
    const levelRows = state.data.levels.map(item => [
      esc(item.label), integer(item.stock), integer(item.active), rate(item.activityRate), number(item.premiumWan)
    ]);
    const projectRows = state.data.projects.map(item => [
      esc(item.label), integer(item.stock), integer(item.active), rate(item.activityRate), number(item.premiumWan)
    ]);
    const callouts = `<div class="callouts">
      <div class="callout"><b>常规网点激活</b><p>${integer(s.activeRegular)}个活动、${integer(s.inactiveRegular)}个未活动，转介绍网点不进入分母。</p></div>
      <div class="callout"><b>头部集中度</b><p>前5个常规活动网点贡献匹配保费的${rate(s.top5RegularShare)}，需关注大单和重点网点波动。</p></div>
      <div class="callout"><b>转介绍业务</b><p>汇总${number(s.referralPremiumWan)}万元、${integer(s.referralPolicies)}件、${integer(s.referralSellers)}名券商销售人员，不向86个子网点平均分摊。</p></div>
    </div>`;
    return panel('关键经营判断', '网点规模、激活、集中度和转介绍贡献分开观察。', callouts) +
      `<div class="grid-2">${panel('参数等级表现', 'A/B/C/D等级直接引用参数表。', table(
        ['等级', '常规网点', '活动网点', '活动率', '期交保费(万)'], levelRows, [1, 2, 3, 4]
      ))}${panel('机构类项目表现', '按参考表机构类项目汇总常规网点。', table(
        ['项目', '常规网点', '活动网点', '活动率', '期交保费(万)'], projectRows, [1, 2, 3, 4]
      ))}</div>`;
  }

  function bindRegularFilters() {
    ['branchSearch', 'gradeFilter', 'statusFilter'].forEach(id => el(id)?.addEventListener('input', event => {
      if (id === 'branchSearch') state.search = event.target.value;
      if (id === 'gradeFilter') state.grade = event.target.value;
      if (id === 'statusFilter') state.status = event.target.value;
      el('content').innerHTML = renderRegular();
      bindRegularFilters();
      const search = el('branchSearch');
      if (id === 'branchSearch' && search) {
        search.focus();
        search.setSelectionRange(search.value.length, search.value.length);
      }
    }));
  }

  function renderRegular() {
    const query = state.search.trim().toLowerCase();
    const rows = state.data.regularBranches.filter(item => {
      const matches = !query || `${item.branch} ${item.parent} ${item.project} ${item.subproject} ${item.org} ${item.city}`.toLowerCase().includes(query);
      return matches && (!state.grade || item.grade === state.grade) && (!state.status || item.status === state.status);
    });
    const toolbar = `<div class="toolbar">
      <input id="branchSearch" placeholder="搜索网点、项目、机构或城市" value="${esc(state.search)}">
      <select id="gradeFilter"><option value="">全部等级</option>${['A','B','C','D'].map(item => `<option ${state.grade === item ? 'selected' : ''}>${item}</option>`).join('')}</select>
      <select id="statusFilter"><option value="">全部状态</option>${['持续经营','新增/恢复','待唤醒','未活动'].map(item => `<option ${state.status === item ? 'selected' : ''}>${item}</option>`).join('')}</select>
      <span class="meta">当前显示 ${rows.length} / ${state.data.summary.regularStock} 个常规网点</span>
    </div>`;
    const tableRows = rows.map(item => [
      statusBadge(item.status), esc(item.grade), esc(item.project), esc(item.org || '--'),
      `<span title="${esc(item.branch)}">${esc(item.branch)}</span>`, esc(item.city),
      number(item.premiumWan), `<span class="${changeClass(item.premiumChange)}">${change(item.premiumChange)}</span>`,
      integer(item.policies), number(item.averageCaseWan), integer(item.externalSellers), integer(item.activeMonths)
    ]);
    return toolbar + panel('147个常规网点经营明细', '按期内正向保单识别活动网点；保费保留冲正后的净额。', table(
      ['状态', '等级', '项目', '太平机构', '证券网点', '城市', '期交保费(万)', '同比', '件数', '件均(万)', '券商人员', '活动月'],
      tableRows, [6, 7, 8, 9, 10, 11]
    ));
  }

  function renderReferral() {
    const s = state.data.summary;
    const rows = state.data.referralBranches.map(item => [
      esc(item.referenceId), esc(item.branch), esc(item.parent), esc(item.province), esc(item.city),
      esc(item.project), esc(item.subproject), esc(item.locality)
    ]);
    const note = `<div class="notice">86个转介绍网点统一归属于广发证券股份有限公司，当前业绩底表只支持展示总体贡献
      ${number(s.referralPremiumWan)}万元、${integer(s.referralPolicies)}件；不将总体保费平均分摊到下列子网点。</div>`;
    return note + panel('转介绍网点名录', '仅作规划和归属参考，不纳入常规网点数、常规活动率及常规网均。', table(
      ['编号', '转介绍网点', '归属主体', '省', '市', '机构类项目', '项目细分', '本地/异地'], rows
    ));
  }

  function renderQuality() {
    const q = state.data.quality;
    const batch = state.data.meta.referenceBatch || {};
    const definitions = Object.entries(q.definitions).map(([key, value]) => `<div><b>${esc({
      regularCount: '常规网点数', referralCount: '转介绍网点数', activity: '活动网点', referralPerformance: '转介绍业绩'
    }[key] || key)}</b><br><span class="meta">${esc(value)}</span></div>`).join('');
    const unmatched = q.unmatchedBranches.map(item => [esc(item.branch), number(item.premiumWan), integer(item.policies)]);
    return `<div class="grid-2">${panel('统计口径', '本页面不把待确认项填成0。', `<div class="definition">${definitions}</div>`)}
      ${panel('参考表批次', '网点名单存放在受保护的生产数据库，不进入公开GitHub。', table(
        ['批次', '文件', '常规', '转介绍', '导入时间'],
        [[integer(batch.id), esc(batch.fileName || '--'), integer(batch.regularCount), integer(batch.referralCount), esc(batch.importedAt || '--')]], [0, 2, 3]
      ))}</div>` +
      panel('待匹配网点名称', '名称不一致或空网点不会自动归并，避免误配。', table(
        ['业绩表网点名称', '期交保费(万)', '件数'], unmatched, [1, 2]
      ));
  }

  function render() {
    renderKpis();
    const renderers = { overview: renderOverview, regular: renderRegular, referral: renderReferral, quality: renderQuality };
    el('content').innerHTML = renderers[state.tab]();
    if (state.tab === 'regular') bindRegularFilters();
  }

  async function load() {
    const year = el('yearInput').value;
    const asOf = el('asOfInput').value;
    const query = new URLSearchParams();
    if (year) query.set('year', year);
    if (asOf) query.set('asOf', asOf);
    el('sourceLine').textContent = '正在读取生产数据…';
    const payload = await window.fetchJson(`/api/branch-analysis/overview?${query}`);
    state.data = window.unwrapApiResponse(payload);
    el('yearInput').value = state.data.meta.year;
    el('asOfInput').value = state.data.meta.asOf;
    el('sourceLine').textContent = `业绩截至 ${state.data.meta.asOf} · 对比截至 ${state.data.meta.previousAsOf} · 参考表批次 ${state.data.meta.referenceBatch?.id || '--'}`;
    render();
  }

  function bind() {
    el('backBtn').addEventListener('click', () => { window.location.href = '/'; });
    el('refreshBtn').addEventListener('click', () => load().catch(showError));
    el('tabs').addEventListener('click', event => {
      const button = event.target.closest('[data-tab]');
      if (!button) return;
      state.tab = button.dataset.tab;
      document.querySelectorAll('.tab').forEach(item => {
        const selected = item === button;
        item.classList.toggle('active', selected);
        item.setAttribute('aria-selected', String(selected));
      });
      render();
    });
  }

  function showError(error) {
    el('sourceLine').textContent = '读取失败';
    el('content').innerHTML = `<div class="panel empty">${esc(error.message)}</div>`;
  }

  async function init() {
    if (!requireAccess()) return;
    bind();
    try {
      await load();
    } catch (error) {
      showError(error);
    }
  }

  init();
})();
