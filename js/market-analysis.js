(function (window, document) {
  const SECTION_LABELS = {
    all: '全部研判',
    macro: '宏观经济',
    regulation: '监管政策',
    peers: '同业动态',
    business_line: '条线判断'
  };
  const CHANGE_LABELS = {
    persistent: '持续有效',
    strengthened: '继续强化',
    reversed: '发生反转',
    new: '本期新增',
    expired: '已失效'
  };
  const CONFIDENCE_LABELS = { high: '高置信', medium: '中置信', low: '低置信' };
  let currentReport = null;
  let currentSection = 'all';

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function clear(element) {
    while (element && element.firstChild) element.removeChild(element.firstChild);
  }

  function formatTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false });
  }

  function sourceMap(report) {
    return Object.fromEntries((report.sources || []).map(source => [source.id, source]));
  }

  function evidenceChips(evidenceIds, report) {
    const row = node('div', 'evidence-row');
    row.appendChild(node('span', '', '证据'));
    const sources = sourceMap(report);
    (evidenceIds || []).forEach(id => {
      const source = sources[id] || {};
      const isExternal = /^https?:\/\//i.test(source.url || '');
      const chip = node(isExternal ? 'a' : 'span', 'evidence-chip', `${id} · ${source.publisher || '内部数据'}`);
      if (isExternal) {
        chip.href = source.url;
        chip.target = '_blank';
        chip.rel = 'noopener noreferrer';
        chip.title = source.title || id;
      }
      row.appendChild(chip);
    });
    return row;
  }

  function renderHero(report) {
    const executive = report.executiveSummary || {};
    document.getElementById('reportHeadline').textContent = executive.headline || report.title || '寿险市场研判';
    document.getElementById('reportSummary').textContent = executive.summary || '';
    const executiveEvidence = document.getElementById('executiveEvidence');
    clear(executiveEvidence);
    executiveEvidence.appendChild(evidenceChips(executive.evidenceIds, report));
    const meta = document.getElementById('reportMeta');
    clear(meta);
    const coverage = report.coverage || {};
    [
      `研究期 ${report.period?.start || '—'} 至 ${report.period?.end || '—'}`,
      `生成 ${formatTime(report.generatedAt)}`,
      `${(report.modules || []).length} 个研判模块`,
      `${(report.sources || []).length} 项证据`,
      `${coverage.officialSourceCount || 0} 项官方来源`
    ].forEach(text => meta.appendChild(node('span', 'pill', text)));
    document.getElementById('coverageNote').textContent = `检索 ${coverage.queryCount || 0} 组主题；微信公众号来源 ${coverage.wechatSourceCount || 0} 项。`;
  }

  function renderSignals(report) {
    const grid = document.getElementById('signalGrid');
    clear(grid);
    Object.keys(CHANGE_LABELS).forEach(key => {
      const entries = report.changeSignals?.[key] || [];
      const card = node('article', 'signal-card');
      const title = node('div', 'signal-title');
      title.appendChild(node('span', '', CHANGE_LABELS[key]));
      title.appendChild(node('span', 'signal-count', entries.length));
      card.appendChild(title);
      const list = node('div', 'signal-list');
      if (!entries.length) list.appendChild(node('div', 'signal-empty', '本期无此类变化'));
      const appendEntry = (entry, target) => {
        const item = node('div', 'signal-item');
        item.appendChild(node('strong', '', entry.title));
        item.appendChild(node('span', '', entry.summary));
        item.appendChild(evidenceChips(entry.evidenceIds, report));
        target.appendChild(item);
      };
      entries.slice(0, 3).forEach(entry => appendEntry(entry, list));
      if (entries.length > 3) {
        const more = node('details', 'signal-more');
        more.appendChild(node('summary', '', `展开其余 ${entries.length - 3} 项`));
        entries.slice(3).forEach(entry => appendEntry(entry, more));
        list.appendChild(more);
      }
      card.appendChild(list);
      grid.appendChild(card);
    });
  }

  function renderTabs() {
    const nav = document.getElementById('researchNav');
    clear(nav);
    Object.entries(SECTION_LABELS).forEach(([key, label]) => {
      const button = node('button', `research-tab${currentSection === key ? ' active' : ''}`, label);
      button.type = 'button';
      button.addEventListener('click', () => {
        currentSection = key;
        renderTabs();
        renderModules(currentReport);
      });
      nav.appendChild(button);
    });
  }

  function field(label, value, extraClass) {
    const box = node('div', `field${extraClass ? ` ${extraClass}` : ''}`);
    box.appendChild(node('span', '', label));
    box.appendChild(node('p', '', value || '—'));
    return box;
  }

  function renderModules(report) {
    const grid = document.getElementById('moduleGrid');
    clear(grid);
    const modules = (report.modules || []).filter(item => currentSection === 'all' || item.section === currentSection);
    modules.forEach(module => {
      const card = node('article', 'module-card');
      card.dataset.section = module.section || '';
      const top = node('div', 'module-top');
      const heading = node('div');
      heading.appendChild(node('h3', '', module.title));
      heading.appendChild(node('div', 'module-question', `${SECTION_LABELS[module.section] || module.section} · ${module.question || ''}`));
      top.appendChild(heading);
      const badges = node('div', 'module-badges');
      badges.appendChild(node('span', 'history-badge', CHANGE_LABELS[module.history?.state] || module.history?.state || '待归类'));
      badges.appendChild(node('span', `confidence ${module.confidence || ''}`, CONFIDENCE_LABELS[module.confidence] || module.confidence || '待判断'));
      top.appendChild(badges);
      card.appendChild(top);
      const fields = node('div', 'module-fields');
      fields.appendChild(field('已核验事实', module.fact));
      fields.appendChild(field('分析判断', module.judgment, 'judgment'));
      fields.appendChild(field('对条线的影响', module.impact, 'impact'));
      fields.appendChild(field('继续观察 / 失效条件', module.watchCondition));
      card.appendChild(fields);
      card.appendChild(evidenceChips(module.evidenceIds, report));
      const history = node('details', 'topic-history');
      const historySummary = node('summary', '', `跨期轨迹 · 自 ${module.history?.since || '本期'} 起`);
      history.appendChild(historySummary);
      const timeline = node('div', 'timeline');
      history.appendChild(timeline);
      history.addEventListener('toggle', async () => {
        if (!history.open || history.dataset.loaded === '1') return;
        history.dataset.loaded = '1';
        timeline.appendChild(node('span', '', '正在读取历史轨迹…'));
        try {
          const rows = await api(`/api/market-analysis/topics/${encodeURIComponent(module.topicKey)}?limit=12`);
          clear(timeline);
          (rows || []).forEach(row => {
            const item = node('div', 'timeline-item');
            item.appendChild(node('strong', '', `${formatTime(row.generatedAt)} · ${CHANGE_LABELS[row.state] || row.state || ''}`));
            item.appendChild(node('span', '', row.judgment || row.fact || ''));
            timeline.appendChild(item);
          });
          if (!(rows || []).length) timeline.appendChild(node('span', '', '暂无更早的同主题记录。'));
        } catch (error) {
          clear(timeline);
          timeline.appendChild(node('span', '', `轨迹读取失败：${error.message}`));
        }
      });
      if (module.history?.previousReportId) {
        const previous = node('button', 'previous-link', `查看上一期依据：${module.history.previousReportId}`);
        previous.type = 'button';
        previous.addEventListener('click', () => {
          const select = document.getElementById('historySelect');
          select.value = module.history.previousReportId;
          loadReport(module.history.previousReportId).catch(error => { document.getElementById('runMessage').textContent = error.message; });
        });
        history.appendChild(previous);
      }
      card.appendChild(history);
      grid.appendChild(card);
    });
    if (!modules.length) grid.appendChild(node('div', 'empty', '该模块本期没有通过证据校验的判断。'));
  }

  function renderActions(report) {
    const grid = document.getElementById('actionsGrid');
    clear(grid);
    (report.actions || []).forEach(action => {
      const card = node('article', 'action-card');
      const top = node('div', 'action-top');
      top.appendChild(node('h3', '', action.title));
      top.appendChild(node('span', 'priority', action.priority || 'P2'));
      card.appendChild(top);
      card.appendChild(node('p', 'action-text', action.action));
      const meta = node('div', 'action-meta');
      meta.appendChild(node('span', '', `责任对象：${action.owner || '待明确'}`));
      meta.appendChild(node('span', '', `复核节奏：${action.cadence || '待明确'}`));
      meta.appendChild(node('span', '', `触发条件：${action.trigger || '待明确'}`));
      card.appendChild(meta);
      card.appendChild(evidenceChips(action.evidenceIds, report));
      grid.appendChild(card);
    });
  }

  function renderSources(report) {
    const grid = document.getElementById('sourceGrid');
    clear(grid);
    (report.sources || []).forEach(source => {
      const card = node('article', 'source-card');
      const external = /^https?:\/\//i.test(source.url || '');
      const title = node(external ? 'a' : 'strong', '', `${source.id} · ${source.title || '未命名来源'}`);
      if (external) {
        title.href = source.url;
        title.target = '_blank';
        title.rel = 'noopener noreferrer';
      }
      card.appendChild(title);
      card.appendChild(node('p', '', source.excerpt || ''));
      const meta = node('div', 'source-meta');
      meta.appendChild(node('span', '', `${source.sourceLevel || '?'}级`));
      meta.appendChild(node('span', '', source.publisher || ''));
      meta.appendChild(node('span', '', `发布 ${formatTime(source.publishedAt)}`));
      meta.appendChild(node('span', '', `检索 ${formatTime(source.retrievedAt)}`));
      card.appendChild(meta);
      grid.appendChild(card);
    });
    document.getElementById('sourceSummary').textContent = `展开证据与来源（${(report.sources || []).length}）`;
    const limitations = [...(report.limitations || []), ...((report.coverage || {}).limitations || [])].filter(Boolean);
    document.getElementById('limitations').textContent = limitations.length ? `研究边界：${limitations.join('；')}` : '';
  }

  function renderReport(report) {
    currentReport = report;
    document.getElementById('emptyState').classList.toggle('hidden', Boolean(report));
    document.getElementById('reportContent').classList.toggle('hidden', !report);
    if (!report) {
      document.getElementById('reportHeadline').textContent = '尚无已发布的寿险市场研判';
      document.getElementById('reportSummary').textContent = '定时研究只有在事实来源和证据引用全部通过校验后才会显示。';
      clear(document.getElementById('executiveEvidence'));
      clear(document.getElementById('reportMeta'));
      return;
    }
    renderHero(report);
    renderSignals(report);
    renderTabs();
    renderModules(report);
    renderActions(report);
    renderSources(report);
  }

  async function api(path) {
    const response = await window.authFetch(path, { cache: 'no-store' });
    if (!response.ok) {
      if (response.status === 401) window.location.href = '/';
      throw new Error(`请求失败（${response.status}）`);
    }
    const payload = await response.json();
    return payload.data;
  }

  async function loadStatus() {
    try {
      const status = await api('/api/market-analysis/status');
      const state = status?.state || 'never_run';
      document.getElementById('runDot').className = `dot ${state}`;
      document.getElementById('runState').textContent = ({ success: '最近运行成功', running: '研究正在运行', failed: '最近运行失败', never_run: '尚未运行' })[state] || state;
      document.getElementById('runMessage').textContent = `${status?.message || ''}${status?.updatedAt ? ` · ${formatTime(status.updatedAt)}` : ''}`;
    } catch (error) {
      document.getElementById('runState').textContent = '状态读取失败';
      document.getElementById('runMessage').textContent = error.message;
    }
  }

  async function loadHistory() {
    const history = await api('/api/market-analysis/history?limit=36');
    const select = document.getElementById('historySelect');
    clear(select);
    const latestOption = node('option', '', '最新一期');
    latestOption.value = '';
    select.appendChild(latestOption);
    (history || []).forEach(item => {
      const option = node('option', '', `${formatTime(item.generatedAt)} · ${item.headline || item.title || item.reportId}`);
      option.value = item.reportId;
      select.appendChild(option);
    });
  }

  async function loadReport(reportId) {
    const path = reportId ? `/api/market-analysis/reports/${encodeURIComponent(reportId)}` : '/api/market-analysis/latest';
    renderReport(await api(path));
  }

  async function refreshAll() {
    try {
      await Promise.all([loadStatus(), loadHistory()]);
      await loadReport(document.getElementById('historySelect').value);
    } catch (error) {
      document.getElementById('reportHeadline').textContent = '市场研判读取失败';
      document.getElementById('reportSummary').textContent = error.message;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const user = window.getCurrentUser?.();
    if (!window.getAuthToken?.()) {
      window.location.href = '/';
      return;
    }
    if (user?.role !== 'admin' && user?.permissions?.market_analysis !== true) {
      document.getElementById('reportHeadline').textContent = '当前账号没有市场研判查看权限';
      document.getElementById('reportSummary').textContent = '请联系管理员在权限管理中开通“市场研判”。';
      document.getElementById('refreshButton').disabled = true;
      return;
    }
    document.getElementById('backButton').addEventListener('click', () => { window.location.href = '/'; });
    document.getElementById('refreshButton').addEventListener('click', refreshAll);
    document.getElementById('historySelect').addEventListener('change', event => loadReport(event.target.value).catch(error => { document.getElementById('runMessage').textContent = error.message; }));
    refreshAll();
  });
})(window, document);
