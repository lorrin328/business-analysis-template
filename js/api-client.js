(function (window) {
  const AUTH_TOKEN_STORAGE_KEY = 'business_auth_token';
  const AUTH_USER_STORAGE_KEY = 'business_auth_user';

  function apiUrl(path) {
    const base = window.API_BASE || '';
    return `${base}${path}`;
  }

  function getAuthToken() {
    return sessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || '';
  }

  function getCurrentUser() {
    try {
      return JSON.parse(sessionStorage.getItem(AUTH_USER_STORAGE_KEY) || 'null');
    } catch (e) {
      return null;
    }
  }

  function setAuthSession(token, user) {
    if (token) sessionStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    if (user) sessionStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(user));
    window.currentUser = user || null;
  }

  function clearAuthSession() {
    sessionStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    sessionStorage.removeItem(AUTH_USER_STORAGE_KEY);
    window.currentUser = null;
  }

  function authHeaders(headers = {}) {
    const token = getAuthToken();
    return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
  }

  async function authFetch(url, options = {}) {
    const headers = authHeaders(options.headers || {});
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401 && !String(url).includes('/api/auth/')) {
      clearAuthSession();
      if (window.showAuthGate) window.showAuthGate('登录已失效，请重新登录');
    }
    return resp;
  }

  async function fetchJson(path, options = {}) {
    const resp = await authFetch(apiUrl(path), options);
    if (!resp.ok) throw new Error(`API ${path} failed: ${resp.status}`);
    return resp.json();
  }

  function unwrapApiResponse(payload) {
    return payload && payload.success === true && Object.prototype.hasOwnProperty.call(payload, 'data')
      ? payload.data
      : payload;
  }

  window.apiUrl = apiUrl;
  window.fetchJson = fetchJson;
  window.unwrapApiResponse = unwrapApiResponse;
  window.authFetch = authFetch;
  window.adminFetch = authFetch;
  window.getAuthToken = getAuthToken;
  window.getCurrentUser = getCurrentUser;
  window.setAuthSession = setAuthSession;
  window.clearAuthSession = clearAuthSession;
  window.clearAdminToken = clearAuthSession;
})(window);
