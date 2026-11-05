// platform-trend.js — shared helpers for platform trend rendering.
(function (window) {
  function daysInMonth(year, month) {
    return new Date(Number(year), Number(month), 0).getDate();
  }

  function dailyDisplayEndDay(year, month) {
    const y = Number(year);
    const m = Number(month);
    const dim = daysInMonth(y, m);
    const bounds = platformRangeBounds(y);
    if (bounds) {
      if (m < bounds.startMonth || m > bounds.endMonth) return 0;
      return m === bounds.endMonth ? bounds.endDay : dim;
    }
    const now = new Date();
    if (y === now.getFullYear() && m > now.getMonth() + 1) return 0;
    if (y === now.getFullYear() && m === now.getMonth() + 1) {
      return Math.min(now.getDate(), dim);
    }
    return dim;
  }

  // Map month/day to the comparison year, including February 29 -> 28.
  function platformRangeBounds(year) {
    const applied = typeof window.getPlatformTrendPeriod === 'function' ? window.getPlatformTrendPeriod(year) : null;
    const range = applied || (typeof window.getDashboardRange === 'function' ? window.getDashboardRange() : null);
    if (!range?.startDate || !range?.endDate) return null;
    const parts = value => String(value).split('-').map(Number);
    const [, startMonth, rawStartDay] = parts(range.startDate);
    const [, endMonth, rawEndDay] = parts(range.endDate);
    const startDay = Math.min(rawStartDay, daysInMonth(year, startMonth));
    const endDay = Math.min(rawEndDay, daysInMonth(year, endMonth));
    return { startMonth, startDay, endMonth, endDay };
  }

  function platformDateInRange(year, month, day) {
    const bounds = platformRangeBounds(year);
    if (!bounds) return true;
    const m = Number(month), d = Number(day);
    if (m < bounds.startMonth || m > bounds.endMonth) return false;
    // Undated historical totals are usable only for a complete natural month.
    if (!d) return (m !== bounds.startMonth || bounds.startDay === 1)
      && (m !== bounds.endMonth || bounds.endDay === daysInMonth(year, m));
    return (m > bounds.startMonth || d >= bounds.startDay)
      && (m < bounds.endMonth || d <= bounds.endDay);
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
  window.platformRangeBounds = platformRangeBounds;
  window.platformDateInRange = platformDateInRange;
})(window);
