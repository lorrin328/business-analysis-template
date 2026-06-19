// kpi-modal-content.js - KPI detail modal content builders
function getModalContent(type) {
      switch(type) {
        case 'overall': {
          loadTargetData();
          const year = String((apiData.kpi && apiData.kpi.year) || selectedYear || DEFAULT_DASHBOARD_YEAR);
          const pm = platformMock[year];
          const qjData = pm ? pm.year.qj : null;
          const prevYear = String(Number(year) - 1);
          const prevPm = platformMock[prevYear];
          const prevQjData = prevPm ? prevPm.year.qj : null;
          const qjPrevApi = apiData.kpi && apiData.kpi.qj_premium_prev ? apiData.kpi.qj_premium_prev : {};
          const targets = targetData.categories.qjPremium.metrics;
          function fmt(n) { return n ? n.toLocaleString('zh-CN', {maximumFractionDigits:0}) : '0'; }
          function calc(a, t) { return t > 0 ? Math.round(a / t * 1000) / 10 : 0; }
          function yoy(a, p) { return p > 0 ? Math.round((a / p - 1) * 1000) / 10 : null; }
          function yoyFmt(v) { return v == null ? '-' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`; }
          function yoyCls(v) { return v == null ? 'text-secondary' : v >= 10 ? 'danger' : v >= 0 ? 'warning' : 'success'; }
          function rc(r) { return r >= 100 ? 'up' : r >= 80 ? 'warning' : 'down'; }
          function sumCh(ch) { if (!qjData || !qjData[ch]) return 0; let s=0; for(const v of qjData[ch]){ if(v==null)break; s+=v;} return s; }
          function sumChPrev(ch) { if (!prevQjData || !prevQjData[ch]) return 0; let s=0; for(const v of prevQjData[ch]){ if(v==null)break; s+=v;} return s; }
          const otoA = sumCh('OTO'), zbA = sumCh('证保'), yqA = sumCh('蚁桥'), jdA = sumCh('经代');
          const zxA = otoA + zbA + yqA, ztA = jdA + zxA;
          const prevOtoA = qjPrevApi.oto ?? sumChPrev('OTO');
          const prevZbA = qjPrevApi.zhengbao ?? sumChPrev('证保');
          const prevYqA = qjPrevApi.yiqiao ?? sumChPrev('蚁桥');
          const prevJdA = qjPrevApi.jingdai ?? sumChPrev('经代');
          const prevZxA = qjPrevApi.total_transform ?? (prevOtoA + prevZbA + prevYqA);
          const prevZtA = qjPrevApi.total ?? (prevJdA + prevZxA);
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
          function qSumPrev(ch, q) { const qm=[q*3,q*3+1,q*3+2]; if(!prevQjData||!prevQjData[ch])return 0; let s=0; for(const i of qm){const v=prevQjData[ch][i]; if(v!=null) s+=v;} return s; }
          function mVal(ch, m) { if(!qjData||!qjData[ch])return 0; const v=qjData[ch][m]; return v!=null?v:0; }
          function mValPrev(ch, m) { if(!prevQjData||!prevQjData[ch])return 0; const v=prevQjData[ch][m]; return v!=null?v:0; }
          const qotoA=qSum('OTO',qIdx), qzbA=qSum('证保',qIdx), qyqA=qSum('蚁桥',qIdx), qjdA=qSum('经代',qIdx);
          const qzxA=qotoA+qzbA+qyqA, qztA=qjdA+qzxA;
          const qPrevOtoA=qSumPrev('OTO',qIdx), qPrevZbA=qSumPrev('证保',qIdx), qPrevYqA=qSumPrev('蚁桥',qIdx), qPrevJdA=qSumPrev('经代',qIdx);
          const qPrevZxA=qPrevOtoA+qPrevZbA+qPrevYqA, qPrevZtA=qPrevJdA+qPrevZxA;
          const motoA=mVal('OTO',mIdx), mzbA=mVal('证保',mIdx), myqA=mVal('蚁桥',mIdx), mjdA=mVal('经代',mIdx);
          const mzxA=motoA+mzbA+myqA, mztA=mjdA+mzxA;
          const mPrevOtoA=mValPrev('OTO',mIdx), mPrevZbA=mValPrev('证保',mIdx), mPrevYqA=mValPrev('蚁桥',mIdx), mPrevJdA=mValPrev('经代',mIdx);
          const mPrevZxA=mPrevOtoA+mPrevZbA+mPrevYqA, mPrevZtA=mPrevJdA+mPrevZxA;
          function qjRow(label, target, actual, prev, opts = {}) {
            const rate = calc(actual, target);
            const yoyValue = yoy(actual, prev);
            const indent = opts.sub ? 'padding-left:20px;color:var(--text-secondary);' : '';
            const weight = opts.bold ? 'font-weight:600;' : '';
            return `<tr style="${weight}">
                <td style="text-align:left;${indent}">${label}</td>
                <td>${fmt(target)}</td>
                <td>${fmt(actual)}</td>
                <td style="color:var(--${rc(rate)});">${rate}%</td>
                <td style="color:var(--${yoyCls(yoyValue)});">${yoyFmt(yoyValue)}</td>
              </tr>`;
          }
          const monthLabels = [];
          const chartData = { OTO:[], 证保:[], 蚁桥:[], 经代:[] };
          ['OTO','证保','蚁桥','经代'].forEach(ch=>{ for(let i=0;i<maxMonth;i++){ if (i===0) monthLabels.push((i+1)+'月'); chartData[ch].push(qjData&&qjData[ch]?qjData[ch][i]||0:0); } });
          const qNum = qIdx + 1;
          return {
            title: '期交保费达成率',
            body: `
              <div class="modal-section-title">年度累计</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th><th>同比</th></tr></thead>
                <tbody>
                  ${qjRow('整体', ztT, ztA, prevZtA, { bold: true })}
                  ${qjRow('经代', jdT, jdA, prevJdA)}
                  ${qjRow('转型业务', zxT, zxA, prevZxA)}
                  ${qjRow('OTO', otoT, otoA, prevOtoA, { sub: true })}
                  ${qjRow('证保', zbT, zbA, prevZbA, { sub: true })}
                  ${qjRow('蚁桥', yqT, yqA, prevYqA, { sub: true })}
                </tbody>
              </table>

              <div class="modal-section-title">季度累计（Q${qNum}）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th><th>同比</th></tr></thead>
                <tbody>
                  ${qjRow('整体', qztT, qztA, qPrevZtA, { bold: true })}
                  ${qjRow('经代', qjdT, qjdA, qPrevJdA)}
                  ${qjRow('转型业务', qzxT, qzxA, qPrevZxA)}
                  ${qjRow('OTO', qotoT, qotoA, qPrevOtoA, { sub: true })}
                  ${qjRow('证保', qzbT, qzbA, qPrevZbA, { sub: true })}
                  ${qjRow('蚁桥', qyqT, qyqA, qPrevYqA, { sub: true })}
                </tbody>
              </table>

              <div class="modal-section-title">月度累计（${maxMonth}月）</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">口径</th><th>目标（万）</th><th>达成（万）</th><th>达成率</th><th>同比</th></tr></thead>
                <tbody>
                  ${qjRow('整体', mztT, mztA, mPrevZtA, { bold: true })}
                  ${qjRow('经代', mjdT, mjdA, mPrevJdA)}
                  ${qjRow('转型业务', mzxT, mzxA, mPrevZxA)}
                  ${qjRow('OTO', motoT, motoA, mPrevOtoA, { sub: true })}
                  ${qjRow('证保', mzbT, mzbA, mPrevZbA, { sub: true })}
                  ${qjRow('蚁桥', myqT, myqA, mPrevYqA, { sub: true })}
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
              <p style="color: var(--text-secondary); font-size: 13px; margin-top: 8px;">注：价值达成率口径包含经代；当前经代价值数据表尚未接入，经代实绩暂按 0 展示，待补充数据后自动纳入。</p>
            `,
            initChart: () => {
              const chart = echarts.init(document.getElementById('modalChart'));
              chart.setOption({
                tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#f1f5f9' } },
                legend: { data: ['OTO', '证保', '蚁桥', '经代'], textStyle: { color: '#94a3b8' }, bottom: 0 },
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
                xAxis: { type: 'category', data: valueLabels, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94a3b8' } },
                yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#334155', type: 'dashed' } }, axisLabel: { color: '#94a3b8' } },
                series: [
                  { name: 'OTO', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly.OTO[i]||0), itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: 0.1 } },
                  { name: '证保', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly['证保'][i]||0), itemStyle: { color: '#10b981' }, areaStyle: { opacity: 0.1 } },
                  { name: '蚁桥', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly['蚁桥'][i]||0), itemStyle: { color: '#f59e0b' }, areaStyle: { opacity: 0.1 } },
                  { name: '经代', type: 'line', smooth: true, data: valueLabels.map((_,i)=>valueMonthly['经代'][i]||0), itemStyle: { color: '#8b5cf6' }, areaStyle: { opacity: 0.1 } }
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
          const currentCacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(year) : String(year);
          const platform = apiCache[currentCacheKey]?.platform || {};
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
          function calcPC(p, a, monthCount = 1) {
            return a > 0 && monthCount > 0 ? Math.round((p / monthCount) / a * 100) / 100 : 0;
          }
          function calcRange(s, e) {
            const periodMonths = e - s + 1;
            const res = { ch: {}, totalPrem: 0, totalAvg: 0, months: periodMonths };
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
              res.ch[ch] = { prem: p, avg: a, pc: calcPC(p, a, periodMonths) };
              res.totalPrem += p; res.totalAvg += a;
            });
            res.totalAvg = Math.round(res.totalAvg * 10) / 10;
            res.totalPc = calcPC(res.totalPrem, res.totalAvg, periodMonths);
            return res;
          }
          const ytd = calcRange(1, maxMonth);
          const qIdx = Math.ceil(maxMonth / 3);
          const q = calcRange((qIdx - 1) * 3 + 1, Math.min(qIdx * 3, maxMonth));
          const curr = calcRange(maxMonth, maxMonth);
          const prevCacheKey = typeof dashboardCacheKey === 'function' ? dashboardCacheKey(year - 1) : String(year - 1);
          const prevPlat = apiCache[prevCacheKey]?.platform || {};
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
              res.ch[ch] = calcPC(p, a, endM); tp += p; ta += a;
            });
            res.totalPc = calcPC(tp, ta, endM); return res;
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
            chs.forEach(ch => { chartSeries[ch].push(calcPC(premMap[m]?.[ch] || 0, avgMap[m]?.[ch] || 0, 1)); });
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
              <p style="color: var(--text-secondary); font-size: 13px; margin-top: 12px;">注：人均保费 = 月均新单保费 ÷ 月均在职人力，仅计算转型业务。同比为与上年同期人均保费的绝对差值（万元）。</p>
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
          loadTargetData();
          const kpiData = apiData.kpi || {};
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

          function fmtWan(n) {
            return Math.round(n || 0).toLocaleString('zh-CN');
          }
          function calcRate(actual, target) {
            return target > 0 ? Math.round(actual / target * 1000) / 10 : null;
          }
          function rateText(rate) {
            return rate === null ? '--' : `${rate}%`;
          }
          function rateColor(rate) {
            if (rate === null) return 'var(--text-secondary)';
            return rate >= 100 ? 'var(--success)' : rate >= 80 ? 'var(--warning)' : 'var(--danger)';
          }
          function targetForChannel(ch) {
            let total = 0;
            if (targetData?.orgTargets) {
              Object.entries(targetData.orgTargets).forEach(([key, value]) => {
                if (key.endsWith('|' + ch)) total += (value?.shangbao?.year || 0);
              });
            }
            return total || metrics[ch]?.year || 0;
          }
          function mainRow(label, actual, target) {
            const rate = calcRate(actual, target);
            return `<tr>
              <td style="text-align:left;">${label}</td>
              <td>${fmtWan(actual)}万</td>
              <td style="color:${rateColor(rate)}">${rateText(rate)}</td>
            </tr>`;
          }
          const chRows = chs.map(ch => {
            const actual = Math.round(chVals[ch] || 0);
            const target = targetForChannel(ch);
            const rate = calcRate(actual, target);
            return `<tr>
              <td style="text-align:left;padding-left:20px;color:var(--text-secondary);">${ch}</td>
              <td>${fmtWan(actual)}万</td>
              <td style="color:${rateColor(rate)}">${rateText(rate)}</td>
            </tr>`;
          }).join('');
          return {
            title: '商保年金达成率',
            body: `
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">业务系列</th><th>年度累计达成</th><th>达成率</th></tr></thead>
                <tbody>
                  ${mainRow('经代', jdActual, targetJd)}
                  ${mainRow('转型', tfActual, targetTf)}
                </tbody>
              </table>
              <div class="modal-section-title">转型业务分模式</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">业务模式</th><th>年度累计达成</th><th>达成率</th></tr></thead>
                <tbody>${chRows}</tbody>
              </table>
            `
          };
        }
        case 'protection': {
          loadTargetData();
          const kpiData = apiData.kpi || {};
          const chs = ['OTO','证保','蚁桥'];
          const metrics = targetData?.categories?.baozhang?.metrics || {};
          let chVals = {}; chs.forEach(c => chVals[c] = 0);
          if (orgKpiData?.perf) {
            Object.entries(orgKpiData.perf).forEach(([key, item]) => {
              const ch = chs.find(c => key.endsWith('|' + c));
              if (ch) chVals[ch] = (chVals[ch] || 0) + (item.year?.product_protection || 0);
            });
          }

          const tfActual = Math.round((kpiData.protection_tf ?? Object.values(chVals).reduce((s, v) => s + v, 0)) || 0);
          const jdActual = Math.round(kpiData.protection_jd || 0);
          const targetJd = Math.round(metrics['经代']?.year || 0);
          const targetTf = Math.round(metrics['转型业务']?.year || 0);

          function fmtWan(n) {
            return Math.round(n || 0).toLocaleString('zh-CN');
          }
          function calcRate(actual, target) {
            return target > 0 ? Math.round(actual / target * 1000) / 10 : null;
          }
          function rateText(rate) {
            return rate === null ? '--' : `${rate}%`;
          }
          function rateColor(rate) {
            if (rate === null) return 'var(--text-secondary)';
            return rate >= 100 ? 'var(--success)' : rate >= 80 ? 'var(--warning)' : 'var(--danger)';
          }
          function targetForChannel(ch) {
            let total = 0;
            if (targetData?.orgTargets) {
              Object.entries(targetData.orgTargets).forEach(([key, value]) => {
                if (key.endsWith('|' + ch)) total += (value?.baozhang?.year || 0);
              });
            }
            return total || metrics[ch]?.year || 0;
          }
          function mainRow(label, actual, target) {
            const rate = calcRate(actual, target);
            return `<tr>
              <td style="text-align:left;">${label}</td>
              <td>${fmtWan(actual)}万</td>
              <td style="color:${rateColor(rate)}">${rateText(rate)}</td>
            </tr>`;
          }
          const chRows = chs.map(ch => {
            const actual = Math.round(chVals[ch] || 0);
            const target = targetForChannel(ch);
            const rate = calcRate(actual, target);
            return `<tr>
              <td style="text-align:left;padding-left:20px;color:var(--text-secondary);">${ch}</td>
              <td>${fmtWan(actual)}万</td>
              <td style="color:${rateColor(rate)}">${rateText(rate)}</td>
            </tr>`;
          }).join('');

          return {
            title: '保障类产品达成率',
            body: `
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">业务系列</th><th>年度累计达成</th><th>达成率</th></tr></thead>
                <tbody>
                  ${mainRow('经代', jdActual, targetJd)}
                  ${mainRow('转型', tfActual, targetTf)}
                </tbody>
              </table>
              <div class="modal-section-title">转型业务分模式</div>
              <table class="modal-table">
                <thead><tr><th style="text-align:left;">业务模式</th><th>年度累计达成</th><th>达成率</th></tr></thead>
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
            ? Math.round(kpiData.tenyear_tf ?? Object.values(chVals).reduce((s, v) => s + v, 0))
            : Math.round(kpiData.longterm_qj_tf || 0);
          const jdActual = is10y ? Math.round(kpiData.tenyear_jd || 0) : Math.round(kpiData.longterm_qj_jd || 0);
          const targetCategory = is10y ? 'tenYear' : 'qjPremium';
          const targetTf = Math.round(targetData?.categories?.[targetCategory]?.metrics?.['转型业务']?.year || 0);
          const targetJd = Math.round(targetData?.categories?.[targetCategory]?.metrics?.['经代']?.year || 0);
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
                if (k.endsWith('|' + ch)) ct += (v?.[targetCategory]?.year || 0);
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
