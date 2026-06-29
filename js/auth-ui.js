(function (window, document) {
  const FALLBACK_TOKEN_KEY = 'business_auth_token';
  const FALLBACK_USER_KEY = 'business_auth_user';
  const MODULE_LABELS = {
    kpi: 'KPI概览',
    org: '机构维度',
    platform_trend: '业务平台趋势',
    product_structure: '产品结构',
    payment_period: '交期结构',
    team: '队伍分析',
    team_enhanced: '队伍结构与产能分析',
    upload: '数据上传',
    product_config: '参数设置',
    targets: '目标设置',
    excel_export: '导出Excel',
    permission_admin: '权限管理',
    personnel_management: '人员管理',
    recalculate: '重新计算',
    honor_view: '星钻联盟查看',
    honor_audit: '星钻数据适配',
    honor_recalculate: '星钻重算',
    honor_export: '星钻导出',
    honor_admin: '星钻规则管理',
    honor_upload: '星钻上传'
  };
  const ROLE_LABELS = { admin: '管理员组', senior: '高级用户组', normal: '普通用户组' };
  const ROLE_OPTIONS = ['normal', 'senior', 'admin'];
  let adminUsersCache = [];
  let authConfig = { allowPublicRegistration: false };

  function ensureAuthClient() {
    if (typeof window.setAuthSession !== 'function') {
      window.setAuthSession = function (token, user) {
        if (token) sessionStorage.setItem(FALLBACK_TOKEN_KEY, token);
        if (user) sessionStorage.setItem(FALLBACK_USER_KEY, JSON.stringify(user));
        window.currentUser = user || null;
      };
    }
    if (typeof window.getAuthToken !== 'function') {
      window.getAuthToken = function () {
        return sessionStorage.getItem(FALLBACK_TOKEN_KEY) || '';
      };
    }
    if (typeof window.getCurrentUser !== 'function') {
      window.getCurrentUser = function () {
        try {
          return JSON.parse(sessionStorage.getItem(FALLBACK_USER_KEY) || 'null');
        } catch (e) {
          return null;
        }
      };
    }
    if (typeof window.clearAuthSession !== 'function') {
      window.clearAuthSession = function () {
        sessionStorage.removeItem(FALLBACK_TOKEN_KEY);
        sessionStorage.removeItem(FALLBACK_USER_KEY);
        window.currentUser = null;
      };
    }
    if (typeof window.authFetch !== 'function') {
      window.authFetch = function (url, options = {}) {
        const token = window.getAuthToken();
        const headers = token
          ? { ...(options.headers || {}), Authorization: `Bearer ${token}` }
          : (options.headers || {});
        return fetch(url, { ...options, headers });
      };
    }
  }

  ensureAuthClient();

  function getUser() {
    return window.currentUser || window.getCurrentUser?.() || null;
  }

  function hasPermission(key) {
    const user = getUser();
    return user?.role === 'admin' || user?.permissions?.[key] === true;
  }

  function applyPermissionVisibility() {
    const user = getUser();
    document.body.classList.toggle('is-authenticated', !!user);
    document.querySelectorAll('[data-permission]').forEach(el => {
      const key = el.getAttribute('data-permission');
      el.style.display = hasPermission(key) ? '' : 'none';
    });
    const name = document.getElementById('currentUserName');
    if (name && user) name.textContent = `${user.username} · ${ROLE_LABELS[user.role] || user.role}`;
  }

  function setAuthMessage(message) {
    const el = document.getElementById('authMessage');
    if (el) el.textContent = message || '';
  }

  function applyAuthConfig() {
    const subtitle = document.getElementById('authSubtitle');
    const registerBtn = document.getElementById('authRegisterBtn');
    if (subtitle) {
      subtitle.textContent = authConfig.allowPublicRegistration
        ? '请登录或注册后进入系统。新注册账号默认为普通用户。'
        : '请登录后进入系统。账号由管理员开通。';
    }
    if (registerBtn) registerBtn.style.display = authConfig.allowPublicRegistration ? '' : 'none';
  }

  async function loadAuthConfig() {
    try {
      const resp = await fetch(window.apiUrl('/api/auth/config'), { cache: 'no-store' });
      const payload = await resp.json().catch(() => ({}));
      const data = window.unwrapApiResponse ? window.unwrapApiResponse(payload) : payload;
      authConfig.allowPublicRegistration = data?.allowPublicRegistration === true;
    } catch (e) {
      authConfig.allowPublicRegistration = false;
    }
    applyAuthConfig();
  }

  function showAuthGate(message) {
    const gate = document.getElementById('authGate');
    if (gate) gate.style.display = 'flex';
    setAuthMessage(message || '');
  }

  function hideAuthGate() {
    const gate = document.getElementById('authGate');
    if (gate) gate.style.display = 'none';
  }

  async function submitAuth(mode) {
    const username = document.getElementById('authUsername')?.value?.trim();
    const password = document.getElementById('authPassword')?.value || '';
    if (!username || !password) {
      setAuthMessage('请输入用户名和密码');
      return;
    }
    setAuthMessage(mode === 'register' ? '正在注册...' : '正在登录...');
    try {
      const resp = await fetch(window.apiUrl(`/api/auth/${mode}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(payload.detail || payload.message || '认证失败');
      const data = window.unwrapApiResponse(payload);
      window.setAuthSession(data.token, data.user);
      window.currentUser = data.user;
      hideAuthGate();
      applyPermissionVisibility();
    } catch (err) {
      setAuthMessage(err.message || '认证失败，请检查用户名和密码');
    }
  }

  async function requireAuthenticatedUser() {
    const token = window.getAuthToken?.();
    if (!token) {
      showAuthGate();
      return new Promise(resolve => {
        window.__authResolve = resolve;
      });
    }
    try {
      const payload = await window.fetchJson('/api/auth/me');
      const user = window.unwrapApiResponse(payload);
      window.setAuthSession(token, user);
      hideAuthGate();
      applyPermissionVisibility();
      return user;
    } catch (e) {
      window.clearAuthSession();
      showAuthGate('登录已失效，请重新登录');
      return new Promise(resolve => {
        window.__authResolve = resolve;
      });
    }
  }

  async function logout() {
    try {
      await window.authFetch(window.apiUrl('/api/auth/logout'), { method: 'POST' });
    } catch (e) {
      // Ignore logout network failures; local session must still be cleared.
    }
    window.clearAuthSession();
    applyPermissionVisibility();
    showAuthGate('已退出登录');
  }

  function createAuthGate() {
    const gate = document.createElement('div');
    gate.id = 'authGate';
    gate.className = 'auth-gate';
    gate.innerHTML = `
      <div class="auth-panel">
        <div class="auth-title">经营分析看板</div>
        <div class="auth-subtitle" id="authSubtitle">请登录后进入系统。账号由管理员开通。</div>
        <label class="auth-label">用户名</label>
        <input class="auth-input" id="authUsername" autocomplete="username" placeholder="请输入用户名">
        <label class="auth-label">密码</label>
        <input class="auth-input" id="authPassword" type="password" autocomplete="current-password" placeholder="请输入密码">
        <div class="auth-actions">
          <button class="chart-btn auth-primary" id="authLoginBtn">登录</button>
          <button class="chart-btn" id="authRegisterBtn" style="display:none;">注册</button>
        </div>
        <div class="auth-message" id="authMessage"></div>
      </div>`;
    document.body.appendChild(gate);
    document.getElementById('authLoginBtn').addEventListener('click', async () => {
      await submitAuth('login');
      if (window.__authResolve && getUser()) {
        const resolve = window.__authResolve;
        window.__authResolve = null;
        resolve(getUser());
      }
    });
    document.getElementById('authRegisterBtn').addEventListener('click', async () => {
      if (!authConfig.allowPublicRegistration) {
        setAuthMessage('当前环境已关闭自助注册，请联系管理员开通账号');
        return;
      }
      await submitAuth('register');
      if (window.__authResolve && getUser()) {
        const resolve = window.__authResolve;
        window.__authResolve = null;
        resolve(getUser());
      }
    });
    document.getElementById('authPassword').addEventListener('keydown', event => {
      if (event.key === 'Enter') document.getElementById('authLoginBtn').click();
    });
  }

  async function openPermissionAdmin() {
    if (!hasPermission('permission_admin')) return;
    const overlay = document.getElementById('modalOverlay');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');
    title.textContent = '权限管理';
    body.innerHTML = '<div class="structure-empty">正在加载用户权限...</div>';
    overlay.classList.add('active');
    try {
      const payload = await window.fetchJson('/api/admin/users');
      const data = window.unwrapApiResponse(payload);
      adminUsersCache = data.users || [];
      renderPermissionAdmin(body);
    } catch (e) {
      body.innerHTML = `<div class="structure-empty">权限数据加载失败：${e.message || e}</div>`;
    }
  }

  const OPERATION_LABELS = {
    register: '用户注册',
    login: '用户登录',
    password_reset: '重置密码',
    import_report: '导入报表',
    target_save: '设置目标',
    excel_export: '导出Excel',
    product_config: '参数设置',
    permission_admin: '权限管理',
    honor_field_audit: '星钻数据适配',
    honor_recalculate: '星钻重算',
    honor_export: '星钻导出',
    honor_view_batch: '星钻批次查看'
  };

  function formatOperationTime(value) {
    if (!value) return '-';
    return String(value).replace('T', ' ').slice(0, 19);
  }

  function summarizeOperationDetail(raw) {
    if (!raw) return '-';
    try {
      const detail = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (detail.operation) return detail.operation;
      if (detail.year && detail.import_id) return `${detail.year}年，导入ID ${detail.import_id}`;
      if (detail.year) return `${detail.year}年`;
      if (detail.reason) return detail.reason;
      return Object.keys(detail).length ? JSON.stringify(detail) : '-';
    } catch (e) {
      return String(raw).slice(0, 120);
    }
  }

  async function openOperationLogs() {
    if (!hasPermission('permission_admin')) return;
    const overlay = document.getElementById('modalOverlay');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');
    title.textContent = '操作日志';
    body.innerHTML = '<div class="structure-empty">正在加载操作日志...</div>';
    overlay.classList.add('active');
    try {
      const payload = await window.fetchJson('/api/admin/operation-logs?limit=300');
      const data = window.unwrapApiResponse(payload);
      const logs = data.logs || [];
      const rows = logs.map(log => `
        <tr>
          <td>${formatOperationTime(log.created_at)}</td>
          <td>${escapeHtml(log.username || '-')}</td>
          <td>${escapeHtml(OPERATION_LABELS[log.action] || log.action || '-')}</td>
          <td>${escapeHtml(log.target_username || '-')}</td>
          <td>${escapeHtml(log.status || '-')}</td>
          <td>${escapeHtml(summarizeOperationDetail(log.detail))}</td>
        </tr>
      `).join('');
      body.innerHTML = `
        <div class="chart-note" style="margin-bottom:10px;color:#94a3b8;font-size:12px;">
          记录用户注册、登录、重置密码、导入报表、设置目标、导出Excel、参数设置和权限管理等关键动作，时间按北京时间展示，按发生时间倒序排列。
        </div>
        <div class="structure-table-wrapper">
          <table class="structure-table">
            <thead>
              <tr><th>时间</th><th>操作用户</th><th>动作</th><th>对象用户</th><th>状态</th><th>说明</th></tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" class="structure-empty">暂无操作日志</td></tr>'}</tbody>
          </table>
        </div>
      `;
    } catch (e) {
      body.innerHTML = `<div class="structure-empty">操作日志加载失败：${escapeHtml(e.message || e)}</div>`;
    }
  }

  function renderPermissionAdmin(container) {
    const currentUser = getUser();
    const rows = adminUsersCache.map(user => {
      const isCurrentUser = currentUser?.id === user.id;
      const roleOptions = ROLE_OPTIONS.map(role => (
        `<option value="${role}" ${user.role === role ? 'selected' : ''}>${ROLE_LABELS[role]}</option>`
      )).join('');
      return `
      <tr data-user-id="${user.id}">
        <td><input class="permission-input" data-field="username" value="${escapeHtml(user.username)}" ${isCurrentUser ? 'disabled' : ''}></td>
        <td>
          <select class="permission-input" data-field="role" ${isCurrentUser ? 'disabled' : ''}>
            ${roleOptions}
          </select>
        </td>
        <td><input class="permission-input" data-field="password" type="password" placeholder="留空不修改"></td>
        <td class="permission-checkboxes">
          ${Object.keys(MODULE_LABELS).map(key => {
            const locked = user.role === 'admin' || key === 'permission_admin';
            return `<label><input type="checkbox" data-module="${key}" ${user.permissions?.[key] ? 'checked' : ''} ${locked ? 'disabled' : ''}>${MODULE_LABELS[key]}</label>`;
          }).join('')}
        </td>
        <td class="permission-action-cell"><button class="chart-btn permission-delete-btn" data-action="delete-user" data-user-id="${user.id}" data-username="${escapeHtml(user.username)}" ${isCurrentUser ? 'disabled' : ''}>删除</button></td>
      </tr>
    `;
    }).join('');
    container.innerHTML = `
      <div class="permission-toolbar">
        <input class="permission-input" id="newUserName" placeholder="新用户名">
        <input class="permission-input" id="newUserPassword" type="password" placeholder="初始密码">
        <select class="permission-input" id="newUserRole">
          ${ROLE_OPTIONS.map(role => `<option value="${role}">${ROLE_LABELS[role]}</option>`).join('')}
        </select>
        <button class="chart-btn auth-primary" data-action="create-user">新增用户</button>
      </div>
      <div class="structure-table-wrapper">
        <table class="structure-table permission-table">
          <thead><tr><th>用户名</th><th>用户组</th><th>重置密码</th><th>模块权限</th><th>操作</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="permission-footer">
        <div class="chart-note" style="color:#94a3b8;font-size:12px;">管理员账号拥有全部权限；密码只支持重置，不展示原密码。修改多个用户后，点击右侧按钮统一保存。</div>
        <button class="chart-btn auth-primary permission-save-all-btn" data-action="save-all-users">统一保存</button>
      </div>
    `;
    bindPermissionAdminActions(container);
  }

  function bindPermissionAdminActions(container) {
    container.querySelector('[data-action="create-user"]')?.addEventListener('click', createPermissionUser);
    container.querySelector('[data-action="save-all-users"]')?.addEventListener('click', saveAllUserPermissions);
    container.querySelectorAll('[data-action="delete-user"]').forEach(button => {
      button.addEventListener('click', () => {
        deletePermissionUser(button.dataset.userId, button.dataset.username || '');
      });
    });
  }

  async function createPermissionUser() {
    const username = document.getElementById('newUserName').value.trim();
    const password = document.getElementById('newUserPassword').value;
    const role = document.getElementById('newUserRole').value;
    const resp = await window.authFetch(window.apiUrl('/api/admin/users'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role })
    });
    if (!resp.ok) {
      const payload = await resp.json().catch(() => ({}));
      alert(payload.detail || '新增用户失败');
      return;
    }
    await openPermissionAdmin();
  }

  function buildPermissionPayload(row) {
    const password = row.querySelector('[data-field="password"]').value;
    const payload = {
      username: row.querySelector('[data-field="username"]').value.trim(),
      role: row.querySelector('[data-field="role"]').value,
      permissions: {}
    };
    if (password) payload.password = password;
    row.querySelectorAll('[data-module]').forEach(input => {
      payload.permissions[input.dataset.module] = input.checked;
    });
    return payload;
  }

  async function saveUserPermission(userId) {
    const row = document.querySelector(`tr[data-user-id="${userId}"]`);
    if (!row) return;
    const payload = buildPermissionPayload(row);
    const resp = await window.authFetch(window.apiUrl(`/api/admin/users/${userId}`), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      alert(data.detail || '保存失败');
      return;
    }
    await openPermissionAdmin();
  }

  async function saveAllUserPermissions() {
    const rows = Array.from(document.querySelectorAll('tr[data-user-id]')).filter(row => {
      const usernameInput = row.querySelector('[data-field="username"]');
      return usernameInput && !usernameInput.disabled;
    });
    for (const row of rows) {
      const userId = row.dataset.userId;
      const resp = await window.authFetch(window.apiUrl(`/api/admin/users/${userId}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPermissionPayload(row))
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        alert(data.detail || `用户 ${userId} 保存失败`);
        return;
      }
    }
    await openPermissionAdmin();
  }

  async function deletePermissionUser(userId, username) {
    if (!confirm(`确认删除用户「${username}」？删除后该用户将无法继续登录。`)) return;
    const resp = await window.authFetch(window.apiUrl(`/api/admin/users/${userId}`), { method: 'DELETE' });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      alert(data.detail || '删除用户失败');
      return;
    }
    await openPermissionAdmin();
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  document.addEventListener('DOMContentLoaded', () => {
    createAuthGate();
    loadAuthConfig();
    applyPermissionVisibility();
  });

  window.hasPermission = hasPermission;
  window.applyPermissionVisibility = applyPermissionVisibility;
  window.requireAuthenticatedUser = requireAuthenticatedUser;
  window.showAuthGate = showAuthGate;
  window.logout = logout;
  window.openPermissionAdmin = openPermissionAdmin;
  window.openOperationLogs = openOperationLogs;
  window.createPermissionUser = createPermissionUser;
  window.saveUserPermission = saveUserPermission;
  window.saveAllUserPermissions = saveAllUserPermissions;
  window.deletePermissionUser = deletePermissionUser;
})(window, document);
