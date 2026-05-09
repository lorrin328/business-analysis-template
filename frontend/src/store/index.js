const listeners = new Set();

export const store = {
  state: {
    year: 2026,
    quarter: 'Q2',
    month: 4,
    businessLines: ['经代', 'OTO', '证保', '蚁桥'],
    orgs: [],
    premiumType: 'qj',
    chartState: {}
  },
  set(partial) {
    this.state = { ...this.state, ...partial };
    listeners.forEach(fn => fn(this.state));
  },
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }
};
