// 筛选器：UI 选择器值 → SQL WHERE 子句
//
// 自 P3 起拆分为两层：
//   readFilterValues()         从 DOM 读取当前筛选值（纯 I/O）
//   buildWhereFromValues()     纯函数：筛选值 → SQL WHERE（可脱离浏览器测试）
//   buildWhere()               兼容包装，行为不变

import { FILTER_KEYS, METRIC_MAP } from './constants.js';
import { state, allYears } from './state.js';
import { q } from './db.js';

// 当前选中的金额指标对应的数据库列名
export function metricCol() {
  return METRIC_MAP[state.metric];
}

// 从 DOM 读取所有筛选器当前值，返回纯数据对象
export function readFilterValues() {
  const values = {};
  FILTER_KEYS.forEach(f => {
    values[f.col] = document.getElementById(f.sel).value;
  });
  return values;
}

// 纯函数：根据筛选值构造参数化 SQL WHERE 子句（可脱离浏览器单独测试）
//   filterValues:  { colName: value }   来自 readFilterValues()
//   extraClauses:  string[]             额外 AND 子句（已是 SQL 文本）
//   extraParams:   Record<string, any>  绑定参数（含 $ 前缀）
export function buildWhereFromValues(filterValues, extraClauses, extraParams) {
  const clauses = [];
  const params = {};
  FILTER_KEYS.forEach(f => {
    const v = filterValues[f.col];
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

// 兼容包装：直接从 DOM 读取并构造 WHERE（保持原有调用方不变）
export function buildWhere(extraClauses, extraParams) {
  return buildWhereFromValues(readFilterValues(), extraClauses, extraParams);
}

// 用于检测筛选条件变化、缓存失效等场景
export function filterStateHash() {
  return FILTER_KEYS.map(f => document.getElementById(f.sel).value).join('|') +
         '|' + state.metric + '|' + state.view;
}

// 纯函数版本：从 filterValues 计算 hash（不读 DOM）
export function filterStateHashFromValues(filterValues) {
  return FILTER_KEYS.map(f => filterValues[f.col]).join('|') +
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
