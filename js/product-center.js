/* Product research uses only authenticated administrator endpoints. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const base = '/api/product-center';
  const dimensions = ['客户需求', '保障责任', '利益水平', '退出与灵活性', '服务权益', '渠道承接', '公司经济性'];
  const state = { authorized: false, epoch: 0, stage: 'formal', products: [], selected: new Map(), sources: new Map(), blobs: new Set(), batch: null, product: null, listRequest: 0, detailRequest: 0, scenarioRequest: 0, previewRequest: 0, compareRequest: 0 };
  const number = value => value == null || value === '' || !Number.isFinite(Number(value)) ? '待核' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  const money = value => value == null ? '待核' : `${number(value)} 元`;
  const array = value => Array.isArray(value) ? value : [];
  const labels = { guarantee: '保证利益', example: '原例 / 非保证演示 / 万能假设', development: '开发稿', guaranteed: '保证利益', illustrated: '非保证演示', assumed: '万能或其他假设', confirmed: '已确认', provisional: '身份待核', unknown: '待核', verified: '已核验', passed: '校验通过', pending: '待核', timing_pending: '退出时点待核', source_reviewed: '已核对来源', formal: '正式材料', draft: '开发稿', published: '已发布', preview: '待发布', previewed: '待发布', archived: '历史批次', withdrawn: '已撤回', ready: '预检通过', rejected: '预检未通过', blocked: '待修正', failed: '失败' };
  const label = value => labels[value] || String(value || '待核');
  const revisionLabel = value => /^source-[0-9a-f]+$/i.test(String(value || '')) ? '来源锁定版本，合同版本待核' : value || '合同版本待核';
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }
  function button(text, action, className) {
    const node = el('button', text, className);
    node.type = 'button';
    node.addEventListener('click', action);
    return node;
  }
  function empty(target, text) { target.replaceChildren(el('div', text, 'empty')); }
  function notify(message, error = false) {
    $('notice').textContent = message;
    $('notice').className = `notice${error ? ' error' : ''}`;
    $('notice').hidden = !message;
  }
  function errorText(payload) {
    const value = payload && (payload.detail || payload.message);
    return typeof value === 'string' ? value : '操作未完成，请检查资料后重试。';
  }
  function safeError(error) { if (!error.stale && state.authorized) notify(error.message || '读取失败，请重试。', true); }
  function closePreviews() {
    state.previewRequest++;
    for (const id of ['sourceDialog', 'cashflowDialog']) if ($(id).open) $(id).close();
    $('sourceBody').replaceChildren();
    $('cashflowBody').replaceChildren();
    for (const url of state.blobs) URL.revokeObjectURL(url);
    state.blobs.clear();
  }
  function gate(message = '本中心仅管理员可访问。') {
    state.authorized = false;
    state.epoch += 1;
    closePreviews();
    state.products = [];
    state.selected.clear();
    state.sources.clear();
    state.product = null;
    state.batch = null;
    for (const id of ['productList', 'productDetail', 'comparisonResult', 'selectedProducts', 'importHistory', 'previewPanel']) $(id).replaceChildren();
    $('workspace').hidden = true;
    $('authGate').hidden = false;
    $('logout').hidden = true;
    $('userLabel').textContent = '';
    $('productCount').textContent = '';
    $('batchLabel').textContent = '尚无已发布资料';
    $('sourceTitle').textContent = '原始资料';
    $('sourceMeta').textContent = '';
    $('cashflowTitle').textContent = '逐笔现金流';
    $('notice').textContent = '';
    $('notice').hidden = true;
    $('authMessage').textContent = message;
    $('password').value = '';
    $('packageFile').value = '';
  }
  window.showAuthGate = gate;
  async function request(path, options = {}) {
    if (!state.authorized) throw Object.assign(new Error('请先登录管理员账号。'), { stale: true });
    const epoch = state.epoch;
    const response = await window.authFetch(window.apiUrl(base + path), options);
    if (response.status === 401 || response.status === 403) {
      window.clearAuthSession();
      gate(response.status === 403 ? '当前账号无管理员权限，请使用管理员账号登录。' : '登录已失效，请重新登录。');
      throw Object.assign(new Error('身份验证失败'), { stale: true });
    }
    const payload = await response.json().catch(() => ({}));
    if (epoch !== state.epoch || !state.authorized) throw Object.assign(new Error('请求已结束'), { stale: true });
    if (!response.ok || payload.success === false) throw new Error(errorText(payload));
    return window.unwrapApiResponse(payload);
  }
  function jsonPost(path, data) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  }
  function setOptions(id, values, placeholder) {
    const select = $(id);
    const prior = select.value;
    select.replaceChildren(new Option(placeholder, ''));
    for (const value of array(values)) {
      const item = typeof value === 'object' ? value.value || value.name : value;
      if (item) select.add(new Option(String(item), String(item)));
    }
    if ([...select.options].some(option => option.value === prior)) select.value = prior;
  }
  function limitations(target, items) {
    if (!array(items).length) return;
    const list = el('ul', null, 'definition-list');
    array(items).forEach(item => list.append(el('li', typeof item === 'string' ? item : JSON.stringify(item))));
    target.append(list);
  }
  function registerSources(sources) { array(sources).forEach(source => state.sources.set(source.id, source)); }
  function sourceRefs(ids) {
    const group = el('div', null, 'source-refs');
    array(ids).forEach(id => {
      const source = state.sources.get(id);
      group.append(button(source ? source.filename : `资料 ${id}`, () => viewSource(id), 'source-button'));
    });
    return group;
  }
  function renderFact(fact) {
    const node = el('div', null, 'fact');
    const heading = el('div', null, 'fact-title');
    heading.append(el('strong', fact.label || fact.dimension), el('span', label(fact.status), 'badge'));
    node.append(heading);
    if (String(fact.text || '').length > 1800 || String(fact.label || '').includes('全文')) {
      const extract = el('details', null, 'fact-extract');
      extract.append(el('summary', '展开来源原文与完整分支'), el('p', fact.text || '尚无已核验资料')); node.append(extract);
    } else node.append(el('p', fact.text || '尚无已核验资料'));
    const meta = [fact.locator, fact.reviewDate ? `核验日期 ${fact.reviewDate}` : null].filter(Boolean);
    if (meta.length) node.append(el('div', meta.join(' · '), 'fact-meta'));
    limitations(node, fact.limitations);
    node.append(sourceRefs(fact.sourceIds));
    return node;
  }
  function updateSelection() {
    $('selectedProducts').replaceChildren();
    if (!state.selected.size) $('selectedProducts').append(el('span', '尚未选择产品', 'muted'));
    for (const product of state.selected.values()) {
      const chip = el('span', null, 'selected-chip');
      chip.append(el('span', `${product.name} · ${product.channel || '渠道待核'}${product.stage === 'development' ? ' · 开发稿' : ''}`));
      const remove = button('×', () => { state.selected.delete(product.id); updateSelection(); }, '');
      remove.setAttribute('aria-label', `移除比较产品 ${product.name}`);
      chip.append(remove); $('selectedProducts').append(chip);
    }
    document.querySelectorAll('[data-compare-id]').forEach(input => { input.checked = state.selected.has(input.dataset.compareId); });
    $('compareButton').disabled = state.selected.size < 2 || state.selected.size > 4;
    $('compareButton').textContent = `比较所选产品${state.selected.size ? `（${state.selected.size}）` : ''}`;
    $('comparisonResult').replaceChildren();
  }
  function renderProducts(items) {
    const list = $('productList'); list.replaceChildren();
    if (!items.length) return empty(list, '没有符合筛选条件的产品。');
    for (const product of items) {
      const card = el('article', null, `product-card${state.product?.id === product.id ? ' selected' : ''}`);
      card.dataset.versionId = product.id;
      card.append(button(product.name, () => loadDetail(product.id), 'product-open'));
      card.append(el('p', `${product.code || '产品代码待核'} · ${product.channel || '渠道待核'}`));
      card.append(el('p', `${product.responsibilityType || '责任待核'} / ${product.benefitMechanism || '利益机制待核'}`));
      const bottom = el('div', null, 'product-bottom');
      bottom.append(el('span', product.stage === 'development' ? '开发稿' : revisionLabel(product.revision), `badge${product.stage === 'development' ? ' development' : ''}`));
      const checkLabel = el('label', null, 'compare-check'); const check = el('input'); check.type = 'checkbox'; check.dataset.compareId = product.id; check.checked = state.selected.has(product.id);
      check.addEventListener('change', () => {
        if (check.checked && state.selected.size >= 4) { check.checked = false; notify('最多同时比较 4 个产品版本。', true); return; }
        if (check.checked) state.selected.set(product.id, product); else state.selected.delete(product.id);
        updateSelection();
      });
      checkLabel.append(check, el('span', '加入比较')); bottom.append(checkLabel); card.append(bottom); list.append(card);
    }
  }
  async function loadProducts() {
    const sequence = ++state.listRequest;
    empty($('productList'), '正在读取产品目录…');
    const params = new URLSearchParams({ q: $('search').value.trim(), stage: state.stage });
    for (const key of ['channel', 'responsibilityType', 'benefitMechanism']) if ($(key).value) params.set(key, $(key).value);
    try {
      const data = await request(`/products?${params}`);
      if (sequence !== state.listRequest) return;
      state.products = array(data.items); renderProducts(state.products);
      $('productCount').textContent = `${data.total || 0} 个产品版本`;
      $('batchLabel').textContent = data.activeBatchId ? '已发布资料批次' : '尚无已发布资料';
      setOptions('channel', data.facets?.channels, '全部渠道');
      setOptions('responsibilityType', data.facets?.responsibilityTypes, '全部责任');
      setOptions('benefitMechanism', data.facets?.benefitMechanisms, '全部利益机制');
    } catch (error) { if (sequence === state.listRequest && state.authorized) empty($('productList'), '目录读取失败，可重新查询。'); safeError(error); }
  }
  function overviewItem(title, value) {
    const entry = el('div'); entry.append(el('dt', title), el('dd', value || '待核')); return entry;
  }
  async function loadDetail(id) {
    const sequence = ++state.detailRequest; state.scenarioRequest++;
    empty($('productDetail'), '正在读取产品资料…');
    try {
      const data = await request(`/products/${encodeURIComponent(id)}`);
      if (sequence !== state.detailRequest) return;
      state.product = data.product; registerSources(data.sources);
      const product = data.product; const target = $('productDetail'); target.replaceChildren();
      document.querySelectorAll('.product-card').forEach(card => card.classList.toggle('selected', card.dataset.versionId === product.id));
      const heading = el('div', null, 'detail-heading'); const badges = el('div', null, 'badges');
      badges.append(el('span', `${product.channel || '渠道待核'} · ${label(product.stage)}`, `badge${product.stage === 'development' ? ' development' : ''}`));
      badges.append(el('span', product.identityStatus === 'confirmed' ? '产品身份已确认' : '产品身份待核', 'badge'));
      // A formal source does not establish current sale approval.
      badges.append(el('span', product.saleStatus === 'unknown' || !product.saleStatus ? '当前可售待核' : `可售状态：${label(product.saleStatus)}`, 'badge'));
      heading.append(badges, el('h2', product.name), el('p', `${product.insurer || '公司待核'} · ${product.code || '代码待核'} · ${revisionLabel(product.revision)}`, 'muted'));
      if (product.stage === 'development') heading.append(el('p', '开发稿，不代表已批准或在售。', 'development-warning'));
      limitations(heading, product.limitations); target.append(heading);
      const overview = el('dl', null, 'overview-grid');
      overview.append(overviewItem('责任类型', product.responsibilityType), overviewItem('利益机制', product.benefitMechanism), overviewItem('最近核验', product.reviewDate)); target.append(overview);
      const dimensionNav = el('nav', null, 'dimension-nav'); dimensionNav.setAttribute('aria-label', '产品研究维度');
      const anchors = new Map();
      for (const [index, dimension] of dimensions.entries()) {
        const anchor = el('a', dimension); anchor.href = `#detail-dimension-${index}`; anchor.addEventListener('click', () => { $(`detail-dimension-${index}`).open = true; }); dimensionNav.append(anchor); anchors.set(dimension, index);
      }
      const cashflowLink = el('a', '收益与现金流'); cashflowLink.href = '#detail-benefits'; dimensionNav.append(cashflowLink); target.append(dimensionNav);
      for (const dimension of dimensions) {
        const facts = array(data.facts).filter(fact => fact.dimension === dimension);
        const section = el('details', null, 'dimension-section'); section.id = `detail-dimension-${anchors.get(dimension)}`;
        section.open = ['保障责任', '利益水平'].includes(dimension);
        const summary = el('summary', dimension); summary.append(el('span', facts.length ? `${facts.length} 项有来源记录` : '证据待补充', 'muted')); section.append(summary);
        if (facts.length) facts.forEach(fact => section.append(renderFact(fact)));
        else section.append(el('p', dimension === '公司经济性' ? '尚缺正式公司价值资料，不推算 NBV、CSM 或费用实绩。' : '尚无有来源的研究记录，待补充核验。', 'muted'));
        target.append(section);
      }
      const benefitsHeading = el('h3', '客户利益与现金流'); benefitsHeading.id = 'detail-benefits'; target.append(benefitsHeading);
      target.append(el('p', '保单年度 IRR。保证、原例演示、万能假设与开发稿分区展示；退出情景互斥。', 'scenario-note'));
      const toolbar = el('form', null, 'detail-toolbar');
      const partition = el('select'); partition.id = 'scenarioPartition';
      const partitions = product.stage === 'development' ? ['development'] : ['guarantee', 'example'];
      partitions.forEach(value => partition.add(new Option(labels[value], value)));
      for (const [title, input] of [['收益分区', partition], ['缴费年期', scenarioInput('payYears', '如 5，趸交填 0', 0)], ['退出保单年度', scenarioInput('horizonYear', '如 20', 1)]]) {
        const field = el('label', title); field.append(input); toolbar.append(field);
      }
      const queryButton = el('button', '查询'); queryButton.type = 'submit'; toolbar.append(queryButton);
      toolbar.addEventListener('submit', event => { event.preventDefault(); loadScenarios(product.id); });
      partition.addEventListener('change', () => loadScenarios(product.id)); target.append(toolbar);
      const scenarios = el('div'); scenarios.id = 'scenarioResults'; target.append(scenarios);
      target.append(el('h3', '来源资料'));
      if (!array(data.sources).length) target.append(el('p', '尚未关联原件。', 'muted'));
      for (const source of array(data.sources)) {
        const sourceItem = el('div', null, 'fact'); sourceItem.append(button(source.filename, () => viewSource(source.id), 'source-button'));
        sourceItem.append(el('div', `${source.locator || '定位待核'}${source.reviewDate ? ` · ${source.reviewDate}` : ''}`, 'fact-meta'));
        target.append(sourceItem);
      }
      loadScenarios(product.id);
    } catch (error) { if (state.authorized && sequence === state.detailRequest) empty($('productDetail'), '资料读取失败，请重新选择产品。'); safeError(error); }
  }
  function scenarioInput(id, placeholder, min) {
    const input = el('input'); input.id = id; input.type = 'number'; input.min = String(min); input.max = /horizon/i.test(id) ? '200' : '100'; input.step = '1'; input.placeholder = placeholder; return input;
  }
  function isPrimaryScenario(scenario) {
    return Number(scenario.age) === 40 && ['女', '女性', 'female', 'f', 'F'].includes(scenario.sex) && Math.abs(Number(scenario.totalPremium) - 1500000) < 0.01;
  }
  function scenarioYield(scenario) {
    const status = `${scenario.arithmeticStatus || ''} ${scenario.status || ''} ${scenario.contractStatus || ''}`;
    if (scenario.irr == null || !Number.isFinite(Number(scenario.irr)) || /pending|excluded|failed|待核/i.test(status)) return '待核 / 不纳入已核验比较';
    return `${(Number(scenario.irr) * 100).toFixed(4)}%`;
  }
  function renderScenarioTable(items, target) {
    if (!items.length) return empty(target, '暂无符合条件的已有测算。可调整缴费年期或退出年度。');
    const wrapper = el('div', null, 'table-wrap'); const table = el('table'); const head = el('thead'); const header = el('tr');
    ['产品 / 情景', '年龄 / 性别', '缴费年期', '计划总保费', '已交保费', '退出年度', '已领合计', '退出价值', '保单年度 IRR', '核验与现金流'].forEach(title => header.append(el('th', title)));
    head.append(header); table.append(head); const body = el('tbody');
    for (const scenario of items) {
      const row = el('tr');
      const values = [scenario.productName || '', `${scenario.age ?? '待核'} / ${scenario.sex || '待核'}`, scenario.payLabel || (scenario.payYears != null ? `${scenario.payYears} 年` : '待核'), money(scenario.totalPremium), money(scenario.paidPremiumAtExit), scenario.horizonYear ?? '待核', money(scenario.incomeTotal), money(scenario.terminalValue), scenarioYield(scenario)];
      values.forEach((value, i) => row.append(el('td', value, i > 2 ? 'num' : '')));
      const nameCell = row.firstChild; nameCell.append(el('div', [label(scenario.benefitNature), scenario.variant].filter(Boolean).join(' · '), 'muted'));
      if (array(scenario.limitations).length) {
        const conditions = el('details', null, 'scenario-conditions');
        conditions.append(el('summary', `适用条件与限制（${scenario.limitations.length} 项）`));
        limitations(conditions, scenario.limitations); nameCell.append(conditions);
      }
      if (scenario.scenarioLabel && scenario.scenarioLabel !== scenario.benefitNature) nameCell.append(el('div', label(scenario.scenarioLabel), 'fact-meta'));
      const action = el('td'); action.append(el('div', `算术：${label(scenario.arithmeticStatus)}`), el('div', `合同：${label(scenario.contractStatus)}`), button('查看逐笔现金流', () => viewCashflows(scenario.id), 'link-button')); row.append(action); body.append(row);
    }
    table.append(body); wrapper.append(table); target.append(wrapper);
  }
  async function loadScenarios(id) {
    const sequence = ++state.scenarioRequest; const target = $('scenarioResults'); if (!target) return;
    empty(target, '正在读取已有测算…');
    const partition = $('scenarioPartition').value;
    const params = new URLSearchParams({ partition });
    if ($('payYears').value) params.set('payYears', $('payYears').value);
    if ($('horizonYear').value) params.set('horizonYear', $('horizonYear').value);
    try {
      const data = await request(`/products/${encodeURIComponent(id)}/scenarios?${params}`);
      if (sequence !== state.scenarioRequest || state.product?.id !== id) return;
      target.replaceChildren();
      const all = array(data.items); const items = partition === 'guarantee' ? all.filter(isPrimaryScenario) : all;
      target.append(el('p', partition === 'guarantee' ? '同条件主视图：40 岁女性、计划总保费 150 万元。产品限制与退出时点仍需逐项核对。' : '本分区包含各自原始条件，非保证结果仅为假设或演示，不承诺实际收益。', partition === 'guarantee' ? 'scenario-note' : 'scenario-note warning'));
      renderScenarioTable(items, target);
      if (partition === 'guarantee' && all.length > items.length) {
        const other = el('details'); other.append(el('summary', `其他条件的保证测算（${all.length - items.length} 条）`));
        other.append(el('p', '以下条件与主视图不同，须分别核对，不作直接排名。', 'scenario-note'));
        renderScenarioTable(all.filter(scenario => !isPrimaryScenario(scenario)), other); target.append(other);
      }
    } catch (error) { if (state.authorized && sequence === state.scenarioRequest) empty(target, '测算读取失败，请重新查询。'); safeError(error); }
  }
  async function viewCashflows(id) {
    try {
      const data = await request(`/scenarios/${encodeURIComponent(id)}/cashflows`); registerSources(data.sources); const target = $('cashflowBody'); target.replaceChildren();
      const s = data.scenario; $('cashflowTitle').textContent = `${s.productName || '产品'} · 逐笔现金流`;
      target.append(el('p', `保单年度 IRR：${scenarioYield(s)}。年度以原底稿时点为准，正数为流入，负数为流出。`, 'scenario-note'));
      limitations(target, s.limitations);
      const summary = el('dl', null, 'overview-grid'); summary.append(overviewItem('计划总保费', money(s.totalPremium)), overviewItem('截至退出已交保费', money(s.paidPremiumAtExit)), overviewItem('退出价值', money(s.terminalValue))); target.append(summary);
      const table = el('table'); const head = el('tr'); ['保单年度时点', '类型', '现金流（元）'].forEach(title => head.append(el('th', title))); const thead = el('thead'); thead.append(head); table.append(thead);
      const tbody = el('tbody'); const kind = { premium: '保费投入', income: '领取', benefit: '领取', terminal: '退出价值', exit: '退出价值', net: '净现金流', guaranteed_surrender_value_including_current_due_benefit: '保证退保价值（含当期应领利益）', guaranteed_survival_payment: '保证生存保险金', surrender_cash_value: '退保现金价值', maturity_benefit: '满期保险金', special_survival_benefit: '特别生存保险金', guaranteed_annuity: '保证年金', source_unspecified: '原底稿未区分性质' };
      array(data.cashflows).forEach(flow => { const row = el('tr'); row.append(el('td', flow.timeYear), el('td', kind[flow.kind] || '原始现金流（性质待核）'), el('td', number(flow.amount), 'num')); tbody.append(row); }); table.append(tbody);
      const wrapper = el('div', null, 'table-wrap'); wrapper.append(table); target.append(wrapper);
      target.append(el('h3', '来源与时点口径'));
      for (const evidence of array(s.sourceEvidence)) {
        const item = el('div', null, 'fact');
        item.append(el('p', [evidence.locator, evidence.unit ? `原表单位：${evidence.unit}` : '', evidence.notes].filter(Boolean).join(' · ') || '定位待核'));
        item.append(sourceRefs([evidence.sourceId])); target.append(item);
      }
      target.append(sourceRefs(s.sourceIds)); $('cashflowDialog').showModal();
    } catch (error) { safeError(error); }
  }
  async function pdfPreview(id, url, source, epoch, sequence) {
    const isCurrent = () => epoch === state.epoch && sequence === state.previewRequest && state.authorized && $('sourceDialog').open;
    const toolbar = el('div', null, 'preview-toolbar'); toolbar.setAttribute('aria-label', '原件预览模式');
    const textPane = el('section', null, 'pdf-text-pane'); const originalPane = el('section'); originalPane.hidden = true;
    const pageControls = el('div', null, 'preview-pagination'); const pageLabel = el('span', '正在读取页码…', 'muted'); pageLabel.setAttribute('role', 'status');
    const pageText = el('pre', '正在读取原件文字…', 'source-text'); pageText.setAttribute('aria-label', '原件分页文字');
    let page = 1; let pageCount = 1; let pageRequest = 0; let frame;
    const textMode = button('分页文字预览', () => selectMode(false));
    const originalMode = button('PDF原件预览', () => selectMode(true));
    function selectMode(original) {
      if (!isCurrent()) return;
      textPane.hidden = original; originalPane.hidden = !original;
      textMode.classList.toggle('active', !original); originalMode.classList.toggle('active', original);
      textMode.setAttribute('aria-pressed', String(!original)); originalMode.setAttribute('aria-pressed', String(original));
      if (original && !frame) {
        frame = el('iframe'); frame.title = source?.filename || '原始 PDF'; frame.src = url; originalPane.append(frame);
        originalPane.append(el('p', '如原件预览空白，请切换分页文字预览，或下载原件用本地软件核对。', 'scenario-note'));
      }
    }
    const previous = button('上一页', () => loadPage(page - 1));
    const next = button('下一页', () => loadPage(page + 1));
    async function loadPage(requestedPage) {
      if (!isCurrent() || requestedPage < 1 || requestedPage > pageCount) return;
      const currentRequest = ++pageRequest; previous.disabled = true; next.disabled = true; pageText.textContent = '正在读取原件文字…';
      try {
        const data = await request(`/sources/${encodeURIComponent(id)}/text?page=${requestedPage}`);
        if (!isCurrent() || currentRequest !== pageRequest) return;
        if (data.source) registerSources([data.source]);
        page = Number(data.page) || requestedPage; pageCount = Math.max(1, Number(data.pageCount) || 1);
        pageLabel.textContent = `第 ${page} / ${pageCount} 页（原件物理页码）`;
        pageText.textContent = typeof data.text === 'string' && data.text.trim() ? data.text : '本页没有可提取的文字，可能包含图片或扫描内容。请查看或下载 PDF 原件。';
        previous.disabled = page <= 1; next.disabled = page >= pageCount;
      } catch (error) {
        if (!isCurrent() || currentRequest !== pageRequest) return;
        pageLabel.textContent = '文字预览暂不可用'; pageText.textContent = error.stale ? '' : '本页文字读取失败。请切换 PDF 原件预览，或下载原件用本地软件阅读。';
      }
    }
    textMode.classList.toggle('active', true); textMode.setAttribute('aria-pressed', 'true'); originalMode.setAttribute('aria-pressed', 'false');
    toolbar.append(textMode, originalMode); pageControls.append(previous, pageLabel, next);
    textPane.append(el('p', '文字预览不含原版图表，提取顺序可能与版面不同；核对版式和数值关系请下载原件。', 'scenario-note warning'), pageControls, pageText);
    $('sourceBody').append(toolbar, textPane, originalPane); await loadPage(1);
  }
  async function viewSource(id) {
    if (!state.authorized) return;
    const epoch = state.epoch; closePreviews();
    const sequence = state.previewRequest;
    const source = state.sources.get(id); $('sourceTitle').textContent = source?.filename || '原始资料'; $('sourceMeta').textContent = '正在安全读取资料…'; $('sourceDialog').showModal();
    try {
      const response = await window.authFetch(window.apiUrl(`${base}/sources/${encodeURIComponent(id)}/file`));
      if (response.status === 401 || response.status === 403) { window.clearAuthSession(); gate('登录已失效或无资料访问权限，请重新登录管理员账号。'); return; }
      if (!response.ok) throw new Error('原件读取失败，请确认资料仍存在。');
      const blob = await response.blob();
      if (epoch !== state.epoch || sequence !== state.previewRequest || !state.authorized || !$('sourceDialog').open) return;
      const url = URL.createObjectURL(blob); state.blobs.add(url);
      $('sourceMeta').textContent = [source?.locator, source?.reviewDate ? `核验日期 ${source.reviewDate}` : '', source?.sha256 ? `SHA256 ${source.sha256}` : ''].filter(Boolean).join(' · ');
      const download = el('a', '下载原件', 'button source-download'); download.href = url; download.download = source?.filename || '产品资料'; $('sourceBody').append(download);
      const type = (response.headers.get('Content-Type') || source?.mediaType || '').split(';')[0].toLowerCase();
      if (type === 'application/pdf') {
        await pdfPreview(id, url, source, epoch, sequence);
      } else if (['image/png', 'image/jpeg'].includes(type)) {
        const picture = el('img', null, 'source-image'); picture.src = url; picture.alt = source?.filename || '原始资料图片'; $('sourceBody').append(picture);
      } else if (['text/plain', 'text/csv', 'application/json'].includes(type)) {
        const text = await blob.text();
        if (epoch !== state.epoch || sequence !== state.previewRequest || !state.authorized || !$('sourceDialog').open) return;
        $('sourceBody').append(el('pre', text, 'source-text'));
      } else $('sourceBody').append(el('p', '此格式请下载后用本地软件阅读。', 'muted'));
    } catch (error) { if (epoch === state.epoch && sequence === state.previewRequest && state.authorized) $('sourceMeta').textContent = error.message; }
  }
  async function compareProducts(filters = {}) {
    const ids = [...state.selected.keys()]; if (ids.length < 2 || ids.length > 4) return;
    const target = $('comparisonResult'); empty(target, '正在整理产品证据与适用条件…');
    const epoch = state.epoch; const sequence = ++state.compareRequest;
    const partition = filters.partition || 'guarantee';
    try {
      const data = await jsonPost('/compare', { versionIds: ids, partition, payYears: filters.payYears ?? null, horizonYear: filters.horizonYear ?? null });
      if (epoch !== state.epoch || sequence !== state.compareRequest || ids.join('|') !== [...state.selected.keys()].join('|')) return;
      registerSources(data.sources);
      target.replaceChildren();
      const form = el('form', null, 'detail-toolbar'); const partitionSelect = el('select');
      for (const value of ['guarantee', 'example', 'development']) partitionSelect.add(new Option(labels[value], value)); partitionSelect.value = partition;
      const years = scenarioInput('comparePayYears', '如 5，趸交填 0', 0); years.value = filters.payYears ?? '';
      const horizon = scenarioInput('compareHorizonYear', '如 20', 1); horizon.value = filters.horizonYear ?? '';
      for (const [title, input] of [['收益分区', partitionSelect], ['缴费年期', years], ['退出保单年度', horizon]]) { const field = el('label', title); field.append(input); form.append(field); }
      const queryButton = el('button', '应用比较条件'); queryButton.type = 'submit'; form.append(queryButton);
      form.addEventListener('submit', event => { event.preventDefault(); compareProducts({ partition: partitionSelect.value, payYears: years.value === '' ? null : Number(years.value), horizonYear: horizon.value === '' ? null : Number(horizon.value) }); }); target.append(form);
      const table = el('table', null, 'comparison-matrix'); const thead = el('thead'); const row = el('tr'); row.append(el('th', '比较维度'));
      array(data.products).forEach(product => { const cell = el('th', product.name); cell.append(el('div', `${product.channel || ''} · ${product.stage === 'development' ? '开发稿，不代表已批准或在售' : revisionLabel(product.revision)}`, product.stage === 'development' ? 'warning' : 'muted')); row.append(cell); }); thead.append(row); table.append(thead);
      const tbody = el('tbody');
      for (const dimension of dimensions) {
        const item = array(data.dimensions).find(d => d.dimension === dimension); const tr = el('tr'); tr.append(el('th', dimension));
        array(data.products).forEach(product => {
          const cell = el('td'); const facts = array(array(item?.items).find(entry => entry.versionId === product.id)?.facts);
          if (!facts.length) cell.append(el('span', '证据待补充', 'muted')); else facts.forEach(fact => cell.append(renderFact(fact))); tr.append(cell);
        }); tbody.append(tr);
      }
      table.append(tbody); const wrapper = el('div', null, 'table-wrap'); wrapper.append(table); target.append(wrapper);
      const notes = el('div', null, 'comparison-notes'); notes.append(el('strong', '适用条件与证据缺口'));
      limitations(notes, [...array(data.differences), ...array(data.limitations)]);
      notes.append(el('p', partition === 'guarantee' ? '下列收益仅展示保证利益中 40 岁女性、计划总保费 150 万元的已有测算。年期、退出年度及责任限制不同，需逐项核对。' : '本分区包含各自原始条件，非保证和开发稿结果仅为假设或演示，不承诺实际收益。', partition === 'guarantee' ? '' : 'warning')); target.append(notes);
      const primary = array(data.scenarios).filter(s => s.partition === partition && (partition !== 'guarantee' || isPrimaryScenario(s))); renderScenarioTable(primary, target);
    } catch (error) { if (state.authorized && sequence === state.compareRequest) empty(target, '比较未完成，请重试。'); safeError(error); }
  }
  function statistic(title, value, note) {
    const card = el('div', null, 'review-stat'); card.append(el('span', title, 'muted'), el('strong', number(value)));
    if (note) card.append(el('span', note, 'muted')); return card;
  }
  function detailList(title, entries, formatter) {
    if (!entries.length) return null;
    const details = el('details', null, 'review-details'); details.append(el('summary', `${title}（${entries.length} 项）`));
    const list = el('ul', null, 'definition-list'); entries.forEach(entry => list.append(el('li', formatter(entry)))); details.append(list); return details;
  }
  function smallNumber(value) { return value == null || !Number.isFinite(Number(value)) ? '待核' : Number(value).toExponential(3); }
  function reviewReport(report = {}, diff = {}, gaps = []) {
    const output = el('div', null, 'review-overview');
    const counts = report.counts || {};
    const statistics = el('div', null, 'review-stats');
    for (const [title, value, note] of [
      ['产品版本', counts.versions, '正式与开发稿分别展示'], ['来源原件', counts.sources, '内容哈希校验'],
      ['责任与研究记录', counts.facts], ['收益情景', counts.scenarios, counts.guarantee == null ? null : `其中保证利益 ${number(counts.guarantee)} 条`]
    ]) statistics.append(statistic(title, value, note)); output.append(statistics);
    const checks = el('div', null, 'review-checks');
    const coverage = report.coverage || {}; const arithmetic = report.arithmetic || {};
    const coverageCard = el('section', null, 'review-check');
    coverageCard.append(el('h3', '来源覆盖'), el('span', coverage.passed === true ? '核验通过' : coverage.passed === false ? '存在需处理差异' : '尚无来源覆盖报告', `badge${coverage.passed === false ? ' development' : ''}`));
    coverageCard.append(el('p', `分类基线 ${number(coverage.baselineCount)} 份 · 资料索引 ${number(coverage.indexCount)} 份 · 哈希已核验 ${number(coverage.baselineHashVerifiedCount)} 份`, 'muted'));
    const baselineOnly = array(coverage.baselineOnly); const indexOnly = array(coverage.indexOnly);
    if (baselineOnly.length || indexOnly.length) coverageCard.append(el('p', `范围差异：仅基线收录 ${baselineOnly.length} 份，仅索引收录 ${indexOnly.length} 份。展开清单核对原因。`, 'scenario-note'));
    for (const [title, entries] of [['仅分类基线收录', baselineOnly], ['仅资料索引收录', indexOnly], ['来源校验异常', array(coverage.errors)]]) {
      const list = detailList(title, entries, item => typeof item === 'string' ? item : [item.filename, item.reason || item.message].filter(Boolean).join('：')); if (list) coverageCard.append(list);
    }
    checks.append(coverageCard);
    const arithmeticCard = el('section', null, 'review-check'); arithmeticCard.append(el('h3', '数值回归'), el('span', arithmetic.passed === true ? '复算通过' : arithmetic.passed === false ? '复算未通过' : '尚无数值回归报告', `badge${arithmetic.passed === false ? ' development' : ''}`));
    arithmeticCard.append(el('p', `独立复算 ${number(arithmetic.numericCount)} 条 · 通过 ${number(arithmetic.passedCount)} 条 · 失败 ${number(arithmetic.failureCount)} 条`, 'muted'));
    arithmeticCard.append(el('p', `原底稿空值待核 ${number(arithmetic.pendingCount)} 条。空值、身份待核和退出时点待核结果不纳入已核验比较。`, 'scenario-note'));
    const metrics = el('dl', null, 'review-metrics');
    for (const [title, value] of [['最大 IRR 差值', smallNumber(arithmetic.maxIrrDifference)], ['允许 IRR 差值', smallNumber(arithmetic.irrTolerance)], ['最大现值残差', arithmetic.maxNpvResidual == null ? '待核' : `${smallNumber(arithmetic.maxNpvResidual)} 元`], ['允许现值残差', arithmetic.npvToleranceYuan == null ? '待核' : money(arithmetic.npvToleranceYuan)]]) metrics.append(el('dt', title), el('dd', value)); arithmeticCard.append(metrics);
    const errors = detailList('复算范围异常', array(arithmetic.coverageErrors), item => String(item)); if (errors) arithmeticCard.append(errors);
    // Successful numerical rows stay in the protected report, never expanded
    // into this administrator review page. Only failed rows need attention.
    const failed = array(arithmetic.rows).filter(row => row.passed === false);
    const failedList = detailList('复算失败清单', failed, row => `${row.id || '测算记录'}：${row.reason || '请核对原始现金流与时点'}`); if (failedList) arithmeticCard.append(failedList);
    checks.append(arithmeticCard); output.append(checks);
    const changes = el('section', null, 'review-change'); changes.append(el('h3', '与当前发布资料的差异'));
    changes.append(el('p', `新增 ${number(diff.addedVersions)} 个版本 · 保留 ${number(diff.retainedVersions)} 个版本 · 减少 ${number(diff.removedVersions)} 个版本`));
    for (const [kind, name] of [['Facts', '责任与研究记录'], ['Scenarios', '收益情景'], ['Sources', '来源资料']]) {
      if (diff['added'+kind] != null) changes.append(el('p', `${name}：新增 ${number(diff['added'+kind])} · 更正 ${number(diff['changed'+kind])} · 减少 ${number(diff['removed'+kind])}`, 'muted'));
    }
    changes.append(el('p', diff.previousBatchId ? '本次确认后切换到新批次；原发布批次与来源记录保留。' : '这是首个发布批次。', 'muted')); output.append(changes);
    const pending = el('section', null, 'review-change'); pending.append(el('h3', '重要缺口与待核项'));
    pending.append(el('p', `收益显示为空 ${number(counts.pendingIrr)} 条 · 身份待核情景 ${number(report.quarantinedScenarioCount ?? counts.quarantinedScenarios)} 条 · 退出时点待核 ${number(report.timingPendingCount)} 条`, 'warning'));
    const types = { identity: '产品身份', scenarioIdentity: '情景身份', saleStatus: '当前可售状态', parameters: '产品与公司参数', developmentIrr: '开发稿收益', timing: '退出时点', scenario: '收益情景' };
    const groups = new Map();
    array(gaps).forEach(gap => {
      const type = typeof gap === 'string' ? '其他待核' : types[gap.type] || '其他待核';
      if (!groups.has(type)) groups.set(type, []); groups.get(type).push(gap);
    });
    for (const [title, items] of groups) {
      const messages = [...new Set(items.map(item => typeof item === 'string' ? item : item.message || item.reason || '尚缺来源核验'))];
      const group = detailList(`${title} · 涉及 ${items.length} 条记录`, messages, item => item); if (group) pending.append(group);
    }
    const identity = array(report.identityMappings).filter(item => item.identityStatus === 'provisional' || item.override === true);
    const identityList = detailList('身份待核与有来源的更正', identity, item => `${item.code ? `产品代码 ${item.code}` : '产品代码待核'}：${item.reason || '来源身份待核'}${item.locator ? `；${item.locator}` : ''}`); if (identityList) pending.append(identityList);
    limitations(pending, report.limitations); output.append(pending);
    const inputList = detailList('本次转换输入资料', array(report.sourceInputNames), item => String(item)); if (inputList) output.append(inputList);
    return output;
  }
  function renderPreview(data) {
    state.batch = data.batch;
    const target = $('previewPanel'); target.hidden = false; target.replaceChildren();
    const card = el('div', null, 'review-card'); card.append(el('h3', data.duplicate ? '已存在相同资料批次' : '预检与发布核对'));
    const badges = el('div', null, 'review-summary'); badges.append(el('span', label(data.batch?.status), 'badge')); if (data.batch?.id) badges.append(el('span', `批次 ${data.batch.id}`, 'badge')); card.append(badges);
    card.append(reviewReport(data.report, data.diff, data.gaps));
    card.append(el('p', '待核身份保留在待核区；正式、开发稿和非保证演示分别展示。发布以本次预检报告为准。', 'muted'));
    if (!['published', 'withdrawn', 'rejected', 'blocked', 'failed'].includes(data.batch?.status)) {
      const confirm = el('label', null, 'review-confirm'); const check = el('input'); check.type = 'checkbox'; confirm.append(check, el('span', '我已核对差异、来源及待核项目，确认发布此批次。'));
      const publish = button('确认发布', () => publishBatch(data.batch.id, publish), 'primary'); publish.disabled = true;
      check.addEventListener('change', () => { publish.disabled = !check.checked; }); card.append(confirm, publish);
    }
    target.append(card);
  }
  async function loadImports() {
    empty($('importHistory'), '正在读取批次历史…');
    try {
      const data = await request('/imports'); const target = $('importHistory'); target.replaceChildren();
      if (!array(data.items).length) return empty(target, '尚无导入记录。');
      const table = el('table'); const thead = el('thead'); const header = el('tr'); ['批次', '状态', '导入时间', '操作'].forEach(title => header.append(el('th', title))); thead.append(header); table.append(thead); const tbody = el('tbody');
      array(data.items).forEach(batch => {
        const row = el('tr'); row.append(el('td', batch.label || batch.id), el('td', data.activeBatchId === batch.id ? '当前发布批次' : label(batch.status)), el('td', batch.createdAt || batch.created_at || '待核'));
        const actions = el('td'); actions.append(button('查看预检', async () => { try { renderPreview(await request(`/imports/${encodeURIComponent(batch.id)}`)); } catch (error) { safeError(error); } }, 'link-button'));
        if (data.activeBatchId === batch.id) {
          const withdrawal = el('span');
          function resetWithdrawal() { withdrawal.replaceChildren(button('撤回发布', confirmWithdrawal, 'link-button')); }
          function confirmWithdrawal() {
            withdrawal.replaceChildren(el('p', '撤回后恢复上一发布批次，历史来源与审核记录保留。', 'warning'),
              button('确认撤回', () => withdrawBatch(batch.id), 'link-button'), button('取消', resetWithdrawal, 'link-button'));
          }
          resetWithdrawal(); actions.append(withdrawal);
        }
        row.append(actions); tbody.append(row);
      }); table.append(tbody); target.append(table);
    } catch (error) { if (state.authorized) empty($('importHistory'), '批次历史读取失败，请切换后重试。'); safeError(error); }
  }
  async function publishBatch(id, publishButton) {
    publishButton.disabled = true;
    try {
      await jsonPost(`/imports/${encodeURIComponent(id)}/publish`, {}); notify('资料批次已发布，产品目录已更新。'); $('previewPanel').hidden = true;
      await Promise.all([loadImports(), loadProducts()]);
      state.selected.clear(); updateSelection(); state.product = null; empty($('productDetail'), '资料已更新，请重新选择产品。'); closePreviews();
    } catch (error) { publishButton.disabled = false; safeError(error); }
  }
  async function withdrawBatch(id) {
    try {
      await jsonPost(`/imports/${encodeURIComponent(id)}/withdraw`, {}); notify('已撤回发布并恢复上一批次。'); $('previewPanel').hidden = true;
      await Promise.all([loadImports(), loadProducts()]); state.selected.clear(); updateSelection(); state.product = null; empty($('productDetail'), '发布批次已变化，请重新选择产品。'); closePreviews();
    } catch (error) { safeError(error); }
  }
  async function enter(user) {
    if (user?.role !== 'admin') { window.clearAuthSession(); gate('当前账号无管理员权限，请使用管理员账号登录。'); return; }
    state.epoch++; state.authorized = true;
    $('authGate').hidden = true; $('workspace').hidden = false; $('logout').hidden = false; $('userLabel').textContent = `${user.username} · 管理员`;
    $('password').value = ''; notify(''); updateSelection(); empty($('productDetail'), '选择产品，查看责任、收益及原始资料。'); await loadProducts();
  }
  $('loginForm').addEventListener('submit', async event => {
    event.preventDefault(); $('loginButton').disabled = true; $('authMessage').textContent = '正在验证管理员身份…';
    const epoch = ++state.epoch;
    try {
      const response = await fetch(window.apiUrl('/api/auth/login'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: $('username').value.trim(), password: $('password').value }) });
      const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(errorText(payload));
      if (epoch !== state.epoch) return;
      const data = window.unwrapApiResponse(payload); window.setAuthSession(data.token, data.user); await enter(data.user);
    } catch (error) { $('authMessage').textContent = error.message; } finally { $('loginButton').disabled = false; }
  });
  $('logout').addEventListener('click', () => {
    const token = window.getAuthToken(); gate('已退出登录。'); window.clearAuthSession();
    if (token) fetch(window.apiUrl('/api/auth/logout'), { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
  });
  $('filters').addEventListener('submit', event => { event.preventDefault(); loadProducts(); });
  $('resetFilters').addEventListener('click', () => { $('filters').reset(); loadProducts(); });
  document.querySelectorAll('[data-stage]').forEach(tab => tab.addEventListener('click', () => {
    state.stage = tab.dataset.stage; $('developmentWarning').hidden = state.stage !== 'development';
    document.querySelectorAll('[data-stage]').forEach(item => { item.classList.toggle('active', item === tab); item.setAttribute('aria-pressed', String(item === tab)); });
    state.product = null; state.detailRequest++; state.scenarioRequest++; empty($('productDetail'), state.stage === 'development' ? '选择开发稿查看资料。开发稿不代表已批准或在售。' : '选择产品，查看责任、收益及原始资料。'); loadProducts();
  }));
  function showSection(imports) {
    $('catalogPanel').hidden = imports; $('importsPanel').hidden = !imports;
    for (const [id, active] of [['catalogTab', !imports], ['importsTab', imports]]) { $(id).classList.toggle('active', active); if (active) $(id).setAttribute('aria-current', 'page'); else $(id).removeAttribute('aria-current'); }
    if (imports) loadImports();
  }
  $('catalogTab').addEventListener('click', () => showSection(false)); $('importsTab').addEventListener('click', () => showSection(true)); $('compareButton').addEventListener('click', compareProducts);
  $('uploadForm').addEventListener('submit', async event => {
    event.preventDefault(); const file = $('packageFile').files[0];
    if (!file || !/\.zip$/i.test(file.name)) { notify('请选择 ZIP 格式的产品导入包。', true); return; }
    if (file.size > 100 * 1024 * 1024) { notify('导入包超过 100 MB，请缩小范围后上传。', true); return; }
    $('previewButton').disabled = true; notify('正在上传并核验来源、身份和测算，请稍候…');
    try { const form = new FormData(); form.append('file', file); renderPreview(await request('/imports/preview', { method: 'POST', body: form })); notify('预检完成。请核对报告，勾选确认后发布。'); await loadImports(); }
    catch (error) { safeError(error); } finally { $('previewButton').disabled = false; }
  });
  $('closeSource').addEventListener('click', closePreviews); $('closeCashflow').addEventListener('click', () => $('cashflowDialog').close());
  $('sourceDialog').addEventListener('close', () => { if ($('sourceDialog').open) return; state.previewRequest++; $('sourceBody').replaceChildren(); for (const url of state.blobs) URL.revokeObjectURL(url); state.blobs.clear(); });
  window.addEventListener('pagehide', closePreviews);
  window.addEventListener('pageshow', event => { if (event.persisted) { gate('请重新验证身份。'); initialize(); } });
  async function initialize() {
    const token = window.getAuthToken(); if (!token) return; const epoch = state.epoch;
    try {
      const response = await window.authFetch(window.apiUrl('/api/auth/me')); const payload = await response.json().catch(() => ({}));
      if (epoch !== state.epoch) return;
      if (!response.ok) { window.clearAuthSession(); gate('登录已失效，请重新登录。'); return; }
      const user = window.unwrapApiResponse(payload); window.setAuthSession(token, user); await enter(user);
    } catch (error) { gate('无法验证登录状态，请检查连接后重试。'); }
  }
  initialize();
})();
