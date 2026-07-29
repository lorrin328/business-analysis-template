// month-multi-select.js — shared visible month checkbox control for dashboard modules
(function () {
  function normalizeMonths(values, maxMonth = 12) {
    const upper = Math.min(12, Math.max(1, Number(maxMonth) || 12));
    return Array.from(new Set((values || [])
      .map(Number)
      .filter(month => Number.isInteger(month) && month >= 1 && month <= upper)))
      .sort((a, b) => a - b);
  }

  function defaultMonths(dimension, maxMonth = 12) {
    const latest = Math.min(12, Math.max(1, Number(maxMonth) || 12));
    if (dimension !== 'quarter') return [latest];
    const quarterStart = Math.floor((latest - 1) / 3) * 3 + 1;
    return [quarterStart, quarterStart + 1, quarterStart + 2].filter(month => month <= latest);
  }

  function periodLabel(year, months) {
    const normalized = normalizeMonths(months);
    if (normalized.length === 0) return `${year}年`;
    return `${year}年${normalized.join('、')}月`;
  }

  function quarterMonths(quarter, maxMonth = 12) {
    const q = Math.min(4, Math.max(1, Number(quarter) || 1));
    const start = (q - 1) * 3 + 1;
    return normalizeMonths([start, start + 1, start + 2], maxMonth);
  }

  function render(container, options = {}) {
    if (!container) return [];
    const maxMonth = Math.min(12, Math.max(1, Number(options.maxMonth) || 12));
    const dimension = options.dimension === 'quarter' ? 'quarter' : 'month';
    let selected = normalizeMonths(options.selectedMonths, maxMonth);
    if (selected.length === 0) selected = defaultMonths(dimension, maxMonth);

    const quarterButtons = dimension === 'quarter'
      ? `<div class="month-preset-row" aria-label="季度快捷选择">
          ${[1, 2, 3, 4].map(q => {
            const months = quarterMonths(q, maxMonth);
            const disabled = months.length === 0;
            const active = months.length > 0 && months.every(month => selected.includes(month));
            return `<button type="button" class="month-preset-btn${active ? ' active' : ''}" data-month-quarter="${q}" aria-pressed="${active ? 'true' : 'false'}" ${disabled ? 'disabled' : ''}>Q${q}</button>`;
          }).join('')}
          <button type="button" class="month-preset-btn" data-month-action="all">全部可用月份</button>
        </div>`
      : `<div class="month-preset-row">
          <button type="button" class="month-preset-btn" data-month-action="all">全部可用月份</button>
          <button type="button" class="month-preset-btn" data-month-action="latest">最新月</button>
        </div>`;

    container.hidden = false;
    container.classList.add('month-multi-select');
    container.innerHTML = `
      ${quarterButtons}
      <div class="month-check-grid" role="group" aria-label="月份复选">
        ${Array.from({ length: 12 }, (_, index) => {
          const month = index + 1;
          const disabled = month > maxMonth;
          const checked = selected.includes(month);
          return `<label class="month-check-label${checked ? ' active' : ''}${disabled ? ' disabled' : ''}">
            <input type="checkbox" data-month-value="${month}" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''}>
            <span>${month}月</span>
          </label>`;
        }).join('')}
      </div>
      <div class="month-selection-summary" aria-live="polite"></div>
    `;

    function sync(next, notify = true) {
      const normalized = normalizeMonths(next, maxMonth);
      if (normalized.length === 0) return false;
      selected = normalized;
      container.querySelectorAll('input[data-month-value]').forEach(input => {
        const checked = selected.includes(Number(input.dataset.monthValue));
        input.checked = checked;
        input.closest('.month-check-label')?.classList.toggle('active', checked);
      });
      container.querySelectorAll('button[data-month-quarter]').forEach(button => {
        const months = quarterMonths(button.dataset.monthQuarter, maxMonth);
        const active = months.length > 0 && months.every(month => selected.includes(month));
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      const summary = container.querySelector('.month-selection-summary');
      if (summary) summary.textContent = `已选 ${selected.join('、')} 月，共 ${selected.length} 个月`;
      if (notify && typeof options.onChange === 'function') options.onChange(selected.slice());
      return true;
    }

    container.onchange = event => {
      const input = event.target.closest('input[data-month-value]');
      if (!input || !container.contains(input)) return;
      const next = Array.from(container.querySelectorAll('input[data-month-value]:checked'))
        .map(item => Number(item.dataset.monthValue));
      if (!sync(next)) {
        input.checked = true;
        input.closest('.month-check-label')?.classList.add('active');
      }
    };

    container.onclick = event => {
      const quarterButton = event.target.closest('button[data-month-quarter]');
      if (quarterButton && container.contains(quarterButton)) {
        event.preventDefault();
        const quarterSelection = quarterMonths(quarterButton.dataset.monthQuarter, maxMonth);
        if (options.allowQuarterMultiSelect === true) {
          const selectedSet = new Set(selected);
          const quarterIsSelected = quarterSelection.every(month => selectedSet.has(month));
          const next = quarterIsSelected
            ? selected.filter(month => !quarterSelection.includes(month))
            : selected.concat(quarterSelection);
          sync(next);
        } else {
          sync(quarterSelection);
        }
        return;
      }
      const actionButton = event.target.closest('button[data-month-action]');
      if (!actionButton || !container.contains(actionButton)) return;
      event.preventDefault();
      const next = actionButton.dataset.monthAction === 'latest'
        ? [maxMonth]
        : Array.from({ length: maxMonth }, (_, index) => index + 1);
      sync(next);
    };

    sync(selected, false);
    return selected.slice();
  }

  window.MonthMultiSelect = {
    defaultMonths,
    normalizeMonths,
    periodLabel,
    quarterMonths,
    render
  };
})();
