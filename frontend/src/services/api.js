const API_BASE = window.API_BASE || '';

async function request(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });
  const data = await resp.json().catch(() => null);
  if (!resp.ok || (data && data.success === false)) {
    const message = data?.message || data?.detail || `API请求失败：${path}`;
    console.error(message, data);
    throw new Error(message);
  }
  return data?.success ? data.data : data;
}

export const api = {
  getKpi: (year) => request(`/api/kpi?year=${encodeURIComponent(year)}`),
  getPlatformTrend: ({ year, periodType = 'year', periodValue, month, quarter, businessLines, metric = 'qj' }) => {
    const params = new URLSearchParams({ year, metric, periodType });
    if (month) params.set('month', month);
    if (quarter) params.set('quarter', quarter);
    if (periodValue != null) params.set('periodValue', periodValue);
    if (businessLines?.length) params.set('businessLines', businessLines.join(','));
    return request(`/api/platform-trend?${params.toString()}`);
  },
  getOrgAnalysis: (year) => request(`/api/org-analysis?year=${encodeURIComponent(year)}`),
  getTeamAnalysis: (year) => request(`/api/team-analysis?year=${encodeURIComponent(year)}`),
  getProductAnalysis: (year) => request(`/api/product-analysis?year=${encodeURIComponent(year)}`),
  getTargets: (year) => request(`/api/targets?year=${encodeURIComponent(year)}`),
  saveTargets: (year, payload) => request(`/api/targets?year=${encodeURIComponent(year)}`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
};
