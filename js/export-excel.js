// export-excel.js — dashboard Excel download
(function (window, document) {
  async function exportDashboardExcel() {
    const btn = document.getElementById('exportExcelBtn');
    const yearSelect = document.getElementById('yearSelect');
    const year = yearSelect?.value || window.CONSTANTS?.DEFAULT_YEAR || new Date().getFullYear();
    const params = new URLSearchParams({ year: String(year) });
    if (typeof window.appendDashboardRange === 'function') window.appendDashboardRange(params);
    const range = typeof window.getDashboardRange === 'function' ? window.getDashboardRange() : null;
    const url = window.apiUrl(`/api/export/excel?${params.toString()}`);
    const originalText = btn ? btn.textContent : '';

    try {
      if (btn) {
        btn.disabled = true;
        btn.textContent = '导出中...';
      }
      const resp = await (window.authFetch || fetch)(url);
      if (!resp.ok) throw new Error(`导出失败：${resp.status}`);
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      const rangeLabel = (range?.label || range?.endDate || year).replace(/[\\/:*?"<>|]/g, '-');
      link.download = `经营分析看板数据_${rangeLabel}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error(err);
      alert(err.message || 'Excel导出失败，请稍后重试');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalText || '导出Excel';
      }
    }
  }

  window.exportDashboardExcel = exportDashboardExcel;
})(window, document);
