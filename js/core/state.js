// 全局应用状态
//
// ESM 规则下，本模块的 `state` 是单例。多个 view-* 模块直接 import 后
// 读写同一对象引用即可。
//
// 自 P4 起提供 onChange / updateState：模块可订阅变更，updateState 合并 patch
// 后通过 requestAnimationFrame 批量通知，避免多次 render() 调用。

// 用户交互状态：金额指标、时间粒度、对比开关、维度视图
export const state = {
  metric: '折算保费',   // 见 constants.METRIC_MAP
  gran:   'day',        // day | month | quarter
  view:   'overall',    // overall | byOrg | byMode
  compare: true         // YoY 同比开关
};

// 变更订阅（轻量，不引入 store 框架）
const _listeners = [];

export function onChange(fn) {
  _listeners.push(fn);
}

export function updateState(patch) {
  Object.assign(state, patch);
  if (_listeners.length && !updateState._pending) {
    updateState._pending = true;
    requestAnimationFrame(() => {
      updateState._pending = false;
      _listeners.forEach(fn => fn(patch));
    });
  }
}

// 日明细查询结果缓存：key = year + period 标识
export const dailyCache = new Map();

// 年份集合：导入后由 importer 写入（数据中出现过的年份去重）
export const allYears = [];

// ECharts 实例容器；由各 view-*.init() 注入；其它模块用名字索引
const _charts = {
  main: null,
  yoy: null,
  struct: null,
  mini: null
};

export function getChart(name) {
  return _charts[name];
}

export function setChart(name, instance) {
  if (!(name in _charts)) {
    throw new Error(`未知的 chart 名称: ${name}`);
  }
  _charts[name] = instance;
}

// 重置所有图表实例（如换文件、重新导入）
export function disposeAllCharts() {
  for (const k of Object.keys(_charts)) {
    if (_charts[k] && typeof _charts[k].dispose === 'function') {
      _charts[k].dispose();
    }
    _charts[k] = null;
  }
}
