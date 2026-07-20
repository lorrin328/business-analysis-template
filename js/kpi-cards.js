// kpi-cards.js — KPI card calculation and rendering
(function (window) {
    // ---------- KPI Dynamic Calculation ----------
    function updateKPICards() {
      try {
        loadTargetData();
        const year = String((apiData.kpi && apiData.kpi.year) || selectedYear || DEFAULT_DASHBOARD_YEAR);
        const pm = platformMock[year];
        const tm = teamMock[year];
        if (!pm) return;
        const kpi = apiData.kpi;
        const hasApiKpi = kpi && String(kpi.year) === year && kpi.qj_premium && (kpi.qj_premium.total > 0 || kpi.qj_premium.jingdai > 0);
        const period = kpi?.period || {};
        const targetMode = period.targetMode || 'year';
        const targetMonthIndex = Math.max(0, Number((period.endDate || '').slice(5, 7) || 1) - 1);
        const targetLabel = typeof targetSourceLabel === 'function' ? targetSourceLabel() : '目标来源待确认';
        const targetsOfficial = targetLabel === '服务端目标';
        const targetsComparable = targetsOfficial && targetMode !== 'none';

        function updateTargetTrustState() {
          const banner = window.document.getElementById('targetTrustBanner');
          const status = window.document.getElementById('targetSourceStatus');
          window.document.body.classList.toggle('targets-unverified', !targetsComparable);
          if (banner) {
            banner.hidden = targetsComparable;
            const message = banner.querySelector('div');
            if (message && targetsOfficial && targetMode === 'none') {
              message.innerHTML = '<strong>当前区间不计算目标达成率。</strong>按日或自定义日期范围没有可直接对应的正式目标，卡片保留实际值和同比，避免用年度目标形成误导。';
            } else if (message) {
              message.innerHTML = '<strong>正式目标尚未配置。</strong>达成率卡片暂不展示参考目标计算结果，避免将系统默认值误作经营结论；实际保费和同比仍按当前数据口径展示。';
            }
          }
          if (status) status.textContent = targetsOfficial && targetMode === 'none' ? '区间目标不可计算' : targetLabel;
          window.document.querySelectorAll('.kpi-card.target-dependent').forEach(card => {
            card.dataset.targetTrust = targetsComparable ? 'official' : 'unverified';
            if (!targetsComparable) {
              const value = card.querySelector('.kpi-big-value');
              const meta = card.querySelector('.kpi-bottom-meta');
              if (value) {
                if (targetsOfficial) value.textContent = '区间目标不可计算';
                else value.textContent = '目标待配置';
              }
              if (meta) meta.innerHTML = '<span>点击查看实际数据与口径</span>';
            }
          });
        }

        function sumArr(arr) {
          if (!Array.isArray(arr)) return 0;
          let sum = 0;
          for (const v of arr) { if (v === null || v === undefined) break; sum += v; }
          return sum;
        }
        function avgArr(arr) {
          if (!Array.isArray(arr)) return 0;
          let sum = 0, n = 0;
          for (const v of arr) {
            if (v === null || v === undefined) break;
            sum += v;
            n += 1;
          }
          return n > 0 ? sum / n : 0;
        }
        function calcRate(actual, target) {
          if (!target || target <= 0) return 0;
          return Math.round(actual / target * 1000) / 10;
        }
        function rateClass(rate) {
          if (rate >= 100) return 'up';
          if (rate >= 80) return 'warning';
          return 'down';
        }
        function calcYoy(current, previous) {
          if (!previous || previous <= 0) return null;
          return Math.round((current / previous - 1) * 1000) / 10;
        }
        function yoyClass(yoy) {
          if (yoy == null) return '';
          if (yoy >= 10) return 'kpi-yoy-strong';
          if (yoy >= 0) return 'kpi-yoy-mid';
          return 'kpi-yoy-negative';
        }
        function yoyText(yoy) {
          if (yoy == null || !Number.isFinite(Number(yoy))) return '--';
          return `${yoy >= 0 ? '+' : ''}${Number(yoy).toFixed(1)}%`;
        }
        function getTarget(catKey, metric, dim, idx) {
          const metricData = targetData.categories?.[catKey]?.metrics?.[metric];
          if (!metricData) return 0;
          if (dim === 'year') return metricData.year || 0;
          const arr = metricData[dim];
          return Array.isArray(arr) ? (arr[idx] || 0) : 0;
        }
        function getPeriodTarget(catKey, metric) {
          if (targetMode === 'year') return getTarget(catKey, metric, 'year');
          if (targetMode === 'month') return getTarget(catKey, metric, 'month', targetMonthIndex);
          return 0;
        }
        function valueActuals() {
          const value = hasApiKpi && kpi.value ? kpi.value : {};
          const oto = value['OTO'] || 0;
          const zhengbao = value['证保'] || 0;
          const yiqiao = value['蚁桥'] || 0;
          const jingdai = value['经代'] || 0;
          const transform = oto + zhengbao + yiqiao;
          return { oto, zhengbao, yiqiao, jingdai, transform, total: jingdai + transform };
        }
        function fmtPct(value) {
          if (value == null || !Number.isFinite(Number(value))) return '--';
          return `${Number(value).toFixed(1)}%`;
        }
        function fmtWan(value) {
          const num = Number(value || 0);
          if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(2)}亿`;
          return `${Math.round(num).toLocaleString('zh-CN')}万`;
        }
        function formatAsOfLabel(value) {
          if (!value) return '当前可用数据';
          const parts = String(value).split('-');
          if (parts.length !== 3) return value;
          return `${parts[0]}年${Number(parts[1])}月${Number(parts[2])}日`;
        }
        function calcTimeProgress(asOf, yearValue) {
          const yearNum = Number(yearValue);
          const date = asOf ? new Date(`${asOf}T00:00:00`) : new Date(yearNum, new Date().getMonth(), new Date().getDate());
          if (!Number.isFinite(date.getTime()) || date.getFullYear() !== yearNum) return null;
          const start = new Date(yearNum, 0, 1);
          const end = new Date(yearNum + 1, 0, 1);
          return Math.round(((date - start + 86400000) / (end - start)) * 1000) / 10;
        }
        function renderKpiInsight({ overallRate, jdRate, tfRate, overallYoy, jdYoy, tfYoy, overallActual, jdActual, tfActual }) {
          const panel = document.getElementById('kpiInsightPanel');
          if (!panel) return;
          const texts = panel.querySelectorAll('.kpi-insight-text');
          if (texts.length < 3) return;
          if (!hasApiKpi) {
            texts[0].textContent = '当前未取得服务端 KPI 数据，暂不形成经营研判。';
            texts[1].textContent = '请先确认后端连接、登录权限和数据导入状态。';
            texts[2].textContent = window.ALLOW_LOCAL_FALLBACK ? '当前允许开发环境本地兜底数据。' : '当前生产口径不展示本地兜底数据。';
            return;
          }
          const asOf = period.endDate || kpi?.as_of?.selectedDate || window.selectedAsOf || '';
          const progress = targetMode === 'year' ? calcTimeProgress(asOf, year) : null;
          const gap = progress == null ? null : Math.round((overallRate - progress) * 10) / 10;
          const progressText = gap == null
            ? '暂无法计算时间进度'
            : `时间进度${fmtPct(progress)}，达成${gap >= 0 ? '领先' : '落后'}${fmtPct(Math.abs(gap))}`;
          const jdShare = overallActual > 0 ? Math.round(jdActual / overallActual * 1000) / 10 : 0;
          const tfShare = overallActual > 0 ? Math.round(tfActual / overallActual * 1000) / 10 : 0;
          const weakerLine = jdRate <= tfRate ? '经代' : '转型业务';
          let focus = '';
          if (gap != null && gap < -5) {
            focus = `${weakerLine}达成率相对偏低，优先压实目标缺口、机构分层和有效人力转化。`;
          } else if (overallYoy != null && overallYoy < 0) {
            focus = `整体同比${yoyText(overallYoy)}，需区分去年同期基数、当前新增质量和渠道结构变化。`;
          } else {
            focus = `整体节奏可控，继续跟踪经代同比${yoyText(jdYoy)}、转型同比${yoyText(tfYoy)}及品质风险。`;
          }
          const warningText = kpi?.as_of?.warningText ? `；${kpi.as_of.warningText}` : '';
          if (!targetsComparable) {
            const reason = targetsOfficial ? '当前日期区间无可直接对应的正式目标' : '正式目标未配置';
            texts[0].textContent = `整体期交${fmtWan(overallActual)}，同比${yoyText(overallYoy)}；${reason}，暂不判断达成进度。`;
            texts[1].textContent = `经代贡献${fmtPct(jdShare)}、转型贡献${fmtPct(tfShare)}；继续跟踪经代同比${yoyText(jdYoy)}、转型同比${yoyText(tfYoy)}及品质风险。`;
            texts[2].textContent = `KPI 按${period.label || formatAsOfLabel(asOf)}统计，目标来源：${targetLabel}${warningText}。`;
            return;
          }
          texts[0].textContent = `整体期交${fmtWan(overallActual)}，达成${fmtPct(overallRate)}，同比${yoyText(overallYoy)}；${progressText}。`;
          texts[1].textContent = `${focus} 经代贡献${fmtPct(jdShare)}、转型贡献${fmtPct(tfShare)}。`;
          texts[2].textContent = `KPI 按${period.label || formatAsOfLabel(asOf)}统计，目标来源：${targetLabel}${warningText}。`;
        }

        // 如果API数据可用且包含有效保费，优先使用
      // 1. 期交保费达成率
      let 经代实际, OTO实际, 证保实际, 蚁桥实际, 转型实际, 整体实际;
      if (hasApiKpi && kpi.qj_premium) {
        经代实际 = kpi.qj_premium.jingdai || 0;
        OTO实际 = kpi.qj_premium.oto || 0;
        证保实际 = kpi.qj_premium.zhengbao || 0;
        蚁桥实际 = kpi.qj_premium.yiqiao || 0;
        转型实际 = kpi.qj_premium.total_transform || 0;
        整体实际 = kpi.qj_premium.total || 0;
      } else {
        const qjData = pm.year.qj;
        经代实际 = sumArr(qjData['经代']);
        OTO实际 = sumArr(qjData['OTO']);
        证保实际 = sumArr(qjData['证保']);
        蚁桥实际 = sumArr(qjData['蚁桥']);
        转型实际 = OTO实际 + 证保实际 + 蚁桥实际;
        整体实际 = 经代实际 + 转型实际;
      }

      const 整体目标 = getPeriodTarget('qjPremium', '整体');
      const 经代目标 = getPeriodTarget('qjPremium', '经代');
      const 转型目标 = getPeriodTarget('qjPremium', '转型业务');
      const 整体达成率 = calcRate(整体实际, 整体目标);
      const 经代达成率 = calcRate(经代实际, 经代目标);
      const 转型达成率 = calcRate(转型实际, 转型目标);
      const qjRateEl = document.getElementById('kpi-qj-rate');
      if (qjRateEl) qjRateEl.textContent = 整体达成率 + '%';
      const qjSubEl = document.getElementById('kpi-qj-sub');
      if (qjSubEl) {
        const qjPrev = hasApiKpi ? (kpi.qj_premium_prev || {}) : {};
        const 整体同比 = calcYoy(整体实际, qjPrev.total);
        const 经代同比 = calcYoy(经代实际, qjPrev.jingdai);
        const 转型同比 = calcYoy(转型实际, qjPrev.total_transform);
        qjSubEl.innerHTML = `
          <span>整体 <span class="${yoyClass(整体同比)}">同比 ${yoyText(整体同比)}</span></span>
          <span>经代 <span class="${rateClass(经代达成率)}">${经代达成率}%</span> <span class="${yoyClass(经代同比)}">同比 ${yoyText(经代同比)}</span></span>
          <span>转型 <span class="${rateClass(转型达成率)}">${转型达成率}%</span> <span class="${yoyClass(转型同比)}">同比 ${yoyText(转型同比)}</span></span>`;
        renderKpiInsight({
          overallRate: 整体达成率,
          jdRate: 经代达成率,
          tfRate: 转型达成率,
          overallYoy: 整体同比,
          jdYoy: 经代同比,
          tfYoy: 转型同比,
          overallActual: 整体实际,
          jdActual: 经代实际,
          tfActual: 转型实际
        });
      }

      // 2. 价值达成率
      if (hasApiKpi && kpi.value && Object.keys(kpi.value).length > 0) {
        const actual = valueActuals();
        const valueTarget = getPeriodTarget('value', '整体');
        const jingdaiTarget = getPeriodTarget('value', '经代');
        const transformTarget = getPeriodTarget('value', '转型业务');
        const valueRate = calcRate(actual.total, valueTarget);
        const jingdaiRate = calcRate(actual.jingdai, jingdaiTarget);
        const transformRate = calcRate(actual.transform, transformTarget);
        const valueRateEl = document.getElementById('kpi-value-rate');
        if (valueRateEl) valueRateEl.textContent = valueRate > 0 ? valueRate + '%' : '-';
        const valueSubEl = document.getElementById('kpi-value-sub');
        if (valueSubEl) {
          valueSubEl.innerHTML = `
            <span>经代 <span class="${rateClass(jingdaiRate)}">${jingdaiRate > 0 ? jingdaiRate + '%' : '-'}</span></span>
            <span>转型 <span class="${rateClass(transformRate)}">${transformRate > 0 ? transformRate + '%' : '-'}</span></span>`;
        }
      } else {
        const valueRateEl = document.getElementById('kpi-value-rate');
        if (valueRateEl) valueRateEl.textContent = '--';
        const valueSubEl = document.getElementById('kpi-value-sub');
        if (valueSubEl) valueSubEl.innerHTML = '<span style="color:var(--text-secondary)">需上传价值清单</span>';
      }

      // 3. 长险活动率（当月数据）
      const hasApiHr = hasApiKpi && kpi.hr && Object.keys(kpi.hr).length > 0;
      if (hasApiHr) {
        let 总在职 = 0, 总活动 = 0;
        Object.values(kpi.hr).forEach(h => {
          总在职 += (h.avg || 0);
          总活动 += (h.active || 0);
        });
        const 活动率 = 总在职 > 0 ? Math.round(总活动 / 总在职 * 1000) / 10 : 0;
        const activityRateEl = document.getElementById('kpi-activity-rate');
        if (activityRateEl) activityRateEl.textContent = 活动率 + '%';
        // 同比（去年同期同月）
        const kpiMonth = Object.values(kpi.hr)[0]?.month || 0;
        let yoyStr = '';
        if (kpi.hr_prev && Object.keys(kpi.hr_prev).length > 0) {
          let 总在职Prev = 0, 总活动Prev = 0;
          Object.values(kpi.hr_prev).forEach(h => {
            总在职Prev += (h.avg || 0);
            总活动Prev += (h.active || 0);
          });
          const 活动率Prev = 总在职Prev > 0 ? Math.round(总活动Prev / 总在职Prev * 1000) / 10 : 0;
          if (活动率Prev > 0) {
            const yoy = Math.round((活动率 - 活动率Prev) * 10) / 10;
            const cls = yoy >= 0 ? 'up' : 'down';
            const sign = yoy >= 0 ? '+' : '';
            yoyStr = ` <span class="${cls}">同比 ${sign}${yoy}pp</span>`;
          }
        }
        const activitySubEl = document.getElementById('kpi-activity-sub');
        if (activitySubEl) activitySubEl.innerHTML = (kpiMonth ? `<span>${kpiMonth}月</span>` : '<span>点击查看分模式明细</span>') + yoyStr;
      } else if (tm) {
        // Mock路径：取最新有数据的月份
        const channels = ['OTO','证保','蚁桥'];
        let lastMonthIdx = -1;
        for (let i = 11; i >= 0; i--) {
          let hasData = false;
          for (const ch of channels) {
            if ((tm.headcount[ch]?.[i] ?? 0) > 0) { hasData = true; break; }
          }
          if (hasData) { lastMonthIdx = i; break; }
        }
        if (lastMonthIdx >= 0) {
          let 总在职 = 0, 总活动 = 0;
          for (const ch of channels) {
            总在职 += (tm.headcount[ch]?.[lastMonthIdx] || 0);
            总活动 += (tm.activeHeadcount[ch]?.[lastMonthIdx] || 0);
          }
          const 活动率 = 总在职 > 0 ? Math.round(总活动 / 总在职 * 1000) / 10 : 0;
          const activityRateEl = document.getElementById('kpi-activity-rate');
          if (activityRateEl) activityRateEl.textContent = 活动率 + '%';
          const activitySubEl = document.getElementById('kpi-activity-sub');
          if (activitySubEl) activitySubEl.innerHTML = `<span>${lastMonthIdx+1}月</span>`;
        }
      }

      // 商保年金 / 保障类 / 10年期 / 长险期交 — 目标值
      const targetOverall = getPeriodTarget('qjPremium', '整体');

      // 4. 商保年金（转型读取业绩基表标识，经代读取参数设置）
      if (hasApiKpi && kpi.annuity_total !== undefined) {
        const actual = kpi.annuity_total || 0;
        const jdActual = kpi.annuity_jd || 0;
        const tfActual = kpi.annuity_tf || 0;
        const totalTarget = getPeriodTarget('shangbao', '整体');
        const jdTarget = getPeriodTarget('shangbao', '经代');
        const tfTarget = getPeriodTarget('shangbao', '转型业务');
        const totalRate = totalTarget > 0 ? Math.round(actual / totalTarget * 1000) / 10 : 0;
        const jdRate = jdTarget > 0 ? Math.round(jdActual / jdTarget * 1000) / 10 : 0;
        const tfRate = tfTarget > 0 ? Math.round(tfActual / tfTarget * 1000) / 10 : 0;
        const el = document.getElementById('kpi-annuity-rate');
        if (el) el.textContent = totalTarget > 0 ? totalRate + '%' : '--';
        const sub = document.getElementById('kpi-annuity-sub');
        if (sub) sub.innerHTML = totalTarget > 0
          ? `<span>经代 ${jdTarget > 0 ? jdRate + '%' : '--'} · 转型 ${tfTarget > 0 ? tfRate + '%' : '--'}</span>`
          : '<span style="color:var(--text-secondary)">未配置商保年金目标</span>';
      }

      // 5. 保障类产品（转型读取业绩基表标识，经代读取参数设置）
      if (hasApiKpi && kpi.protection_total !== undefined) {
        const actual = kpi.protection_total || 0;
        const jdActual = kpi.protection_jd || 0;
        const tfActual = kpi.protection_tf || 0;
        const totalTarget = getPeriodTarget('baozhang', '整体');
        const jdTarget = getPeriodTarget('baozhang', '经代');
        const tfTarget = getPeriodTarget('baozhang', '转型业务');
        const totalRate = totalTarget > 0 ? Math.round(actual / totalTarget * 1000) / 10 : 0;
        const jdRate = jdTarget > 0 ? Math.round(jdActual / jdTarget * 1000) / 10 : 0;
        const tfRate = tfTarget > 0 ? Math.round(tfActual / tfTarget * 1000) / 10 : 0;
        const el = document.getElementById('kpi-protection-rate');
        if (el) el.textContent = totalTarget > 0 ? totalRate + '%' : '--';
        const sub = document.getElementById('kpi-protection-sub');
        if (sub) sub.innerHTML = totalTarget > 0
          ? `<span>经代 ${jdTarget > 0 ? jdRate + '%' : '--'} · 转型 ${tfTarget > 0 ? tfRate + '%' : '--'}</span>`
          : '<span style="color:var(--text-secondary)">未配置保障类目标</span>';
      }

      // 6. 10年期产品（转型 + 经代）
      if (hasApiKpi && kpi.tenyear_total !== undefined) {
        const actual = kpi.tenyear_total || 0;
        const jdActual = kpi.tenyear_jd || 0;
        const tfActual = kpi.tenyear_tf || 0;
        const totalTarget = getPeriodTarget('tenYear', '整体');
        const jdTarget = getPeriodTarget('tenYear', '经代');
        const tfTarget = getPeriodTarget('tenYear', '转型业务');
        const totalRate = totalTarget > 0 ? Math.round(actual / totalTarget * 1000) / 10 : 0;
        const jdRate = jdTarget > 0 ? Math.round(jdActual / jdTarget * 1000) / 10 : 0;
        const tfRate = tfTarget > 0 ? Math.round(tfActual / tfTarget * 1000) / 10 : 0;
        const el = document.getElementById('kpi-10year-rate');
        if (el) el.textContent = totalTarget > 0 ? totalRate + '%' : '--';
        const sub = document.getElementById('kpi-10year-sub');
        if (sub) sub.innerHTML = totalTarget > 0
          ? `<span>经代 ${jdTarget > 0 ? jdRate + '%' : '--'} · 转型 ${tfTarget > 0 ? tfRate + '%' : '--'}</span>`
          : '<span style="color:var(--text-secondary)">未配置10年期产品目标</span>';
      }

      // 7. 长险期交达成率
      if (hasApiKpi && kpi.longterm_qj !== undefined && kpi.longterm_qj > 0) {
        const ltQj = kpi.longterm_qj || 0;
        const ltTf = kpi.longterm_qj_tf || 0;
        const ltJd = kpi.longterm_qj_jd || 0;
        const rate = targetOverall > 0 ? Math.round(ltQj / targetOverall * 1000) / 10 : 0;
        const el = document.getElementById('kpi-longterm-rate');
        if (el) el.textContent = rate + '%';
        let yoyStr = '';
        if (kpi.longterm_qj_prev !== undefined && kpi.longterm_qj_prev > 0) {
          const yoy = Math.round((ltQj / kpi.longterm_qj_prev - 1) * 1000) / 10;
          const cls = yoy >= 0 ? 'up' : 'down';
          yoyStr = ` <span class="${cls}">同比 ${yoy >= 0 ? '+' : ''}${yoy}%</span>`;
        }
        const jdTarget = getPeriodTarget('qjPremium', '经代');
        const tfTarget = getPeriodTarget('qjPremium', '转型业务');
        const jdRate = jdTarget > 0 ? Math.round(ltJd / jdTarget * 1000) / 10 : 0;
        const tfRate = tfTarget > 0 ? Math.round(ltTf / tfTarget * 1000) / 10 : 0;
        const sub = document.getElementById('kpi-longterm-sub');
        if (sub) sub.innerHTML = `<span>经代 ${jdRate}% · 转型 ${tfRate}%</span>${yoyStr}`;
      } else {
        const el = document.getElementById('kpi-longterm-rate');
        if (el) el.textContent = '--';
        const sub = document.getElementById('kpi-longterm-sub');
        if (sub) sub.innerHTML = '<span style="color:var(--text-secondary)">暂无长险期交数据</span>';
      }

      // 8. 人均保费（月均新单保费 / 月均在职人力）
      if (hasApiKpi && kpi.qj_premium && kpi.hr && Object.keys(kpi.hr).length > 0) {
        let 总保费 = kpi.qj_premium.total_transform || 0;
        let 总在职 = 0;
        let 统计月数 = 0;
        Object.values(kpi.hr).forEach(h => {
          const months = Number(h.months || 0);
          const avgSum = Number(h.avg_sum || 0);
          统计月数 = Math.max(统计月数, months);
          总在职 += months > 0 && avgSum > 0 ? avgSum / months : Number(h.avg || 0);
        });
        const 月均保费 = 统计月数 > 0 ? 总保费 / 统计月数 : 总保费;
        const 人均保费 = 总在职 > 0 ? Math.round(月均保费 / 总在职 * 10) / 10 : 0;
        const perCapitaEl = document.getElementById('kpi-percapita');
        if (perCapitaEl) perCapitaEl.innerHTML = 人均保费 + '<span style="font-size:18px">万</span>';
        const perCapitaSubEl = document.getElementById('kpi-percapita-sub');
        if (perCapitaSubEl) {
          perCapitaSubEl.innerHTML = '<span style="color:var(--text-secondary)">转型业务人均保费</span>';
        }
      } else if (tm) {
        const 保费OTO = sumArr(tm.premium['OTO']);
        const 保费证保 = sumArr(tm.premium['证保']);
        const 保费蚁桥 = sumArr(tm.premium['蚁桥']);
        const 总保费 = 保费OTO + 保费证保 + 保费蚁桥;
        const hcOto = avgArr(tm.headcount['OTO']);
        const hcZb = avgArr(tm.headcount['证保']);
        const hcYq = avgArr(tm.headcount['蚁桥']);
        const 总在职 = hcOto + hcZb + hcYq;
        const 统计月数 = Math.max(
          tm.premium['OTO']?.filter(v => v !== null && v !== undefined).length || 0,
          tm.premium['证保']?.filter(v => v !== null && v !== undefined).length || 0,
          tm.premium['蚁桥']?.filter(v => v !== null && v !== undefined).length || 0,
          1
        );
        const 月均保费 = 总保费 / 统计月数;
        const 人均保费 = 总在职 > 0 ? Math.round(月均保费 / 总在职 * 10) / 10 : 0;
        const perCapitaEl = document.getElementById('kpi-percapita');
        if (perCapitaEl) perCapitaEl.innerHTML = 人均保费 + '<span style="font-size:18px">万</span>';
        const perCapitaSubEl = document.getElementById('kpi-percapita-sub');
        if (perCapitaSubEl) {
          const otoPc = hcOto > 0 ? Math.round((保费OTO / 统计月数) / hcOto * 10) / 10 : 0;
          const zbPc = hcZb > 0 ? Math.round((保费证保 / 统计月数) / hcZb * 10) / 10 : 0;
          const yqPc = hcYq > 0 ? Math.round((保费蚁桥 / 统计月数) / hcYq * 10) / 10 : 0;
          perCapitaSubEl.innerHTML = `
            <span>OTO <span class="${otoPc >= 3 ? 'up' : 'down'}">${otoPc}万</span></span>
            <span>证保 <span class="${zbPc >= 3 ? 'up' : 'down'}">${zbPc}万</span></span>
            <span>蚁桥 <span class="${yqPc >= 3 ? 'up' : 'down'}">${yqPc}万</span></span>`;
        }
      }
        updateTargetTrustState();
      } catch (e) { console.error('updateKPICards error:', e); }
    }

    function bindKPICardActions() {
      const grid = window.document.querySelector('.kpi-grid');
      if (!grid || grid.dataset.kpiActionsBound === '1') return;
      grid.dataset.kpiActionsBound = '1';
      grid.addEventListener('click', event => {
        const card = event.target.closest('.kpi-card[data-kpi-modal]');
        if (!card || !grid.contains(card)) return;
        const modalType = card.dataset.kpiModal;
        if (!modalType) return;
        if (typeof window.openModal !== 'function') {
          console.error('KPI modal opener is unavailable');
          return;
        }
        window.openModal(modalType);
      });
      grid.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('.kpi-card[data-kpi-modal]');
        if (!card || !grid.contains(card)) return;
        event.preventDefault();
        card.click();
      });
    }

    if (window.document.readyState === 'loading') {
      window.document.addEventListener('DOMContentLoaded', bindKPICardActions);
    } else {
      bindKPICardActions();
    }

    window.updateKPICards = updateKPICards;
    window.bindKPICardActions = bindKPICardActions;
})(window);
