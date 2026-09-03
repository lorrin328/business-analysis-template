const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  const classes = new Set();
  return {
    dataset: {}, disabled: false, hidden: false, textContent: '', children: [], listeners: {},
    classList: { add: key => classes.add(key), remove: key => classes.delete(key),
      toggle: (key, on) => on ? classes.add(key) : classes.delete(key) },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    appendChild(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
    querySelector() { return null; },
  };
}

function harness(options = {}) {
  const elements = new Map();
  const ids = ['uploadImportMode', 'forceUploadRewrite', 'previewUploadButton', 'confirmUploadButton',
    'resetUploadButton', 'uploadPreview', 'uploadPreviewMode', 'uploadPreviewRows',
    'uploadPreviewNotes', 'uploadStatus', 'uploadModeDescription'];
  ids.forEach(id => elements.set(id, element()));
  elements.get('uploadImportMode').value = 'replace_months';
  const inputs = [];
  for (let i = 1; i <= 4; i++) {
    const input = element();
    const card = element();
    const button = element();
    const badge = element();
    card.querySelector = selector => selector === 'button' ? button : badge;
    input.closest = () => card;
    input.files = [];
    input.dataset.uploadInfo = 'info' + i;
    Object.defineProperty(input, 'value', { set(value) { if (value === '') this.files = []; } });
    inputs.push(input);
    elements.set('file' + i, input);
    elements.set('info' + i, element());
  }
  const grid = element();
  const document = {
    readyState: 'complete',
    getElementById: id => elements.get(id) || null,
    querySelector: () => grid,
    querySelectorAll: () => inputs,
    createElement: () => element(),
  };
  const requests = [];
  const responses = [];
  const storage = options.storage || new Map();
  const timers = new Map();
  let timerId = 0;
  let clock = 0;
  const setTimeout = (fn, delay) => { const id = ++timerId; timers.set(id, { fn, at: clock + delay }); return id; };
  const clearTimeout = id => timers.delete(id);
  function advance(ms) {
    clock += ms;
    for (const [id, timer] of timers) {
      if (timer.at <= clock) { timers.delete(id); timer.fn(); }
    }
  }
  const window = {
    currentYear: 2026,
    sessionStorage: { getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    confirm: () => false,
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (!responses.length) throw new Error('unexpected fetch');
      return typeof responses[0] === 'function' ? responses.shift()() : responses.shift();
    },
  };
  class FormData { constructor() { this.parts = []; } append(kind, file) { this.parts.push({ kind, file }); } }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../js/upload.js'), 'utf8'),
    { window, document, FormData, console, Date, setTimeout, clearTimeout, AbortController });
  function select(number, name = 'synthetic.xlsx') {
    const input = elements.get('file' + number);
    input.files = [{ name, size: 1024, lastModified: 1 }];
    window.handleFile(input, 'info' + number);
  }
  return { window, elements, requests, responses, select, advance, timers, storage };
}

function previewResult(canImport = true) {
  return { canImport, manifestHash: 'test-manifest', modeLabel: '完整月替换', modeDescription: '替换所涉月份',
    files: [{ label: '转型业务清单', fileName: '<img onerror=alert(1)>', rowCount: 2,
      periods: ['2026-08'], coverageLabel: '替换 1 行，写入 2 行' }], warnings: [], errors: canImport ? [] : ['缺少字段'] };
}
const response = data => ({ ok: true, json: async () => data });

test('selecting all four files never sends an upload or preview request', async () => {
  const h = harness();
  for (let i = 1; i <= 4; i++) h.select(i);
  assert.equal(h.requests.length, 0);
  assert.equal(h.elements.get('previewUploadButton').disabled, false);
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  await h.window.confirmUpload();
  assert.equal(h.requests.length, 0);
});

