// platform-trend.js — shared helpers for platform trend rendering.
(function (window) {
  function daysInMonth(year, month) {
    return new Date(Number(year), Number(month), 0).getDate();
  }

  function dailyDisplayEndDay(year, month) {
    const y = Number(year);
    const m = Number(month);
    const dim = daysInMonth(y, m);
    const asOf = typeof window.getDashboardAsOf === 'function' ? window.getDashboardAsOf() : null;
    if (asOf) {
      const parts = String(asOf).split('-').map(Number);
      const cutoffMonth = parts[1];
      const cutoffDay = parts[2];
      if (Number.isFinite(cutoffMonth) && Number.isFinite(cutoffDay)) {
        if (m > cutoffMonth) return 0;
        if (m === cutoffMonth) return Math.min(cutoffDay, dim);
      }
    }
    const now = new Date();
    if (y === now.getFullYear() && m > now.getMonth() + 1) return 0;
    if (y === now.getFullYear() && m === now.getMonth() + 1) {
      return Math.min(now.getDate(), dim);
    }
    return dim;
  }

  function completeDailySeries(values, year, month) {
    if (!Array.isArray(values) || values.length === 0) return [];
    const dim = dailyDisplayEndDay(year, month);
    if (dim <= 0) return [];
    const completed = [];
    let running = 0;
    for (let i = 0; i < dim; i++) {
      const v = values[i];
      if (v !== null && v !== undefined) running = Number(v) || 0;
      completed.push(Math.round(running * 10) / 10);
    }
    return completed;
  }

  window.daysInMonth = daysInMonth;
  window.dailyDisplayEndDay = dailyDisplayEndDay;
  window.completeDailySeries = completeDailySeries;
})(window);
