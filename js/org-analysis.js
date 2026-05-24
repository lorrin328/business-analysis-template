// org-analysis.js - organization KPI loading, filters, and table rendering
let orgKpiData = null;
    let selectedOrgs = ['all'];
    let orgTimeDim = 'year';
    let orgSubPeriod = 1; // Q2 default
    let orgSubMonth = 3;  // 4月 default

    const ORG_LIST = ['上海','湖北','四川','辽宁','山东','广东','福建','浙江','河南','北京'];
    const CHANNEL_LIST = ['OTO','证保','蚁桥'];

    async function fetchOrgKpiData(year) {
      try {
        orgKpiData = unwrapApiResponse(await fetchJson(`/api/org-analysis?year=${year}`));
        renderOrgTable();
      } catch (e) {
        console.error('fetchOrgKpiData error:', e);
        document.getElementById('orgTableWrapper').innerHTML =
          '<div class="org-empty">机构数据加载失败，请确认已上传含机构信息的业绩清单</div>';
      }
    }

    function toggleOrgFilter(label, org) {
      const input = label.querySelector('input');
      input.checked = !input.checked;
      label.classList.toggle('active', input.checked);

      if (org === 'all') {
        // 全部选中/取消
        if (input.checked) {
          selectedOrgs = ['all'];
          document.querySelectorAll('#orgFilterChecks label:not(:first-child)').forEach(l => {
            l.querySelector('input').checked = false;
            l.classList.remove('active');
          });
        }
      } else {
        // 单独选中某个机构
        const allLabel = document.querySelector('#orgFilterChecks label:first-child');
        const allInput = allLabel.querySelector('input');
        allInput.checked = false;
        allLabel.classList.remove('active');

        selectedOrgs = [];
        document.querySelectorAll('#orgFilterChecks label:not(:first-child)').forEach(l => {
          if (l.querySelector('input').checked) {
            selectedOrgs.push(l.querySelector('input').dataset.org);
          }
        });
        if (selectedOrgs.length === 0) {
          selectedOrgs = ['all'];
          allInput.checked = true;
          allLabel.classList.add('active');
        }
      }
      renderOrgTable();
    }

    function switchOrgDim(dim) {
      orgTimeDim = dim;
      document.querySelectorAll('#orgDimBtns button').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');

      const qSelect = document.getElementById('orgSubPeriod');
      const mSelect = document.getElementById('orgSubMonth');
      if (dim === 'year') {
        qSelect.style.display = 'none';
        mSelect.style.display = 'none';
      } else if (dim === 'quarter') {
        qSelect.style.display = 'inline-block';
        mSelect.style.display = 'none';
        orgSubPeriod = parseInt(qSelect.value);
      } else {
        qSelect.style.display = 'none';
        mSelect.style.display = 'inline-block';
        orgSubMonth = parseInt(mSelect.value);
      }
      renderOrgTable();
    }

    function getOrgPeriodKey(dim, idx) {
      if (dim === 'quarter') return `Q${idx + 1}`;
      if (dim === 'month') return String(idx + 1);
      return 'year';
    }

    function getOrgPerfMetric(source, org, channel, metric, dim, idx) {
      if (!source) return 0;
      const key = `${org}|${channel}`;
      const item = source[key];
      if (!item) return 0;
      const fieldMap = {
        'qj': 'qj_premium',
        '10year': 'product_10year',
        'annuity': 'product_annuity',
        'protection': 'product_protection'
      };
      const field = fieldMap[metric];
      if (!field) return 0;

      // 兼容旧接口：旧接口只返回年度扁平值。
      if (typeof item[field] === 'number') return item[field] || 0;

      if (dim === 'year') return item.year?.[field] || 0;
      const periodKey = getOrgPeriodKey(dim, idx);
      return item[dim]?.[periodKey]?.[field] || 0;
    }

    function getOrgValueMetric(source, org, channel, dim, idx) {
      if (!source) return 0;
      const key = `${org}|${channel}`;
      const item = source[key];
      if (item == null) return 0;
      if (typeof item === 'number') return item || 0;
      if (dim === 'year') return item.year || 0;
      const periodKey = getOrgPeriodKey(dim, idx);
      return item[dim]?.[periodKey] || 0;
    }

    function getOrgActual(org, channel, metric, dim, idx) {
      if (!orgKpiData) return 0;
      if (metric === 'value') return getOrgValueMetric(orgKpiData.value, org, channel, dim, idx);
      return getOrgPerfMetric(orgKpiData.perf, org, channel, metric, dim, idx);
    }

    function getOrgPrevActual(org, channel, metric, dim, idx) {
      if (!orgKpiData) return 0;
      if (metric === 'value') return getOrgValueMetric(orgKpiData.value_prev, org, channel, dim, idx);
      if (metric === 'qj') return getOrgPerfMetric(orgKpiData.perf_prev, org, channel, metric, dim, idx);
      return getOrgPerfMetric(orgKpiData.perf_prev, org, channel, metric, dim, idx);
    }

    function getOrgTarget(org, channel, metric, dim, idx) {
      const metricMap = {
        'qj': 'qjPremium',
        'value': 'value',
        '10year': 'tenYear',
        'annuity': 'shangbao',
        'protection': 'baozhang'
      };
      const catKey = metricMap[metric];
      if (!catKey) return 0;

      const key = `${org}|${channel}`;
      const orgTargets = targetData?.orgTargets;
      if (!orgTargets || !orgTargets[key] || !orgTargets[key][catKey]) return 0;

      const item = orgTargets[key][catKey];
      if (dim === 'year') return item.year || 0;
      if (dim === 'quarter') return item.quarter?.[idx] || 0;
      if (dim === 'month') return item.month?.[idx] || 0;
      return 0;
    }

    function calcOrgRate(actual, target) {
      if (!target || target <= 0) return null;
      return Math.round(actual / target * 1000) / 10;
    }

    function calcOrgYoy(current, prev) {
      if (!prev || prev <= 0) return null;
      return Math.round((current - prev) / prev * 1000) / 10;
    }

    function fmtOrgNum(n) {
      if (n === 0 || n == null) return '-';
      return Math.round(n).toLocaleString('zh-CN');
    }

    function rateCell(rate) {
      if (rate == null) return '<td>-</td>';
      const cls = rate >= 100 ? 'up' : rate >= 80 ? 'warning' : 'down';
      return `<td style="color:var(--${cls});">${rate}%</td>`;
    }

    function yoyCell(yoy) {
      if (yoy == null) return '<td>-</td>';
      const cls = yoy >= 0 ? 'up' : 'down';
      const sign = yoy >= 0 ? '+' : '';
      return `<td class="${cls}">${sign}${yoy}%</td>`;
    }

    function renderOrgTable() {
      const wrapper = document.getElementById('orgTableWrapper');
      if (!orgKpiData) {
        wrapper.innerHTML = '<div class="org-empty">正在加载机构数据...</div>';
        return;
      }

      const orgs = selectedOrgs.includes('all') ? ORG_LIST : selectedOrgs;
      const dim = orgTimeDim;
      const qIdx = orgSubPeriod;
      const mIdx = orgSubMonth;

      // 构建行数据
      let rows = [];
      orgs.forEach(org => {
        CHANNEL_LIST.forEach(ch => {
          const periodIdx = dim === 'month' ? mIdx : qIdx;
          const qjActual = getOrgActual(org, ch, 'qj', dim, periodIdx);
          const valueActual = getOrgActual(org, ch, 'value', dim, periodIdx);
          const p10Actual = getOrgActual(org, ch, '10year', dim, periodIdx);
          const annuityActual = getOrgActual(org, ch, 'annuity', dim, periodIdx);
          const protectionActual = getOrgActual(org, ch, 'protection', dim, periodIdx);

          // 只有有数据的行才显示
          if (qjActual === 0 && valueActual === 0 && p10Actual === 0 && annuityActual === 0 && protectionActual === 0) {
            return;
          }

          const qjTarget = getOrgTarget(org, ch, 'qj', dim, periodIdx);
          const valueTarget = getOrgTarget(org, ch, 'value', dim, periodIdx);
          const p10Target = getOrgTarget(org, ch, '10year', dim, periodIdx);
          const annuityTarget = getOrgTarget(org, ch, 'annuity', dim, periodIdx);
          const protectionTarget = getOrgTarget(org, ch, 'protection', dim, periodIdx);

          const qjPrev = getOrgPrevActual(org, ch, 'qj', dim, periodIdx);
          const valuePrev = getOrgPrevActual(org, ch, 'value', dim, periodIdx);

          rows.push({
            org, channel: ch,
            qjTarget, qjActual, qjRate: calcOrgRate(qjActual, qjTarget), qjYoy: calcOrgYoy(qjActual, qjPrev),
            valueTarget, valueActual, valueRate: calcOrgRate(valueActual, valueTarget), valueYoy: calcOrgYoy(valueActual, valuePrev),
            p10Target, p10Actual, p10Rate: calcOrgRate(p10Actual, p10Target),
            annuityTarget, annuityActual, annuityRate: calcOrgRate(annuityActual, annuityTarget),
            protectionTarget, protectionActual, protectionRate: calcOrgRate(protectionActual, protectionTarget),
          });
        });
      });

      if (rows.length === 0) {
        wrapper.innerHTML = '<div class="org-empty">暂无机构数据，请上传含"销售机构名称"和"业务模式"的Excel</div>';
        return;
      }

      // 按机构分组，添加小计行
      let displayRows = [];
      const orgGroups = {};
      rows.forEach(r => {
        if (!orgGroups[r.org]) orgGroups[r.org] = [];
        orgGroups[r.org].push(r);
      });

      Object.keys(orgGroups).sort().forEach(org => {
        const group = orgGroups[org];
        group.forEach(r => displayRows.push(r));
        // 机构小计（仅当有多个业务模式时）
        if (group.length > 1) {
          const periodIdx = dim === 'month' ? mIdx : qIdx;
          const sum = {
            org, channel: '小计', isSubtotal: true,
            qjTarget: 0, qjActual: 0, qjRate: null, qjYoy: null,
            valueTarget: 0, valueActual: 0, valueRate: null, valueYoy: null,
            p10Target: 0, p10Actual: 0, p10Rate: null,
            annuityTarget: 0, annuityActual: 0, annuityRate: null,
            protectionTarget: 0, protectionActual: 0, protectionRate: null,
          };
          let qjHasTarget = false, valueHasTarget = false;
          let qjPrevSum = 0, valuePrevSum = 0;
          group.forEach(r => {
            sum.qjActual += r.qjActual;
            sum.valueActual += r.valueActual;
            sum.p10Actual += r.p10Actual;
            sum.annuityActual += r.annuityActual;
            sum.protectionActual += r.protectionActual;
            if (r.qjTarget > 0) { sum.qjTarget += r.qjTarget; qjHasTarget = true; }
            if (r.valueTarget > 0) { sum.valueTarget += r.valueTarget; valueHasTarget = true; }
            if (r.p10Target > 0) sum.p10Target += r.p10Target;
            if (r.annuityTarget > 0) sum.annuityTarget += r.annuityTarget;
            if (r.protectionTarget > 0) sum.protectionTarget += r.protectionTarget;
            qjPrevSum += getOrgPrevActual(org, r.channel, 'qj', dim, periodIdx);
            valuePrevSum += getOrgPrevActual(org, r.channel, 'value', dim, periodIdx);
          });
          sum.qjRate = qjHasTarget ? calcOrgRate(sum.qjActual, sum.qjTarget) : null;
          sum.valueRate = valueHasTarget ? calcOrgRate(sum.valueActual, sum.valueTarget) : null;
          sum.p10Rate = sum.p10Target > 0 ? calcOrgRate(sum.p10Actual, sum.p10Target) : null;
          sum.annuityRate = sum.annuityTarget > 0 ? calcOrgRate(sum.annuityActual, sum.annuityTarget) : null;
          sum.protectionRate = sum.protectionTarget > 0 ? calcOrgRate(sum.protectionActual, sum.protectionTarget) : null;
          sum.qjYoy = calcOrgYoy(sum.qjActual, qjPrevSum);
          sum.valueYoy = calcOrgYoy(sum.valueActual, valuePrevSum);
          displayRows.push(sum);
        }
      });

      // 总计行
      const totalPeriodIdx = dim === 'month' ? mIdx : qIdx;
      const totalRow = {
        org: '合计', channel: '', isTotal: true,
        qjTarget: 0, qjActual: 0, qjRate: null, qjYoy: null,
        valueTarget: 0, valueActual: 0, valueRate: null, valueYoy: null,
        p10Target: 0, p10Actual: 0, p10Rate: null,
        annuityTarget: 0, annuityActual: 0, annuityRate: null,
        protectionTarget: 0, protectionActual: 0, protectionRate: null,
      };
      let totalQjHasTarget = false, totalValueHasTarget = false;
      let totalQjPrev = 0, totalValuePrev = 0;
      displayRows.filter(r => !r.isSubtotal && !r.isTotal).forEach(r => {
        totalRow.qjActual += r.qjActual;
        totalRow.valueActual += r.valueActual;
        totalRow.p10Actual += r.p10Actual;
        totalRow.annuityActual += r.annuityActual;
        totalRow.protectionActual += r.protectionActual;
        if (r.qjTarget > 0) { totalRow.qjTarget += r.qjTarget; totalQjHasTarget = true; }
        if (r.valueTarget > 0) { totalRow.valueTarget += r.valueTarget; totalValueHasTarget = true; }
        if (r.p10Target > 0) totalRow.p10Target += r.p10Target;
        if (r.annuityTarget > 0) totalRow.annuityTarget += r.annuityTarget;
        if (r.protectionTarget > 0) totalRow.protectionTarget += r.protectionTarget;
        totalQjPrev += getOrgPrevActual(r.org, r.channel, 'qj', dim, totalPeriodIdx);
        totalValuePrev += getOrgPrevActual(r.org, r.channel, 'value', dim, totalPeriodIdx);
      });
      totalRow.qjRate = totalQjHasTarget ? calcOrgRate(totalRow.qjActual, totalRow.qjTarget) : null;
      totalRow.valueRate = totalValueHasTarget ? calcOrgRate(totalRow.valueActual, totalRow.valueTarget) : null;
      totalRow.p10Rate = totalRow.p10Target > 0 ? calcOrgRate(totalRow.p10Actual, totalRow.p10Target) : null;
      totalRow.annuityRate = totalRow.annuityTarget > 0 ? calcOrgRate(totalRow.annuityActual, totalRow.annuityTarget) : null;
      totalRow.protectionRate = totalRow.protectionTarget > 0 ? calcOrgRate(totalRow.protectionActual, totalRow.protectionTarget) : null;
      totalRow.qjYoy = calcOrgYoy(totalRow.qjActual, totalQjPrev);
      totalRow.valueYoy = calcOrgYoy(totalRow.valueActual, totalValuePrev);

      // 渲染表格
      const periodLabel = dim === 'year' ? '年度' : dim === 'quarter' ? `Q${qIdx+1}` : `${mIdx+1}月`;
      const html = `
        <table class="org-table">
          <thead>
            <tr>
              <th rowspan="2" style="min-width:80px;">机构</th>
              <th rowspan="2" style="min-width:60px;">业务模式</th>
              <th colspan="4" class="group-header">期交保费 (${periodLabel})</th>
              <th colspan="4" class="group-header">价值保费</th>
              <th colspan="3" class="group-header">10年期产品</th>
              <th colspan="3" class="group-header">商保年金</th>
              <th colspan="3" class="group-header">保障类产品</th>
            </tr>
            <tr>
              <th>目标(万)</th><th>达成(万)</th><th>达成率</th><th>同比</th>
              <th>目标(万)</th><th>达成(万)</th><th>达成率</th><th>同比</th>
              <th>目标(万)</th><th>达成(万)</th><th>达成率</th>
              <th>目标(万)</th><th>达成(万)</th><th>达成率</th>
              <th>目标(万)</th><th>达成(万)</th><th>达成率</th>
            </tr>
          </thead>
          <tbody>
            ${displayRows.map(r => `
              <tr ${r.isSubtotal ? 'style="background:rgba(255,255,255,0.03);"' : ''} ${r.isTotal ? 'class="total-row"' : ''}>
                <td style="${r.isTotal ? 'font-weight:600;' : ''}">${r.org}</td>
                <td class="${r.channel !== '小计' && r.channel !== '' ? 'sub-channel' : ''}" style="${r.isTotal||r.isSubtotal?'font-weight:600;':''}">${r.channel}</td>
                <td>${fmtOrgNum(r.qjTarget)}</td>
                <td>${fmtOrgNum(r.qjActual)}</td>
                ${rateCell(r.qjRate)}
                ${yoyCell(r.qjYoy)}
                <td>${fmtOrgNum(r.valueTarget)}</td>
                <td>${fmtOrgNum(r.valueActual)}</td>
                ${rateCell(r.valueRate)}
                ${yoyCell(r.valueYoy)}
                <td>${fmtOrgNum(r.p10Target)}</td>
                <td>${fmtOrgNum(r.p10Actual)}</td>
                ${rateCell(r.p10Rate)}
                <td>${fmtOrgNum(r.annuityTarget)}</td>
                <td>${fmtOrgNum(r.annuityActual)}</td>
                ${rateCell(r.annuityRate)}
                <td>${fmtOrgNum(r.protectionTarget)}</td>
                <td>${fmtOrgNum(r.protectionActual)}</td>
                ${rateCell(r.protectionRate)}
              </tr>
            `).join('')}
            <tr class="total-row">
              <td colspan="2">${totalRow.org}</td>
              <td>${fmtOrgNum(totalRow.qjTarget)}</td>
              <td>${fmtOrgNum(totalRow.qjActual)}</td>
              ${rateCell(totalRow.qjRate)}
              ${yoyCell(totalRow.qjYoy)}
              <td>${fmtOrgNum(totalRow.valueTarget)}</td>
              <td>${fmtOrgNum(totalRow.valueActual)}</td>
              ${rateCell(totalRow.valueRate)}
              ${yoyCell(totalRow.valueYoy)}
              <td>${fmtOrgNum(totalRow.p10Target)}</td>
              <td>${fmtOrgNum(totalRow.p10Actual)}</td>
              ${rateCell(totalRow.p10Rate)}
              <td>${fmtOrgNum(totalRow.annuityTarget)}</td>
              <td>${fmtOrgNum(totalRow.annuityActual)}</td>
              ${rateCell(totalRow.annuityRate)}
              <td>${fmtOrgNum(totalRow.protectionTarget)}</td>
              <td>${fmtOrgNum(totalRow.protectionActual)}</td>
              ${rateCell(totalRow.protectionRate)}
            </tr>
          </tbody>
        </table>
      `;
      wrapper.innerHTML = html;
    }
