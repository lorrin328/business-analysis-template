const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag = 'div') {
  return {
    tag, children: [], textContent: '', value: '',
    classList: { contains: () => true },
    get firstChild() { return this.children[0]; },
    get selectedOptions() { return this.children.filter(child => child.value === this.value); },
    appendChild(child) {
      this.children.push(child);
      if (this.tag === 'select' && this.children.length === 1) this.value = child.value;
    },
    removeChild(child) {
      this.children.splice(this.children.indexOf(child), 1);
      if (this.tag === 'select') this.value = this.children[0]?.value || '';
    }
  };
}

function harness() {
  const elements = new Map([['historySelect', element('select')]]);
  const requests = [];
  const rendered = [];
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element,
    addEventListener() {}
  };
  const window = {
    authFetch(url) {
      return new Promise((resolve, reject) => requests.push({
        url, reject,
        resolve(data) { resolve({ ok: true, json: async () => ({ data }) }); }
      }));
    }
  };
  const context = { window, document, rendered };
  vm.createContext(context);
  const source = fs.readFileSync(path.join(__dirname, '../js/market-analysis.js'), 'utf8');
  // Execute production request/selection logic; replace only presentation renderers.
  const exposed = source.replace('})(window, document);', `
    renderReport = report => rendered.push(report.reportId);
    renderObservability = () => {};
    window.testApi = { loadReport, loadHistory, refreshAll, formatPercent };
  })(window, document);`);
  vm.runInContext(exposed, context);
  const select = document.getElementById('historySelect');
  function choose(id) {
    if (!select.children.some(item => item.value === id)) {
      const option = element('option'); option.value = id; option.textContent = id;
      select.appendChild(option);
    }
    select.value = id;
  }
  return { api: window.testApi, requests, rendered, select, choose, document };
}

async function settle() { await new Promise(resolve => setImmediate(resolve)); }

test('later historical selection wins when the older request finishes last', async () => {
  const h = harness();
  const old = h.api.loadReport('A');
  const latest = h.api.loadReport('B');
  h.requests[1].resolve({ reportId: 'B' }); await latest;
  h.requests[0].resolve({ reportId: 'A' }); await old;
  assert.deepEqual(h.rendered, ['B']);
});

test('late failure of superseded report does not replace current report with an error', async () => {
  const h = harness();
  const old = h.api.loadReport('A');
  const latest = h.api.loadReport('B');
  h.requests[1].resolve({ reportId: 'B' }); await latest;
  h.requests[0].reject(new Error('old request timed out'));
  await assert.doesNotReject(old);
  assert.deepEqual(h.rendered, ['B']);
});

test('refresh retains selected history and reloads that report', async () => {
  const h = harness(); h.choose('A');
  const refresh = h.api.refreshAll();
  h.requests.find(r => r.url.endsWith('/status')).resolve({ state: 'success' });
  h.requests.find(r => r.url.includes('/history?')).resolve([{ reportId: 'A' }, { reportId: 'B' }]);
  h.requests.find(r => r.url.includes('/observability?')).resolve({ summary: {} });
  await settle();
  assert.equal(h.select.value, 'A');
  const report = h.requests.find(r => r.url.endsWith('/reports/A'));
  assert.ok(report); report.resolve({ reportId: 'A' }); await refresh;
  assert.deepEqual(h.rendered, ['A']);
});

test('history refresh retains a new selection made while waiting, including older paginated report', async () => {
  const h = harness(); h.choose('A');
  const history = h.api.loadHistory(); h.choose('older-B');
  h.requests[0].resolve([{ reportId: 'A' }]); await history;
  assert.equal(h.select.value, 'older-B');
  assert.equal(h.select.selectedOptions[0].textContent, 'older-B');
});

test('background refresh does not supersede a report selection made while refreshing', async () => {
  const h = harness(); h.choose('A');
  const refresh = h.api.refreshAll();
  h.choose('B'); const selected = h.api.loadReport('B');
  h.requests.find(r => r.url.endsWith('/reports/B')).resolve({ reportId: 'B' }); await selected;
  h.requests.find(r => r.url.endsWith('/status')).resolve({ state: 'success' });
  h.requests.find(r => r.url.includes('/history?')).resolve([{ reportId: 'A' }, { reportId: 'B' }]);
  h.requests.find(r => r.url.includes('/observability?')).resolve({}); await refresh;
  assert.equal(h.select.value, 'B'); assert.deepEqual(h.rendered, ['B']);
  assert.equal(h.requests.filter(r => r.url.includes('/reports/')).length, 1);
});

test('missing observation percentages stay distinct from a measured zero', () => {
  const { api } = harness();
  for (const value of [null, undefined, '', '   ', NaN]) assert.equal(api.formatPercent(value), '待积累');
  assert.equal(api.formatPercent(0), '0%');
  assert.equal(api.formatPercent(0.8), '80%');
});
