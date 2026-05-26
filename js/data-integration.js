// data-integration.js - API loading, fallback conversion, and dashboard refresh
// ---------- API Integration ----------
    // 如需手动指定后端地址，取消下面一行的注释并修改：
    // const BACKEND_URL = 'http://your-server-ip:45679';
    const API_BASE = typeof BACKEND_URL !== 'undefined' ? BACKEND_URL
      : (window.location.protocol === 'file:' ? 'http://localhost:45679' : '');
    window.API_BASE = API_BASE;

    let apiData = { kpi: null, platform: null, team: null, product: null };
    const apiCache = {};
    let apiAvailable = false;
    const ALLOW_LOCAL_FALLBACK = true;

    function clearRuntimeFallbackYear(year) {
      // Keep local seed data available. API data overwrites it after load; if API is slow
      // or unavailable, the dashboard remains usable instead of rendering blank cards.
    }

    function buildProductQuery(year) {
      const params = new URLSearchParams();
      params.set('dimension', 'product_mix');
      params.set('includeTransform', productFilters.transform ? 'true' : 'false');
      params.set('includeJingdai', productFilters.jingdai ? 'true' : 'false');
      const transformLines = Object.keys(productFilters.transformLines).filter(k => productFilters.transformLines[k]);
      if (productFilters.transform) params.set('transformLines', transformLines.length > 0 ? transformLines.join(',') : '__none__');
      const selectedOrgs = Object.keys(productFilters.jingdaiOrgs).filter(k => productFilters.jingdaiOrgs[k]);
      if (productFilters.orgsInitialized) params.set('jingdaiOrgs', selectedOrgs.length > 0 ? selectedOrgs.join(',') : '__none__');
      // New: org filter, time dim, metric
      if (productFilters.orgs && !productFilters.orgs['all']) {
        const o = Object.keys(productFilters.orgs).filter(k => k !== 'all' && productFilters.orgs[k]);
        if (o.length > 0) params.set('orgs', o.join(','));
      }
      if (productFilters.timeDim && productFilters.timeDim !== 'year' && productFilters.subPeriod !== 'all') {
        if (productFilters.timeDim === 'quarter') {
          const qNum = parseInt(productFilters.subPeriod.replace('Q',''));
          const m = Array.from({length:3},(_,i)=>(qNum-1)*3+i+1).join(',');
          params.set('months', m);
        } else {
          params.set('months', productFilters.subPeriod);
        }
      }
      if (productFilters.metric && productFilters.metric !== 'qj') params.set('metric', productFilters.metric);
      params.set('year', String(year));
      return `/api/product-analysis?${params.toString()}`;
    }

    async function fetchAPIData(year) {
      try {
        const platform = unwrapApiResponse(await fetchJson(`/api/platform-data?year=${year}`, { method: 'GET' }));

        let kpi = null;
        try {
          kpi = unwrapApiResponse(await fetchJson(`/api/kpi?year=${year}`, { method: 'GET' }));
        } catch (e) {
          kpi = null;
        }

        let product = null;
        try {
          product = unwrapApiResponse(await fetchJson(buildProductQuery(year), { method: 'GET' }));
        } catch (e) {
          product = null;
        }

        apiCache[String(year)] = { platform, kpi, product };
        apiData.platform = platform;
        apiData.kpi = kpi;
        apiData.product = product;
        apiAvailable = true;
        return true;
      } catch (e) {
        apiAvailable = false;
        return false;
      }
    }

    function getLatestMonthForYear(year) {
      const pm = platformMock[year];
      const data = pm && pm.year && pm.year.qj;
      if (!data) return 12;
      const channels = Object.keys(data);
      for (let i = 11; i >= 0; i--) {
        if (channels.some(ch => data[ch][i] !== null && data[ch][i] !== undefined && data[ch][i] !== 0)) {
          return i + 1;
        }
      }
      return 12;
    }

    function updateCutoffLabel(year) {
      const el = document.getElementById('dataCutoff');
      if (!el) return;
      const cutoff = apiData?.kpi?.daily_cutoff;
      if (cutoff?.use_daily && cutoff.month && cutoff.day) {
        el.textContent = `数据截止：${year}年${cutoff.month}月${cutoff.day}日`;
        return;
      }
      const latest = getLatestMonthForYear(year);
      el.textContent = `数据截止：${year}年${latest}月`;
    }

    // 检查API数据是否包含有效记录（非空）
    function hasValidApiData(apiPlatform) {
      if (!apiPlatform) return false;
      const perf = apiPlatform.performance;
      const jd = apiPlatform.jingdai;
      const hasPerf = Array.isArray(perf) && perf.length > 0 && perf.some(r => (r.qj_premium || 0) > 0 || (r.gm_premium || 0) > 0);
      const hasJd = Array.isArray(jd) && jd.length > 0 && jd.some(r => (r.qj_premium || 0) > 0 || (r.gm_premium || 0) > 0);
      const hasHr = Array.isArray(apiPlatform.hr) && apiPlatform.hr.length > 0;
      const hasValue = Array.isArray(apiPlatform.value) && apiPlatform.value.length > 0;
      return hasPerf || hasJd || hasHr || hasValue;
    }

    // 将API数据转换为 platformMock 格式
    function convertApiToPlatformMock(apiPlatform, year) {
      const mock = { year: {}, quarter: {}, month: {} };
      ['qj', 'gm', 'zs'].forEach(type => {
        mock.year[type] = { 'OTO': [], '证保': [], '蚁桥': [], '经代': [] };
        for (let m = 0; m < 12; m++) {
          mock.year[type]['OTO'][m] = 0;
          mock.year[type]['证保'][m] = 0;
          mock.year[type]['蚁桥'][m] = 0;
          mock.year[type]['经代'][m] = 0;
        }
      });

      // 填充转型业务数据
      if (apiPlatform.performance) {
        apiPlatform.performance.forEach(r => {
          const m = r.month - 1;
          if (m >= 0 && m < 12) {
            if (mock.year.qj[r.channel]) mock.year.qj[r.channel][m] = r.qj_premium || 0;
            if (mock.year.gm[r.channel]) mock.year.gm[r.channel][m] = r.gm_premium || 0;
            if (mock.year.zs[r.channel]) mock.year.zs[r.channel][m] = r.zs_premium || 0;
          }
        });
      }

      // 填充经代数据
      if (apiPlatform.jingdai) {
        apiPlatform.jingdai.forEach(r => {
          const m = r.month - 1;
          if (m >= 0 && m < 12) {
            mock.year.qj['经代'][m] = r.qj_premium || 0;
            mock.year.gm['经代'][m] = r.gm_premium || 0;
            mock.year.zs['经代'][m] = r.zs_premium || 0;
          }
        });
      }

      // 构建机构级保费索引
      platformOrgPerfData[year] = {};
      if (apiPlatform.org_performance) {
        apiPlatform.org_performance.forEach(r => {
          const m = r.month - 1;
          if (m < 0 || m >= 12) return;
          const ch = r.channel;
          if (!ch) return;
          if (!platformOrgPerfData[year][ch]) {
            platformOrgPerfData[year][ch] = Array.from({ length: 12 }, () => ({ total: { qj: 0, gm: 0, zs: 0 }, orgs: {} }));
          }
          const entry = platformOrgPerfData[year][ch][m];
          const org = r.org || '未知';
          if (!entry.orgs[org]) entry.orgs[org] = { qj: 0, gm: 0, zs: 0 };
          ['qj', 'gm', 'zs'].forEach(t => {
            const col = t === 'qj' ? 'qj_premium' : t === 'gm' ? 'gm_premium' : 'zs_premium';
            const v = r[col] || 0;
            entry.orgs[org][t] += v;
            entry.total[t] += v;
          });
        });
      }

      // 补null表示未到月份：找到第一个全为0的月份之后置null
      const channels = ['OTO', '证保', '蚁桥', '经代'];
      for (let m = 11; m >= 0; m--) {
        const hasData = channels.some(ch => mock.year.qj[ch][m] > 0);
        if (!hasData) {
          channels.forEach(ch => {
            mock.year.qj[ch][m] = null;
            mock.year.gm[ch][m] = null;
            mock.year.zs[ch][m] = null;
          });
        } else break;
      }

      // quarter 数据：直接使用该季度3个月的真实月度数据（不再伪造日累计）
      ['Q1', 'Q2', 'Q3', 'Q4'].forEach((q, qi) => {
        const qm = [qi * 3, qi * 3 + 1, qi * 3 + 2];
        mock.quarter[q] = { qj: {}, gm: {}, zs: {} };
        ['qj', 'gm', 'zs'].forEach(t => {
          mock.quarter[q][t] = {};
          channels.forEach(ch => {
            // 直接取该季度3个月的真实月度数据（null 保留表示未到月份）
            mock.quarter[q][t][ch] = qm.map(i => mock.year[t][ch][i]);
          });
        });
      });

      // month 数据：使用真实日数据生成日累计序列（如果日数据不存在则退化为单点）
      const dailyIndex = {};
      if (apiPlatform.daily_performance) {
        apiPlatform.daily_performance.forEach(r => {
          const monthKey = normalizeMonth(r.month);
          if (!monthKey) return;
          const key = `${monthKey}|${r.channel}`;
          if (!dailyIndex[key]) dailyIndex[key] = {};
          dailyIndex[key][r.day] = r;
        });
      }

      // 经代日累计来源必须清晰：daily_performance 已含经代时不再叠加 jingdai_daily。
      if (apiPlatform.jingdai_daily && !dailyRowsContainJingdai(apiPlatform.daily_performance || [])) {
        apiPlatform.jingdai_daily.forEach(r => {
          const monthKey = normalizeMonth(r.month);
          if (!monthKey) return;
          const key = `${monthKey}|经代`;
          if (!dailyIndex[key]) dailyIndex[key] = {};
          dailyIndex[key][r.day] = r;
        });
      }

      for (let mon = 1; mon <= 12; mon++) {
        mock.month[mon] = { qj: {}, gm: {}, zs: {} };
        ['qj', 'gm', 'zs'].forEach(t => {
          mock.month[mon][t] = {};
          channels.forEach(ch => {
            const yearVal = mock.year[t][ch][mon - 1];
            if (yearVal === null || yearVal === undefined) {
              mock.month[mon][t][ch] = [];
              return;
            }
            const key = `${mon}|${ch}`;
            const dailyData = dailyIndex[key];
            const dim = dailyDisplayEndDay(year, mon);
            if (dailyData) {
              const cum = [];
              let sum = 0;
              const col = t === 'qj' ? 'qj_premium' : t === 'gm' ? 'gm_premium' : 'zs_premium';
              for (let d = 1; d <= dim; d++) {
                const dr = dailyData[d];
                const val = dr ? (dr[col] || 0) : 0;
                sum += val;
                cum.push(Math.round(sum * 10) / 10);
              }
              mock.month[mon][t][ch] = cum;
            } else {
              mock.month[mon][t][ch] = [];
            }
          });
        });
      }

      return { [year]: mock };
    }

    function mergeProductRows(rows, mixedSources = false) {
      const merged = {};
      rows.forEach(row => {
        const sourcePrefix = mixedSources && row.source ? `${row.source}-` : '';
        const name = sourcePrefix + (row.name || '未分类');
        if (!merged[name]) merged[name] = { name, premium: 0, count: 0 };
        merged[name].premium += Number(row.premium ?? row.value ?? 0) || 0;
        merged[name].count += Number(row.count ?? 0) || 0;
      });
      const sorted = Object.values(merged).sort((a, b) => Math.abs(b.premium) - Math.abs(a.premium)).slice(0, 20);
      return {
        premium: sorted.filter(r => r.premium !== 0).map(r => ({ name: r.name, value: Math.round(r.premium * 100) / 100 })),
        count: sorted.filter(r => r.count !== 0).map(r => ({ name: r.name, value: Math.round(r.count) }))
      };
    }

    function productFallbackOrgs(year) {
      const groups = productFallbackData[String(year)] || {};
      return Object.keys(groups).filter(k => k.startsWith('jingdai:')).map(k => k.slice('jingdai:'.length));
    }

    function applyProductFallback(year) {
      const groups = productFallbackData[String(year)] || {};
      const rows = [];
      const transformLines = Object.keys(productFilters.transformLines).filter(k => productFilters.transformLines[k]);
      const mixedSources = productFilters.transform && productFilters.jingdai;
      if (productFilters.transform) {
        transformLines.forEach(line => rows.push(...(groups[`transform:${line}`] || []).map(row => ({ ...row, source: '转型' }))));
      }
      const orgs = productFallbackOrgs(year);
      renderProductJingdaiOrgs(orgs);
      if (productFilters.jingdai) {
        const selectedOrgs = productFilters.orgsInitialized
          ? Object.keys(productFilters.jingdaiOrgs).filter(k => productFilters.jingdaiOrgs[k])
          : orgs;
        selectedOrgs.forEach(org => rows.push(...(groups[`jingdai:${org}`] || []).map(row => ({ ...row, source: '经代' }))));
      }
      const data = mergeProductRows(rows, mixedSources);
      productData.premium = data.premium;
      productData.count = data.count;
      if (typeof renderProductTopTable === 'function') renderProductTopTable([]);
      return productData.premium.length > 0 || productData.count.length > 0;
    }

    function updateProductDataFromApi() {
      const product = apiData.product;
      if (!product || !Array.isArray(product.premium)) return applyProductFallback(selectedYear || DEFAULT_DASHBOARD_YEAR);
      renderProductJingdaiOrgs(product.jingdaiOrgs || []);
      if (product.premium.length === 0) {
        return applyProductFallback(selectedYear || DEFAULT_DASHBOARD_YEAR);
      }
      productData.premium = product.premium;
      productData.count = Array.isArray(product.count) && product.count.length > 0 ? product.count : product.premium;
      if (typeof renderProductTopTable === 'function') renderProductTopTable(product.topProducts || []);
      return true;
    }

    async function fetchProductData(year) {
      try {
        apiData.product = unwrapApiResponse(await fetchJson(buildProductQuery(year), { method: 'GET' }));
        return updateProductDataFromApi();
      } catch (e) {
        console.error('fetchProductData error:', e);
        return applyProductFallback(year);
      }
    }

    function createCheckboxLabel(labelText, checked, onChange) {
      const label = document.createElement('label');
      label.className = 'check-label';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = checked !== false;
      input.dataset.org = String(labelText || '');
      input.addEventListener('change', () => onChange(input.dataset.org, input.checked));
      const span = document.createElement('span');
      span.textContent = String(labelText || '');
      label.appendChild(input);
      label.appendChild(document.createTextNode(' '));
      label.appendChild(span);
      return label;
    }

    function renderProductJingdaiOrgs(orgs) {
      const wrapper = document.getElementById('productJingdaiOrgChecks');
      if (!wrapper || !Array.isArray(orgs)) return;
      if (!productFilters.orgsInitialized) {
        orgs.forEach(org => { productFilters.jingdaiOrgs[org] = true; });
        productFilters.orgsInitialized = true;
      }
      wrapper.replaceChildren(...orgs.map(org => (
        createCheckboxLabel(org, productFilters.jingdaiOrgs[org] !== false, toggleProductJingdaiOrg)
      )));
    }

    async function refreshProductChart() {
      await fetchProductData(selectedYear || DEFAULT_DASHBOARD_YEAR);
      productChart.setOption(getPieOption(currentPieType), true);
    }

    async function recalculateDashboard() {
      const btn = document.getElementById('recalcBtn');
      const original = btn ? btn.textContent : '';
      if (btn) {
        btn.textContent = '计算中...';
        btn.disabled = true;
      }
      try {
        const platformYear = selectedYear || DEFAULT_DASHBOARD_YEAR;
        await fetchTargetData(platformYear);
        if (selectedTeamYear && selectedTeamYear !== platformYear) {
          await loadYearFromApi(selectedTeamYear, { updateKpi: false, updateProduct: false });
        }
        await loadYearFromApi(platformYear, { updateKpi: true, updateProduct: true });
        await refreshPlatformChart();
        productChart.setOption(getPieOption(currentPieType), true);
        teamChart.setOption(getTeamOption(), true);
        if (typeof renderTeamEnhancedPanel === 'function') renderTeamEnhancedPanel();
        updateCutoffLabel(platformYear);
        updateKPICards();
        if (btn) {
          btn.textContent = '已重算';
          setTimeout(() => { btn.textContent = original; }, 900);
        }
      } catch (e) {
        console.error('recalculateDashboard error:', e);
        if (btn) btn.textContent = '重算失败';
      } finally {
        if (btn) {
          setTimeout(() => {
            btn.disabled = false;
            if (btn.textContent === '重算失败') btn.textContent = original;
          }, 900);
        }
      }
    }

    // 将API数据转换为 teamMock 格式
    function convertApiToTeamMock(apiPlatform, year) {
      const mock = {
        headcount: { 'OTO': [], '证保': [], '蚁桥': [] },
        activeHeadcount: { 'OTO': [], '证保': [], '蚁桥': [] },
        premium: { 'OTO': [], '证保': [], '蚁桥': [] }
      };
      for (let m = 0; m < 12; m++) {
        ['OTO', '证保', '蚁桥'].forEach(ch => {
          mock.headcount[ch][m] = null;
          mock.activeHeadcount[ch][m] = null;
          mock.premium[ch][m] = null;
        });
      }

      // Build org-level data
      const orgData = {};
      ORG_LIST_TEAM.forEach(org => {
        orgData[org] = {
          headcount: { 'OTO': [], '证保': [], '蚁桥': [] },
          activeHeadcount: { 'OTO': [], '证保': [], '蚁桥': [] },
          premium: { 'OTO': [], '证保': [], '蚁桥': [] }
        };
        for (let m = 0; m < 12; m++) {
          ['OTO', '证保', '蚁桥'].forEach(ch => {
            orgData[org].headcount[ch][m] = null;
            orgData[org].activeHeadcount[ch][m] = null;
            orgData[org].premium[ch][m] = null;
          });
        }
      });

      if (apiPlatform.org_hr) {
        apiPlatform.org_hr.forEach(r => {
          const m = r.month - 1;
          const org = r.org;
          if (m >= 0 && m < 12 && orgData[org] && orgData[org].headcount[r.channel]) {
            orgData[org].headcount[r.channel][m] = Math.round((r.start_headcount + r.end_headcount) / 2);
            orgData[org].activeHeadcount[r.channel][m] = r.active_headcount;
          }
        });
      }

      if (apiPlatform.org_performance) {
        apiPlatform.org_performance.forEach(r => {
          const m = r.month - 1;
          const org = r.org;
          if (m >= 0 && m < 12 && orgData[org] && orgData[org].premium[r.channel]) {
            orgData[org].premium[r.channel][m] = r.qj_premium || 0;
          }
        });
      }

      teamOrgData[year] = orgData;

      if (apiPlatform.hr) {
        apiPlatform.hr.forEach(r => {
          const m = r.month - 1;
          if (m >= 0 && m < 12 && mock.headcount[r.channel]) {
            mock.headcount[r.channel][m] = Math.round((r.start_headcount + r.end_headcount) / 2);
            mock.activeHeadcount[r.channel][m] = r.active_headcount;
          }
        });
      }

      if (apiPlatform.performance) {
        apiPlatform.performance.forEach(r => {
          const m = r.month - 1;
          if (m >= 0 && m < 12 && mock.premium[r.channel]) {
            mock.premium[r.channel][m] = r.qj_premium || 0;
          }
        });
      }

      return { [year]: mock };
    }
