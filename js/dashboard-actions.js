// dashboard-actions.js - header action binding for dashboard shell
// ---------- Dashboard Toolbar Actions ----------
(function bindDashboardActions(window, document) {
  function invokeGlobal(functionName) {
    const fn = window[functionName];
    if (typeof fn !== 'function') {
      console.error(`Dashboard action target is unavailable: ${functionName}`);
      return;
    }
    fn();
  }

  const ACTIONS = {
    'open-permission-admin': () => invokeGlobal('openPermissionAdmin'),
    'open-operation-logs': () => invokeGlobal('openOperationLogs'),
    'export-excel': () => invokeGlobal('exportDashboardExcel'),
    'open-product-config': () => invokeGlobal('openProductConfigModal'),
    'open-targets': () => invokeGlobal('openTargetModal'),
    recalculate: () => invokeGlobal('recalculateDashboard'),
    logout: () => invokeGlobal('logout'),
    navigate: button => {
      const href = button.dataset.dashboardHref;
      if (href) window.location.href = href;
    },
  };

  function handleDashboardAction(event) {
    const button = event.target.closest('[data-dashboard-action]');
    if (!button) return;
    const action = ACTIONS[button.dataset.dashboardAction];
    if (!action) return;
    event.preventDefault();
    action(button);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('.header-right')?.addEventListener('click', handleDashboardAction);
  });

  window.dashboardToolbarActions = ACTIONS;
})(window, document);
