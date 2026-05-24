// dashboard-config.js - runtime metric and KPI display configuration
(function (window) {
  const DEFAULT_DASHBOARD_CONFIG = {
    metrics: {},
    displayConstraints: {},
    dashboardKpiCards: []
  };

  let dashboardConfig = { ...DEFAULT_DASHBOARD_CONFIG };

  function getDashboardConfig() {
    return dashboardConfig;
  }

  function getDashboardKpiCards() {
    return Array.isArray(dashboardConfig.dashboardKpiCards)
      ? dashboardConfig.dashboardKpiCards
      : [];
  }

  function applyDashboardKpiCardLabels() {
    getDashboardKpiCards().forEach(card => {
      if (!card || !card.code || !card.name) return;
      const node = document.querySelector(`.kpi-card[onclick="openModal('${card.code}')"] .kpi-top-label`);
      if (!node) return;
      node.textContent = card.name;
      if (card.definition) node.title = card.definition;
    });
  }

  async function loadDashboardConfig() {
    try {
      const config = unwrapApiResponse(await fetchJson('/api/config/metrics', { method: 'GET' }));
      if (config && typeof config === 'object') {
        dashboardConfig = {
          metrics: config.metrics || {},
          displayConstraints: config.displayConstraints || {},
          dashboardKpiCards: Array.isArray(config.dashboardKpiCards) ? config.dashboardKpiCards : []
        };
        applyDashboardKpiCardLabels();
      }
    } catch (e) {
      dashboardConfig = { ...DEFAULT_DASHBOARD_CONFIG };
    }
    return dashboardConfig;
  }

  window.getDashboardConfig = getDashboardConfig;
  window.getDashboardKpiCards = getDashboardKpiCards;
  window.applyDashboardKpiCardLabels = applyDashboardKpiCardLabels;
  window.loadDashboardConfig = loadDashboardConfig;
})(window);