test('preview is separate and explicit confirmation carries manifest and mode once', async () => {
  const h = harness();
  h.select(2);
  h.responses.push(response(previewResult()));
  await h.window.previewUpload();
  assert.equal(h.requests.length, 1);
  assert.match(h.requests[0].url, /^\/api\/upload\/preview\?force=false&import_mode=replace_months$/);
  assert.equal(h.requests[0].options.body.parts.length, 1);
  assert.equal(h.elements.get('confirmUploadButton').disabled, false);
  assert.equal(h.elements.get('uploadPreviewRows').children[0].children[1].textContent, '<img onerror=alert(1)>');
  h.responses.push(response({ status: 'success', uploaded: ['performance'], data_years: [2026] }));
  await h.window.confirmUpload();
  assert.match(h.requests[1].url, /^\/api\/upload\?force=false&import_mode=replace_months&preview_manifest=test-manifest$/);
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  assert.match(h.elements.get('uploadStatus').textContent, /已重新写入并刷新看板数据/);
  await h.window.confirmUpload();
  assert.equal(h.requests.length, 2);
});

test('supplement mode excludes and clears all non-performance file selections', async () => {
  const h = harness();
  for (let i = 1; i <= 4; i++) h.select(i);
  h.elements.get('uploadImportMode').value = 'supplement';
  h.window.uploadModeChanged();
  for (const number of [1, 3, 4]) {
    assert.equal(h.elements.get('file' + number).files.length, 0);
    assert.equal(h.elements.get('file' + number).disabled, true);
  }
  h.responses.push(response(previewResult()));
  await h.window.previewUpload();
  assert.match(h.requests[0].url, /import_mode=supplement$/);
  assert.equal(h.requests[0].options.body.parts.length, 1);
  assert.equal(h.requests[0].options.body.parts[0].kind, 'performance');
});

test('file or force option changes invalidate successful previews', async () => {
  for (const change of ['file', 'force', 'mode']) {
    const h = harness();
    h.select(2);
    h.responses.push(response(previewResult()));
    await h.window.previewUpload();
    if (change === 'file') h.select(2); // same file metadata still invalidates
    if (change === 'force') {
      h.elements.get('forceUploadRewrite').checked = true;
      h.elements.get('forceUploadRewrite').listeners.change();
    }
    if (change === 'mode') {
      h.elements.get('uploadImportMode').value = 'supplement';
      h.window.uploadModeChanged();
    }
    await h.window.confirmUpload();
    assert.equal(h.requests.length, 1);
    assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  }
});

test('late preview response cannot confirm changed selection', async () => {
  const h = harness();
  h.select(2);
  let finish;
  h.responses.push(() => new Promise(resolve => { finish = resolve; }));
  const pending = h.window.previewUpload();
  assert.equal(h.elements.get('file2').disabled, true);
  h.select(2, 'changed.xlsx');
  finish(response(previewResult()));
  await pending;
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  await h.window.confirmUpload();
  assert.equal(h.requests.length, 1);
});

test('invalid and failed previews never enable writes', async () => {
  for (const resp of [response(previewResult(false)),
    { ok: false, status: 400, json: async () => ({ detail: { errors: ['缺少完整月份数据'] } }) }]) {
    const h = harness();
    h.select(2);
    h.responses.push(resp);
    await h.window.previewUpload();
    assert.equal(h.elements.get('confirmUploadButton').disabled, true);
    await h.window.confirmUpload();
    assert.equal(h.requests.length, 1);
  }
});

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

async function readyToImport(h) {
  h.select(2);
  h.responses.push(response(previewResult()));
  await h.window.previewUpload();
}

