// 顶部控件事件绑定
//
// 与原 经营分析模板.html bindEvents()（行 810-849）行为一致。
// 触发 render() 重绘；resize 时仅 dispose-aware 调用 chart.resize()。

import { FILTER_KEYS } from '../../core/constants.js';
import { state, getChart } from '../../core/state.js';
import { render } from './render.js';

export function bindEvents() {
  document.getElementById('metricBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#metricBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    state.metric = e.target.dataset.val;
    render();
  });

  document.getElementById('granBtns').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('#granBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    state.gran = e.target.dataset.val;
    render();
  });

  document.querySelector('.tabs').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    state.view = e.target.dataset.view;
    render();
  });

  document.getElementById('compareToggle').addEventListener('change', e => {
    state.compare = e.target.checked;
    render();
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
