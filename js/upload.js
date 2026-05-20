// upload.js — 文件上传处理
(function (window) {
  const _uploading = false;
    let _uploading = false;

    function _allFilesReady() {
      return ['file1','file2','file3','file4'].every(id => document.getElementById(id).files[0]);
    }

    function _setAllInfos(msg) {
      ['info1','info2','info3','info4'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = msg;
      });
    }

    function _resetAllCards() {
      ['file1','file2','file3','file4'].forEach(id => {
        const card = document.getElementById(id).closest('.upload-card');
        if (card) card.classList.remove('has-file');
      });
    }

    async function handleFile(input, infoId) {
      if (!input.files || !input.files[0]) return;
      const file = input.files[0];
      const card = input.closest('.upload-card');
      const info = document.getElementById(infoId);
      const sizeKB = (file.size / 1024).toFixed(0);
      info.textContent = `✓ 已选择: ${file.name} (${sizeKB}KB)`;
      card.classList.add('has-file');

      // 检查后端是否可连接
      if (!apiAvailable) {
        _setAllInfos('✗ 后端未连接，请确认服务已启动');
        _resetAllCards();
        return;
      }

      // 等待四份文件全部选完后才上传
      if (!_allFilesReady()) {
        const ready = ['file1','file2','file3','file4'].filter(id => document.getElementById(id).files[0]).length;
        info.textContent = `✓ 已选择: ${file.name} (${sizeKB}KB) · 已选 ${ready}/4`;
        return;
      }

      if (_uploading) return;
      _uploading = true;

      try {
        _setAllInfos('⏳ 正在上传并聚合...');

        const fd = new FormData();
        fd.append('hr', document.getElementById('file1').files[0]);
        fd.append('performance', document.getElementById('file2').files[0]);
        fd.append('jingdai', document.getElementById('file3').files[0]);
        fd.append('value', document.getElementById('file4').files[0]);

        const resp = await adminFetch(`${API_BASE}/api/upload`, {
          method: 'POST',
          body: fd
        });
        if (resp.status === 413) {
          _setAllInfos('✗ 文件过大，需调整 nginx client_max_body_size（参考 deploy/nginx.conf）');
          _resetAllCards();
          _uploading = false;
          return;
        }
        if (!resp.ok) {
          _setAllInfos(`✗ 服务器错误 (${resp.status})，请检查后端日志`);
          _resetAllCards();
          _uploading = false;
          return;
        }
        const result = await resp.json();
        if (result.errors && result.errors.length > 0) {
          _setAllInfos(`✗ 错误: ${result.errors.join('; ')}`);
          _resetAllCards();

  window.handleFile = handleFile;
  window._setAllInfos = _setAllInfos;
  window._resetAllCards = _resetAllCards;
})(window);

