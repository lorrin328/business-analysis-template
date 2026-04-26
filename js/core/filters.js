// 筛选器：UI 选择器值 → SQL WHERE 子句
//
// 现阶段读取直接 DOM；P1.X 切换到 ESM bootstrap 后，main.js 负责
// 在 DOMContentLoaded 之后再调用 initSelects()。

import { FILTER_KEYS, METRIC_MAP } from './constants.js';
import { state, allYears } from './state.js';
import { q } from './db.js';

// 当前选中的金额指标对应的数据库列名
export function metricCol() {
  return METRIC_MAP[state.metric];
}

// 收集筛选器当前值，构造参数化的 SQL WHERE 子句
//   extraClauses: string[]    额外 AND 子句（已是 SQL 文本）
//   extraParams:  Record<string, any>   绑定参数（含 $ 前缀）
export function buildWhere(extraClauses, extraParams) {
  const clauses = [];
  const params = {};
  FILTER_KEYS.forEach(f => {
    const v = document.getElementById(f.sel).value;
    if (v) {
      clauses.push(`${f.col} = $${f.col}`);
      params['$' + f.col] = v;
    }
  });
  if (extraClauses && extraClauses.length) {
    extraClauses.forEach(c => clauses.push(c));
    Object.assign(params, extraParams || {});
  }
  return {
    where: clauses.length ? 'WHERE ' + clauses.join(' AND ') : '',
    params
  };
}

// 用于检测筛选条件变化、缓存失效等场景
export function filterStateHash() {
  return FILTER_KEYS.map(f => document.getElementById(f.sel).value).join('|') +
         '|' + state.metric + '|' + state.view;
}

// 用每个筛选器的可用值填充 <select>，并刷新 allYears
// 必须在 db 已经准备好（fact_premium 表存在）之后调用
export function initSelects() {
  FILTER_KEYS.forEach(f => {
    const rows = q(`SELECT DISTINCT ${f.col} AS v FROM fact_premium WHERE ${f.col} IS NOT NULL AND ${f.col} != '' ORDER BY ${f.col}`);
    const sel = document.getElementById(f.sel);
    const current = sel.value;
    sel.innerHTML = '<option value="">全部</option>';
    rows.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.v;
      opt.textContent = r.v;
      sel.appendChild(opt);
    });
    sel.value = current || '';
  });

  // 刷新年份集合（mutate state.js 的导出引用）
  allYears.length = 0;
  for (const r of q(`SELECT DISTINCT year AS v FROM fact_premium ORDER BY year`)) {
    allYears.push(r.v);
  }
}