test('preview timeout releases a never-settling fetch and preserves selected files', async () => {
  const h = harness();
  for (let i = 1; i <= 4; i++) h.select(i);
  h.responses.push(() => new Promise(() => {}));
  const pending = h.window.previewUpload();
  assert.equal(h.elements.get('resetUploadButton').disabled, false);
  assert.equal(h.elements.get('resetUploadButton').textContent, '取消预览');
  h.advance(120000);
  await pending;
  assert.match(h.elements.get('uploadStatus').textContent, /预览等待.*尚未提交导入/);
  assert.equal(h.elements.get('previewUploadButton').disabled, false);
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  for (let i = 1; i <= 4; i++) {
    assert.equal(h.elements.get('file' + i).files.length, 1);
    assert.equal(h.elements.get('file' + i).disabled, false);
  }
  assert.equal(h.requests[0].options.signal.aborted, true);
  assert.equal(h.timers.size, 0);
  assert.equal(h.storage.size, 0);
});

test('200 headers with a hanging JSON body time out and a late body cannot replace a new preview', async () => {
  const h = harness();
  h.select(2);
  const body = deferred();
  let bodyStarted = false;
  h.responses.push({ ok: true, status: 200, json: () => { bodyStarted = true; return body.promise; } });
  const pending = h.window.previewUpload();
  await new Promise(setImmediate);
  assert.equal(bodyStarted, true);
  h.advance(120000);
  await pending;
  const latest = { ...previewResult(), manifestHash: 'latest-manifest' };
  latest.files[0].periods = Array.from({ length: 33 }, (_, i) => `${2024 + Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}`);
  h.responses.push(response(latest));
  await h.window.previewUpload();
  body.resolve(previewResult(false));
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(h.elements.get('confirmUploadButton').disabled, false);
  assert.match(h.elements.get('uploadPreviewRows').children[0].children[3].textContent, /2026-09/);
  h.responses.push(response({ status: 'skipped' }));
  await h.window.confirmUpload();
  assert.match(h.requests[2].url, /preview_manifest=latest-manifest$/);
});

test('cancel preview immediately unlocks without clearing files and old cleanup does not unlock a newer request', async () => {
  const h = harness();
  h.select(2);
  const oldResponse = deferred();
  h.responses.push(() => oldResponse.promise);
  const old = h.window.previewUpload();
  h.elements.get('resetUploadButton').listeners.click();
  assert.equal(h.elements.get('file2').files.length, 1);
  assert.equal(h.elements.get('file2').disabled, false);
  assert.match(h.elements.get('uploadStatus').textContent, /已取消预览/);
  const nextResponse = deferred();
  h.responses.push(() => nextResponse.promise);
  const next = h.window.previewUpload();
  await old;
  oldResponse.resolve(response(previewResult(false)));
  await Promise.resolve();
  assert.equal(h.elements.get('file2').disabled, true);
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  nextResponse.resolve(response(previewResult()));
  await next;
  assert.equal(h.elements.get('confirmUploadButton').disabled, false);
  assert.equal(h.requests[0].options.signal.aborted, true);
  assert.equal(h.timers.size, 0);
});

test('malformed preview response or rejected JSON restores controls without enabling confirmation', async () => {
  for (const result of [response({}), { ok: true, json: async () => { throw new SyntaxError('bad JSON'); } }]) {
    const h = harness();
    h.select(2);
    h.responses.push(result);
    await h.window.previewUpload();
    assert.equal(h.elements.get('previewUploadButton').disabled, false);
    assert.equal(h.elements.get('confirmUploadButton').disabled, true);
    assert.equal(h.elements.get('file2').files.length, 1);
    assert.equal(h.timers.size, 0);
  }
});

