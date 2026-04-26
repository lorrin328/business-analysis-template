// Boot 进度浮层控制
//
// 与原 经营分析模板.html 行 852-865 行为一致。

// state ∈ {'loading', 'empty', 'error'}；msg 仅 loading/error 状态使用
export function setBoot(state, msg) {
  const ov = document.getElementById('bootOverlay');
  const loading = document.getElementById('bootLoading');
  const empty = document.getElementById('bootEmpty');
  const err = document.getElementById('bootError');
  ov.style.display = 'flex';
  ov.classList.toggle('error', state === 'error');
  loading.style.display = state === 'loading' ? 'flex' : 'none';
  empty.style.display   = state === 'empty'   ? 'flex' : 'none';
  err.style.display     = state === 'error'   ? 'flex' : 'none';
  if (state === 'loading') document.getElementById('bootMsg').textContent = msg || '正在处理 ...';
  if (state === 'error')   document.getElementById('bootErrorMsg').textContent = msg || '未知错误';
}

export function hideBoot() {
  document.getElementById('bootOverlay').style.display = 'none';
}
