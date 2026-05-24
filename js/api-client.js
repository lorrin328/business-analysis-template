(function (window) {
  const ADMIN_TOKEN_STORAGE_KEY = 'business_admin_token';

  function apiUrl(path) {
    const base = window.API_BASE || '';
    return `${base}${path}`;
  }

  async function fetchJson(path, options = {}) {
    const resp = await fetch(apiUrl(path), options);
    if (!resp.ok) throw new Error(`API ${path} failed: ${resp.status}`);
    return resp.json();
  }

  function unwrapApiResponse(payload) {
    return payload && payload.success === true && Object.prototype.hasOwnProperty.call(payload, 'data')
      ? payload.data
      : payload;
  }

  function adminHeaders(headers = {}) {
    const token = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || '';
    return token ? { ...headers, 'X-Admin-Token': token } : headers;
  }

  async function adminFetch(url, options = {}) {
    let resp = await fetch(url, { ...options, headers: adminHeaders(options.headers || {}) });
    if ([401, 403, 503].includes(resp.status)) {
      const token = prompt('请输入后台管理 Token', sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || '');
      if (token) {
        sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token.trim());
        resp = await fetch(url, { ...options, headers: adminHeaders(options.headers || {}) });
      }
    }
    return resp;
  }

  window.apiUrl = apiUrl;
  window.fetchJson = fetchJson;
  window.unwrapApiResponse = unwrapApiResponse;
  window.adminFetch = adminFetch;
  window.clearAdminToken = () => sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
})(window);
