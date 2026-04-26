// 文件导入流：handleImport / bindReimport / bindEmptyUI
//
// 与原 经营分析模板.html 行 1193-1253 行为一致。
// 编排 importer.parseAndBuild + idb.idbPut + initApp/render，
// 通过 onProgress 回调驱动 boot 浮层。

import { setDb, getDb, isReady } from '../../core/db.js';
import { dailyCache, getChart } from '../../core/state.js';
import { idbPut } from '../../core/idb.js';
import { parseAndBuild, collectMeta } from '../importer/index.js';
import { setBoot, hideBoot } from './boot-overlay.js';
import { render } from './render.js';
import { initApp, updateMetaInfo } from './init.js';

// 完整导入流：解析 → 写 IDB → 切换内存 db → 渲染 / 初始化 UI
export async function handleImport(file) {
  try {
    const { newDb, fileName } = await parseAndBuild(
      file,
      msg => setBoot('loading', msg)
    );

    setBoot('loading', '正在保存到浏览器缓存 ...');
    const exported = newDb.export();
    await idbPut('db', exported);
    const meta = collectMeta(newDb, fileName);
    await idbPut('meta', meta);

    const oldDb = getDb();
    if (oldDb) { try { oldDb.close(); } catch (e) {} }
    setDb(newDb);
    dailyCache.clear();

    console.log('✅ 导入成功', meta);
    if (getChart('main')) {
      // 已有图表实例：复用，仅刷新数据
      const { initSelects } = await import('../../core/filters.js');
      initSelects();
      updateMetaInfo(meta);
      try {
        render();
        hideBoot();
      } catch (e) {
        console.error('渲染失败:', e);
        setBoot('error', '图表渲染失败：' + (e.message || String(e)) + '\n请打开浏览器控制台（F12）查看详细错误。');
      }
    } else {
      initApp(meta);
    }
  } catch (e) {
    console.error(e);
    setBoot('error', e.message || String(e));
  }
}

// 「重新导入」按钮
export function bindReimport() {
  const btn = document.getElementById('btnReimport');
  btn.onclick = () => {
    if (!confirm('确定要替换当前数据吗？这将清除浏览器中已保存的数据。')) return;
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = '.xlsx,.xls,.xlsm';
    inp.onchange = () => { if (inp.files[0]) handleImport(inp.files[0]); };
    inp.click();
  };
}

// 首次进入「无数据」UI：dropzone + 文件选择 + 重试
export function bindEmptyUI(retryFn) {
  const dz = document.getElementById('dropzone');
  const fi = document.getElementById('fileInput');
  dz.onclick = () => fi.click();
  fi.onchange = () => { if (fi.files[0]) handleImport(fi.files[0]); };
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add('dragover'); };
  dz.ondragleave = () => dz.classList.remove('dragover');
  dz.ondrop = (e) => {
    e.preventDefault();
    dz.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) handleImport(f);
  };
  document.getElementById('btnRetry').onclick = () => retryFn();
}
