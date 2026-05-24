// target-modal.js — 弹窗系统 + 目标设置
(function (window) {
  // ===== Modal System =====
  <script>
    // ---------- Modal System ----------
    const modalOverlay = document.getElementById('modalOverlay');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');

    async function openModal(type) {
      if (type === 'overall' || type === 'value') {
        await fetchTargetData();
      }
      const content = getModalContent(type);
      modalTitle.textContent = content.title;
      modalBody.innerHTML = content.body;
      modalOverlay.classList.add('active');
      if (content.initChart) {
        setTimeout(content.initChart, 100);
      }
    }

    function closeModal(e) {
      if (!e || e.target === modalOverlay) {
        modalOverlay.classList.remove('active');
        modalOverlay.classList.remove('modal-target');
      }
    }

  // ===== Target Setting =====
    // ---------- Target Setting System ----------
    const TARGET_STORAGE_KEY = 'business_targets_v1';
    let targetData = null;
    let targetDataSource = 'default';

    function createDefaultTargetData(year) {
      const metrics = ['整体', '经代', '转型业务', 'OTO', '证保', '蚁桥'];
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
      const qFactors = [0.22, 0.25, 0.26, 0.27];
      const mFactors = [0.07,0.07,0.08,0.08,0.09,0.09,0.08,0.08,0.09,0.09,0.09,0.09];
      const data = { year: parseInt(year), categories: {}, orgTargets: {} };
      categories.forEach(cat => {
        data.categories[cat.key] = { name: cat.name, color: cat.color, metrics: {} };
        metrics.forEach((m, i) => {
          const yearVal = cat.yearTargets[i];
          data.categories[cat.key].metrics[m] = {
            year: yearVal,
            quarter: qFactors.map(f => Math.round(yearVal * f)),
            month: mFactors.map(f => Math.round(yearVal * f))
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
      const base = createDefaultTargetData(year || data?.year || 2026);
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
            metricData.quarter = [Math.round(v*0.22), Math.round(v*0.25), Math.round(v*0.26), Math.round(v*0.27)];
          }
          if (!Array.isArray(metricData.quarter)) metricData.quarter = [0,0,0,0];
          if (typeof metricData.month === 'number') {
            const v = metricData.month;
            const factors = [0.07,0.07,0.08,0.08,0.09,0.09,0.08,0.08,0.09,0.09,0.09,0.09];
            metricData.month = factors.map(f => Math.round(v * f * 12));
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
      return `${TARGET_STORAGE_KEY}_${year || targetData?.year || 2026}`;
    }

    function loadTargetData(year) {
      const desiredYear = parseInt(year || targetData?.year || 2026);
      if (targetData && targetData.year === desiredYear) {
        targetData = normalizeTargetData(targetData, desiredYear);
        return;
      }
      const saved = localStorage.getItem(targetStorageKey(desiredYear)) || localStorage.getItem(TARGET_STORAGE_KEY);
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
      if (targetDataSource === 'local') return '本地缓存目标';
      return '默认目标，服务端尚未配置正式目标';
    }

    async function fetchTargetData(year) {
      const desiredYear = parseInt(year || targetData?.year || selectedYear || 2026);
      try {
        const data = unwrapApiResponse(await fetchJson(`/api/targets?year=${desiredYear}`, { method: 'GET' }));
        const hasServerTarget = !!(data && data.categories);
        targetData = normalizeTargetData(hasServerTarget ? data : createDefaultTargetData(desiredYear), desiredYear);
        targetDataSource = hasServerTarget ? 'server' : 'default';
        localStorage.setItem(targetStorageKey(desiredYear), JSON.stringify(targetData));
        return true;
      } catch(e) {
        loadTargetData(desiredYear);
        return false;
      }
    }

    async function openTargetModal() {
      loadTargetData(targetData?.year || selectedYear || 2026);
      modalTitle.textContent = '经营目标设置';
      modalOverlay.classList.add('modal-target');
      modalBody.innerHTML = `
        <div class="target-toolbar">
          <label>目标年份</label>
          <select id="targetYearSelect" onchange="changeTargetYear(this.value)">
            <option value="2026" ${targetData.year === 2026 ? 'selected' : ''}>2026</option>
            <option value="2025" ${targetData.year === 2025 ? 'selected' : ''}>2025</option>
            <option value="2024" ${targetData.year === 2024 ? 'selected' : ''}>2024</option>
          </select>
          <span id="targetSourceNote" style="color:var(--text-secondary);font-size:12px;">单位：万 · ${targetSourceLabel()}</span>
          <div style="flex:1;"></div>
          <button class="chart-btn" onclick="exportTargetJSON()">导出 JSON</button>
          <button class="chart-btn" onclick="document.getElementById('targetFileInput').click()">导入 JSON</button>
          <input type="file" id="targetFileInput" accept=".json" style="display:none;" onchange="importTargetJSON(this)">
          <button class="chart-btn active" onclick="saveTargetData(event)">保存</button>
        </div>
        <div class="target-grid" id="targetGrid"></div>
      `;
      await fetchTargetData(targetData.year);
      const select = document.getElementById('targetYearSelect');
      if (select) select.value = targetData.year;
      const note = document.getElementById('targetSourceNote');
      if (note) note.textContent = `单位：万 · ${targetSourceLabel()}`;
      renderTargetForm();
      modalOverlay.classList.add('active');
    }

    async function changeTargetYear(year) {
      await fetchTargetData(parseInt(year));
      renderTargetForm();
    }

    function renderTargetForm() {
      const grid = document.getElementById('targetGrid');
      if (!grid) return;
      grid.innerHTML = '';
      Object.entries(targetData.categories).forEach(([catKey, cat]) => {
        const card = document.createElement('div');
        card.className = 'target-card';
        card.innerHTML = `
          <div class="target-card-header">
            <span class="icon" style="background:${cat.color}"></span>
            ${cat.name}目标
          </div>
          <div class="target-card-body">${renderTargetCategoryTable(catKey, cat)}</div>
        `;
        grid.appendChild(card);
      });
      renderOrgTargetForm(grid);
    }

    function renderTargetCategoryTable(catKey, cat) {
      const metrics = ['整体', '经代', '转型业务', 'OTO', '证保', '蚁桥'];

      // 年度目标
      let html = `
        <div class="target-dim-title">年度目标</div>
        <table class="target-table">
          <thead><tr><th style="width:40%">口径</th><th>目标值（万）</th></tr></thead>
          <tbody>
            ${metrics.map(m => `
              <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                <td>${m}</td>
                <td><input type="number" class="target-input"
                  value="${cat.metrics[m]?.year ?? 0}"
                  data-cat="${catKey}" data-metric="${m}" data-dim="year"
                  onchange="updateTargetValue(this)"></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      // 季度目标（Q1-Q4）
      html += `
        <div class="target-dim-title">季度目标</div>
        <table class="target-table">
          <thead><tr><th>口径</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr></thead>
          <tbody>
            ${metrics.map(m => `
              <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                <td>${m}</td>
                ${[0,1,2,3].map(q => `
                  <td><input type="number" class="target-input target-input-sm"
                    value="${cat.metrics[m]?.quarter?.[q] ?? 0}"
                    data-cat="${catKey}" data-metric="${m}" data-dim="quarter" data-idx="${q}"
                    onchange="updateTargetValue(this)"></td>
                `).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      // 月度目标 - 上半年
      html += `
        <div class="target-dim-title">月度目标（1-6月）</div>
        <table class="target-table">
          <thead><tr><th>口径</th>${[1,2,3,4,5,6].map(mo => `<th>${mo}月</th>`).join('')}</tr></thead>
          <tbody>
            ${metrics.map(m => `
              <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                <td>${m}</td>
                ${[0,1,2,3,4,5].map(mi => `
                  <td><input type="number" class="target-input target-input-sm"
                    value="${cat.metrics[m]?.month?.[mi] ?? 0}"
                    data-cat="${catKey}" data-metric="${m}" data-dim="month" data-idx="${mi}"
                    onchange="updateTargetValue(this)"></td>
                `).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      // 月度目标 - 下半年
      html += `
        <div class="target-dim-title">月度目标（7-12月）</div>
        <table class="target-table">
          <thead><tr><th>口径</th>${[7,8,9,10,11,12].map(mo => `<th>${mo}月</th>`).join('')}</tr></thead>
          <tbody>
            ${metrics.map(m => `
              <tr class="${m === 'OTO' || m === '证保' || m === '蚁桥' ? 'sub' : ''}">
                <td>${m}</td>
                ${[6,7,8,9,10,11].map(mi => `
                  <td><input type="number" class="target-input target-input-sm"
                    value="${cat.metrics[m]?.month?.[mi] ?? 0}"
                    data-cat="${catKey}" data-metric="${m}" data-dim="month" data-idx="${mi}"
                    onchange="updateTargetValue(this)"></td>
                `).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;

      return html;
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
      const card = document.createElement('div');
      card.className = 'target-card';
      card.style.gridColumn = '1 / -1';
      card.innerHTML = `
        <div class="target-card-header">
          <span class="icon" style="background:#64748b"></span>
          机构目标
        </div>
        <div class="target-card-body" id="orgTargetBody">${renderOrgTargetTable()}</div>
      `;
      grid.appendChild(card);
    }

    function switchOrgTargetDim(dim) {
      orgTargetDim = dim;
      const body = document.getElementById('orgTargetBody');
      if (body) body.innerHTML = renderOrgTargetTable();
    }

    function renderOrgTargetTable() {
      const dim = orgTargetDim;
      const isYear = dim === 'year';
      const isQuarter = dim === 'quarter';
      const isMonth1 = dim === 'month1';
      const isMonth2 = dim === 'month2';

      let html = `
        <div style="display:flex;gap:6px;margin-bottom:12px;">
          <button class="org-dim-btn ${isYear ? 'active' : ''}" onclick="switchOrgTargetDim('year')">年度</button>
          <button class="org-dim-btn ${isQuarter ? 'active' : ''}" onclick="switchOrgTargetDim('quarter')">季度</button>
          <button class="org-dim-btn ${isMonth1 ? 'active' : ''}" onclick="switchOrgTargetDim('month1')">月度（1-6月）</button>
          <button class="org-dim-btn ${isMonth2 ? 'active' : ''}" onclick="switchOrgTargetDim('month2')">月度（7-12月）</button>
        </div>
        <div style="overflow-x:auto;">
          <table class="target-table org-target-table">
            <thead>
              <tr>
                <th style="width:60px;">机构</th>
                <th style="width:60px;">业务模式</th>
      `;

      if (isYear) {
        html += ORG_TARGET_CATS.map(c => `<th style="text-align:center;">${c.name}（万）</th>`).join('');
      } else if (isQuarter) {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="4" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th></th><th></th>`;
        ORG_TARGET_CATS.forEach(() => {
          html += `<th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th>`;
        });
      } else if (isMonth1) {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="6" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th></th><th></th>`;
        ORG_TARGET_CATS.forEach(() => {
          [1,2,3,4,5,6].forEach(m => { html += `<th>${m}月</th>`; });
        });
      } else {
        ORG_TARGET_CATS.forEach(c => {
          html += `<th colspan="6" style="text-align:center;background:var(--bg);">${c.name}</th>`;
        });
        html += `</tr><tr><th></th><th></th>`;
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
            html += `<td rowspan="${ORG_TARGET_CHANNELS.length}" style="font-weight:600;vertical-align:middle;">${org}</td>`;
          }
          html += `<td>${ch}</td>`;

          ORG_TARGET_CATS.forEach(cat => {
            const t = targets[cat.key] || { year: 0, quarter: [0,0,0,0], month: Array(12).fill(0) };
            if (isYear) {
              html += `<td style="text-align:center;"><input type="number" class="target-input"
                value="${t.year}" data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="year"
                onchange="updateOrgTargetValue(this)" style="width:80px;"></td>`;
            } else if (isQuarter) {
              [0,1,2,3].forEach(qi => {
                html += `<td style="text-align:center;"><input type="number" class="target-input target-input-sm"
                  value="${t.quarter[qi]}" data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="quarter" data-idx="${qi}"
                  onchange="updateOrgTargetValue(this)"></td>`;
              });
            } else if (isMonth1) {
              [0,1,2,3,4,5].forEach(mi => {
                html += `<td style="text-align:center;"><input type="number" class="target-input target-input-sm"
                  value="${t.month[mi]}" data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="month" data-idx="${mi}"
                  onchange="updateOrgTargetValue(this)"></td>`;
              });
            } else {
              [6,7,8,9,10,11].forEach(mi => {
                html += `<td style="text-align:center;"><input type="number" class="target-input target-input-sm"
                  value="${t.month[mi]}" data-org="${org}" data-ch="${ch}" data-cat="${cat.key}" data-dim="month" data-idx="${mi}"
                  onchange="updateOrgTargetValue(this)"></td>`;
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
    }

    async function saveTargetData(evt) {
      const btn = evt ? evt.target : null;
      const original = btn ? btn.textContent : '';
      if (btn) {
        btn.textContent = '保存中...';
        btn.disabled = true;
      }
      try {
        targetData = normalizeTargetData(targetData, targetData?.year || 2026);
        localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
        const resp = await adminFetch(apiUrl(`/api/targets?year=${targetData.year}`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(targetData)
        });
        if (!resp.ok) throw new Error('目标保存失败');
        targetData = normalizeTargetData(unwrapApiResponse(await resp.json()), targetData.year);
        localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
        await recalculateDashboard();
        if (btn) {
          btn.textContent = '已保存';
          setTimeout(() => { btn.textContent = original; closeModal(); }, 800);
        } else {
          closeModal();
        }
      } catch(e) {
        console.error('saveTargetData error:', e);
        if (btn) {
          btn.textContent = '保存失败';
          setTimeout(() => {
            btn.textContent = original;
            btn.disabled = false;
          }, 1200);
        }
      } finally {
        if (btn && btn.textContent !== '保存失败') btn.disabled = false;
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
            localStorage.setItem(targetStorageKey(targetData.year), JSON.stringify(targetData));
            const resp = await adminFetch(apiUrl(`/api/targets?year=${targetData.year}`), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(targetData)
            });
            if (!resp.ok) throw new Error('目标导入保存失败');
            document.getElementById('targetYearSelect').value = targetData.year;
            renderTargetForm();
            await recalculateDashboard();
          }
        } catch(err) { alert('JSON 解析失败'); }
      };
      reader.readAsText(file);
      input.value = '';
    }

    // ---------- KPI Dynamic Calculation ----------


  // ===== Modal Content Generator =====
    function getModalContent(type) {
      switch(type) {
        case 'overall': {
          loadTargetData();
          const year = (apiData.kpi && apiData.kpi.year) || 2026;
          const pm = platformMock[year] || platformMock[2026];
          const qjData = pm ? pm.year.qj : null;
          const targets = targetData.categories.qjPremium.metrics;
          function fmt(n) { return n ? n.toLocaleString('zh-CN', {maximumFractionDigits:0}) : '0'; }
          function calc(a, t) { return t > 0 ? Math.round(a / t * 1000) / 10 : 0; }
          function rc(r) { return r >= 100 ? 'up' : r >= 80 ? 'warning' : 'down'; }
          function sumCh(ch) { if (!qjData || !qjData[ch]) return 0; let s=0; for(const v of qjData[ch]){ if(v==null)break; s+=v;} return s; }
          const otoA = sumCh('OTO'), zbA = sumCh('证保'), yqA = sumCh('蚁桥'), jdA = sumCh('经代');
          const zxA = otoA + zbA + yqA, ztA = jdA + zxA;
          const ztT = targets['整体']?.year || 0, jdT = targets['经代']?.year || 0, zxT = targets['转型业务']?.year || 0;
          const otoT = targets['OTO']?.year || 0, zbT = targets['证保']?.year || 0, yqT = targets['蚁桥']?.year || 0;
          // 动态计算当前月份和季度
          let maxMonth = 0;
          if (qjData) {
            ['OTO','证保','蚁桥','经代'].forEach(ch => {
              if (!qjData[ch]) return;
              for (let i = 0; i < 12; i++) {
                if (qjData[ch][i] != null && qjData[ch][i] > 0) maxMonth = Math.max(maxMonth, i + 1);
              }
            });
          }
          if (!maxMonth) maxMonth = 4;
          const qIdx = Math.ceil(maxMonth / 3) - 1;
          const mIdx = maxMonth - 1;
          const qztT = (targets['整体']?.quarter?.[qIdx]||0), qjdT = (targets['经代']?.quarter?.[qIdx]||0), qzxT = (targets['转型业务']?.quarter?.[qIdx]||0);
          const qotoT = (targets['OTO']?.quarter?.[qIdx]||0), qzbT = (targets['证保']?.quarter?.[qIdx]||0), qyqT = (targets['蚁桥']?.quarter?.[qIdx]||0);
          const mztT = (targets['整体']?.month?.[mIdx]||0), mjdT = (targets['经代']?.month?.[mIdx]||0), mzxT = (targets['转型业务']?.month?.[mIdx]||0);
          const motoT = (targets['OTO']?.month?.[mIdx]||0), mzbT = (targets['证保']?.month?.[mIdx]||0), myqT = (targets['蚁桥']?.month?.[mIdx]||0);
          function qSum(ch, q) { const qm=[q*3,q*3+1,q*3+2]; if(!qjData||!qjData[ch])return 0; let s=0; for(const i of qm){const v=qjData[ch][i]; if(v!=null) s+=v;} return s; }
          function mVal(ch, m) { if(!qjData||!qjData[ch])return 0; const v=qjData[ch][m]; return v!=null?v:0; }
          const qotoA=qSum('OTO',qIdx), qzbA=qSum('证保',qIdx), qyqA=qSum('蚁桥',qIdx), qjdA=qSum('经代',qIdx);
          const qzxA=qotoA+qzbA+qyqA, qztA=qjdA+qzxA;
          const motoA=mVal('OTO',mIdx), mzbA=mVal('证保',mIdx), myqA=mVal('蚁桥',mIdx), mjdA=mVal('经代',mIdx);
          const mzxA=motoA+mzbA+myqA, mztA=mjdA+mzxA;
          const monthLabels = [];
          const chartData = { OTO:[], 证保:[], 蚁桥:[], 经代:[] };
          ['OTO','证保','蚁桥','经代'].forEach(ch=>{ for(let i=0;i<maxMonth;i++){ if (i===0) monthLabels.push((i+1)+'月'); chartData[ch].push(qjData&&qjData[ch]?qjData[ch][i]||0:0); } });
          const qNum = qIdx + 1;
          return {
            title: '期交保费达成率',
            body: `
              <div class="modal-section-title">年度累计</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${fmt(ztT)}</td><td>${fmt(ztA)}</td><td style="color:var(--${rc(calc(ztA,ztT))});">${calc(ztA,ztT)}%</td></tr>
                  <tr><td style="text-align:left;">经代</td><td>${fmt(jdT)}</td><td>${fmt(jdA)}</td><td style="color:var(--${rc(calc(jdA,jdT))});">${calc(jdA,jdT)}%</td></tr>
                  <tr><td style="text-align:left;">转型业务</td><td>${fmt(zxT)}</td><td>${fmt(zxA)}</td><td style="color:var(--${rc(calc(zxA,zxT))});">${calc(zxA,zxT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">OTO</td><td>${fmt(otoT)}</td><td>${fmt(otoA)}</td><td style="color:var(--${rc(calc(otoA,otoT))});">${calc(otoA,otoT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">证保</td><td>${fmt(zbT)}</td><td>${fmt(zbA)}</td><td style="color:var(--${rc(calc(zbA,zbT))});">${calc(zbA,zbT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">蚁桥</td><td>${fmt(yqT)}</td><td>${fmt(yqA)}</td><td style="color:var(--${rc(calc(yqA,yqT))});">${calc(yqA,yqT)}%</td></tr>
                </tbody>
              </table>

              <div class="modal-section-title">季度累计（Q${qNum}）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${fmt(qztT)}</td><td>${fmt(qztA)}</td><td style="color:var(--${rc(calc(qztA,qztT))});">${calc(qztA,qztT)}%</td></tr>
                  <tr><td style="text-align:left;">经代</td><td>${fmt(qjdT)}</td><td>${fmt(qjdA)}</td><td style="color:var(--${rc(calc(qjdA,qjdT))});">${calc(qjdA,qjdT)}%</td></tr>
                  <tr><td style="text-align:left;">转型业务</td><td>${fmt(qzxT)}</td><td>${fmt(qzxA)}</td><td style="color:var(--${rc(calc(qzxA,qzxT))});">${calc(qzxA,qzxT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">OTO</td><td>${fmt(qotoT)}</td><td>${fmt(qotoA)}</td><td style="color:var(--${rc(calc(qotoA,qotoT))});">${calc(qotoA,qotoT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">证保</td><td>${fmt(qzbT)}</td><td>${fmt(qzbA)}</td><td style="color:var(--${rc(calc(qzbA,qzbT))});">${calc(qzbA,qzbT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">蚁桥</td><td>${fmt(qyqT)}</td><td>${fmt(qyqA)}</td><td style="color:var(--${rc(calc(qyqA,qyqT))});">${calc(qyqA,qyqT)}%</td></tr>
                </tbody>
              </table>

              <div class="modal-section-title">月度累计（${maxMonth}月）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${fmt(mztT)}</td><td>${fmt(mztA)}</td><td style="color:var(--${rc(calc(mztA,mztT))});">${calc(mztA,mztT)}%</td></tr>
                  <tr><td style="text-align:left;">经代</td><td>${fmt(mjdT)}</td><td>${fmt(mjdA)}</td><td style="color:var(--${rc(calc(mjdA,mjdT))});">${calc(mjdA,mjdT)}%</td></tr>
                  <tr><td style="text-align:left;">转型业务</td><td>${fmt(mzxT)}</td><td>${fmt(mzxA)}</td><td style="color:var(--${rc(calc(mzxA,mzxT))});">${calc(mzxA,mzxT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">OTO</td><td>${fmt(motoT)}</td><td>${fmt(motoA)}</td><td style="color:var(--${rc(calc(motoA,motoT))});">${calc(motoA,motoT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">证保</td><td>${fmt(mzbT)}</td><td>${fmt(mzbA)}</td><td style="color:var(--${rc(calc(mzbA,mzbT))});">${calc(mzbA,mzbT)}%</td></tr>
                  <tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">蚁桥</td><td>${fmt(myqT)}</td><td>${fmt(myqA)}</td><td style="color:var(--${rc(calc(myqA,myqT))});">${calc(myqA,myqT)}%</td></tr>
                </tbody>
              </table>

              <div id="modalChart" class="modal-chart" style="margin-top:16px;"></div>
            `,
            initChart: () => {
              const chart = echarts.init(document.getElementById('modalChart'));
              chart.setOption({
                tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
                legend: { data: ['OTO', '证保', '蚁桥', '经代'], textStyle: { color: '#94a3b8' }, bottom: 0 },
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
                xAxis: { type: 'category', data: monthLabels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
                yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
                series: [
                  { name: 'OTO', type: 'bar', stack: 'total', data: chartData.OTO, itemStyle: { color: '#3b82f6' } },
                  { name: '证保', type: 'bar', stack: 'total', data: chartData.证保, itemStyle: { color: '#10b981' } },
                  { name: '蚁桥', type: 'bar', stack: 'total', data: chartData.蚁桥, itemStyle: { color: '#f59e0b' } },
                  { name: '经代', type: 'bar', stack: 'total', data: chartData.经代, itemStyle: { color: '#8b5cf6' } }
                ]
              });
            }
          };
        }
        case 'value': {
          loadTargetData();
          const valueTargets = targetData.categories.value.metrics;
          const valueApi = apiData.kpi && apiData.kpi.value ? apiData.kpi.value : {};
          const valueMonthly = { OTO: [], '证保': [], '蚁桥': [], '经代': [] };
          if (apiData.platform && Array.isArray(apiData.platform.value)) {
            apiData.platform.value.forEach(r => {
              if (valueMonthly[r.channel]) valueMonthly[r.channel][(r.month || 1) - 1] = r.value_premium || 0;
            });
          }
          // 动态计算最大月份
          let valueMaxMonth = 0;
          ['OTO','证保','蚁桥','经代'].forEach(ch => {
            const arr = valueMonthly[ch];
            if (!arr) return;
            for (let i = 0; i < arr.length; i++) {
              if (arr[i] > 0) valueMaxMonth = Math.max(valueMaxMonth, i + 1);
            }
          });
          if (!valueMaxMonth) valueMaxMonth = 4;
          const valueQIdx = Math.ceil(valueMaxMonth / 3) - 1;
          const valueMIdx = valueMaxMonth - 1;
          function sumValueMonths(channels, start, end) {
            let sum = 0;
            channels.forEach(ch => {
              for (let i = start; i <= end; i++) sum += valueMonthly[ch]?.[i] || 0;
            });
            return sum;
          }
          const valueRows = [
            { label: '整体', targetKey: '整体', channels: ['经代', 'OTO', '证保', '蚁桥'], sub: false },
            { label: '经代', targetKey: '经代', channels: ['经代'], sub: false },
            { label: '转型业务', targetKey: '转型业务', channels: ['OTO', '证保', '蚁桥'], sub: false },
            { label: 'OTO', targetKey: 'OTO', channels: ['OTO'], sub: true },
            { label: '证保', targetKey: '证保', channels: ['证保'], sub: true },
            { label: '蚁桥', targetKey: '蚁桥', channels: ['蚁桥'], sub: true }
          ];
          function fmtValue(n) { return (n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 }); }
          function calcValueRate(actual, target) { return target > 0 ? Math.round(actual / target * 1000) / 10 : 0; }
          function valueClass(rate) { return rate >= 100 ? 'up' : rate >= 80 ? 'warning' : 'down'; }
          function valueTarget(metric, dim, idx) {
            const item = valueTargets[metric];
            if (!item) return 0;
            if (dim === 'year') return item.year || 0;
            const arr = item[dim];
            return Array.isArray(arr) ? (arr[idx] || 0) : 0;
          }
          function renderValueRows(dim, idx) {
            return valueRows.map(row => {
              const target = valueTarget(row.targetKey, dim, idx);
              const actual = dim === 'year'
                ? sumValueMonths(row.channels, 0, 11)
                : dim === 'quarter'
                  ? sumValueMonths(row.channels, idx * 3, idx * 3 + 2)
                  : sumValueMonths(row.channels, idx, idx);
              const rate = calcValueRate(actual, target);
              return `<tr ${row.label === '整体' ? 'style="font-weight:600;"' : ''}>
                <td style="text-align:left;${row.sub ? 'padding-left:20px;color:var(--text-secondary);' : ''}">${row.label}</td>
                <td>${fmtValue(target)}</td>
                <td>${fmtValue(actual)}</td>
                <td style="color:var(--${valueClass(rate)});">${rate}%</td>
              </tr>`;
            }).join('');
          }
          const valueLabels = [];
          for (let i = 1; i <= valueMaxMonth; i++) valueLabels.push(i + '月');
          return {
            title: '价值达成率',
            body: `
              <div class="modal-section-title">年度累计</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>${renderValueRows('year')}</tbody>
              </table>

              <div class="modal-section-title">季度累计（Q${valueQIdx + 1}）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>${renderValueRows('quarter', valueQIdx)}</tbody>
              </table>

              <div class="modal-section-title">月度目标（${valueMaxMonth}月）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th></tr></thead>
                <tbody>${renderValueRows('month', valueMIdx)}</tbody>
              </table>

              <div id="modalChart" class="modal-chart" style="margin-top:16px;"></div>
              <p style="color: var(--text-secondary); font-size: 13px; margin-top: 8px;">注：当前价值清单覆盖转型业务，若后续补充经代价值数据，整体口径将自动纳入。</p>
            `,
            initChart: () => {
              const chart = echarts.init(document.getElementById('modalChart'));
              chart.setOption({
                tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
                legend: { data: ['OTO', '证保', '蚁桥'], textStyle: { color: '#94a3b8' }, bottom: 0 },
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
                xAxis: { type: 'category', data: valueLabels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
                yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
                series: [
                  { name: 'OTO', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly.OTO[i]||0), itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: 0.1 } },
                  { name: '证保', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly['证保'][i]||0), itemStyle: { color: '#10b981' }, areaStyle: { opacity: 0.1 } },
                  { name: '蚁桥', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly['蚁桥'][i]||0), itemStyle: { color: '#f59e0b' }, areaStyle: { opacity: 0.1 } }
                ]
              });
            }
          };
        }
        case 'activity': {
          const kpiData = apiData.kpi || {};
          const hr = kpiData.hr || {};
          const hrPrev = kpiData.hr_prev || {};
          const chs = ['OTO', '证保', '蚁桥'];

          function calcActivity(h) {
            const avg = h?.avg || 0;
            const active = h?.active || 0;
            return avg > 0 ? Math.round(active / avg * 1000) / 10 : 0;
          }

          let totalActive = 0, totalAvg = 0;
          let tfActive = 0, tfAvg = 0;
          const chRows = [];

          chs.forEach(ch => {
            const h = hr[ch];
            const avg = h?.avg || 0;
            const active = h?.active || 0;
            totalActive += active;
            totalAvg += avg;
            tfActive += active;
            tfAvg += avg;
            const rate = calcActivity(h);
            const hPrev = hrPrev[ch];
            const prevRate = calcActivity(hPrev);
            const yoy = prevRate > 0 ? Math.round((rate - prevRate) * 10) / 10 : 0;
            const yoyStr = prevRate > 0 ? (yoy >= 0 ? `+${yoy}pp` : `${yoy}pp`) : '--';
            const yoyCls = yoy >= 0 ? 'up' : 'down';
            chRows.push(`<tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">${ch}</td><td>${active}</td><td>${avg}</td><td style="color:${rate >= 70 ? 'var(--success)' : rate >= 50 ? 'var(--warning)' : 'var(--danger)'}">${rate}%</td><td class="${yoyCls}">${yoy >= 0 && yoyStr !== '--' ? '▲ ' : yoyStr !== '--' ? '▼ ' : ''}${yoyStr}</td></tr>`);
          });

          const totalRate = totalAvg > 0 ? Math.round(totalActive / totalAvg * 1000) / 10 : 0;
          const tfRate = tfAvg > 0 ? Math.round(tfActive / tfAvg * 1000) / 10 : 0;

          // 整体同比
          let totalActivePrev = 0, totalAvgPrev = 0;
          Object.values(hrPrev).forEach(h => {
            totalActivePrev += (h?.active || 0);
            totalAvgPrev += (h?.avg || 0);
          });
          const totalRatePrev = totalAvgPrev > 0 ? Math.round(totalActivePrev / totalAvgPrev * 1000) / 10 : 0;
          const totalYoy = totalRatePrev > 0 ? Math.round((totalRate - totalRatePrev) * 10) / 10 : 0;
          const totalYoyStr = totalRatePrev > 0 ? (totalYoy >= 0 ? `+${totalYoy}pp` : `${totalYoy}pp`) : '--';
          const totalYoyCls = totalYoy >= 0 ? 'up' : 'down';

          // 转型同比
          let tfActivePrev = 0, tfAvgPrev = 0;
          chs.forEach(ch => {
            const h = hrPrev[ch];
            tfActivePrev += (h?.active || 0);
            tfAvgPrev += (h?.avg || 0);
          });
          const tfRatePrev = tfAvgPrev > 0 ? Math.round(tfActivePrev / tfAvgPrev * 1000) / 10 : 0;
          const tfYoy = tfRatePrev > 0 ? Math.round((tfRate - tfRatePrev) * 10) / 10 : 0;
          const tfYoyStr = tfRatePrev > 0 ? (tfYoy >= 0 ? `+${tfYoy}pp` : `${tfYoy}pp`) : '--';
          const tfYoyCls = tfYoy >= 0 ? 'up' : 'down';

          return {
            title: '长险活动率 - 分业务模式',
            body: `
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>长险活动人力</th><th>月均在职人力</th><th>长险活动率</th><th>同比</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${totalActive}</td><td>${totalAvg}</td><td style="color:var(--accent-light);">${totalRate}%</td><td class="${totalYoyCls}">${totalYoy >= 0 && totalYoyStr !== '--' ? '▲ ' : totalYoyStr !== '--' ? '▼ ' : ''}${totalYoyStr}</td></tr>
                  <tr><td style="text-align:left;">转型业务</td><td>${tfActive}</td><td>${tfAvg}</td><td style="color:var(--warning);">${tfRate}%</td><td class="${tfYoyCls}">${tfYoy >= 0 && tfYoyStr !== '--' ? '▲ ' : tfYoyStr !== '--' ? '▼ ' : ''}${tfYoyStr}</td></tr>
                  ${chRows.join('')}
                </tbody>
              </table>
              <p style="color: var(--text-secondary); font-size: 13px; margin-top: 12px;">注：同比为与上年同期活动率的百分点差（pp）。</p>
            `
          };
        }
        case 'percapita': {
          const kpiData = apiData.kpi || {};
          const year = kpiData.year || new Date().getFullYear();
          const platform = apiCache[String(year)]?.platform || {};
          const perfRows = platform.performance || [];
          const hrRows = platform.hr || [];
          if (!perfRows.length || !hrRows.length) {
            return {
              title: '人均保费 - 分业务模式（转型业务）',
              body: '<p style="color: var(--text-secondary);">暂无明细数据，请完成数据导入后再查看该指标。</p>'
            };
          }
          const chs = ['OTO', '证保', '蚁桥'];
          const monthNames = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
          function buildMaps(rows, chKey, valFn) {
            const map = {};
            rows.forEach(r => {
              const m = r.month, ch = r[chKey];
              if (!chs.includes(ch)) return;
              if (!map[m]) map[m] = {};
              map[m][ch] = (map[m][ch] || 0) + valFn(r);
            });
            return map;
          }
          const premMap = buildMaps(perfRows, 'channel', r => r.qj_premium || 0);
          const avgMap = buildMaps(hrRows, 'channel', r => ((r.start_headcount || 0) + (r.end_headcount || 0)) / 2);
          let maxMonth = Math.max(0, ...Object.keys(premMap).map(Number));
          if (!maxMonth) maxMonth = Math.max(0, ...Object.keys(avgMap).map(Number));
          if (!maxMonth) maxMonth = kpiData.hr?.OTO?.month || 1;
          function calcPC(p, a) { return a > 0 ? Math.round(p / a * 100) / 100 : 0; }
          function calcRange(s, e) {
            const res = { ch: {}, totalPrem: 0, totalAvg: 0 };
            chs.forEach(ch => {
              let p = 0, aSum = 0, monthCount = 0;
              for (let m = s; m <= e; m++) {
                p += premMap[m]?.[ch] || 0;
                const avg = avgMap[m]?.[ch];
                if (avg !== undefined && avg !== null) {
                  aSum += avg || 0;
                  monthCount += 1;
                }
              }
              const a = monthCount > 0 ? Math.round(aSum / monthCount * 10) / 10 : 0;
              res.ch[ch] = { prem: p, avg: a, pc: calcPC(p, a) };
              res.totalPrem += p; res.totalAvg += a;
            });
            res.totalAvg = Math.round(res.totalAvg * 10) / 10;
            res.totalPc = calcPC(res.totalPrem, res.totalAvg);
            return res;
          }
          const ytd = calcRange(1, maxMonth);
          const qIdx = Math.ceil(maxMonth / 3);
          const q = calcRange((qIdx - 1) * 3 + 1, Math.min(qIdx * 3, maxMonth));
          const curr = calcRange(maxMonth, maxMonth);
          const prevPlat = apiCache[String(year - 1)]?.platform || {};
          const prevPrem = buildMaps(prevPlat.performance || [], 'channel', r => r.qj_premium || 0);
          const prevAvg = buildMaps(prevPlat.hr || [], 'channel', r => ((r.start_headcount || 0) + (r.end_headcount || 0)) / 2);
          function calcPrev(endM) {
            const res = { ch: {}, totalPc: 0 };
            if (!Object.keys(prevPrem).length) return null;
            let tp = 0, ta = 0;
            chs.forEach(ch => {
              let p = 0, aSum = 0, monthCount = 0;
              for (let m = 1; m <= endM; m++) {
                p += prevPrem[m]?.[ch] || 0;
                const avg = prevAvg[m]?.[ch];
                if (avg !== undefined && avg !== null) {
                  aSum += avg || 0;
                  monthCount += 1;
                }
              }
              const a = monthCount > 0 ? aSum / monthCount : 0;
              res.ch[ch] = calcPC(p, a); tp += p; ta += a;
            });
            res.totalPc = calcPC(tp, ta); return res;
          }
          const prevYtd = calcPrev(maxMonth), prevQ = calcPrev(Math.min(qIdx * 3, maxMonth)), prevCurr = calcPrev(maxMonth);
          function yoyStr(c, p) {
            if (!p || p === 0) return { text: '--', cls: '' };
            const d = Math.round((c - p) * 100) / 100;
            return { text: (d >= 0 ? '+' : '') + d + '万', cls: d >= 0 ? 'up' : 'down' };
          }
          function buildRows(data, prevData, isCurr) {
            return chs.map(ch => {
              const pc = data.ch[ch].pc, prevPc = prevData?.ch?.[ch] || 0;
              const y = yoyStr(pc, prevPc);
              const avg = isCurr ? data.ch[ch].avg : data.ch[ch].avg;
              return `<tr><td style="text-align:left;padding-left:20px;color:var(--text-secondary);">${ch}</td><td>${avg}</td><td style="color:${pc >= 3 ? 'var(--success)' : pc >= 2 ? 'var(--accent-light)' : 'var(--warning)'}">${pc}</td><td class="${y.cls}">${y.text}</td></tr>`;
            }).join('');
          }
          const ytdYoy = yoyStr(ytd.totalPc, prevYtd?.totalPc);
          const qYoy = yoyStr(q.totalPc, prevQ?.totalPc);
          const currYoy = yoyStr(curr.totalPc, prevCurr?.totalPc);
          const chartLabels = [], chartSeries = { OTO: [], 证保: [], 蚁桥: [] };
          for (let m = 1; m <= maxMonth; m++) {
            chartLabels.push(monthNames[m - 1]);
            chs.forEach(ch => { chartSeries[ch].push(calcPC(premMap[m]?.[ch] || 0, avgMap[m]?.[ch] || 0)); });
          }
          return {
            title: '人均保费 - 分业务模式（转型业务）',
            body: `
              <div class="modal-section-title">年度累计（截至${maxMonth}月）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>月均在职人力</th><th>人均保费（万）</th><th>同比</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${ytd.totalAvg}</td><td style="color:var(--accent-light);">${ytd.totalPc}</td><td class="${ytdYoy.cls}">${ytdYoy.text}</td></tr>
                  ${buildRows(ytd, prevYtd, false)}
                </tbody>
              </table>
              <div class="modal-section-title">季度累计（Q${qIdx}）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>月均在职人力</th><th>人均保费（万）</th><th>同比</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${q.totalAvg}</td><td style="color:var(--accent-light);">${q.totalPc}</td><td class="${qYoy.cls}">${qYoy.text}</td></tr>
                  ${buildRows(q, prevQ, false)}
                </tbody>
              </table>
              <div class="modal-section-title">当月（${maxMonth}月）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>月均在职人力</th><th>人均保费（万）</th><th>同比</th></tr></thead>
                <tbody>
                  <tr style="font-weight:600;"><td style="text-align:left;">整体</td><td>${curr.totalAvg}</td><td style="color:var(--accent-light);">${curr.totalPc}</td><td class="${currYoy.cls}">${currYoy.text}</td></tr>
                  ${buildRows(curr, prevCurr, true)}
                </tbody>
              </table>
              <p style="color: var(--text-secondary); font-size: 13px; margin-top: 12px;">注：人均保费 = 新单保费 ÷ 月均在职人力，仅计算转型业务。同比为与上年同期人均保费的绝对差值（万元）。</p>
              <div id="modalChart" class="modal-chart" style="margin-top:16px;"></div>
            `,
            initChart: () => {
              const chart = echarts.init(document.getElementById('modalChart'));
              chart.setOption({
                tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
                legend: { data: ['OTO', '证保', '蚁桥'], textStyle: { color: '#94a3b8' }, bottom: 0 },
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
                xAxis: { type: 'category', data: chartLabels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
                yAxis: { type: 'value', name: '万', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
                series: [
                  { name: 'OTO', type: 'line', smooth: true, data: chartSeries.OTO, itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: 0.1 } },
                  { name: '证保', type: 'line', smooth: true, data: chartSeries.证保, itemStyle: { color: '#10b981' }, areaStyle: { opacity: 0.1 } },
                  { name: '蚁桥', type: 'line', smooth: true, data: chartSeries.蚁桥, itemStyle: { color: '#f59e0b' }, areaStyle: { opacity: 0.1 } }
                ]
              });
            }
          };
        }
        case 'annuity': {
          const kpiData = apiData?.kpi || {};
          const chs = ['OTO','证保','蚁桥'];
          const metrics = targetData?.categories?.shangbao?.metrics || {};
          let chVals = {}; chs.forEach(c => chVals[c] = 0);
          if (orgKpiData?.perf) {
            Object.entries(orgKpiData.perf).forEach(([key, item]) => {
              const ch = chs.find(c => key.endsWith('|' + c));
              if (ch) chVals[ch] = (chVals[ch] || 0) + (item.year?.product_annuity || 0);
            });
          }
          const tfActual = Math.round((kpiData.annuity_tf ?? Object.values(chVals).reduce((s, v) => s + v, 0)) || 0);
          const jdActual = Math.round(kpiData.annuity_jd || 0);
          const targetJd = Math.round(metrics['经代']?.year || 0);
          const targetTf = Math.round(metrics['转型业务']?.year || 0);
          function fmtWan(n) { return Math.round(n || 0).toLocaleString('zh-CN'); }
          function calcRate(actual, target) { return target > 0 ? Math.round(actual / target * 1000) / 10 : null; }
          function rateText(rate) { return rate === null ? '--' : `${rate}%`; }
          function rateColor(rate) {
            if (rate === null) return 'var(--text-secondary)';
            return rate >= 100 ? 'var(--success)' : rate >= 80 ? 'var(--warning)' : 'var(--danger)';
          }
          function mainRow(label, actual, target) {
            const rate = calcRate(actual, target);
            return `<tr><td style="text-align:left;">${label}</td><td>${fmtWan(actual)}万</td><td style="color:${rateColor(rate)}">${rateText(rate)}</td></tr>`;
          }
          const chRows = chs.map(ch => {
            const a = Math.round(chVals[ch] || 0);
            let ct = 0;
            if (targetData?.orgTargets) {
              Object.entries(targetData.orgTargets).forEach(([k, v]) => {
                if (k.endsWith('|' + ch)) ct += (v?.shangbao?.year || 0);
              });
            }
            const rate = calcRate(a, ct || metrics[ch]?.year || 0);
            return `<tr><td>${ch}</td><td>${fmtWan(a)}万</td><td style="color:${rateColor(rate)}">${rateText(rate)}</td></tr>`;
          }).join('');
          return {
            title: '商保年金达成率',
            body: `
              <table class="modal-table">
                <thead><tr><th>业务系列</th><th>年度累计</th><th>达成率</th></tr></thead>
                <tbody>
                  ${mainRow('经代', jdActual, targetJd)}
                  ${mainRow('转型', tfActual, targetTf)}
                </tbody>
              </table>
              <div class="modal-section-title">转型业务分模式</div>
              <table class="modal-table">
                <thead><tr><th>渠道</th><th>年度累计</th><th>达成率</th></tr></thead>
                <tbody>${chRows}</tbody>
              </table>
            `
          };
        }
        case '10year':
        case 'longterm': {
          const is10y = type === '10year';
          const title = is10y ? '10年期产品达成率' : '长险期交达成率';
          const kpiData = apiData.kpi || {};
          const chs = ['OTO','证保','蚁桥'];
          const field = is10y ? 'product_10year' : 'qj_premium';
          let chVals = {}; chs.forEach(c => chVals[c] = 0);
          if (orgKpiData?.perf) {
            Object.entries(orgKpiData.perf).forEach(([key, item]) => {
              const ch = chs.find(c => key.endsWith('|' + c));
              if (ch) chVals[ch] = (chVals[ch] || 0) + (item.year?.[field] || 0);
            });
          }
          if (!is10y && !(kpiData.longterm_qj > 0)) {
            return {
              title,
              body: '<p style="color: var(--text-secondary);">暂无长险期交数据，请完成长险期交聚合后再查看该指标。</p>'
            };
          }
          const tfActual = is10y
            ? Math.round(Object.values(chVals).reduce((s, v) => s + v, 0))
            : Math.round(kpiData.longterm_qj_tf || 0);
          const jdActual = is10y ? 0 : Math.round(kpiData.longterm_qj_jd || 0);
          const targetTf = Math.round(targetData?.categories?.qjPremium?.metrics?.['转型业务']?.year || 0);
          const targetJd = Math.round(targetData?.categories?.qjPremium?.metrics?.['经代']?.year || 0);
          const tfRate = targetTf > 0 ? Math.round(tfActual / targetTf * 1000) / 10 : 0;
          const jdRate = targetJd > 0 ? Math.round(jdActual / targetJd * 1000) / 10 : 0;
          // 同比
          let jdYoy = '--', tfYoy = '--';
          if (is10y) {
            // 10年期同比暂无
          } else if (kpiData.longterm_qj_prev !== undefined) {
            const prevJd = is10y ? 0 : (kpiData.longterm_qj_jd_prev || 0);
            const prevTf = is10y ? 0 : (kpiData.longterm_qj_tf_prev || 0);
            if (prevJd > 0) { const y = Math.round((jdActual/prevJd - 1)*1000)/10; jdYoy = (y>=0?'+':'') + y + '%'; }
            if (prevTf > 0) { const y = Math.round((tfActual/prevTf - 1)*1000)/10; tfYoy = (y>=0?'+':'') + y + '%'; }
          }
          const chRows = chs.map(ch => {
            const a = Math.round(chVals[ch] || 0);
            let ct = 0;
            if (targetData?.orgTargets) {
              Object.entries(targetData.orgTargets).forEach(([k, v]) => {
                if (k.endsWith('|' + ch)) ct += (v?.qjPremium?.year || 0);
              });
            }
            const r = ct > 0 ? Math.round(a / ct * 1000) / 10 : 0;
            return `<tr><td>${ch}</td><td>${a}万</td><td>${r}%</td></tr>`;
          }).join('');
          const yoyCls = (v) => v.startsWith('+') ? 'up' : 'down';
          return {
            title,
            body: `
              <table class="modal-table">
                <thead><tr><th>业务系列</th><th>年度累计</th><th>达成率</th><th>同比</th></tr></thead>
                <tbody>
                  <tr><td>经代业务</td><td>${jdActual}万</td><td style="color:${jdRate>=80?'var(--success)':'var(--warning)'}">${jdRate}%</td>
                    <td class="${yoyCls(jdYoy)}">${jdYoy}</td></tr>
                  <tr><td>转型业务</td><td>${tfActual}万</td><td style="color:${tfRate>=80?'var(--success)':'var(--warning)'}">${tfRate}%</td>
                    <td class="${yoyCls(tfYoy)}">${tfYoy}</td></tr>
                </tbody>
              </table>
              <div class="modal-section-title">转型业务分渠道</div>
              <table class="modal-table">
                <thead><tr><th>渠道</th><th>年度累计</th><th>达成率</th></tr></thead>
                <tbody>${chRows}</tbody>
              </table>
            `
          };
        }
        default:
          return { title: '详情', body: '<p>暂无数据</p>' };
      }
    }

  window.getModalContent = getModalContent;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.openTargetModal = openTargetModal;
  window.saveTargetData = saveTargetData;
  window.loadTargetData = loadTargetData;
  window.fetchTargetData = fetchTargetData;
  window.recalculateDashboard = recalculateDashboard;
})(window);


