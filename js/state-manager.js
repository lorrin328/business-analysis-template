// state-manager.js — 统一应用状态管理
(function (window) {
  const _listeners = {};

  const State = {
    _data: {
      year: 2026,
      periodType: 'month',
      month: 4,
      quarter: 2,
      businessLines: [],
      metric: 'qj',
      compareMode: true,

      // 平台趋势
      platformOrgs: { 'all': true },
      platformSeries: { '经代': true, 'OTO': true, '证保': true, '蚁桥': true },
      platformYear: '2026',
      platformTimeDim: 'quarter',
      platformSubPeriod: 'Q2',

      // 机构维度
      orgKpiData: null,
      selectedOrgs: ['all'],
      orgTimeDim: 'year',
      orgSubPeriod: 1,
      orgSubMonth: 3,

      // 产品分析
      productFilters: {},

      // 交期结构
      payPeriodFilters: {},

      // 队伍分析
      teamMetric: 'headcount',
      teamYear: '2026',
      teamTimeDim: 'year',
      teamSubPeriod: 'Q2',
      teamSeries: { '经代': true, 'OTO': true, '证保': true, '蚁桥': true },
      teamOrgs: { 'all': true },

      // 目标
      targetData: null,
      targetDataSource: 'default',

      // 上传
      _uploading: false,
    },

    get(key) {
      return this._data[key];
    },

    set(key, value) {
      const old = this._data[key];
      this._data[key] = value;
      if (old !== value && _listeners[key]) {
        _listeners[key].forEach(fn => { try { fn(value, old); } catch (e) { console.error(e); } });
      }
    },

    on(key, fn) {
      if (!_listeners[key]) _listeners[key] = [];
      _listeners[key].push(fn);
    },

    off(key, fn) {
      if (_listeners[key]) {
        _listeners[key] = _listeners[key].filter(f => f !== fn);
      }
    },
  };

  window.AppState = State;
})(window);
