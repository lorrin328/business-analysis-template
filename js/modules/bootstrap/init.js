// 启动编排：initApp / updateMetaInfo / bootFlow
//
// 与原 经营分析模板.html 行 1169-1281 行为一致。
// bootFlow 是顶层入口（取代 IIFE 内的 `bootFlow();` 自调用）。

import { initSelects } from '../../core/filters.js';
import { setDb } from '../../core/db.js';
import { idbGet, idbPut, SCHEMA_VERSION } from '../../core/idb.js';
import { pad2 } from '../importer/index.js';
import { setBoot, hideBoot } from './boot-overlay.js';
import { render } from './render.js';
import { bindEvents } from './events.js';
import { bindReimport, bindEmptyUI } from './import-flow.js';

// 元信息显示：「N 行 · 导入于 YYYY-MM-DD HH:MM」
export function updateMetaInfo(meta) {
  if (!meta) { document.getElementById('metaInfo').textContent = ''; return; }
  const dt = new Date(meta.importedAt);
  const dtStr = `${dt.getFullYear()}-${pad2(dt.getMonth()+1)}-${pad2(dt.getDate())} ${pad2(dt.getHours())}:${pad2(dt.getMinutes())}`;
  document.getElementById('metaInfo').textContent =
    `${meta.rowCount.toLocaleString()} 行 · 导入于 ${dtStr}`;
}

// 已就绪：刷新筛选器选项 → 绑定事件 → 首次渲染 → 隐藏 boot
export function initApp(meta) {
  initSelects();
  bindEvents();
  bindReimport();
  try {
    render();
  } catch (e) {
    console.error('渲染失败:', e);
    setBoot('error', '图表渲染失败：' + (e.message || String(e)) + '\n请打开浏览器控制台（F12）查看详细错误。');
    return;
  }
  updateMetaInfo(meta);
  document.getElementById('btnReimport').disabled = false;
  hideBoot();
}

// 顶层启动流：装载 SQL.js → 检查 IDB 缓存 → 初始化或显示 empty UI
export async function bootFlow() {
  try {
    setBoot('loading', '正在加载 SQLite 引擎 ...');
    if (!window.__SQL) {
      window.__SQL = await initSqlJs({
        locateFile: f => `https://cdn.jsdelivr.net/npm/sql.js@1.10.3/dist/${f}`
      });
    }

    setBoot('loading', '正在检查浏览器缓存 ...');
    const cached = await idbGet('db');
    if (cached) {
      const meta = await idbGet('meta');
      if (!meta || meta.schemaVersion !== SCHEMA_VERSION) {
        console.warn('Schema version mismatch, clearing old cache');
        try { await idbPut('db', null); } catch (e) {}
        try { await idbPut('meta', null); } catch (e) {}
        setBoot('empty');
        bindEmptyUI(bootFlow);
        return;
      }
      setDb(new window.__SQL.Database(new Uint8Array(cached)));
      initApp(meta);
      return;
    }

    setBoot('empty');
    bindEmptyUI(bootFlow);
  } catch (e) {
    console.error(e);
    setBoot('error', e.message || String(e));
  }
}
