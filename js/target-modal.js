// target-modal.js — target setting modal and target data lifecycle
    // ---------- Target Setting System ----------
    const TARGET_STORAGE_KEY = 'business_targets_v1';
    const DEFAULT_DASHBOARD_YEAR_NUM = new Date().getFullYear();
    const DEFAULT_DASHBOARD_YEAR = String(DEFAULT_DASHBOARD_YEAR_NUM);
    let targetData = null;
    let targetDataSource = 'default';

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
      return `${TARGET_STORAGE_KEY}_${year || targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM}`;
    }

    function loadTargetData(year) {
      const desiredYear = parseInt(year || targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM);
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
      const desiredYear = parseInt(year || targetData?.year || selectedYear || DEFAULT_DASHBOARD_YEAR_NUM);
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
      loadTargetData(targetData?.year || selectedYear || DEFAULT_DASHBOARD_YEAR_NUM);
      modalTitle.textContent = '经营目标设置';
      modalOverlay.classList.add('modal-target');
      modalBody.innerHTML = `
        <div class="target-toolbar">
          <label>目标年份</label>
          <select id="targetYearSelect" onchange="changeTargetYear(this.value)">
            ${buildRecentYearOptions(targetData.year)}
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
        targetData = normalizeTargetData(targetData, targetData?.year || DEFAULT_DASHBOARD_YEAR_NUM);
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

