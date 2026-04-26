// 导入模块：入口
//
// parseAndBuild(file, onProgress) — 读取 Excel → 校验 → 建库 → 批量插入
// collectMeta(targetDb, fileName) — 抽取行数 / 年份分布 / 各金额求和
// pad2 — 由 cell-transform 内部使用，亦在外部更新元信息时用到，重新导出方便顶层 import
//
// 与原 经营分析模板.html parseAndBuild + collectMeta 行为一致。
// onProgress(msg) 由调用方提供，用于驱动 boot 进度文案。importer 不直接耦合 boot UI。

import {
  REQUIRED_TIME_COLS,
  ALL_DIM_COLS,
  METRIC_COLS_ZH,
  SCHEMA_SQL,
  INSERT_SQL
} from './schema.js';
import {
  resolveCol,
  validateColumns,
  findDateColumn
} from './column-resolve.js';
import { transformRow, pad2 } from './cell-transform.js';

export { pad2 };

// 由文件构建 SQLite 内存库；不写 IDB、不刷新 UI；只返回内存 db
//   file:        File / Blob
//   onProgress:  (msg) => void   可选；用于报告 reading/parsing/building 进度
//   返回 { newDb, fileName }
export async function parseAndBuild(file, onProgress) {
  const progress = onProgress || (() => {});
  progress(`正在读取 ${file.name} ...`);
  const buf = await file.arrayBuffer();
  progress('正在解析 Excel（大文件可能需要 5-30 秒）...');
  const wb = XLSX.read(buf, { type: 'array', cellDates: true });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  if (!sheet) throw new Error('Excel 文件为空（无 sheet）');
  const rows = XLSX.utils.sheet_to_json(sheet, { defval: null, raw: true });
  if (!rows.length) throw new Error('Excel 第一个 sheet 没有数据行');

  const allCols = Object.keys(rows[0]);
  validateColumns(allCols);
  const dateCol = findDateColumn(allCols);

  // 标准列 → 实际列（含别名）
  const colMap = {};
  for (const col of [...REQUIRED_TIME_COLS, ...ALL_DIM_COLS, ...METRIC_COLS_ZH]) {
    const resolved = resolveCol(col, allCols);
    if (resolved) colMap[col] = resolved;
  }

  progress(`正在构建数据库（${rows.length.toLocaleString()} 行）...`);
  const newDb = new window.__SQL.Database();
  newDb.exec(SCHEMA_SQL);

  const stmt = newDb.prepare(INSERT_SQL);
  newDb.exec('BEGIN');
  let bad = 0;
  for (const r of rows) {
    try { stmt.run(transformRow(r, dateCol, colMap)); }
    catch (e) { bad++; }
  }
  newDb.exec('COMMIT');
  stmt.free();
  newDb.exec('ANALYZE');

  if (bad > 0) console.warn(`${bad} 行写入失败（已跳过）`);
  return { newDb, fileName: file.name };
}

// 抽取 db 元信息（行数 / 年份分布 / 四个金额合计）
export function collectMeta(targetDb, fileName) {
  const totalRow = targetDb.exec('SELECT COUNT(*) AS c FROM fact_premium');
  const total = totalRow[0]?.values[0][0] || 0;
  const yearRows = targetDb.exec('SELECT year, COUNT(*) AS c FROM fact_premium GROUP BY year ORDER BY year');
  const byYear = {};
  if (yearRows[0]) yearRows[0].values.forEach(([y, c]) => { byYear[y] = c; });
  const sumRow = targetDb.exec(
    'SELECT SUM(qj_cents)/100.0, SUM(ghgb_cents)/100.0, SUM(zhsf_cents)/100.0, SUM(jzgb_cents)/100.0 FROM fact_premium'
  );
  const sums = sumRow[0]?.values[0] || [0, 0, 0, 0];
  return {
    importedAt: new Date().toISOString(),
    fileName,
    rowCount: total,
    byYear,
    sumQj: sums[0], sumGhgb: sums[1], sumZhsf: sums[2], sumJzgb: sums[3]
  };
}
