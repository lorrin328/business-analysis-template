// upload.js — 文件上传处理
(function (window) {
  var _uploading = false;

  function _allFilesReady() {
    return ['file1', 'file2', 'file3', 'file4'].every(function (id) {
      return document.getElementById(id) && document.getElementById(id).files[0];
    });
  }

  function _setAllInfos(msg) {
    ['info1', 'info2', 'info3', 'info4'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = msg;
    });
  }

  function _resetAllCards() {
    ['file1', 'file2', 'file3', 'file4'].forEach(function (id) {
      var input = document.getElementById(id);
      if (input) {
        var card = input.closest('.upload-card');
        if (card) card.classList.remove('has-file');
      }
    });
  }

  function _refreshAfterUpload(year) {
    // 上传成功后刷新全部数据，与 init() 链路一致
    var y = year || 2026;
    window.__apiRefreshNonce = Date.now();
    if (window.fetchTargetData) { window.fetchTargetData(y); }
    if (window.loadYearFromApi) {
      window.loadYearFromApi(String(y), { updateKpi: true, updateProduct: true }).then(function (ok) {
        if (ok) {
          if (window.refreshPlatformChart) { window.refreshPlatformChart(); }
          if (window.productChart && window.getPieOption && typeof window.currentPieType !== 'undefined') {
            window.productChart.setOption(window.getPieOption(window.currentPieType), true);
          }
          if (window.teamChart && window.getTeamOption) {
            window.teamChart.setOption(window.getTeamOption(), true);
          }
        }
      });
    }
    if (window.fetchPayPeriodData) { window.fetchPayPeriodData(String(y)); }
    if (window.updateCutoffLabel) { window.updateCutoffLabel(String(y)); }
    if (window.updateKPICards) { window.updateKPICards(); }
    if (window.fetchOrgKpiData) { window.fetchOrgKpiData(y); }
  }

  function _currentDashboardYear() {
    var candidates = [
      window.currentYear,
      window.selectedYear,
      window.DEFAULT_DASHBOARD_YEAR_NUM,
      window.DEFAULT_DASHBOARD_YEAR,
      new Date().getFullYear()
    ];
    for (var i = 0; i < candidates.length; i += 1) {
      var value = Number(candidates[i]);
      if (Number.isFinite(value) && value >= 2000 && value <= 2100) {
        return value;
      }
    }
    return 2026;
  }

  function _pickRefreshYear(years) {
    var normalized = (years || [])
      .map(function (year) { return Number(year); })
      .filter(function (year) { return Number.isFinite(year) && year >= 2000 && year <= 2100; })
      .sort(function (a, b) { return a - b; });

    if (!normalized.length) {
      return _currentDashboardYear();
    }

    var current = _currentDashboardYear();
    if (normalized.indexOf(current) >= 0) {
      return current;
    }

    return normalized[normalized.length - 1];
  }

  function _forceUploadEnabled() {
    var input = document.getElementById('forceUploadRewrite');
    return !!(input && input.checked);
  }

  async function handleFile(input, infoId) {
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var card = input.closest('.upload-card');
    var info = document.getElementById(infoId);
    var sizeKB = (file.size / 1024).toFixed(0);
    if (info) { info.textContent = '已选择: ' + file.name + ' (' + sizeKB + 'KB)'; }
    if (card) { card.classList.add('has-file'); }

    if (!_allFilesReady()) {
      var ready = ['file1', 'file2', 'file3', 'file4'].filter(function (id) {
        return document.getElementById(id) && document.getElementById(id).files[0];
      }).length;
      if (info) { info.textContent = '已选择: ' + file.name + ' (' + sizeKB + 'KB) - 已选 ' + ready + '/4'; }
      return;
    }

    if (_uploading) return;
    _uploading = true;

    try {
      _setAllInfos('正在上传并聚合...');

      var fd = new FormData();
      fd.append('hr', document.getElementById('file1').files[0]);
      fd.append('performance', document.getElementById('file2').files[0]);
      fd.append('jingdai', document.getElementById('file3').files[0]);
      fd.append('value', document.getElementById('file4').files[0]);

      var force = _forceUploadEnabled() ? 'true' : 'false';
      var uploadUrl = window.apiUrl ? window.apiUrl('/api/upload?force=' + force) : (window.API_BASE || '') + '/api/upload?force=' + force;
      var fetchFn = window.adminFetch || window.fetch;

      var resp = await fetchFn(uploadUrl, { method: 'POST', body: fd });

      if (resp.status === 413) {
        _setAllInfos('文件过大 (413)，请调整 nginx client_max_body_size 至 100m');
        _resetAllCards();
        return;
      }
      if (resp.status === 401 || resp.status === 403) {
        _setAllInfos('认证或权限不足 (' + resp.status + ')，请登录有导入权限的账号');
        _resetAllCards();
        return;
      }
      if (resp.status === 500) {
        _setAllInfos('服务器内部错误 (500)，请检查后端日志');
        _resetAllCards();
        return;
      }
      if (!resp.ok) {
        _setAllInfos('服务器错误 (' + resp.status + ')，请检查后端日志');
        _resetAllCards();
        return;
      }

      var result = await resp.json();
      var isPartialImport = result.status === 'partial' || (result.data_integrity && result.data_integrity.complete === false);
      if (result.errors && result.errors.length > 0 && !isPartialImport) {
        _setAllInfos('导入错误: ' + result.errors.join('; '));
        _resetAllCards();
        return;
      }

      var uploadedCount = result.uploaded ? result.uploaded.length : 0;
      var skippedCount = result.skipped ? result.skipped.length : 0;
      var years = result.data_years || [];
      var uploadYear = _pickRefreshYear(years);

      var integrityPrefix = result.status === 'skipped'
        ? '未写入数据: '
        : (isPartialImport ? '部分导入成功，数据口径不完整: ' : '导入成功: ');
      var errorNote = isPartialImport && result.errors ? ' 未更新: ' + result.errors.join('; ') : '';
      _setAllInfos(integrityPrefix + uploadedCount + ' 个文件' +
        (skippedCount > 0 ? ' (' + skippedCount + ' 个已跳过)' : '') +
        (result.status === 'skipped' ? '，所选文件与历史成功导入文件完全相同，聚合表未重写' : '，已重新写入并刷新看板数据') + errorNote);
      _refreshAfterUpload(uploadYear);

    } catch (e) {
      _setAllInfos('上传失败: ' + (e.message || '网络错误'));
      _resetAllCards();
      console.error('upload error:', e);
    } finally {
      _uploading = false;
    }
  }

  function bindUploadControls() {
    var grid = document.querySelector('.upload-grid');
    if (grid && grid.dataset.boundUploadCards !== 'true') {
      grid.dataset.boundUploadCards = 'true';
      grid.addEventListener('click', function (event) {
        if (event.target && event.target.matches('input[type="file"]')) return;
        var card = event.target.closest('.upload-card[data-upload-input]');
        if (!card || !grid.contains(card)) return;
        var input = document.getElementById(card.dataset.uploadInput);
        if (input) input.click();
      });
    }

    document.querySelectorAll('input[type="file"][data-upload-info]').forEach(function (input) {
      if (input.dataset.boundUploadChange === 'true') return;
      input.dataset.boundUploadChange = 'true';
      input.addEventListener('change', function () {
        handleFile(input, input.dataset.uploadInfo);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindUploadControls);
  } else {
    bindUploadControls();
  }

  window.handleFile = handleFile;
  window.bindUploadControls = bindUploadControls;
  window._setAllInfos = _setAllInfos;
  window._resetAllCards = _resetAllCards;
  window._pickUploadRefreshYear = _pickRefreshYear;
  window._forceUploadEnabled = _forceUploadEnabled;
})(window);
