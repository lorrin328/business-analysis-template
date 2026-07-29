// payperiod-chart.js — payment period chart state and rendering
    // ---------- Payment Period Structure ----------
    const payPeriodData = {
      premium: [],
      count: [],
      averagePremium: { categories: [], rows: [] }
    };
    const payPeriodFilters = {
      transform: true,
      jingdai: true,
      channels: { 'OTO': true, '证保': true, '蚁桥': true },
      orgs: { 'all': true },
      jingdaiOrgs: {},
      orgsInitialized: false,
      metric: 'qj',
      timeDim: 'year',
      year: DEFAULT_DASHBOARD_YEAR,
      selectedMonths: {
        quarter: [],
        month: []
      },
      currentPieType: 'premium'
    };
    const payPeriodAverageFilters = {
      org: 'all',
      businessMode: 'all'
    };
    ORG_LIST.forEach(o => payPeriodFilters.orgs[o] = true);

    // Init org checkboxes for 交期结构
    (function initPayPeriodOrgChecks() {
      const container = document.getElementById('payPeriodTransformOrgChecks');
      ORG_LIST.forEach(org => {
        container.appendChild(createCheckboxLabel(org, true, 'payPeriodOrg'));
      });
      // Also init product org checks
      const prodContainer = document.getElementById('productOrgChecks');
      ORG_LIST.forEach(org => {
        prodContainer.appendChild(createCheckboxLabel(org, true, 'productOrg'));
      });
    })();

    const payPeriodChart = echarts.init(document.getElementById('payPeriodChart'));

    function getPayPeriodPieOption(type) {
      const data = type === 'count' ? payPeriodData.count : payPeriodData.premium;
      if (!data || data.length === 0) {
        return {
          title: { text: '暂无交期结构数据', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
          series: [{ type: 'pie', data: [], radius: ['40%', '70%'], center: ['35%', '50%'] }]
        };
      }
      const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];
      return {
        tooltip: { trigger: 'item', formatter: '{b}: {c}' + (type === 'count' ? '件' : '万') + ' ({d}%)' },
        series: [{
          type: 'pie', radius: ['38%', '66%'], center: ['50%', '54%'],
          data: data,
          color: colors,
          label: {
            formatter: '{b}\n{d}%',
            color: '#e5e7eb',
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 14,
            textBorderWidth: 0,
            textShadowBlur: 0,
            textShadowColor: 'transparent'
          },
          labelLine: {
            length: 18,
            length2: 14,
            lineStyle: { width: 1.5 },
            smooth: false
          },
          labelLayout: { hideOverlap: true },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,.2)' } }
        }]
      };
    }

    function applyPayPeriodFallback(year) {
      payPeriodData.premium = [];
      payPeriodData.count = [];
      payPeriodData.averagePremium = { categories: [], rows: [] };
      const chart = payPeriodChart;
      if (chart) chart.setOption(getPayPeriodPieOption('premium'), true);
      renderPayPeriodTable();
      renderPayPeriodAverageTable();
    }

    function fmtPayPeriodAmount(value, digits = 1) {
      const n = Number(value || 0);
      return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    }

    function escapePayPeriodText(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }

    function renderPayPeriodTable() {
      const wrapper = document.getElementById('payPeriodTableWrapper');
      if (!wrapper) return;
      const premiumRows = Array.isArray(payPeriodData.premium) ? payPeriodData.premium : [];
      const countRows = Array.isArray(payPeriodData.count) ? payPeriodData.count : [];
      const map = new Map();
      premiumRows.forEach(row => {
        const name = row.name || '未分类';
        const item = map.get(name) || { name, premium: 0, count: 0 };
        item.premium += Number(row.value || 0);
        map.set(name, item);
      });
      countRows.forEach(row => {
        const name = row.name || '未分类';
        const item = map.get(name) || { name, premium: 0, count: 0 };
        item.count += Number(row.value || 0);
        map.set(name, item);
      });
      const rows = Array.from(map.values()).sort((a, b) => Math.abs(b.premium) - Math.abs(a.premium));
      if (rows.length === 0) {
        wrapper.innerHTML = '<div class="structure-empty">暂无交期结构明细数据</div>';
        return;
      }
      const totalPremium = rows.reduce((sum, row) => sum + Number(row.premium || 0), 0);
      const totalCount = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
      const premiumLabel = payPeriodFilters.metric === 'gm' ? '规模保费' : '期交保费';
      const htmlRows = rows.map(row => {
        const name = escapePayPeriodText(row.name || '未分类');
        const premiumShare = totalPremium ? row.premium / totalPremium * 100 : 0;
        const countShare = totalCount ? row.count / totalCount * 100 : 0;
        return `
          <tr>
            <td class="primary-text">${name}</td>
            <td class="num">${fmtPayPeriodAmount(row.premium)}万</td>
            <td class="num">${premiumShare.toFixed(1)}%</td>
            <td class="num">${fmtPayPeriodAmount(row.count, 0)}件</td>
            <td class="num">${countShare.toFixed(1)}%</td>
          </tr>
        `;
      }).join('');
      wrapper.innerHTML = `
        <table class="structure-table" id="payPeriodTable">
          <thead>
            <tr>
              <th>交期分类</th>
              <th class="num">${premiumLabel}</th>
              <th class="num">保费占比</th>
              <th class="num">件数</th>
              <th class="num">件数占比</th>
            </tr>
          </thead>
          <tbody>${htmlRows}</tbody>
        </table>
      `;
    }

    function renderPayPeriodAverageTable() {
      const wrapper = document.getElementById('payPeriodAverageWrapper');
      const scopeNote = document.getElementById('payPeriodAverageScopeNote');
      const orgSelect = document.getElementById('payPeriodAverageOrgSelect');
      const modeBtns = document.getElementById('payPeriodAverageModeBtns');
      const resetBtn = document.getElementById('payPeriodAverageResetBtn');
      const filterSummary = document.getElementById('payPeriodAverageFilterSummary');
      if (!wrapper) return;

      const payload = payPeriodData.averagePremium || {};
      const categories = Array.isArray(payload.categories) ? payload.categories : [];
      const allRows = Array.isArray(payload.rows) ? payload.rows.slice() : [];
      const premiumLabel = payload.premium_label || (payPeriodFilters.metric === 'gm' ? '规模保费' : '期交保费');
      const modeOrder = { 'OTO': 1, '证保': 2, '蚁桥': 3 };
      const orgOrder = new Map([...ORG_LIST, '其他'].map((org, index) => [org, index]));
      const availableOrgs = Array.from(new Set(allRows.map(row => row.org || '未知')))
        .sort((a, b) => {
          const rankGap = (orgOrder.get(a) ?? 99) - (orgOrder.get(b) ?? 99);
          return rankGap || String(a).localeCompare(String(b), 'zh-CN');
        });
      const availableModes = new Set(allRows.map(row => row.business_mode || '未分类'));

      if (payPeriodAverageFilters.org !== 'all' && !availableOrgs.includes(payPeriodAverageFilters.org)) {
        payPeriodAverageFilters.org = 'all';
      }
      if (payPeriodAverageFilters.businessMode !== 'all' && !availableModes.has(payPeriodAverageFilters.businessMode)) {
        payPeriodAverageFilters.businessMode = 'all';
      }

      if (orgSelect) {
        orgSelect.innerHTML = [
          '<option value="all">全部机构</option>',
          ...availableOrgs.map(org => `<option value="${escapePayPeriodText(org)}">${escapePayPeriodText(org)}</option>`)
        ].join('');
        orgSelect.value = payPeriodAverageFilters.org;
      }
      if (modeBtns) {
        modeBtns.querySelectorAll('button[data-pay-period-average-mode]').forEach(button => {
          const mode = button.dataset.payPeriodAverageMode;
          const active = mode === payPeriodAverageFilters.businessMode;
          button.classList.toggle('active', active);
          button.setAttribute('aria-pressed', active ? 'true' : 'false');
          button.disabled = mode !== 'all' && !availableModes.has(mode);
        });
      }
      if (resetBtn) {
        resetBtn.disabled = payPeriodAverageFilters.org === 'all'
          && payPeriodAverageFilters.businessMode === 'all';
      }

      const rows = allRows.filter(row => {
        const orgMatches = payPeriodAverageFilters.org === 'all'
          || row.org === payPeriodAverageFilters.org;
        const modeMatches = payPeriodAverageFilters.businessMode === 'all'
          || row.business_mode === payPeriodAverageFilters.businessMode;
        return orgMatches && modeMatches;
      });
      rows.sort((a, b) => {
        const modeGap = (modeOrder[a.business_mode] || 9) - (modeOrder[b.business_mode] || 9);
        if (modeGap !== 0) return modeGap;
        const rankGap = (orgOrder.get(a.org) ?? 99) - (orgOrder.get(b.org) ?? 99);
        return rankGap || String(a.org || '').localeCompare(String(b.org || ''), 'zh-CN');
      });

      if (scopeNote) {
        scopeNote.textContent = `转型业务口径：${premiumLabel}净额 ÷ 承保件数净额；单位：万元/件；件数净额小于或等于0时不计算。本表可继续按机构、业务模式筛选。`;
      }
      if (filterSummary) {
        filterSummary.textContent = `显示 ${rows.length} / ${allRows.length} 条`;
      }
      if (allRows.length === 0) {
        wrapper.innerHTML = '<div class="structure-empty">当前筛选范围暂无可展示的转型业务件均保费</div>';
        return;
      }
      if (rows.length === 0) {
        wrapper.innerHTML = '<div class="structure-empty">当前表内筛选条件下暂无件均保费数据，请调整机构或业务模式</div>';
        return;
      }

      function averageCell(cell) {
        if (!cell || cell.calculable !== true || cell.average === null || cell.average === undefined) {
          const reason = escapePayPeriodText(cell?.reason || '该交期暂无数据');
          return `<span class="muted" title="${reason}">--</span>`;
        }
        const average = fmtPayPeriodAmount(cell.average, 2);
        const premium = fmtPayPeriodAmount(cell.premium, 2);
        const count = fmtPayPeriodAmount(cell.count, 0);
        const title = escapePayPeriodText(`${premiumLabel}${premium}万元 ÷ 承保件数净额${count}件`);
        return `<span class="pay-period-average-value" title="${title}" aria-label="${title}">${average}</span>`;
      }

      const headerCells = categories
        .map(category => `<th class="num">${escapePayPeriodText(category)}</th>`)
        .join('');
      const bodyRows = rows.map((row, index) => {
        const termMap = new Map((row.terms || []).map(item => [item.category, item]));
        const termCells = categories
          .map(category => `<td class="num">${averageCell(termMap.get(category))}</td>`)
          .join('');
        const modeStart = index > 0 && rows[index - 1].business_mode !== row.business_mode;
        return `
          <tr${modeStart ? ' class="mode-start"' : ''}>
            <td class="primary-text">${escapePayPeriodText(row.org || '未知')}</td>
            <td><span class="pay-period-mode-badge">${escapePayPeriodText(row.business_mode || '未分类')}</span></td>
            ${termCells}
            <td class="num total-cell">${averageCell(row.total)}</td>
          </tr>
        `;
      }).join('');

      wrapper.innerHTML = `
        <table class="structure-table" id="payPeriodAverageTable">
          <thead>
            <tr>
              <th>机构</th>
              <th>业务模式</th>
              ${headerCells}
              <th class="num">${escapePayPeriodText(premiumLabel)}合计件均</th>
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      `;
    }

    function renderPayPeriodChart() {
      const type = payPeriodFilters.currentPieType;
      payPeriodChart.setOption(getPayPeriodPieOption(type), true);
      renderPayPeriodTable();
      renderPayPeriodAverageTable();
    }

    function switchPayPeriodPie(btn, type) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      payPeriodFilters.currentPieType = type;
      renderPayPeriodChart();
    }

    function _buildPeriodMonths() {
      const dim = payPeriodFilters.timeDim;
      if (dim === 'year') return null;
      const maxMonth = typeof getLatestMonthForYear === 'function'
        ? getLatestMonthForYear(String(payPeriodFilters.year))
        : 12;
      const selected = MonthMultiSelect.normalizeMonths(payPeriodFilters.selectedMonths[dim], maxMonth);
      if (selected.length > 0) return selected;
      const fallback = MonthMultiSelect.defaultMonths(dim, maxMonth);
      payPeriodFilters.selectedMonths[dim] = fallback;
      return fallback;
    }

    function renderPayPeriodMonthFilter() {
      const container = document.getElementById('payPeriodMonthMultiSelect');
      if (!container) return;
      if (payPeriodFilters.timeDim === 'year') {
        container.hidden = true;
        return;
      }
      payPeriodFilters.selectedMonths[payPeriodFilters.timeDim] = MonthMultiSelect.render(container, {
        dimension: payPeriodFilters.timeDim,
        maxMonth: typeof getLatestMonthForYear === 'function'
          ? getLatestMonthForYear(String(payPeriodFilters.year))
          : 12,
        selectedMonths: _buildPeriodMonths(),
        onChange: months => {
          payPeriodFilters.selectedMonths[payPeriodFilters.timeDim] = months;
          refreshPayPeriodChart();
        }
      });
    }

    function buildPayPeriodQuery(year) {
      const params = new URLSearchParams();
      const bts = []; if (payPeriodFilters.transform) bts.push('转型'); if (payPeriodFilters.jingdai) bts.push('经代');
      if (bts.length < 2) params.set('businessTypes', bts.join(','));
      if (payPeriodFilters.transform) {
        const chs = Object.entries(payPeriodFilters.channels).filter(([,v])=>v).map(([k])=>k);
        if (chs.length < 3) params.set('channels', chs.join(','));
        const orgs = payPeriodFilters.orgs['all'] ? null : Object.entries(payPeriodFilters.orgs).filter(([k,v])=>k!=='all'&&v).map(([k])=>k);
        if (orgs && orgs.length < ORG_LIST.length) params.set('orgs', orgs.join(','));
      }
      if (payPeriodFilters.jingdai && payPeriodFilters.orgsInitialized) {
        const jdOrgs = Object.entries(payPeriodFilters.jingdaiOrgs).filter(([,v])=>v).map(([k])=>k);
        if (jdOrgs.length > 0 && jdOrgs.length < Object.keys(payPeriodFilters.jingdaiOrgs).length) params.set('jingdaiOrgs', jdOrgs.join(','));
      }
      const months = _buildPeriodMonths();
      if (months && months.length === 1) params.set('month', months[0]);
      else if (months && months.length > 1) params.set('months', months.join(','));
      if (payPeriodFilters.metric !== 'qj') params.set('metric', payPeriodFilters.metric);
      if (typeof window.appendDashboardRange === 'function') window.appendDashboardRange(params);
      return `/api/payment-period/${year}?${params.toString()}`;
    }

    async function fetchPayPeriodData(year) {
      try {
        const d = unwrapApiResponse(await fetchJson(buildPayPeriodQuery(year)));
        payPeriodData.premium = d.premium || [];
        payPeriodData.count = d.count || [];
        payPeriodData.averagePremium = d.average_premium || { categories: [], rows: [] };
        if (d.jingdai_orgs && d.jingdai_orgs.length > 0) {
          renderPayPeriodJingdaiOrgs(d.jingdai_orgs);
        }
      } catch (e) { applyPayPeriodFallback(year); }
      renderPayPeriodChart();
    }

    function refreshPayPeriodChart() { fetchPayPeriodData(payPeriodFilters.year); }

    function togglePayPeriodBiz(type, checked) {
      payPeriodFilters[type === '转型' ? 'transform' : 'jingdai'] = checked;
      document.getElementById('payPeriodTransformRow').style.display = payPeriodFilters.transform ? 'flex' : 'none';
      document.getElementById('payPeriodTransformOrgRow').style.display = payPeriodFilters.transform ? 'flex' : 'none';
      document.getElementById('payPeriodJingdaiOrgRow').style.display = payPeriodFilters.jingdai ? 'flex' : 'none';
      refreshPayPeriodChart();
    }

    function togglePayPeriodChannel(ch, checked) {
      payPeriodFilters.channels[ch] = checked;
      refreshPayPeriodChart();
    }

    function togglePayPeriodOrg(org, checked) {
      if (org === 'all') {
        payPeriodFilters.orgs['all'] = checked;
        ORG_LIST.forEach(o => payPeriodFilters.orgs[o] = checked);
        document.querySelectorAll('#payPeriodTransformOrgChecks [data-pay-period-org]:not([data-pay-period-org="all"])').forEach(cb => cb.checked = checked);
      } else {
        payPeriodFilters.orgs[org] = checked;
        const allChecked = ORG_LIST.every(o => payPeriodFilters.orgs[o]);
        payPeriodFilters.orgs['all'] = allChecked;
        const allCb = document.querySelector('#payPeriodTransformOrgChecks [data-pay-period-org="all"]');
        if (allCb) allCb.checked = allChecked;
      }
      refreshPayPeriodChart();
    }

    function togglePayPeriodJingdaiOrg(org, checked) {
      payPeriodFilters.jingdaiOrgs[org] = checked;
      refreshPayPeriodChart();
    }

    function switchPayPeriodDim(btn, dim) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      payPeriodFilters.timeDim = dim;
      renderPayPeriodMonthFilter();
      refreshPayPeriodChart();
    }

    function switchPayPeriodYear(value) {
      payPeriodFilters.year = value;
      renderPayPeriodMonthFilter();
      refreshPayPeriodChart();
    }

    function switchPayPeriodMetric(btn, metric) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      payPeriodFilters.metric = metric;
      refreshPayPeriodChart();
    }

    function renderPayPeriodJingdaiOrgs(orgs) {
      const container = document.getElementById('payPeriodJingdaiOrgChecks');
      if (!orgs || orgs.length === 0) { container.innerHTML = ''; return; }
      const labels = orgs.map(org => {
        const checked = payPeriodFilters.orgsInitialized ? (payPeriodFilters.jingdaiOrgs[org] !== false) : true;
        if (!payPeriodFilters.orgsInitialized) payPeriodFilters.jingdaiOrgs[org] = true;
        return createCheckboxLabel(org, checked, 'payPeriodJingdaiOrg');
      });
      container.replaceChildren(...labels);
      payPeriodFilters.orgsInitialized = true;
    }

    function bindPayPeriodControls() {
      const pieBtns = document.getElementById('payPeriodPieTypeBtns');
      if (pieBtns && pieBtns.dataset.boundPayPeriodPie !== 'true') {
        pieBtns.dataset.boundPayPeriodPie = 'true';
        pieBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-pay-period-pie-type]');
          if (!button || !pieBtns.contains(button)) return;
          event.preventDefault();
          switchPayPeriodPie(button, button.dataset.payPeriodPieType);
        });
      }

      const yearSelect = document.getElementById('payPeriodYearSelect');
      if (yearSelect && yearSelect.dataset.boundPayPeriodYear !== 'true') {
        yearSelect.dataset.boundPayPeriodYear = 'true';
        yearSelect.addEventListener('change', () => switchPayPeriodYear(yearSelect.value));
      }

      const dimBtns = document.getElementById('payPeriodDimBtns');
      if (dimBtns && dimBtns.dataset.boundPayPeriodDims !== 'true') {
        dimBtns.dataset.boundPayPeriodDims = 'true';
        dimBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-pay-period-dim]');
          if (!button || !dimBtns.contains(button)) return;
          event.preventDefault();
          switchPayPeriodDim(button, button.dataset.payPeriodDim);
        });
      }

      const bizChecks = document.getElementById('payPeriodBizChecks');
      if (bizChecks && bizChecks.dataset.boundPayPeriodBiz !== 'true') {
        bizChecks.dataset.boundPayPeriodBiz = 'true';
        bizChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-pay-period-biz]');
          if (!input || !bizChecks.contains(input)) return;
          togglePayPeriodBiz(input.dataset.payPeriodBiz, input.checked);
        });
      }

      const transformRow = document.getElementById('payPeriodTransformRow');
      if (transformRow && transformRow.dataset.boundPayPeriodChannels !== 'true') {
        transformRow.dataset.boundPayPeriodChannels = 'true';
        transformRow.addEventListener('change', event => {
          const input = event.target.closest('input[data-pay-period-channel]');
          if (!input || !transformRow.contains(input)) return;
          togglePayPeriodChannel(input.dataset.payPeriodChannel, input.checked);
        });
      }

      const transformOrgChecks = document.getElementById('payPeriodTransformOrgChecks');
      if (transformOrgChecks && transformOrgChecks.dataset.boundPayPeriodOrgs !== 'true') {
        transformOrgChecks.dataset.boundPayPeriodOrgs = 'true';
        transformOrgChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-pay-period-org]');
          if (!input || !transformOrgChecks.contains(input)) return;
          togglePayPeriodOrg(input.dataset.payPeriodOrg, input.checked);
        });
      }

      const jingdaiOrgChecks = document.getElementById('payPeriodJingdaiOrgChecks');
      if (jingdaiOrgChecks && jingdaiOrgChecks.dataset.boundPayPeriodJingdaiOrgs !== 'true') {
        jingdaiOrgChecks.dataset.boundPayPeriodJingdaiOrgs = 'true';
        jingdaiOrgChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-pay-period-jingdai-org]');
          if (!input || !jingdaiOrgChecks.contains(input)) return;
          togglePayPeriodJingdaiOrg(input.dataset.payPeriodJingdaiOrg, input.checked);
        });
      }

      const metricBtns = document.getElementById('payPeriodMetricBtns');
      if (metricBtns && metricBtns.dataset.boundPayPeriodMetrics !== 'true') {
        metricBtns.dataset.boundPayPeriodMetrics = 'true';
        metricBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-pay-period-metric]');
          if (!button || !metricBtns.contains(button)) return;
          event.preventDefault();
          switchPayPeriodMetric(button, button.dataset.payPeriodMetric);
        });
      }

      const averageOrgSelect = document.getElementById('payPeriodAverageOrgSelect');
      if (averageOrgSelect && averageOrgSelect.dataset.boundPayPeriodAverageOrg !== 'true') {
        averageOrgSelect.dataset.boundPayPeriodAverageOrg = 'true';
        averageOrgSelect.addEventListener('change', () => {
          payPeriodAverageFilters.org = averageOrgSelect.value || 'all';
          renderPayPeriodAverageTable();
        });
      }

      const averageModeBtns = document.getElementById('payPeriodAverageModeBtns');
      if (averageModeBtns && averageModeBtns.dataset.boundPayPeriodAverageMode !== 'true') {
        averageModeBtns.dataset.boundPayPeriodAverageMode = 'true';
        averageModeBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-pay-period-average-mode]');
          if (!button || !averageModeBtns.contains(button) || button.disabled) return;
          event.preventDefault();
          payPeriodAverageFilters.businessMode = button.dataset.payPeriodAverageMode || 'all';
          renderPayPeriodAverageTable();
        });
      }

      const averageResetBtn = document.getElementById('payPeriodAverageResetBtn');
      if (averageResetBtn && averageResetBtn.dataset.boundPayPeriodAverageReset !== 'true') {
        averageResetBtn.dataset.boundPayPeriodAverageReset = 'true';
        averageResetBtn.addEventListener('click', () => {
          payPeriodAverageFilters.org = 'all';
          payPeriodAverageFilters.businessMode = 'all';
          renderPayPeriodAverageTable();
        });
      }
    }

    bindPayPeriodControls();
    renderPayPeriodMonthFilter();

