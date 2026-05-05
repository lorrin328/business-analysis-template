// 顶部控件事件绑定
//
// 与原 经营分析模板.html bindEvents() 行为一致。
// P4: 改用 updateState 替代直接 state 赋值，render 通过 onChange 订阅。
// 注意：弹窗导航/目标上传事件由 HTML 内联 IIFE 管理（过渡期避免重复绑定）。

import { FILTER_KEYS } from '../../core/constants.js';
import { getChart, onChange, updateState } from '../../core/state.js';
import { render } from './render.js';

// 注册 render 为 state 变更监听器
let _renderRegistered = false;
function ensureRenderListener() {
  if (_renderRegistered) return;
  _renderRegistered = true;
  onChange(() => render());
}

export function bindEvents() {
  ensureRenderListener();

  document.getElementById('metricBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#metricBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    updateState({ metric: e.target.dataset.val });
  });

  document.getElementById('granBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#granBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    updateState({ gran: e.target.dataset.val });
  });

  document.querySelector('.tabs').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    updateState({ view: e.target.dataset.view });
  });

  document.getElementById('compareToggle').addEventListener('change', e => {
    updateState({ compare: e.target.checked });
  });

  FILTER_KEYS.forEach(f => {
    document.getElementById(f.sel).addEventListener('change', () => render());
  });

  window.addEventListener('resize', () => {
    const main   = getChart('main');
    const yoy    = getChart('yoy');
    const struct = getChart('struct');
    if (main)   main.resize();
    if (yoy)    yoy.resize();
    if (struct) struct.resize();
  });
}