test('write timeout remains uncertain across preview, late success, and reload until explicit verification', async () => {
  const h = harness();
  await readyToImport(h);
  const writeResponse = deferred();
  h.responses.push(() => writeResponse.promise);
  const pending = h.window.confirmUpload();
  assert.equal(h.elements.get('resetUploadButton').disabled, true);
  const saved = JSON.parse([...h.storage.values()][0]);
  assert.deepEqual(Object.keys(saved).sort(), ['manifest', 'startedAt']);
  assert.equal(saved.manifest, 'test-manifest');
  h.elements.get('resetUploadButton').listeners.click();
  assert.equal(h.elements.get('file2').disabled, true);
  h.advance(300000);
  await pending;
  assert.match(h.elements.get('uploadStatus').textContent, /结果待核实.*可能仍在服务器处理/);
  assert.doesNotMatch(h.elements.get('uploadStatus').textContent, /上传失败|未写入|导入成功/);
  assert.equal(h.elements.get('file2').disabled, false);
  assert.equal(h.elements.get('confirmUploadButton').disabled, true);
  assert.equal(h.elements.get('resetUploadButton').textContent, '核对结果后恢复');
  h.responses.push(response(previewResult()));
  await h.window.previewUpload();
  await h.window.confirmUpload();
  assert.equal(h.requests.length, 3); // only original preview/write and read-only re-preview
  writeResponse.resolve(response({ status: 'success', uploaded: ['performance'] }));
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(h.storage.size, 1);
  assert.match(h.elements.get('uploadStatus').textContent, /结果待核实/);

  const reloaded = harness({ storage: h.storage });
  assert.match(reloaded.elements.get('uploadStatus').textContent, /结果待核实/);
  await readyToImport(reloaded);
  await reloaded.window.confirmUpload();
  assert.equal(reloaded.requests.length, 1);
  reloaded.elements.get('resetUploadButton').listeners.click(); // confirmation defaults to cancel
  assert.equal(reloaded.storage.size, 1);
  reloaded.window.confirm = message => { assert.match(message, /请求已经结束、结果已核实/); return true; };
  reloaded.elements.get('resetUploadButton').listeners.click();
  assert.equal(reloaded.storage.size, 0);
  assert.equal(reloaded.elements.get('file2').files.length, 1);
  assert.equal(reloaded.elements.get('confirmUploadButton').disabled, true);
  await reloaded.window.confirmUpload();
  assert.equal(reloaded.requests.length, 1); // verification is not a write or a reusable manifest
});

test('network, body timeout and 5xx write responses never become an automatic retry or false failure', async () => {
  for (const mode of ['network', 'body-timeout', 'gateway', 'bad-json']) {
    const h = harness();
    await readyToImport(h);
    h.responses.push(mode === 'network' ? () => Promise.reject(new Error('network lost'))
      : mode === 'body-timeout' ? { ok: true, status: 200, json: () => new Promise(() => {}) }
        : mode === 'gateway' ? { ok: false, status: 504, json: async () => ({ detail: 'gateway timeout' }) }
          : { ok: true, status: 200, json: async () => { throw new SyntaxError('bad JSON'); } });
    const pending = h.window.confirmUpload();
    if (mode === 'body-timeout') {
      await new Promise(setImmediate);
      h.advance(300000);
    }
    await pending;
    assert.match(h.elements.get('uploadStatus').textContent, /结果待核实/);
    assert.doesNotMatch(h.elements.get('uploadStatus').textContent, /上传失败|未写入|导入成功/);
    await h.window.confirmUpload();
    assert.equal(h.requests.length, 2);
    assert.equal(h.elements.get('confirmUploadButton').disabled, true);
    assert.equal(h.timers.size, 0);
  }
});

test('known write success or request rejection clears the pending marker and never reuses confirmation', async () => {
  for (const result of [response({ status: 'success', uploaded: ['performance'] }),
    { ok: false, status: 400, json: async () => ({ detail: { errors: ['完整月份字段缺失'] } }) }]) {
    const h = harness();
    await readyToImport(h);
    h.responses.push(result);
    await h.window.confirmUpload();
    assert.equal(h.storage.size, 0);
    assert.equal(h.elements.get('confirmUploadButton').disabled, true);
    assert.equal(h.elements.get('file2').disabled, false);
    assert.equal(h.timers.size, 0);
    await h.window.confirmUpload();
    assert.equal(h.requests.length, 2);
  }
});
