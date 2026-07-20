// platform-trend-main.js — platform trend chart state and rendering
    // ---------- Chart 1: Platform Trend ----------
    const platformChart = echarts.init(document.getElementById('platformChart'));
    let currentTimeDim = 'year';
    let currentPremiumType = 'qj';
    let selectedYear = DEFAULT_DASHBOARD_YEAR;
    let selectedQuarter = 'Q2';
    let selectedMonth = String(new Date().getMonth() + 1);
    const selectedSeries = { '经代': true, 'OTO': true, '证保': true, '蚁桥': true };
    const seriesColors = { '经代': '#8b5cf6', 'OTO': '#3b82f6', '证保': '#10b981', '蚁桥': '#f59e0b' };
    const ORG_LIST_PLATFORM = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
    const selectedPlatformOrgs = {};
    ORG_LIST_PLATFORM.forEach(o => selectedPlatformOrgs[o] = true);
    // 机构级保费索引：platformOrgPerfData[year][premiumType][channel][monthIndex] = { total, orgs: { [org]: value } }
    const platformOrgPerfData = {};
    const platformTrendDailyCache = {};
    window.clearPlatformTrendDailyCache = function() {
      Object.keys(platformTrendDailyCache).forEach(key => delete platformTrendDailyCache[key]);
    };

    function normalizeMonth(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return null;
      if (n >= 1 && n <= 12) return n;
      const text = String(value || '').trim();
      if (/^\d{6,8}$/.test(text)) {
        const m = Number(text.slice(4, 6));
        return m >= 1 && m <= 12 ? m : null;
      }
      return null;
    }

    function dailyRowsContainJingdai(rows, month) {
      return (rows || []).some(r => normalizeMonth(r.month) === Number(month) && r.channel === '经代');
    }

    function selectedPlatformOrgNames() {
      return ORG_LIST_PLATFORM.filter(o => selectedPlatformOrgs[o]);
    }

    function updatePlatformScopeNote() {
      const el = document.getElementById('platformScopeNote');
      if (!el) return;
      const orgFiltered = hasPlatformOrgFilter();
      const includesJingdai = Boolean(selectedSeries['经代']);
      const selected = selectedPlatformOrgNames();
      const rangeText = orgFiltered ? `当前机构范围：${selected.join('、') || '未选择机构'}。` : '当前机构范围：全部机构。';
      const jdText = orgFiltered && includesJingdai ? '经代暂无机构维度，当前经代数据按整体口径展示。' : '';
      const globalRange = typeof window.getDashboardRange === 'function' ? window.getDashboardRange() : null;
      const trendText = globalRange?.rangeType && globalRange.rangeType !== 'ytd'
        ? `顶部统计范围当前为“${globalRange.label || globalRange.rangeType}”；本趋势图仍按本模块的年/季/月维度展示完整趋势。`
        : '';
      el.textContent = [rangeText, jdText, trendText].filter(Boolean).join(' ');
    }

    // Local fallback platformMock lives in js/platform-seed-data.js.

    function hasPlatformOrgFilter() {
      const allSelected = ORG_LIST_PLATFORM.every(o => selectedPlatformOrgs[o]);
      const noneSelected = ORG_LIST_PLATFORM.every(o => !selectedPlatformOrgs[o]);
      return !allSelected && !noneSelected;
    }

    function findJingdaiChannelKey(channelMap) {
      if (!channelMap) return null;
      if (Object.prototype.hasOwnProperty.call(channelMap, '经代')) return '经代';
      return Object.keys(channelMap).find(k => k.includes('经') && k.includes('代')) || null;
    }

    function getJingdaiMonthFallback(year, premiumType, month) {
      const monthData = platformMock[year]?.month?.[String(month)]?.[premiumType];
      const key = findJingdaiChannelKey(monthData);
      if (!key || !Array.isArray(monthData[key]) || monthData[key].length === 0) return [];
      return completeDailySeries(monthData[key], year, month);
    }

    function getMonthDailyCumulative(year, premiumType, selectedKeys, month) {
      const col = premiumType === 'qj' ? 'qj_premium' : premiumType === 'gm' ? 'gm_premium' : 'zs_premium';
      const useOrgDaily = hasPlatformOrgFilter();
      const daily = [];
      let hasDailyRows = false;
      const cacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(year) : String(year);
      if (useOrgDaily) {
        const selected = selectedPlatformOrgNames();
        const orgDaily = apiCache[cacheKey]?.platform?.org_daily_performance || [];
        const rawDaily = apiCache[cacheKey]?.platform?.daily_performance || [];
        const rawDailyHasJd = dailyRowsContainJingdai(rawDaily, month);
        const jdDaily = apiCache[cacheKey]?.platform?.jingdai_daily || [];
        orgDaily.forEach(r => {
          if (normalizeMonth(r.month) === Number(month) && selectedKeys.includes(r.channel) && selected.includes(r.org)) {
            const idx = (r.day || 1) - 1;
            daily[idx] = (daily[idx] || 0) + (r[col] || 0);
            hasDailyRows = true;
          }
        });

        if (selectedKeys.includes('经代') && rawDailyHasJd) {
          rawDaily.forEach(r => {
            if (normalizeMonth(r.month) === Number(month) && r.channel === '经代') {
              const idx = (r.day || 1) - 1;
              daily[idx] = (daily[idx] || 0) + (r[col] || 0);
              hasDailyRows = true;
            }
          });
        } else if (selectedKeys.includes('经代')) {
          jdDaily.forEach(r => {
            if (normalizeMonth(r.month) === Number(month)) {
              const idx = (r.day || 1) - 1;
              daily[idx] = (daily[idx] || 0) + (r[col] || 0);
              hasDailyRows = true;
            }
          });
        }

        if (hasDailyRows) {
          let running = 0;
          const cumulative = [];
          for (let i = 0; i < daily.length; i++) {
            running += daily[i] || 0;
            cumulative[i] = running;
          }
          const result = completeDailySeries(cumulative, year, month);
          return result;
        }
        // org筛选激活但无org_daily数据 → 返回空，不回退到全机构聚合
        return [];
      }

      const rawDaily = apiCache[cacheKey]?.platform?.daily_performance || [];
      const rawDailyHasJd = dailyRowsContainJingdai(rawDaily, month);
      rawDaily.forEach(r => {
        if (normalizeMonth(r.month) === Number(month) && selectedKeys.includes(r.channel)) {
          const idx = (r.day || 1) - 1;
          daily[idx] = (daily[idx] || 0) + (r[col] || 0);
          hasDailyRows = true;
        }
      });

      if (selectedKeys.includes('经代') && !rawDailyHasJd) {
        const jdDaily = apiCache[cacheKey]?.platform?.jingdai_daily || [];
        jdDaily.forEach(r => {
          if (normalizeMonth(r.month) === Number(month)) {
            const idx = (r.day || 1) - 1;
            daily[idx] = (daily[idx] || 0) + (r[col] || 0);
            hasDailyRows = true;
          }
        });
      }

      if (hasDailyRows) {
        let running = 0;
        const cumulative = [];
        for (let i = 0; i < daily.length; i++) {
          running += daily[i] || 0;
          cumulative[i] = running;
        }
        const result = completeDailySeries(cumulative, year, month);
        return result;
      }

      // Fallback: read from platformMock.month if apiCache has no daily data
      const pm = platformMock[year];
      const typeKey = premiumType === 'qj' ? 'qj' : premiumType === 'gm' ? 'gm' : 'zs';
      if (pm && pm.month && pm.month[month] && pm.month[month][typeKey]) {
        const monthData = pm.month[month][typeKey];
        let combined = null;
        for (const key of selectedKeys) {
          const arr = monthData[key];
          if (arr && arr.length > 0) {
            if (!combined) {
              combined = arr.slice();
            } else {
              for (let i = 0; i < arr.length; i++) {
                combined[i] = (combined[i] || 0) + (arr[i] || 0);
              }
            }
          }
        }
        if (combined) {
          const result = completeDailySeries(combined, year, month);
          return result;
        }
      }

      if (selectedKeys.some(k => k === '经代' || (k.includes('经') && k.includes('代')))) {
        const result = getJingdaiMonthFallback(year, typeKey, month);
        if (result.length > 0) {
          return result;
        }
      }

      return [];
    }

    function getPeriodDailyCumulative(year, premiumType, selectedKeys, monthList) {
      const labels = [];
      const values = [];
      const monthSeriesMap = {};
      let hasAnySeries = false;
      monthList.forEach(month => {
        const series = getMonthDailyCumulative(year, premiumType, selectedKeys, month);
        monthSeriesMap[month] = series;
        if (series.length > 0) hasAnySeries = true;
      });
      if (!hasAnySeries) return { labels: [], values: [] };
      let offset = 0;
      monthList.forEach(month => {
        const monthSeries = monthSeriesMap[month] || [];
        const dim = dailyDisplayEndDay(year, month);
        if (dim <= 0) return;
        for (let idx = 0; idx < dim; idx++) {
          const v = monthSeries[idx] !== undefined ? monthSeries[idx] : (idx > 0 ? monthSeries[idx - 1] || 0 : 0);
          labels.push(`${month}月${idx + 1}日`);
          values.push(Math.round((offset + v) * 10) / 10);
        }
        if (monthSeries.length > 0) offset += monthSeries[monthSeries.length - 1] || 0;
      });
      return { labels, values };
    }

    function platformTrendCacheKey(year, premiumType, selectedKeys, periodType, periodValue) {
      const orgKey = ORG_LIST_PLATFORM.filter(o => selectedPlatformOrgs[o]).join('|');
      return [year, premiumType, selectedKeys.slice().sort().join('|'), periodType, periodValue || 0, orgKey].join('::');
    }

    function getTrendDataFromCache(year, periodType, periodValue, monthList) {
      const selectedKeys = Object.keys(selectedSeries).filter(k => selectedSeries[k]);
      if (hasPlatformOrgFilter()) {
        return getPeriodDailyCumulative(year, currentPremiumType, selectedKeys, monthList)
          || { labels: [], values: [] };
      }
      const cacheKey = platformTrendCacheKey(year, currentPremiumType, selectedKeys, periodType, periodValue);
      return platformTrendDailyCache[cacheKey]
        || getPeriodDailyCumulative(year, currentPremiumType, selectedKeys, monthList)
        || { labels: [], values: [] };
    }

    async function fetchPlatformTrendDaily(year, periodType, periodValue) {
      if (!['month', 'quarter'].includes(periodType) || !periodValue) return;
      const selectedKeys = Object.keys(selectedSeries).filter(k => selectedSeries[k]);
      if (hasPlatformOrgFilter()) return;
      const key = platformTrendCacheKey(year, currentPremiumType, selectedKeys, periodType, periodValue);
      const params = new URLSearchParams();
      params.set('year', String(year));
      params.set('periodType', periodType);
      params.set('periodValue', String(periodValue));
      params.set('metric', currentPremiumType);
      if (selectedKeys.length > 0) params.set('businessLines', selectedKeys.join(','));
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      const timer = controller ? setTimeout(() => controller.abort(), 2500) : null;
      try {
        const payload = await fetchJson(`/api/platform-trend?${params.toString()}`, controller ? { signal: controller.signal } : undefined);
        const data = unwrapApiResponse(payload);
        if (data && data.daily && data.daily.hasRealDailyData) {
          platformTrendDailyCache[key] = {
            labels: data.daily.labels || [],
            values: data.daily.values || []
          };
        }
      } catch (e) {
        console.error('fetchPlatformTrendDaily error:', e);
      } finally {
        if (timer) clearTimeout(timer);
      }
    }

    async function refreshPlatformChart() {
      const year = parseInt(selectedYear);
      platformChart.clear();
      platformChart.setOption(getPlatformOption(), true);
      if (currentTimeDim === 'month') {
        const month = parseInt(selectedMonth);
        await fetchPlatformTrendDaily(year, 'month', month);
        await fetchPlatformTrendDaily(year - 1, 'month', month);
        if (month > 1) {
          await fetchPlatformTrendDaily(year, 'month', month - 1);
        }
      } else if (currentTimeDim === 'quarter') {
        const quarter = Number(String(selectedQuarter).replace('Q', ''));
        await fetchPlatformTrendDaily(year, 'quarter', quarter);
        await fetchPlatformTrendDaily(year - 1, 'quarter', quarter);
        if (quarter > 1) {
          await fetchPlatformTrendDaily(year, 'quarter', quarter - 1);
        }
      }
      platformChart.setOption(getPlatformOption(), true);
    }

    function buildDailyTrendOption(monthList, currentName, prevName, emptyMessage) {
      const selectedKeys = Object.keys(selectedSeries).filter(k => selectedSeries[k]);
      const year = parseInt(selectedYear);
      const prevYear = year - 1;
      const periodType = monthList.length === 1 ? 'month' : 'quarter';
      const periodValue = periodType === 'month' ? monthList[0] : Math.floor((monthList[0] - 1) / 3) + 1;
      const currentKey = platformTrendCacheKey(year, currentPremiumType, selectedKeys, periodType, periodValue);
      const prevKey = platformTrendCacheKey(prevYear, currentPremiumType, selectedKeys, periodType, periodValue);
      const current = platformTrendDailyCache[currentKey] || getPeriodDailyCumulative(year, currentPremiumType, selectedKeys, monthList);
      const prev = platformTrendDailyCache[prevKey] || (platformMock[prevYear] ? getPeriodDailyCumulative(prevYear, currentPremiumType, selectedKeys, monthList) : { labels: [], values: [] });
      if (current.values.length === 0 && prev.values.length === 0) return {
        title: { text: emptyMessage, left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: []
      };

      // 优先使用当前年数据，若当前年无数据但有上年数据则以上年为主
      const hasCurrent = current.values.length > 0;
      const primaryData = hasCurrent ? current : prev;
      const primaryName = hasCurrent ? currentName : prevName;
      const labels = primaryData.labels.slice();
      const seriesList = [
        { name: primaryName, type: 'line', data: primaryData.values, smooth: true, symbol: 'circle', symbolSize: 4, lineStyle: { width: 3 }, itemStyle: { color: '#3b82f6' } }
      ];

      if (hasCurrent && prev.values.length > 0) {
        while (labels.length < prev.labels.length) labels.push(prev.labels[labels.length]);
        const prevValues = labels.map((_, idx) => prev.values[idx] !== undefined ? prev.values[idx] : '-');
        seriesList.push({ name: prevName, type: 'line', data: prevValues, smooth: true, symbol: 'none', lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#94a3b8' } });
      }

      return {
        tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
        legend: { data: seriesList.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
        grid: { left: 50, right: 20, top: 20, bottom: 48 },
        xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8', interval: 'auto' } },
        yAxis: { type: 'value', name: '累计(万)', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
        series: seriesList
      };
    }

    function getPlatformOption() {
      const selectedKeys = Object.keys(selectedSeries).filter(k => selectedSeries[k]);
      const year = parseInt(selectedYear);
      const prevYear = year - 1;
      const emptyOption = (message) => ({
        title: { text: message, left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
        xAxis: { type: 'category', data: [] },
        yAxis: { type: 'value' },
        series: []
      });
      if (!platformMock[year]) return emptyOption('暂无该年份数据');

      if (currentTimeDim === 'year') {
        let currentCum = 0;
        const currentTotal = months.map((_, i) => {
          let sum = 0, hasValue = false;
          for (const key of selectedKeys) {
            const v = getChannelValue(year, currentPremiumType, key, i);
            if (v !== null && v !== undefined) {
              sum += v;
              hasValue = true;
            }
          }
          if (!hasValue) return '-';
          currentCum += sum;
          return Math.round(currentCum * 10) / 10;
        });
        // 单月保费（用于柱状图）
        const currentMonthly = months.map((_, i) => {
          let sum = 0;
          for (const key of selectedKeys) {
            const v = getChannelValue(year, currentPremiumType, key, i);
            if (v !== null && v !== undefined) sum += v;
          }
          return Math.round(sum * 10) / 10;
        });

        const seriesList = [
          { name: year + '年累计', type: 'line', data: currentTotal, smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, itemStyle: { color: '#3b82f6' }, yAxisIndex: 0 }
        ];

        if (platformMock[prevYear]) {
          let prevCum = 0;
          const prevTotal = months.map((_, i) => {
            let sum = 0;
            for (const key of selectedKeys) {
              const v = getChannelValue(prevYear, currentPremiumType, key, i);
              if (v !== null && v !== undefined) sum += v;
            }
            prevCum += sum;
            return Math.round(prevCum * 10) / 10;
          });
          const prevMonthly = months.map((_, i) => {
            let sum = 0;
            for (const key of selectedKeys) {
              const v = getChannelValue(prevYear, currentPremiumType, key, i);
              if (v !== null && v !== undefined) sum += v;
            }
            return Math.round(sum * 10) / 10;
          });
          seriesList.push(
            { name: prevYear + '年累计', type: 'line', data: prevTotal, smooth: true, symbol: 'none', lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#94a3b8' }, yAxisIndex: 0 },
            { name: year + '年单月', type: 'bar', data: currentMonthly, yAxisIndex: 1, itemStyle: { color: 'rgba(59,130,246,0.35)' }, barMaxWidth: 16 },
            { name: prevYear + '年单月', type: 'bar', data: prevMonthly, yAxisIndex: 1, itemStyle: { color: 'rgba(148,163,184,0.3)' }, barMaxWidth: 16 }
          );
        } else {
          seriesList.push(
            { name: year + '年单月', type: 'bar', data: currentMonthly, yAxisIndex: 1, itemStyle: { color: 'rgba(59,130,246,0.35)' }, barMaxWidth: 16 }
          );
        }

        return {
          tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
          legend: { data: seriesList.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
          grid: { left: 50, right: 20, top: 20, bottom: 50 },
          xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
          yAxis: [
            { type: 'value', name: '累计(万)', position: 'left', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
            { type: 'value', name: '单月(万)', position: 'right', axisLine: { show: false }, splitLine: { show: false }, axisLabel: { color: '#94a3b8' } }
          ],
          series: seriesList
        };
      }

      if (currentTimeDim === 'quarter') {
        const quarter = selectedQuarter;
        const qNum = parseInt(quarter.replace('Q', ''));
        const qStartMonth = { 'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10 };
        const startM = qStartMonth[quarter];
        const monthList = [startM, startM + 1, startM + 2];

        const current = getTrendDataFromCache(year, 'quarter', qNum, monthList);
        const prevYearSame = getTrendDataFromCache(prevYear, 'quarter', qNum, monthList);
        let prevQ = null;
        if (qNum > 1) {
          const prevStartM = startM - 3;
          prevQ = getTrendDataFromCache(year, 'quarter', qNum - 1, [prevStartM, prevStartM + 1, prevStartM + 2]);
        }

        const hasCurrent = current.values.length > 0;
        const hasPrevYear = prevYearSame.values.length > 0;
        const hasPrevQ = prevQ && prevQ.values.length > 0;

        if (!hasCurrent && !hasPrevYear && !hasPrevQ) {
          return emptyOption('暂无该季度日累计数据');
        }

        const maxLen = Math.max(
          current.values.length,
          prevYearSame.values.length,
          hasPrevQ ? prevQ.values.length : 0
        );
        const labels = Array.from({length: maxLen}, (_, i) => '第' + (i + 1) + '日');
        const seriesList = [];

        if (hasCurrent) {
          seriesList.push({
            name: year + '年' + quarter,
            type: 'line',
            data: current.values,
            smooth: true,
            symbol: 'circle',
            symbolSize: 4,
            lineStyle: { width: 3 },
            itemStyle: { color: '#3b82f6' }
          });
        }
        if (hasPrevQ) {
          seriesList.push({
            name: year + '年Q' + (qNum - 1),
            type: 'line',
            data: prevQ.values,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2, type: 'dashed' },
            itemStyle: { color: '#f59e0b' }
          });
        }
        if (hasPrevYear) {
          seriesList.push({
            name: prevYear + '年' + quarter,
            type: 'line',
            data: prevYearSame.values,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2, type: 'dashed' },
            itemStyle: { color: '#94a3b8' }
          });
        }

        return {
          tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
          legend: { data: seriesList.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
          grid: { left: 50, right: 20, top: 20, bottom: 48 },
          xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8', interval: 'auto' } },
          yAxis: { type: 'value', name: '累计(万)', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
          series: seriesList
        };
      }

      const month = parseInt(selectedMonth);
      const currentM = getTrendDataFromCache(year, 'month', month, [month]);
      const prevYearSameM = getTrendDataFromCache(prevYear, 'month', month, [month]);
      let prevM = null;
      if (month > 1) {
        prevM = getTrendDataFromCache(year, 'month', month - 1, [month - 1]);
      }

      const hasCurrentM = currentM.values.length > 0;
      const hasPrevYearM = prevYearSameM.values.length > 0;
      const hasPrevM = prevM && prevM.values.length > 0;

      if (!hasCurrentM && !hasPrevYearM && !hasPrevM) {
        return emptyOption('暂无该月份日累计数据');
      }

      const maxLenM = Math.max(
        currentM.values.length,
        prevYearSameM.values.length,
        hasPrevM ? prevM.values.length : 0
      );
      const labelsM = Array.from({length: maxLenM}, (_, i) => '第' + (i + 1) + '日');
      const seriesListM = [];

      if (hasCurrentM) {
        seriesListM.push({
          name: year + '年' + month + '月',
          type: 'line',
          data: currentM.values,
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { width: 3 },
          itemStyle: { color: '#3b82f6' }
        });
      }
      if (hasPrevM) {
        seriesListM.push({
          name: year + '年' + (month - 1) + '月',
          type: 'line',
          data: prevM.values,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, type: 'dashed' },
          itemStyle: { color: '#f59e0b' }
        });
      }
      if (hasPrevYearM) {
        seriesListM.push({
          name: prevYear + '年' + month + '月',
          type: 'line',
          data: prevYearSameM.values,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 2, type: 'dashed' },
          itemStyle: { color: '#94a3b8' }
        });
      }

      return {
        tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
        legend: { data: seriesListM.map(s => s.name), textStyle: { color: '#94a3b8' }, bottom: 0 },
        grid: { left: 50, right: 20, top: 20, bottom: 48 },
        xAxis: { type: 'category', data: labelsM, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8', interval: 'auto' } },
        yAxis: { type: 'value', name: '累计(万)', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
        series: seriesListM
      };
    }

    if (!window.ALLOW_LOCAL_FALLBACK) {
      Object.keys(platformMock).forEach(year => delete platformMock[year]);
    }

    updatePlatformScopeNote();
    platformChart.setOption(getPlatformOption());

    async function loadYearFromApi(year, options = {}) {
      const updateKpi = options.updateKpi !== false;
      const updateProduct = options.updateProduct !== false;
      const yearNum = parseInt(year);
      const yearLabel = String(yearNum);
      let cacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(yearNum) : yearLabel;
      if (!apiCache[cacheKey]) {
        const ok = await fetchAPIData(yearNum);
        if (!ok) {
          clearRuntimeFallbackYear(year);
          return false;
        }
        // KPI 会把默认、月度或超出最新数据日的范围规范化；重新按规范化后的范围取缓存。
        cacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(yearNum) : yearLabel;
      }
      const cached = apiCache[cacheKey];
      if (cached && cached.platform && hasValidApiData(cached.platform)) {
        const apiPM = convertApiToPlatformMock(cached.platform, yearLabel);
        const apiTM = convertApiToTeamMock(cached.platform, yearLabel);
        Object.assign(platformMock, apiPM);
        Object.assign(teamMock, apiTM);
        if (updateKpi) {
          apiData.platform = cached.platform;
          apiData.kpi = cached.kpi;
        }
        if (updateProduct) {
          await fetchProductData(yearLabel);
        }
        // 同时加载上一年数据到 platformMock，用于季度/月度同比趋势线
        const prevYearNum = yearNum - 1;
        const prevYearLabel = String(prevYearNum);
        const prevCacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(prevYearNum) : prevYearLabel;
        if (!apiCache[prevCacheKey]) {
          try {
            const prevParams = new URLSearchParams({ year: String(prevYearNum) });
            const prevPlatform = unwrapApiResponse(await fetchJson(`/api/platform-data?${prevParams.toString()}`, { method: 'GET' }));
            apiCache[prevCacheKey] = { platform: prevPlatform };
          } catch(e) {}
        }
        if (apiCache[prevCacheKey] && apiCache[prevCacheKey].platform && hasValidApiData(apiCache[prevCacheKey].platform)) {
          const prevPM = convertApiToPlatformMock(apiCache[prevCacheKey].platform, prevYearLabel);
          Object.assign(platformMock, prevPM);
          const prevTM = convertApiToTeamMock(apiCache[prevCacheKey].platform, prevYearLabel);
          Object.assign(teamMock, prevTM);
        }
        return true;
      }
      clearRuntimeFallbackYear(year);
      return false;
    }

    async function switchYear(value) {
      selectedYear = value;
      await loadYearFromApi(value, { updateKpi: true, updateProduct: true });
      updateCutoffLabel(value);
      updatePlatformScopeNote();
      await refreshPlatformChart();
      productChart.setOption(getPieOption(currentPieType), true);
      fetchPayPeriodData(value);
      fetchOrgKpiData(value);
    }

    async function switchTimeDim(btn, dim) {
      if (btn?.parentElement) {
        btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      currentTimeDim = dim;

      const subSelect = document.getElementById('subPeriodSelect');
      subSelect.innerHTML = '';
      if (dim === 'year') {
        subSelect.innerHTML = '<option value="all">全年</option>';
        subSelect.style.display = 'none';
      } else if (dim === 'quarter') {
        subSelect.innerHTML = '<option value="Q1">Q1</option><option value="Q2" selected>Q2</option><option value="Q3">Q3</option><option value="Q4">Q4</option>';
        subSelect.style.display = 'inline-block';
      } else if (dim === 'month') {
        const defaultMonth = selectedMonth || String(new Date().getMonth() + 1);
        selectedMonth = defaultMonth;
        subSelect.innerHTML = Array.from({ length: 12 }, (_, i) => {
          const value = String(i + 1);
          return `<option value="${value}"${value === defaultMonth ? ' selected' : ''}>${value}月</option>`;
        }).join('');
        subSelect.style.display = 'inline-block';
      }

      await refreshPlatformChart();
    }

    async function switchSubPeriod(value) {
      if (currentTimeDim === 'quarter') selectedQuarter = value;
      else if (currentTimeDim === 'month') selectedMonth = value;
      await refreshPlatformChart();
    }

    async function switchPremiumType(btn, type) {
      const row = btn?.closest('.control-row');
      if (row) {
        row.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }
      currentPremiumType = type;
      await refreshPlatformChart();
    }

    async function toggleSeries(key, checked) {
      selectedSeries[key] = checked;
      updatePlatformScopeNote();
      await refreshPlatformChart();
    }

    async function toggleOrg(org, checked) {
      selectedPlatformOrgs[org] = checked;
      updatePlatformScopeNote();
      await refreshPlatformChart();
    }

    function bindPlatformTrendControls() {
      const yearSelect = document.getElementById('yearSelect');
      if (yearSelect && yearSelect.dataset.boundPlatformYear !== 'true') {
        yearSelect.dataset.boundPlatformYear = 'true';
        yearSelect.addEventListener('change', () => switchYear(yearSelect.value));
      }

      const timeBtns = document.getElementById('platformTimeDimBtns');
      if (timeBtns && timeBtns.dataset.boundPlatformTimeDim !== 'true') {
        timeBtns.dataset.boundPlatformTimeDim = 'true';
        timeBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-platform-time-dim]');
          if (!button || !timeBtns.contains(button)) return;
          event.preventDefault();
          switchTimeDim(button, button.dataset.platformTimeDim);
        });
      }

      const subPeriodSelect = document.getElementById('subPeriodSelect');
      if (subPeriodSelect && subPeriodSelect.dataset.boundPlatformPeriod !== 'true') {
        subPeriodSelect.dataset.boundPlatformPeriod = 'true';
        subPeriodSelect.addEventListener('change', () => switchSubPeriod(subPeriodSelect.value));
      }

      const seriesChecks = document.getElementById('seriesChecks');
      if (seriesChecks && seriesChecks.dataset.boundPlatformSeries !== 'true') {
        seriesChecks.dataset.boundPlatformSeries = 'true';
        seriesChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-platform-series]');
          if (!input || !seriesChecks.contains(input)) return;
          toggleSeries(input.dataset.platformSeries, input.checked);
        });
      }

      const orgChecks = document.getElementById('orgChecks');
      if (orgChecks && orgChecks.dataset.boundPlatformOrgs !== 'true') {
        orgChecks.dataset.boundPlatformOrgs = 'true';
        orgChecks.addEventListener('change', event => {
          const input = event.target.closest('input[data-platform-org]');
          if (!input || !orgChecks.contains(input)) return;
          toggleOrg(input.dataset.platformOrg, input.checked);
        });
      }

      const premiumBtns = document.getElementById('platformPremiumTypeBtns');
      if (premiumBtns && premiumBtns.dataset.boundPlatformPremium !== 'true') {
        premiumBtns.dataset.boundPlatformPremium = 'true';
        premiumBtns.addEventListener('click', event => {
          const button = event.target.closest('button[data-platform-premium-type]');
          if (!button || !premiumBtns.contains(button)) return;
          event.preventDefault();
          switchPremiumType(button, button.dataset.platformPremiumType);
        });
      }
    }

    bindPlatformTrendControls();

    // 根据机构筛选获取某渠道某月的数值（null 表示无数据；经代无机构维度，始终返回整体数据）
    function getChannelValue(year, premiumType, channel, monthIndex) {
      // 经代没有机构维度，始终返回全国聚合数据
      if (channel === '经代') {
        const v = platformMock[year]?.year?.[premiumType]?.[channel]?.[monthIndex];
        return v !== null && v !== undefined ? v : null;
      }

      // 从机构级索引查询
      const orgData = platformOrgPerfData[year]?.[channel]?.[monthIndex];
      if (!orgData) {
        // 无机构级数据时回退到 platformMock 聚合数据
        const v = platformMock[year]?.year?.[premiumType]?.[channel]?.[monthIndex];
        return v !== null && v !== undefined ? v : null;
      }

      const allSelected = ORG_LIST_PLATFORM.every(o => selectedPlatformOrgs[o]);
      const noneSelected = ORG_LIST_PLATFORM.every(o => !selectedPlatformOrgs[o]);

      if (allSelected || noneSelected) {
        return orgData.total[premiumType] || null;
      }

      let sum = 0;
      let hasAny = false;
      for (const org of ORG_LIST_PLATFORM) {
        if (selectedPlatformOrgs[org] && orgData.orgs[org] && orgData.orgs[org][premiumType] !== undefined) {
          sum += orgData.orgs[org][premiumType];
          hasAny = true;
        }
      }
      return hasAny ? sum : null;
    }

