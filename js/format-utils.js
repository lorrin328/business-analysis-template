// format-utils.js — 格式化和基础计算工具
(function (window) {
  const F = {
    sumArr(arr) {
      if (!Array.isArray(arr)) return 0;
      let sum = 0;
      for (const v of arr) { if (v === null || v === undefined) break; sum += v; }
      return sum;
    },

    avgArr(arr) {
      if (!Array.isArray(arr)) return 0;
      let sum = 0, n = 0;
      for (const v of arr) {
        if (v === null || v === undefined) break;
        sum += v; n += 1;
      }
      return n > 0 ? sum / n : 0;
    },

    calcRate(actual, target) {
      if (!target || target <= 0) return 0;
      return Math.round(actual / target * 1000) / 10;
    },

    rateClass(rate) {
      if (rate >= 100) return 'up';
      if (rate >= 80) return 'warning';
      return 'down';
    },

    formatPercent(val, decimals) {
      if (val == null || isNaN(val)) return '--';
      return val.toFixed(decimals || 1) + '%';
    },

    formatWan(val, decimals) {
      if (val == null || isNaN(val)) return '--';
      return parseFloat(val.toFixed(decimals || 2)).toLocaleString();
    },

    calcYoy(current, prev) {
      if (!prev || prev <= 0) return null;
      return Math.round((current / prev - 1) * 1000) / 10;
    },

    yoyCell(yoy) {
      if (yoy == null || isNaN(yoy)) return '<td class="kpi-na">--</td>';
      const cls = yoy >= 0 ? 'kpi-up' : 'kpi-down';
      const sign = yoy >= 0 ? '+' : '';
      return '<td class="' + cls + '">' + sign + yoy.toFixed(1) + '%</td>';
    },
  };

  window.FMT = F;
})(window);
