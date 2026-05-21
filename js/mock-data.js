// mock-data.js — Mock 数据（teamMock, productFallbackData, API converters）
(function (window) {

  // ===== productFilters =====    const productFilters = {
      transform: true,
      jingdai: true,
      transformLines: { 'OTO': true, '证保': true, '蚁桥': true },
      jingdaiOrgs: {},
      orgsInitialized: false
    };

  // ===== productFallbackData =====    const productFallbackData = {
      "2026": {
        "transform:OTO": [
          {"name":"寿险","premium":6122.98,"count":2199},
          {"name":"年金","premium":2623.49,"count":451},
          {"name":"未分类","premium":56.92,"count":73},
          {"name":"短期险","premium":14.76,"count":222}
        ],
        "transform:证保": [
          {"name":"寿险","premium":1527.55,"count":222},
          {"name":"年金","premium":775.3,"count":42},
          {"name":"短期险","premium":0.11,"count":2}
        ],
        "transform:蚁桥": [
          {"name":"年金","premium":2730.9,"count":3258}
        ],
        "jingdai:支付宝-电商": [
          {"name":"4265e定盈互联网","premium":0,"count":6}
        ],
        "jingdai:蚂蚁保": [
          {"name":"7030e满利互联网","premium":17655.42,"count":368},
          {"name":"7043e满利2.0互联网","premium":2116.84,"count":79},
          {"name":"7032e百分年金互联网","premium":1906.06,"count":496},
          {"name":"7033e起领2.0互联网","premium":1679.88,"count":552},
          {"name":"7037e满多互联网","premium":777.22,"count":263},
          {"name":"7038e成长互联网","premium":653.92,"count":582},
          {"name":"7041利多多","premium":361.94,"count":65},
          {"name":"7031鑫多多2.0互联网","premium":292.73,"count":388},
          {"name":"4144专属商业养老-B账户","premium":160.34,"count":1023},
          {"name":"4265e定盈互联网","premium":83.83,"count":221},
          {"name":"4143专属商业养老-A账户","premium":9.06,"count":219},
          {"name":"7040e满分分红","premium":4.08,"count":16}
        ],
        "jingdai:京东保": [
          {"name":"7032e百分年金互联网","premium":28.36,"count":101},
          {"name":"7034e启航互联网","premium":16.9,"count":9},
          {"name":"7031鑫多多2.0互联网","premium":9.99,"count":97}
        ],
        "jingdai:微保": [
          {"name":"7032e百分年金互联网","premium":551.28,"count":439},
          {"name":"7035e百分2.0互联网","premium":136.73,"count":149},
          {"name":"7031鑫多多2.0互联网","premium":100.3,"count":182}
        ],
        "jingdai:招行网销": [
          {"name":"7031鑫多多2.0互联网","premium":1231.01,"count":436},
          {"name":"7032e百分年金互联网","premium":258.92,"count":148},
          {"name":"4143专属商业养老-A账户","premium":0.1,"count":1},
          {"name":"4144专属商业养老-B账户","premium":0.03,"count":1}
        ],
        "jingdai:慧择经纪": [
          {"name":"7031鑫多多2.0互联网","premium":122.46,"count":109},
          {"name":"7037e满多互联网","premium":2.67,"count":5},
          {"name":"4058荣耀金账户","premium":0,"count":3},
          {"name":"4059荣耀钻账户","premium":0,"count":1}
        ],
        "jingdai:经代自营": [
          {"name":"4144专属商业养老-B账户","premium":10,"count":71},
          {"name":"4248环球共享","premium":1.92,"count":3},
          {"name":"4143专属商业养老-A账户","premium":1.48,"count":28},
          {"name":"7017全球药械2022互联网","premium":0.14,"count":8}
        ]
      }
    };

  // ===== teamMock =====    const teamMock = {
  "2024": {
    "headcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  },
  "2025": {
    "headcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  },
  "2026": {
    "headcount": {
      "OTO": [
        415,
        381,
        368,
        347,
        332,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        57,
        54,
        55,
        54,
        53,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        60,
        63,
        64,
        65,
        67,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "activeHeadcount": {
      "OTO": [
        286,
        113,
        161,
        186,
        22,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        32,
        13,
        21,
        24,
        2,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        63,
        61,
        63,
        64,
        30,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    },
    "premium": {
      "OTO": [
        5848.9,
        393.5,
        1606.5,
        901.7,
        67.6,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "证保": [
        1151.6,
        230.5,
        217.9,
        502.9,
        200.1,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ],
      "蚁桥": [
        818.6,
        528.0,
        868.4,
        504.0,
        11.9,
        null,
        null,
        null,
        null,
        null,
        null,
        null
      ]
    }
  }
  };

  // ===== API Integration =====
    const API_BASE = typeof BACKEND_URL !== 'undefined' ? BACKEND_URL
      : (window.location.protocol === 'file:' ? 'http://localhost:45679' : '');
    window.API_BASE = API_BASE;

    let apiData = { kpi: null, platform: null, team: null, product: null };
    const apiCache = {};
    let apiAvailable = false;

    function buildProductQuery(year) {
      const params = new URLSearchParams();
      params.set('dimension', 'product_mix');
      params.set('includeTransform', productFilters.transform ? 'true' : 'false');
      params.set('includeJingdai', productFilters.jingdai ? 'true' : 'false');
      const transformLines = Object.keys(productFilters.transformLines).filter(k => productFilters.transformLines[k]);
      if (productFilters.transform) params.set('transformLines', transformLines.length > 0 ? transformLines.join(',') : '__none__');
      const selectedOrgs = Object.keys(productFilters.jingdaiOrgs).filter(k => productFilters.jingdaiOrgs[k]);
      if (productFilters.orgsInitialized) params.set('jingdaiOrgs', selectedOrgs.length > 0 ? selectedOrgs.join(',') : '__none__');
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
      return '/api/product-analysis?' + params.toString();
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
      const daysInMonthArr = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
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
            const dim = daysInMonthArr[mon - 1];
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
      return productData.premium.length > 0 || productData.count.length > 0;
    }

    function updateProductDataFromApi() {
      const product = apiData.product;
      if (!product || !Array.isArray(product.premium)) return applyProductFallback(selectedYear || '2026');
      renderProductJingdaiOrgs(product.jingdaiOrgs || []);
      if (product.premium.length === 0) {
        return applyProductFallback(selectedYear || '2026');
      }
      productData.premium = product.premium;
      productData.count = Array.isArray(product.count) && product.count.length > 0 ? product.count : product.premium;
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
      await fetchProductData(selectedYear || '2026');
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
        const platformYear = selectedYear || '2026';
        await fetchTargetData(platformYear);
        if (selectedTeamYear && selectedTeamYear !== platformYear) {
          await loadYearFromApi(selectedTeamYear, { updateKpi: false, updateProduct: false });
        }
        await loadYearFromApi(platformYear, { updateKpi: true, updateProduct: true });
        await refreshPlatformChart();
        productChart.setOption(getPieOption(currentPieType), true);
        teamChart.setOption(getTeamOption(), true);
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

  window.ProductFilters = productFilters;
  window.ProductFallbackData = productFallbackData;
  window.TeamMock = teamMock;
  window.convertApiToPlatformMock = convertApiToPlatformMock;
  window.convertApiToTeamMock = convertApiToTeamMock;
  window.updateCutoffLabel = updateCutoffLabel;
  window.fetchAPIData = fetchAPIData;
  window.apiData = apiData;
  window.apiCache = apiCache;
})(window);

