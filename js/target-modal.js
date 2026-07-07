// target-modal.js — target setting modal and target data lifecycle
    // ---------- Target Setting System ----------
    const TARGET_STORAGE_KEY = 'business_targets_v1';
    const DEFAULT_DASHBOARD_YEAR_NUM = new Date().getFullYear();
    const DEFAULT_DASHBOARD_YEAR = String(DEFAULT_DASHBOARD_YEAR_NUM);
    let targetData = null;
    let targetDataSource = 'default';
    const TARGET_BUSINESS_METRICS = ['整体', '经代', '转型业务', 'OTO', '证保', '蚁桥'];
    const TARGET_QUARTER_FACTORS = [0.22, 0.25, 0.26, 0.27];
    const TARGET_MONTH_FACTORS = [0.07,0.07,0.08,0.08,0.09,0.09,0.08,0.08,0.09,0.09,0.09,0.09];
    let targetActiveSection = 'business';
    let targetPeriodDim = 'year';
    let targetDirty = false;

    function allowLocalTargetCache() {
      return window.ALLOW_LOCAL_FALLBACK === true;
    }

    function buildRecentYearOptions(selectedYear) {
      return [0, 1, 2].map(offset => {
        const year = DEFAULT_DASHBOARD_YEAR_NUM - offset;
        return `<option value="${year}" ${String(selectedYear) === String(year) ? 'selected' : ''}>${year}年</option>`;
      }).join('');
    }

    function populateDashboardYearSelects() {
      [['yearSelect', selectedYear], ['payPeriodYearSelect', payPeriodFilters?.year], ['teamYearSelect', selectedTeamYear]]
        .forEach(([id, selected]) => {
          const el = document.getElementById(id);
          if (el) el.innerHTML = buildRecentYearOptions(selected || DEFAULT_DASHBOARD_YEAR);
        });
    }

    function createDefaultTargetData(year) {
      const categories = [
        { key: 'qjPremium', name: '期交保费', color: '#3b82f6',
          yearTargets: [10500,4800,5700,2500,2200,1000] },
        { key: 'value', name: '价值保费', color: '#8b5cf6',
          yearTargets: [8200,3600,4600,2000,1800,800] },
        { key: 'shangbao', name: '商保年金', color: '#10b981',
          yearTargets: [3500,1500,2000,900,700,400] },
        { key: 'baozhang', name: '保障类产品', color: '#f59e0b',
          yearTargets: [4200,1800,2400,1000,900,500] },
        { key: 'tenYear', name: '10年期产品', color: '#ef4444',
          yearTargets: [2800,1200,1600,700,600,300] }
      ];
      const data = { year: parseInt(year), categories: {}, orgTargets: {} };
      categories.forEach(cat => {
        data.categories[cat.key] = { name: cat.name, color: cat.color, metrics: {} };
        TARGET_BUSINESS_METRICS.forEach((m, i) => {
          const yearVal = cat.yearTargets[i];
          data.categories[cat.key].metrics[m] = {
            year: yearVal,
            quarter: distributeByFactors(yearVal, TARGET_QUARTER_FACTORS),
            month: distributeByFactors(yearVal, TARGET_MONTH_FACTORS)
          };
        });
      });
      // 初始化机构目标
      const orgList = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
      const orgChannels = ['OTO','证保','蚁桥'];
      const orgCats = ['qjPremium','value','shangbao','baozhang','tenYear'];
      orgList.forEach(org => {
        orgChannels.forEach(ch => {
          const key = `${org}|${ch}`;
          data.orgTargets[key] = {};
          orgCats.forEach(cat => {
            data.orgTargets[key][cat] = { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
          });
        });
      });
      return data;
    }

    function normalizeTargetData(data, year) {
      const base = createDefaultTargetData(year || data?.year || DEFAULT_DASHBOARD_YEAR_NUM);
      if (!data || !data.categories) return base;
      data.year = parseInt(year || data.year || base.year);
      Object.entries(base.categories).forEach(([catKey, baseCat]) => {
        if (!data.categories[catKey]) data.categories[catKey] = baseCat;
        if (!data.categories[catKey].name) data.categories[catKey].name = baseCat.name;
        if (!data.categories[catKey].color) data.categories[catKey].color = baseCat.color;
        if (!data.categories[catKey].metrics) data.categories[catKey].metrics = {};
        Object.entries(baseCat.metrics).forEach(([metricKey, baseMetric]) => {
          if (!data.categories[catKey].metrics[metricKey]) {
            data.categories[catKey].metrics[metricKey] = baseMetric;
          }
        });
      });
      Object.values(data.categories).forEach(cat => {
        if (!cat.metrics) cat.metrics = {};
        Object.values(cat.metrics).forEach(metricData => {
          if (typeof metricData.quarter === 'number') {
            const v = metricData.quarter;
            metricData.quarter = distributeByFactors(v, TARGET_QUARTER_FACTORS);
          }
          if (!Array.isArray(metricData.quarter)) metricData.quarter = [0,0,0,0];
          if (typeof metricData.month === 'number') {
            const v = metricData.month;
            metricData.month = distributeByFactors(v * 12, TARGET_MONTH_FACTORS);
          }
          if (!Array.isArray(metricData.month)) metricData.month = Array(12).fill(0);
          if (typeof metricData.year !== 'number') metricData.year = parseFloat(metricData.year) || 0;
        });
      });
      // 规范化 orgTargets
      if (!data.orgTargets) data.orgTargets = {};
      const orgList = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
      const orgChannels = ['OTO','证保','蚁桥'];
      const orgCats = ['qjPremium','value','shangbao','baozhang','tenYear'];
      orgList.forEach(org => {
        orgChannels.forEach(ch => {
          const key = `${org}|${ch}`;
          if (!data.orgTargets[key]) data.orgTargets[key] = {};
          orgCats.forEach(cat => {
            if (!data.orgTargets[key][cat]) data.orgTargets[key][cat] = { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
            const item = data.orgTargets[key][cat];
            if (typeof item.year !== 'number') item.year = parseFloat(item.year) || 0;
            if (!Array.isArray(item.quarter)) item.quarter = [0,0,0,0];
            if (!Array.isArray(item.month)) item.month = Array(12).fill(0);
          });
        });
      });
      return data;
    }

    function targetStorageKey(year) {
      return `${TARGET_STORAGE_KEY}_${year || targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM}`;
    }

    function loadTargetData(year) {
      const desiredYear = parseInt(year || targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM);
      if (targetData && targetData.year === desiredYear) {
        targetData = normalizeTargetData(targetData, desiredYear);
        return;
      }
      const saved = allowLocalTargetCache()
        ? (localStorage.getItem(targetStorageKey(desiredYear)) || localStorage.getItem(TARGET_STORAGE_KEY))
        : null;
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (!parsed.categories) throw new Error('invalid target data');
          targetData = normalizeTargetData(parsed, desiredYear);
          targetDataSource = 'local';
        } catch(e) {
          targetData = createDefaultTargetData(desiredYear);
          targetDataSource = 'default';
        }
      } else {
        targetData = createDefaultTargetData(desiredYear);
        targetDataSource = 'default';
      }
    }

    function targetSourceLabel() {
      if (targetDataSource === 'server') return '服务端目标';
      if (targetDataSource === 'local') return '本机开发缓存目标';
      return '默认目标，服务端尚未配置正式目标';
    }

    function escapeTargetText(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }

    function targetNumber(value) {
      const num = Number(value);
      return Number.isFinite(num) ? num : 0;
    }

    function roundTargetValue(value) {
      return Math.round(targetNumber(value) * 100) / 100;
    }

    function formatTargetValue(value) {
      const num = roundTargetValue(value);
      return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
    }

    function targetInputValue(value) {
      const rounded = roundTargetValue(value);
      return Number.isInteger(rounded) ? String(rounded) : String(rounded);
    }

    function sumTargetValues(values) {
      return (Array.isArray(values) ? values : []).reduce((sum, value) => sum + targetNumber(value), 0);
    }

    function distributeByFactors(total, factors) {
      const target = roundTargetValue(total);
      let used = 0;
      return factors.map((factor, index) => {
        if (index === factors.length - 1) return roundTargetValue(target - used);
        const value = roundTargetValue(target * factor);
        used = roundTargetValue(used + value);
        return value;
      });
    }

    function targetBalance(metricData) {
      const year = targetNumber(metricData?.year);
      const quarter = sumTargetValues(metricData?.quarter);
      const month = sumTargetValues(metricData?.month);
      return {
        year,
        quarter,
        month,
        quarterGap: roundTargetValue(quarter - year),
        monthGap: roundTargetValue(month - year)
      };
    }

    function renderTargetBalancePill(gap) {
      const ok = Math.abs(targetNumber(gap)) < 0.01;
      const text = ok ? '平衡' : `${gap > 0 ? '+' : ''}${formatTargetValue(gap)}`;
      return `<span class="target-balance ${ok ? 'ok' : 'warn'}">${text}</span>`;
    }

    function targetPeriodLabel(dim) {
      return {
        year: '年度',
        quarter: '季度',
        month1: '1-6月',
        month2: '7-12月'
      }[dim] || '年度';
    }

    function targetInputHtml(value, attrs, small = false) {
      return `<input type="number" inputmode="decimal" min="0" step="0.01"
        class="target-input ${small ? 'target-input-sm' : ''}"
        value="${targetInputValue(value)}" ${attrs} data-target-value>`;
    }

    function orgTargetInputHtml(value, attrs, small = false) {
      return `<input type="number" inputmode="decimal" min="0" step="0.01"
        class="target-input ${small ? 'target-input-sm' : ''}"
        value="${targetInputValue(value)}" ${attrs} data-org-target-value>`;
    }

    function updateTargetSourceNote() {
      const note = document.getElementById('targetSourceNote');
      if (note) note.textContent = `单位：万 · ${targetSourceLabel()}`;
    }

    function setTargetStatus(message, type = 'ready') {
      const el = document.getElementById('targetSaveState');
      if (!el) return;
      el.textContent = message;
      el.className = `target-save-state ${type}`;
    }

    function markTargetDirty(message = '有未保存修改') {
      targetDirty = true;
      setTargetStatus(message, 'dirty');
    }

    function syncTargetSectionButtons() {
      document.querySelectorAll('button[data-target-section]').forEach(button => {
        button.classList.toggle('active', button.dataset.targetSection === targetActiveSection);
      });
    }

    async function fetchTargetData(year) {
      const desiredYear = parseInt(year || targetData?.year || selectedYear || DEFAULT_DASHBOARD_YEAR_NUM);
      try {
        const data = unwrapApiResponse(await fetchJson(`/api/targets?year=${desiredYear}`, { method: 'GET' }));
        const hasServerTarget = !!(data && data.categories);
        targetData = normalizeTargetData(hasServerTarget ? data : createDefaultTargetData(desiredYear), desiredYear);
        targetDataSource = hasServerTarget ? 'server' : 'default';
        if (allowLocalTargetCache()) {
          localStorage.setItem(targetStorageKey(desiredYear), JSON.stringify(targetData));
        }
        return true;
      } catch(e) {
        loadTargetData(desiredYear);
        return false;
      }
    }

    async function openTargetModal() {
      loadTargetData(targetData?.year || selectedYear || DEFAULT_DASHBOARD_YEAR_NUM);
      modalTitle.textContent = '经营目标设置';
      modalOverlay.classList.add('modal-target');
      targetActiveSection = 'business';
      targetPeriodDim = 'year';
      orgTargetDim = 'year';
      targetDirty = false;
      modalBody.innerHTML = `
        <div class="target-shell">
          <div class="target-toolbar">
            <div class="target-toolbar-main">
              <label class="target-year-field">
                <span>目标年份</span>
                <select id="targetYearSelect" data-target-year>
                  ${buildRecentYearOptions(targetData.year)}
                </select>
              </label>
              <span id="targetSourceNote" class="target-source-note">单位：万 · ${targetSourceLabel()}</span>
            </div>
            <div class="target-toolbar-actions">
              <button class="chart-btn" data-target-action="distribute">按年度分摊季/月</button>
              <button class="chart-btn" data-target-action="export">导出 JSON</button>
              <button class="chart-btn" data-target-action="import">导入 JSON</button>
              <input type="file" id="targetFileInput" accept=".json" style="display:none;" data-target-import-file>
              <button class="chart-btn active target-save-btn" data-target-action="save">保存并刷新</button>
              <span id="targetSaveState" class="target-save-state ready">已加载</span>
            </div>
          </div>
          <div class="target-switchbar">
            <div class="target-section-tabs" aria-label="目标设置范围">
              <button class="org-dim-btn active" data-target-section="business">总目标与渠道</button>
              <button class="org-dim-btn" data-target-section="org">机构目标</button>
            </div>
          </div>
          <div class="target-grid" id="targetGrid"></div>
        </div>
      `;
      bindTargetModalControls();
      await fetchTargetData(targetData.year);
      const select = document.getElementById('targetYearSelect');
      if (select) select.value = targetData.year;
      updateTargetSourceNote();
      setTargetStatus('已加载', 'ready');
      renderTargetForm();
      modalOverlay.classList.add('active');
    }

    async function changeTargetYear(year) {
      if (targetDirty && !confirm('当前目标尚未保存，切换年份会放弃未保存修改。是否继续？')) {
        const select = document.getElementById('targetYearSelect');
        if (select && targetData?.year) select.value = targetData.year;
        return;
      }
      await fetchTargetData(parseInt(year));
      targetDirty = false;
      updateTargetSourceNote();
      setTargetStatus('已加载', 'ready');
      renderTargetForm();
    }

    function renderTargetForm() {
      const grid = document.getElementById('targetGrid');
      if (!grid) return;
      syncTargetSectionButtons();
      updateTargetSourceNote();
      grid.innerHTML = targetActiveSection === 'org' ? renderOrgTargetPanel() : renderBusinessTargetPanel();
    }

    function renderBusinessTargetPanel() {
      const qjOverall = targetData?.categories?.qjPremium?.metrics?.['整体'];
      const balance = targetBalance(qjOverall || {});
      return `
        <div class="target-content">
          <div class="target-section-head">
            <div>
              <div class="target-section-title">总目标与渠道目标</div>
              <div class="target-summary-strip">
                <span>期交年度 ${formatTargetValue(balance.year)}万</span>
                <span>季度合计 ${formatTargetValue(balance.quarter)}万</span>
                <span>月度合计 ${formatTargetValue(balance.month)}万</span>
              </div>
            </div>
            <div class="target-period-tabs" aria-label="目标周期">
              ${['year','quarter','month1','month2'].map(dim => `
                <button class="org-dim-btn ${targetPeriodDim === dim ? 'active' : ''}" data-target-period="${dim}">
                  ${targetPeriodLabel(dim)}
                </button>
              `).join('')}
            </div>
          </div>
          <div class="target-card-grid">
            ${Object.entries(targetData.categories).map(([catKey, cat]) => renderTargetCategoryCard(catKey, cat)).join('')}
          </div>
        </div>
      `;
    }

    function renderTargetCategoryCard(catKey, cat) {
      const overallBalance = targetBalance(cat.metrics?.['整体'] || {});
      return `
        <div class="target-card">
          <div class="target-card-header">
            <div class="target-card-title">
              <span class="icon" style="background:${cat.color}"></span>
              <span>${escapeTargetText(cat.name)}目标</span>
            </div>
            <span class="target-card-total">整体年度 ${formatTargetValue(overallBalance.year)}万</span>
          </div>
          <div class="target-card-body">${renderTargetCategoryTable(catKey, cat)}</div>
        </div>
      `;
    }

    function renderTargetCategoryTable(catKey, cat) {
      const period = targetPeriodDim;
      const monthIndexes = period === 'month2' ? [6,7,8,9,10,11] : [0,1,2,3,4,5];
      const monthLabels = period === 'month2' ? [7,8,9,10,11,12] : [1,2,3,4,5,6];

      if (period === 'quarter') {
        return `
          <div class="target-table-wrap">
            <table class="target-table">
              <thead><tr><th>口径</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th><th>合计</th><th>年度差</th></tr></thead>
              <tbody>
                ${TARGET_BUSINESS_METRICS.map(m => {
                  const metric = cat.metrics[m] || { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
                  const balance = targetBalance(metric);
                  return `
                    <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                      <td>${escapeTargetText(m)}</td>
                      ${[0,1,2,3].map(q => `
                        <td>${targetInputHtml(metric.quarter?.[q] ?? 0, `data-cat="${catKey}" data-metric="${m}" data-dim="quarter" data-idx="${q}"`, true)}</td>
                      `).join('')}
                      <td class="target-total-cell">${formatTargetValue(balance.quarter)}</td>
                      <td>${renderTargetBalancePill(balance.quarterGap)}</td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `;
      }

      if (period === 'month1' || period === 'month2') {
        return `
          <div class="target-table-wrap">
            <table class="target-table">
              <thead><tr><th>口径</th>${monthLabels.map(mo => `<th>${mo}月</th>`).join('')}<th>全年月度</th><th>年度差</th></tr></thead>
              <tbody>
                ${TARGET_BUSINESS_METRICS.map(m => {
                  const metric = cat.metrics[m] || { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
                  const balance = targetBalance(metric);
                  return `
                    <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                      <td>${escapeTargetText(m)}</td>
                      ${monthIndexes.map(mi => `
                        <td>${targetInputHtml(metric.month?.[mi] ?? 0, `data-cat="${catKey}" data-metric="${m}" data-dim="month" data-idx="${mi}"`, true)}</td>
                      `).join('')}
                      <td class="target-total-cell">${formatTargetValue(balance.month)}</td>
                      <td>${renderTargetBalancePill(balance.monthGap)}</td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `;
      }

      return `
        <div class="target-table-wrap">
          <table class="target-table">
            <thead><tr><th style="width:26%">口径</th><th>年度目标</th><th>季度合计</th><th>月度合计</th><th>月度校验</th></tr></thead>
            <tbody>
              ${TARGET_BUSINESS_METRICS.map(m => {
                const metric = cat.metrics[m] || { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
                const balance = targetBalance(metric);
                return `
                  <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                    <td>${escapeTargetText(m)}</td>
                    <td>${targetInputHtml(metric.year ?? 0, `data-cat="${catKey}" data-metric="${m}" data-dim="year"`)}</td>
                    <td class="target-total-cell">${formatTargetValue(balance.quarter)}</td>
                    <td class="target-total-cell">${formatTargetValue(balance.month)}</td>
                    <td>${renderTargetBalancePill(balance.monthGap)}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    function switchTargetSection(section) {
      if (section !== 'business' && section !== 'org') return;
      targetActiveSection = section;
      renderTargetForm();
    }

    function switchTargetPeriod(dim) {
      if (!['year','quarter','month1','month2'].includes(dim)) return;
      if (targetActiveSection === 'org') {
        switchOrgTargetDim(dim);
        return;
      }
      targetPeriodDim = dim;
      renderTargetForm();
    }

    function distributeMetricTargets(metricData) {
      if (!metricData) return;
      const year = targetNumber(metricData.year);
      metricData.quarter = distributeByFactors(year, TARGET_QUARTER_FACTORS);
      metricData.month = distributeByFactors(year, TARGET_MONTH_FACTORS);
    }

    function distributeTargetData() {
      targetData = normalizeTargetData(targetData, targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM);
      if (targetActiveSection === 'org') {
        Object.values(targetData.orgTargets || {}).forEach(targets => {
          ORG_TARGET_CATS.forEach(cat => distributeMetricTargets(targets?.[cat.key]));
        });
      } else {
        Object.values(targetData.categories || {}).forEach(cat => {
          Object.values(cat.metrics || {}).forEach(metric => distributeMetricTargets(metric));
        });
      }
      markTargetDirty('已按年度分摊，待保存');
      renderTargetForm();
    }

    function updateTargetValue(input) {
      if (!targetData || !targetData.categories) return;
      const cat = input.dataset.cat, metric = input.dataset.metric, dim = input.dataset.dim;
      const idx = input.dataset.idx;
      const val = parseFloat(input.value) || 0;
      if (!targetData.categories[cat]) return;
      if (!targetData.categories[cat].metrics[metric]) {
        targetData.categories[cat].metrics[metric] = { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
      }
      if (dim === 'year') {
        targetData.categories[cat].metrics[metric][dim] = val;
      } else {
        const arr = targetData.categories[cat].metrics[metric][dim];
        if (Array.isArray(arr) && idx !== undefined) {
          arr[parseInt(idx)] = val;
        }
      }
      markTargetDirty();
    }

    const ORG_TARGET_LIST = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
    const ORG_TARGET_CHANNELS = ['OTO','证保','蚁桥'];
    const ORG_TARGET_CATS = [
      { key: 'qjPremium', name: '期交保费' },
      { key: 'value', name: '价值保费' },
      { key: 'shangbao', name: '商保年金' },
      { key: 'baozhang', name: '保障类产品' },
      { key: 'tenYear', name: '10年期产品' }
    ];
    let orgTargetDim = 'year';

    function renderOrgTargetForm(grid) {
      grid.innerHTML = renderOrgTargetPanel();
    }

    function renderOrgTargetPanel() {
      return `
        <div class="target-content">
          <div class="target-section-head">
            <div>
              <div class="target-section-title">机构目标</div>
              <div class="target-summary-strip">
                <span>${ORG_TARGET_LIST.length}家机构</span>
                <span>${ORG_TARGET_CHANNELS.join(' / ')}</span>
                <span>${targetPeriodLabel(orgTargetDim)}</span>
              </div>
            </div>
          </div>
          <div class="target-card target-card-wide">
            <div class="target-card-header">
              <div class="target-card-title">
                <span class="icon" style="background:#64748b"></span>
                <span>机构 × 业务模式目标</span>
              </div>
              <span class="target-card-total">${targetPeriodLabel(orgTargetDim)}</span>
            </div>
            <div class="target-card-body" id="orgTargetBody">${renderOrgTargetTable()}</div>
          </div>
        </div>
      `;
    }

    function switchOrgTargetDim(dim) {
      orgTargetDim = dim;
      targetActiveSection = 'org';
      renderTargetForm();
    }

    function renderOrgTargetTable() {
      const dim = orgTargetDim;
      const isYear = dim === 'year';
      const isQuarter = dim === 'quarter';
      const isMonth1 = dim === 'month1';
      const isMonth2 = dim === 'month2';

      let html = `
        <div class="target-period-tabs target-period-tabs-inline">
          <button class="org-dim-btn ${isYear ? 'active' : ''}" data-org-target-dim="year">年度</button>
          <button class="org-dim-btn ${isQuarter ? 'active' : ''}" data-org-target-dim="quarter">季度</button>
          <button class="org-dim-btn ${isMonth1 ? 'active' : ''}" data-org-target-dim="month1">月度（1-6月）</button>
          <button class="org-dim-btn ${isMonth2 ? 'active' : ''}" data-org-target-dim="month2">月度（7-12月）</button>
        </div>
        <div class="target-table-wrap target-table-wrap-wide">
          <table class="target-table org-target-table">
            <thead>
              <tr>
                <th class="org-sticky org-sticky-org">机构</th>
                <th class="org-sticky org-sticky-channel">业务模式</th>
      `;

      if (isYear) {
        html += ORG_TARGET_CATS.map(c => `<th style="text-align:center;">${c.name}（万）</th>`).join('');
      } else if (isQuarter) {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="4" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th class="org-sticky org-sticky-org"></th><th class="org-sticky org-sticky-channel"></th>`;
        ORG_TARGET_CATS.forEach(() => {
          html += `<th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th>`;
        });
      } else if (isMonth1) {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="6" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th class="org-sticky org-sticky-org"></th><th class="org-sticky org-sticky-channel"></th>`;
        ORG_TARGET_CATS.forEach(() => {
          [1,2,3,4,5,6].forEach(m => { html += `<th>${m}月</th>`; });
        });
      } else {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="6" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th class="org-sticky org-sticky-org"></th><th class="org-sticky org-sticky-channel"></th>`;
        ORG_TARGET_CATS.forEach(() => {
          [7,8,9,10,11,12].forEach(m => { html += `<th>${m}月</th>`; });
        });
      }

      html += `</tr></thead><tbody>`;

      ORG_TARGET_LIST.forEach(org => {
        ORG_TARGET_CHANNELS.forEach((ch, chIdx) => {
          const key = `${org}|${ch}`;
          const targets = targetData?.orgTargets?.[key] || {};
          html += `<tr class="${chIdx > 0 ? 'sub' : ''}">`;
          if (chIdx === 0) {
            html += `<td rowspan="${ORG_TARGET_CHANNELS.length}" class="org-sticky org-sticky-org org-name-cell">${org}</td>`;
          }
          html += `<td class="org-sticky org-sticky-channel">${ch}</td>`;

          ORG_TARGET_CATS.forEach(cat => {
            const t = targets[cat.key] || { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
            if (isYear) {
              html += `<td>${orgTargetInputHtml(t.year, `data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="year"`)}</td>`;
            } else if (isQuarter) {
              [0,1,2,3].forEach(qi => {
                html += `<td>${orgTargetInputHtml(t.quarter[qi], `data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="quarter" data-idx="${qi}"`, true)}</td>`;
              });
            } else if (isMonth1) {
              [0,1,2,3,4,5].forEach(mi => {
                html += `<td>${orgTargetInputHtml(t.month[mi], `data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="month" data-idx="${mi}"`, true)}</td>`;
              });
            } else {
              [6,7,8,9,10,11].forEach(mi => {
                html += `<td>${orgTargetInputHtml(t.month[mi], `data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="month" data-idx="${mi}"`, true)}</td>`;
              });
            }
          });

          html += `</tr>`;
        });
      });

      html += `</tbody></table></div>`;
      return html;
    }

    function updateOrgTargetValue(input) {
      const org = input.dataset.org;
      const ch = input.dataset.ch;
      const cat = input.dataset.cat;
      const dim = input.dataset.dim;
      const val = parseFloat(input.value) || 0;
      const key = `${org}|${ch}`;
      if (!targetData.orgTargets) targetData.orgTargets = {};
      if (!targetData.orgTargets[key]) targetData.orgTargets[key] = {};
      if (!targetData.orgTargets[key][cat]) {
        targetData.orgTargets[key][cat] = { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
      }
      if (dim === 'year') {
        targetData.orgTargets[key][cat].year = val;
      } else {
        const idx = parseInt(input.dataset.idx);
        const arr = targetData.orgTargets[key][cat][dim];
        if (Array.isArray(arr) && idx >= 0 && idx < arr.length) {
          arr[idx] = val;
        }
      }
      markTargetDirty();
    }

    function bindTargetModalControls() {
      const body = document.getElementById('modalBody');
      if (!body || body.dataset.boundTargetControls === 'true') return;
      body.dataset.boundTargetControls = 'true';

      body.addEventListener('click', event => {
        const actionButton = event.target.closest('button[data-target-action]');
        if (actionButton && body.contains(actionButton)) {
          event.preventDefault();
          const action = actionButton.dataset.targetAction;
          if (action === 'export') {
            exportTargetJSON();
          } else if (action === 'import') {
            body.querySelector('input[data-target-import-file]')?.click();
          } else if (action === 'distribute') {
            distributeTargetData();
          } else if (action === 'save') {
            saveTargetData(event);
          }
          return;
        }

        const sectionButton = event.target.closest('button[data-target-section]');
        if (sectionButton && body.contains(sectionButton)) {
          event.preventDefault();
          switchTargetSection(sectionButton.dataset.targetSection);
          return;
        }

        const periodButton = event.target.closest('button[data-target-period]');
        if (periodButton && body.contains(periodButton)) {
          event.preventDefault();
          switchTargetPeriod(periodButton.dataset.targetPeriod);
          return;
        }

        const dimButton = event.target.closest('button[data-org-target-dim]');
        if (!dimButton || !body.contains(dimButton)) return;
        event.preventDefault();
        switchOrgTargetDim(dimButton.dataset.orgTargetDim);
      });

      body.addEventListener('change', event => {
        const yearSelect = event.target.closest('select[data-target-year]');
        if (yearSelect && body.contains(yearSelect)) {
          changeTargetYear(yearSelect.value);
          return;
        }

        const importInput = event.target.closest('input[data-target-import-file]');
        if (importInput && body.contains(importInput)) {
          importTargetJSON(importInput);
          return;
        }

        const targetInput = event.target.closest('input[data-target-value]');
        if (targetInput && body.contains(targetInput)) updateTargetValue(targetInput);

        const orgTargetInput = event.target.closest('input[data-org-target-value]');
        if (orgTargetInput && body.contains(orgTargetInput)) updateOrgTargetValue(orgTargetInput);
      });

      body.addEventListener('input', event => {
        const targetInput = event.target.closest('input[data-target-value]');
        if (targetInput && body.contains(targetInput)) {
          updateTargetValue(targetInput);
          return;
        }

        const orgTargetInput = event.target.closest('input[data-org-target-value]');
        if (!orgTargetInput || !body.contains(orgTargetInput)) return;
        updateOrgTargetValue(orgTargetInput);
      });
    }

    async function saveTargetData(evt) {
      const btn = evt ? evt.target.closest('button') : null;
      const original = btn ? btn.textContent : '';
      if (btn) {
        btn.textContent = '保存中...';
        btn.disabled = true;
      }
      setTargetStatus('保存中...', 'saving');
      try {
        targetData = normalizeTargetData(targetData, targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM);
        if (allowLocalTargetCache()) {
          localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
        }
        const resp = await adminFetch(apiUrl(`/api/targets?year=${targetData.year}`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(targetData)
        });
        if (!resp.ok) throw new Error('目标保存失败');
        targetData = normalizeTargetData(unwrapApiResponse(await resp.json()), targetData.year);
        targetDataSource = 'server';
        if (allowLocalTargetCache()) {
          localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
        }
        await recalculateDashboard();
        targetDirty = false;
        updateTargetSourceNote();
        setTargetStatus('已保存并刷新', 'ready');
        if (btn) {
          btn.textContent = '已保存';
          setTimeout(() => {
            btn.textContent = original;
            btn.disabled = false;
          }, 1200);
        } else {
          setTargetStatus('已保存并刷新', 'ready');
        }
      } catch(e) {
        console.error('saveTargetData error:', e);
        setTargetStatus('保存失败', 'error');
        if (btn) {
          btn.textContent = '保存失败';
          setTimeout(() => {
            btn.textContent = original;
            btn.disabled = false;
          }, 1200);
        }
      } finally {
        if (btn && btn.textContent !== '保存失败' && btn.textContent !== '已保存') btn.disabled = false;
      }
    }

    function exportTargetJSON() {
      const blob = new Blob([JSON.stringify(targetData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `经营目标_${targetData.year}.json`; a.click();
      URL.revokeObjectURL(url);
    }

    async function importTargetJSON(input) {
      const file = input.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const data = JSON.parse(e.target.result);
          if (data.year && data.categories) {
            targetData = normalizeTargetData(data, data.year);
            if (allowLocalTargetCache()) {
              localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
            }
            const resp = await adminFetch(apiUrl(`/api/targets?year=${targetData.year}`), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(targetData)
            });
            if (!resp.ok) throw new Error('目标导入保存失败');
            targetDataSource = 'server';
            document.getElementById('targetYearSelect').value = targetData.year;
            targetDirty = false;
            updateTargetSourceNote();
            setTargetStatus('已导入并刷新', 'ready');
            renderTargetForm();
            await recalculateDashboard();
          }
        } catch(err) {
          setTargetStatus('导入失败', 'error');
          alert('JSON 解析失败');
        }
      };
      reader.readAsText(file);
      input.value = '';
    }

    window.populateDashboardYearSelects = populateDashboardYearSelects;
    window.loadTargetData = loadTargetData;
    window.fetchTargetData = fetchTargetData;
    window.openTargetModal = openTargetModal;

