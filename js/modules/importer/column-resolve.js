// 导入：列名解析与校验
//
// 与原 经营分析模板.html 行 923-1006 完全一致。
// 纯函数：仅依赖 schema.js 中导出的常量。

import {
  REQUIRED_TIME_COLS,
  CORE_DIM_COLS,
  METRIC_COLS_ZH,
  COL_ALIASES,
  DATE_COL_CANDIDATES
} from './schema.js';

// 标准列名 → 实际列名（支持别名）。未匹配返回 null
export function resolveCol(standard, available) {
  if (available.includes(standard)) return standard;
  const aliases = COL_ALIASES[standard];
  if (aliases) {
    for (const a of aliases) { if (available.includes(a)) return a; }
  }
  return null;
}

// Levenshtein 距离（用于列名建议）
export function levenshtein(a, b) {
  const m = a.length, n = b.length;
  if (!m) return n; if (!n) return m;
  const prev = Array(n + 1).fill(0).map((_, i) => i);
  for (let i = 1; i <= m; i++) {
    let cur = [i];
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    for (let j = 0; j <= n; j++) prev[j] = cur[j];
  }
  return prev[n];
}

// 在 candidates 中找出最接近 target 的 n 个（用于列缺失提示）
export function suggest(target, candidates, n = 3) {
  return candidates
    .map(c => ({ c, d: levenshtein(target, c) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, n)
    .filter(x => x.d <= Math.max(2, Math.ceil(target.length * 0.5)))
    .map(x => x.c);
}

// 校验 Excel 表头是否包含所有必需列（含别名）；缺失则抛出 Error
export function validateColumns(allCols) {
  const required = [...REQUIRED_TIME_COLS, ...CORE_DIM_COLS, ...METRIC_COLS_ZH];
  const missing = required.filter(c => !resolveCol(c, allCols));
  if (missing.length === 0) return;
  const lines = ['源文件缺失以下必要列：'];
  missing.forEach(col => {
    const sug = suggest(col, allCols);
    lines.push(`  • ${col}    最相近：${sug.length ? sug.join(', ') : '无'}`);
  });
  lines.push(`\n实际列名共 ${allCols.length} 列。`);
  throw new Error(lines.join('\n'));
}

// 在表头中按 DATE_COL_CANDIDATES 顺序找出第一个匹配的日期列；找不到返回 null
export function findDateColumn(allCols) {
  for (const c of DATE_COL_CANDIDATES) {
    if (allCols.includes(c)) return c;
    const alias = resolveCol(c, allCols);
    if (alias) return alias;
  }
  return null;
}
