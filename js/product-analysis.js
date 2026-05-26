// product-analysis.js — product structure chart state and rendering
    // ---------- Chart 2: Product Structure ----------
    const productChart = echarts.init(document.getElementById('productChart'));

    function getPieOption(type) {
      const data = productData[type] || [];
      if (data.length === 0) {
        return {
          title: { text: '暂无产品结构数据', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14, fontWeight: 400 } },
          series: []
        };
      }
      return {
        tooltip: {
          trigger: 'item',
          backgroundColor: '#1e293b',
          borderColor: '#334155',
          textStyle: { color: '#f1f5f9' },
          formatter: '{b}: {c}万 ({d}%)'
        },
        legend: {
          type: 'scroll',
          orient: 'horizontal',
          left: 'center',
          bottom: 4,
          width: '86%',
          height: 44,
          textStyle: { color: '#94a3b8', fontSize: 10 },
          itemWidth: 9,
          itemHeight: 9,
          itemGap: 10,
          pageIconColor: '#60a5fa',
          pageIconInactiveColor: '#475569',
          pageTextStyle: { color: '#94a3b8' }
        },
        series: [{
          type: 'pie',
          radius: ['36%', '62%'],
          center: ['50%', '42%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 6, borderColor: '#1e293b', borderWidth: 2 },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 13,
              fontWeight: 600,
              color: '#f8fafc',
              textBorderWidth: 0,
              textShadowBlur: 0
            }
          },
          data,
          color: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4']
        }]
      };
    }
    let currentPieType = 'premium';
    productChart.setOption(getPieOption(currentPieType));

    function fmtStructureAmount(value) {
      const n = Number(value || 0);
      return n.toLocaleString('zh-CN', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }

    function escapeStructureText(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }

    function renderProductTopTable(rows) {
      const wrapper = document.getElementById('productTopTableWrapper');
      if (!wrapper) return;
      const order = ['OTO', '证保', '蚁桥', '经代'];
      const visibleRows = (rows || [])
        .filter(row => order.includes(row.businessLine))
        .sort((a, b) => {
          const lineDiff = order.indexOf(a.businessLine) - order.indexOf(b.businessLine);
          if (lineDiff !== 0) return lineDiff;
          return Number(a.rank || 99) - Number(b.rank || 99);
        });
      if (visibleRows.length === 0) {
        wrapper.innerHTML = '<div class="structure-empty">暂无各业务模式前三名产品数据</div>';
        return;
      }
      const htmlRows = visibleRows.map(row => {
        const line = escapeStructureText(row.businessLine || '-');
        const productName = escapeStructureText(row.productName || '-');
        const rank = Number(row.rank || 0);
        return `
        <tr>
          <td class="primary-text">${line}</td>
          <td class="num">${rank > 0 ? rank : '-'}</td>
          <td title="${productName}">${productName}</td>
          <td class="num">${fmtStructureAmount(row.premium)}万</td>
          <td class="num">${Number(row.share || 0).toFixed(1)}%</td>
        </tr>
      `;
      }).join('');
      wrapper.innerHTML = `
        <table class="structure-table" id="productTopTable">
          <thead>
            <tr>
              <th style="width:16%;">业务模式</th>
              <th style="width:12%;" class="num">排名</th>
              <th>前三名产品</th>
              <th style="width:22%;" class="num">期交保费</th>
              <th style="width:18%;" class="num">模式内占比</th>
            </tr>
          </thead>
          <tbody>${htmlRows}</tbody>
        </table>
      `;
    }

    function switchPie(btn, type) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPieType = type;
      productChart.setOption(getPieOption(type), true);
    }

    function toggleProductSource(source, checked) {
      productFilters[source] = checked;
      const row = document.getElementById(source === 'transform' ? 'productTransformRow' : 'productJingdaiRow');
      if (row) row.style.display = checked ? 'flex' : 'none';
      refreshProductChart();
    }

    function toggleProductTransform(line, checked) {
      productFilters.transformLines[line] = checked;
      refreshProductChart();
    }

    function toggleProductJingdaiOrg(org, checked) {
      productFilters.jingdaiOrgs[org] = checked;
      refreshProductChart();
    }

    // ---------- Product Structure Enhancement ----------
    productFilters.orgs = { 'all': true };
    ORG_LIST.forEach(o => productFilters.orgs[o] = true);
    productFilters.timeDim = 'year';
    productFilters.subPeriod = 'all';
    productFilters.metric = 'qj';

    function toggleProductOrg(org, checked) {
      if (org === 'all') {
        productFilters.orgs['all'] = checked;
        ORG_LIST.forEach(o => productFilters.orgs[o] = checked);
        const allLabel = document.querySelector('#productOrgChecks [data-org="all"]');
        document.querySelectorAll('#productOrgChecks [data-org]:not([data-org="all"])').forEach(cb => cb.checked = checked);
      } else {
        productFilters.orgs[org] = checked;
        const allChecked = ORG_LIST.every(o => productFilters.orgs[o]);
        productFilters.orgs['all'] = allChecked;
        const allLabel = document.querySelector('#productOrgChecks [data-org="all"]');
        if (allLabel) allLabel.checked = allChecked;
      }
      refreshProductChart();
    }

    function switchProductDim(btn, dim) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      productFilters.timeDim = dim;
      const sub = document.getElementById('productSubSelect');
      if (dim === 'year') { sub.style.display = 'none'; productFilters.subPeriod = 'all'; }
      else if (dim === 'quarter') {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全部</option>'+['Q1','Q2','Q3','Q4'].map(q => `<option value="${q}">${q}</option>`).join('');
        productFilters.subPeriod = 'all';
      } else {
        sub.style.display = ''; sub.innerHTML = '<option value="all">全年</option>'+Array.from({length:12},(_,i)=>`<option value="${i+1}">${i+1}月</option>`).join('');
        productFilters.subPeriod = 'all';
      }
      refreshProductChart();
    }

    function switchProductSub(value) {
      productFilters.subPeriod = value;
      refreshProductChart();
    }

    function switchProductMetric(btn, metric) {
      btn.parentElement.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      productFilters.metric = metric;
      refreshProductChart();
    }

