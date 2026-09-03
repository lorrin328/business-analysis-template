// upload.js — 文件上传处理
(function (window) {
  var _uploading = false;
  var _preview = null;
  var _selectionRevision = 0;
  var _activeRequest = null;
  var _pendingWriteKey = 'business-analysis.pending-upload';
  var _pendingWrite = _restorePendingWrite();
  var _writeUncertain = !!_pendingWrite;
  var _uncertainMessage = '导入结果待核实：请求可能仍在服务器处理，也可能已经写入。请先核对导入记录和看板；确认结果前请勿重复提交。';
  var _sourceSlots = [
    { id: 'file1', kind: 'hr' }, { id: 'file2', kind: 'performance' },
    { id: 'file3', kind: 'jingdai' }, { id: 'file4', kind: 'value' }
  ];

  function _selectedSources() {
    return _sourceSlots.filter(function (slot) {
      var input = document.getElementById(slot.id);
      return input && input.files && input.files[0] && (_importMode() !== 'supplement' || slot.kind === 'performance');
    });
  }

  function _importMode() {
    var input = document.getElementById('uploadImportMode');
    return input && input.value === 'supplement' ? 'supplement' : 'replace_months';
  }

  function _status(message) {
    var el = document.getElementById('uploadStatus');
    if (el) el.textContent = _writeUncertain && message !== _uncertainMessage
      ? message + '\n' + _uncertainMessage : message;
  }

  function _restorePendingWrite() {
    try {
      var pending = JSON.parse(window.sessionStorage.getItem(_pendingWriteKey));
      return pending && typeof pending.manifest === 'string' && Number.isFinite(pending.startedAt) ? pending : null;
    } catch (e) { return null; }
  }

  function _rememberPendingWrite(manifest) {
    _pendingWrite = { manifest: manifest, startedAt: Date.now() };
    try { window.sessionStorage.setItem(_pendingWriteKey, JSON.stringify(_pendingWrite)); } catch (e) { /* Keep the in-page guard if storage is unavailable. */ }
  }

  function _clearPendingWrite() {
    _pendingWrite = null;
    _writeUncertain = false;
    try { window.sessionStorage.removeItem(_pendingWriteKey); } catch (e) { /* Storage may be disabled. */ }
  }

  function _startRequest(kind) {
    var request = { kind: kind, controller: typeof AbortController === 'function' ? new AbortController() : null };
    request.interrupted = new Promise(function (_, reject) {
      request.stop = function (reason) {
        if (request.stopped) return;
        request.stopped = true;
        var error = new Error(reason === 'cancel' ? '预览已取消' : '等待响应超时');
        error.uploadReason = reason;
        reject(error);
        if (request.controller) request.controller.abort();
      };
    });
    request.timer = setTimeout(function () { request.stop('timeout'); }, kind === 'preview' ? 120000 : 300000);
    _activeRequest = request;
    _uploading = true;
    return request;
  }

  function _finishRequest(request) {
    clearTimeout(request.timer);
    if (_activeRequest !== request) return;
    _activeRequest = null;
    _uploading = false;
    _updateControls();
  }

  async function _requestResponse(request, url, data) {
    // Include response body consumption: a 200 header does not guarantee that
    // json() will finish. The race also works when a fetch wrapper ignores abort.
    var operation = (async function () {
      var fetchFn = window.adminFetch || window.fetch;
      var options = { method: 'POST', body: data };
      if (request.controller) options.signal = request.controller.signal;
      var resp = await fetchFn(url, options);
      return resp.ok ? { response: resp, data: await resp.json() }
        : { response: resp, error: await _readUploadError(resp) };
    })();
    return await Promise.race([operation, request.interrupted]);
  }

  function _cancelPreview() {
    var request = _activeRequest;
    if (!request || request.kind !== 'preview') return;
    request.stop('cancel');
    _finishRequest(request);
    _invalidatePreview('已取消预览，所选文件保留，本次预览尚未提交导入。服务器端的只读解析可能仍在结束处理中。');
  }

  function _updateControls() {
    var previewButton = document.getElementById('previewUploadButton');
    var confirmButton = document.getElementById('confirmUploadButton');
    if (previewButton) previewButton.disabled = _uploading || !_selectedSources().length;
    if (confirmButton) confirmButton.disabled = _uploading || !!_pendingWrite || !_preview || !_preview.canImport;
    ['uploadImportMode', 'forceUploadRewrite'].forEach(function (id) {
      var control = document.getElementById(id);
      if (control) control.disabled = _uploading;
    });
    var resetButton = document.getElementById('resetUploadButton');
    if (resetButton) {
      resetButton.disabled = _uploading && (!_activeRequest || _activeRequest.kind !== 'preview');
      resetButton.textContent = _activeRequest && _activeRequest.kind === 'preview' ? '取消预览'
        : (_writeUncertain ? '核对结果后恢复' : '清空选择');
    }
    _sourceSlots.forEach(function (slot) {
      var input = document.getElementById(slot.id);
      if (!input) return;
      var excluded = _importMode() === 'supplement' && slot.kind !== 'performance';
      input.disabled = _uploading || excluded;
      var card = input.closest('.upload-card');
      if (card) {
        card.classList.toggle('upload-disabled', input.disabled);
        var button = card.querySelector('button');
        if (button) button.disabled = input.disabled;
        var badge = card.querySelector('.upload-mandatory');
        if (badge) badge.textContent = excluded ? '本模式不使用' : (_importMode() === 'supplement' ? '必需' : '按需选择');
      }
    });
  }

  function _invalidatePreview(message) {
    _selectionRevision += 1;
    _preview = null;
    var panel = document.getElementById('uploadPreview');
    if (panel) panel.hidden = true;
    _status(message || '文件已选择，请先预览导入范围。');
    _updateControls();
  }

  function _formData() {
    var data = new FormData();
    _selectedSources().forEach(function (slot) {
      data.append(slot.kind, document.getElementById(slot.id).files[0]);
    });
    return data;
  }

  function _selectionKey() {
    return JSON.stringify([_importMode(), _forceUploadEnabled(), _selectedSources().map(function (slot) {
      var file = document.getElementById(slot.id).files[0];
      return [slot.kind, file.name, file.size, file.lastModified];
    })]);
  }

  function _url(path) {
    return window.apiUrl ? window.apiUrl(path) : (window.API_BASE || '') + path;
  }

  function _renderPreview(preview) {
    var panel = document.getElementById('uploadPreview');
    var mode = document.getElementById('uploadPreviewMode');
    var body = document.getElementById('uploadPreviewRows');
    var notes = document.getElementById('uploadPreviewNotes');
    if (mode) mode.textContent = preview.modeLabel + '：' + preview.modeDescription;
    if (body) {
      body.replaceChildren();
      (preview.files || []).forEach(function (file) {
        var row = document.createElement('tr');
        [file.label, file.fileName, file.rowCount === null ? '—' : String(file.rowCount),
          (file.periods || []).join('、') || '—', file.coverageLabel].forEach(function (value) {
          var cell = document.createElement('td');
          cell.textContent = value;
          row.appendChild(cell);
        });
        body.appendChild(row);
      });
    }
    if (notes) notes.textContent = (preview.errors || []).concat(preview.warnings || []).join('\n');
    if (panel) panel.hidden = false;
  }

  async function previewUpload() {
    if (_uploading || !_selectedSources().length) return;
    _invalidatePreview('正在解析清单并核对覆盖范围，预览本身不会写入数据…');
    var revision = _selectionRevision;
    var selectionKey = _selectionKey();
    var request = _startRequest('preview');
    try {
      _updateControls();
      var outcome = await _requestResponse(request, _url('/api/upload/preview?force=' + (_forceUploadEnabled() ? 'true' : 'false') +
        '&import_mode=' + _importMode()), _formData());
      if (_activeRequest !== request || revision !== _selectionRevision || selectionKey !== _selectionKey()) return;
      if (!outcome.response.ok) throw new Error(outcome.error || '预览未完成，请检查文件格式或稍后重试。');
      var preview = outcome.data;
      if (!preview || typeof preview.canImport !== 'boolean' || !Array.isArray(preview.files) || !preview.manifestHash) {
        throw new Error('预览返回内容不完整，请重新预览。');
      }
      _preview = preview;
      _preview.selectionKey = selectionKey;
      _renderPreview(preview);
      _status(preview.canImport ? (_pendingWrite ? '预览已完成，确认导入仍需先核对上次导入结果。'
        : '预览完成，请核对模式、月份和覆盖范围后点击“确认导入”。') : '预览未通过，本次预览未提交导入；请修正后重新预览。');
    } catch (e) {
      if (_activeRequest !== request) return;
      _preview = null;
      _status(e.uploadReason === 'timeout'
        ? '预览等待已超过两分钟，本次预览尚未提交导入，所选文件已保留。可稍后重新预览；服务器端的只读解析可能仍在处理。'
        : '预览失败: ' + (e.message || '网络错误'));
    } finally {
      _finishRequest(request);
    }
  }

  function _setAllInfos(msg) {
    _status(msg);
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

  async function _readUploadError(resp) {
    try {
      var body = await resp.json();
      var detail = body && body.detail ? body.detail : body;
      var messages = [];
      if (detail && Array.isArray(detail.errors)) {
        messages = messages.concat(detail.errors);
      }
      if (detail && detail.message) {
        messages.push(detail.message);
      }
      if (typeof detail === 'string') {
        messages.push(detail);
      }
      if (body && body.message && body.message !== (detail && detail.message)) {
        messages.push(body.message);
      }
      return messages.filter(Boolean).join('; ');
    } catch (e) {
      return '';
    }
  }

  function handleFile(input, infoId) {
    var file = input.files && input.files[0];
    var card = input.closest('.upload-card');
    var info = document.getElementById(infoId);
    if (info) info.textContent = file ? '已选择: ' + file.name + ' (' + (file.size / 1024).toFixed(0) + 'KB)' : '';
    if (card) card.classList.toggle('has-file', !!file);
    _invalidatePreview();
  }

  async function confirmUpload() {
    if (_uploading) return;
    if (_pendingWrite) {
      _writeUncertain = true;
      _status(_uncertainMessage);
      _updateControls();
      return;
    }
    if (!_preview || !_preview.canImport || !_preview.manifestHash || _preview.selectionKey !== _selectionKey()) {
      _invalidatePreview('请先重新预览，再确认导入。');
      return;
    }
    var manifest = _preview.manifestHash;
    _preview = null;
    var request = _startRequest('write');
    var resultKnown = false;
    _rememberPendingWrite(manifest);

    try {
      _updateControls();
      _setAllInfos('正在上传并聚合...');

      var fd = _formData();

      var force = _forceUploadEnabled() ? 'true' : 'false';
      var uploadUrl = window.apiUrl ? window.apiUrl('/api/upload?force=' + force) : (window.API_BASE || '') + '/api/upload?force=' + force;
      uploadUrl += '&import_mode=' + _importMode() + '&preview_manifest=' + encodeURIComponent(manifest);
      var outcome = await _requestResponse(request, uploadUrl, fd);
      var resp = outcome.response;

      if (!resp.ok) {
        var serverError = outcome.error;
        // Gateway/server failures can happen after the transaction committed.
        // Only known request rejections are safe to treat as a non-write.
        if ([400, 401, 403, 409, 413, 422].indexOf(resp.status) < 0) {
          throw new Error('服务器未返回可确认的导入结果');
        }
        resultKnown = true;
        _clearPendingWrite();
        if (resp.status === 413) {
          _setAllInfos(serverError || '文件超过上传限制，请缩小文件或联系管理员调整上传容量。');
        } else if (resp.status === 401 || resp.status === 403) {
          _setAllInfos(serverError || ('认证或权限不足 (' + resp.status + ')，请登录有导入权限的账号'));
        } else if (resp.status === 400) {
          _setAllInfos('导入失败: ' + (serverError || '服务器拒绝本次导入，请检查文件类型、字段和后端日志'));
        } else {
          _setAllInfos(serverError || ('服务器错误 (' + resp.status + ')，请检查后端日志'));
        }
        _resetAllCards();
        return;
      }

      var result = outcome.data;
      if (!result || ['success', 'partial', 'skipped', 'failed'].indexOf(result.status) < 0) {
        throw new Error('导入响应内容不完整');
      }
      resultKnown = true;
      _clearPendingWrite();
      if (result.status === 'failed') {
        _setAllInfos('导入未完成: ' + ((result.errors || []).join('; ') || '服务器已拒绝本次导入，请核对源文件后重新预览。'));
        return;
      }
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
      if (resultKnown) {
        _setAllInfos('已收到导入结果，但页面更新未完成。请刷新看板核对，不要重复提交本次导入。');
      } else {
        _writeUncertain = true;
        _setAllInfos(_uncertainMessage);
      }
    } finally {
      _finishRequest(request);
    }
  }

  function uploadModeChanged() {
    if (_importMode() === 'supplement') {
      _sourceSlots.filter(function (slot) { return slot.kind !== 'performance'; }).forEach(function (slot) {
        var input = document.getElementById(slot.id);
        if (input) {
          input.value = '';
          var info = document.getElementById(input.dataset.uploadInfo);
          if (info) info.textContent = '';
          var card = input.closest('.upload-card');
          if (card) card.classList.remove('has-file');
        }
      });
    }
    var description = document.getElementById('uploadModeDescription');
    if (description) description.textContent = _importMode() === 'supplement'
      ? '仅上传转型业务清单，补充缺失保单记录；相同记录跳过，冲突则整批停止。其他清单请切回完整月替换后选择。'
      : '按需选择 1–4 份清单。每份清单必须包含其所涉月份的完整记录与字段；确认后替换对应来源的整月数据。';
    _invalidatePreview('已选择' + (_importMode() === 'supplement' ? '业绩补充' : '完整月替换') + '模式，请选择文件并预览。');
  }

  function resetUpload() {
    if (_activeRequest && _activeRequest.kind === 'preview') {
      _cancelPreview();
      return;
    }
    if (_uploading) return;
    if (_writeUncertain) {
      var checked = typeof window.confirm === 'function' && window.confirm(
        '请先核对导入记录与看板，并确认上次请求已经结束、结果已核实。\n\n尚未核实请点“取消”；已完成核实请点“确定”，恢复后仍须重新预览，不会自动导入。'
      );
      if (!checked) return;
      _clearPendingWrite();
      _invalidatePreview('已恢复操作，所选文件保留。如确需再次导入，请重新预览并核对覆盖范围。');
      return;
    }
    _sourceSlots.forEach(function (slot) {
      var input = document.getElementById(slot.id);
      if (input) { input.value = ''; handleFile(input, input.dataset.uploadInfo); }
    });
    _invalidatePreview('已清空选择，请选择文件并预览。');
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
        if (input && !input.disabled) input.click();
      });
    }

    document.querySelectorAll('input[type="file"][data-upload-info]').forEach(function (input) {
      if (input.dataset.boundUploadChange === 'true') return;
      input.dataset.boundUploadChange = 'true';
      input.addEventListener('change', function () {
        handleFile(input, input.dataset.uploadInfo);
      });
    });
    [
      ['previewUploadButton', 'click', previewUpload], ['confirmUploadButton', 'click', confirmUpload],
      ['resetUploadButton', 'click', resetUpload], ['uploadImportMode', 'change', uploadModeChanged],
      ['forceUploadRewrite', 'change', function () { _invalidatePreview('强制重写选项已改变，请重新预览。'); }]
    ].forEach(function (binding) {
      var control = document.getElementById(binding[0]);
      if (control && control.dataset.boundUploadAction !== 'true') {
        control.dataset.boundUploadAction = 'true';
        control.addEventListener(binding[1], binding[2]);
      }
    });
    _updateControls();
    if (_writeUncertain) _status(_uncertainMessage);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindUploadControls);
  } else {
    bindUploadControls();
  }

  window.handleFile = handleFile;
  window.bindUploadControls = bindUploadControls;
  window.previewUpload = previewUpload;
  window.confirmUpload = confirmUpload;
  window.uploadModeChanged = uploadModeChanged;
  window._readUploadError = _readUploadError;
  window._setAllInfos = _setAllInfos;
  window._resetAllCards = _resetAllCards;
  window._pickUploadRefreshYear = _pickRefreshYear;
  window._forceUploadEnabled = _forceUploadEnabled;
})(window);
