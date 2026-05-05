// 目标数据导入模块
//
// parseAndBuildTarget(file, db) — 读取目标 Excel → 校验列名 → 写入 fact_target 表
// 支持自动匹配列名（中文/英文别名），多指标列同时导入。

export const TARGET_SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS fact_target (
    id INTEGER PRIMARY KEY,
    year TEXT NOT NULL,
    quarter INTEGER,
    month INTEGER,
    week INTEGER,
    org TEXT,
    project TEXT,
    metric TEXT NOT NULL,
    target_value REAL NOT NULL DEFAULT 0
  );
  CREATE INDEX IF NOT EXISTS ix_target_ym ON fact_target(year, month);
  CREATE INDEX IF NOT EXISTS ix_target_yq ON fact_target(year, quarter);
  CREATE INDEX IF NOT EXISTS ix_target_org ON fact_target(org);
`;

export async function parseAndBuildTarget(file, db) {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: 'array', cellDates: true });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  if (!sheet) throw new Error('Excel 文件为空');
  const rows = XLSX.utils.sheet_to_json(sheet, { defval: null, raw: true });
  if (!rows.length) throw new Error('没有数据行');

  const cols = Object.keys(rows[0]);

  const findCol = (names) => {
    for (const n of names) {
      const exact = cols.find(c => c === n);
      if (exact) return exact;
      const partial = cols.find(c => c.includes(n));
      if (partial) return partial;
    }
    return null;
  };

  const colMap = {};
  colMap.year = findCol(['年', '年份', '年度']);
  colMap.quarter = findCol(['季', '季度']);
  colMap.month = findCol(['月', '月份']);
  colMap.week = findCol(['周', '星期']);
  colMap.org = findCol(['机构', '销售机构', '销售机构名称', 'org']);
  colMap.project = findCol(['项目', '产品', '产品设计分类', 'project']);

  const metricCols = [];
  for (const c of cols) {
    const lc = String(c).toLowerCase();
    if (lc.includes('折算') && lc.includes('目标')) metricCols.push({ col: c, metric: '折算保费' });
    else if (lc.includes('期交') && lc.includes('目标')) metricCols.push({ col: c, metric: '期交保费' });
    else if ((lc.includes('规模') || lc.includes('年化') || lc.includes('规保')) && lc.includes('目标')) metricCols.push({ col: c, metric: '规模保费' });
    else if (c === '折算保费目标') metricCols.push({ col: c, metric: '折算保费' });
    else if (c === '期交保费目标') metricCols.push({ col: c, metric: '期交保费' });
    else if (c === '规模保费目标') metricCols.push({ col: c, metric: '规模保费' });
  }

  if (!colMap.year) throw new Error('目标文件缺少"年"列');
  if (metricCols.length === 0) throw new Error('目标文件缺少指标列（如"折算保费目标"）');

  // Ensure target table exists
  db.exec(TARGET_SCHEMA_SQL);

  // Clear existing targets for the years in this file
  const yearsInFile = new Set(rows.map(r => String(r[colMap.year] || '').trim()).filter(y => y));
  if (yearsInFile.size > 0) {
    const yearList = [...yearsInFile].map(y => `'${y}'`).join(',');
    db.exec(`DELETE FROM fact_target WHERE year IN (${yearList})`);
  }

  const insertStmt = db.prepare(`INSERT INTO fact_target (year, quarter, month, week, org, project, metric, target_value) VALUES (?,?,?,?,?,?,?,?)`);
  db.exec('BEGIN');
  let inserted = 0;
  for (const r of rows) {
    const year = String(r[colMap.year] || '').trim();
    if (!year) continue;
    const quarter = parseInt(r[colMap.quarter], 10) || null;
    const month = parseInt(r[colMap.month], 10) || null;
    const week = parseInt(r[colMap.week], 10) || null;
    const org = trimEmpty(r[colMap.org]);
    const project = trimEmpty(r[colMap.project]);

    for (const mc of metricCols) {
      const val = parseFloat(r[mc.col]);
      if (!isFinite(val) || val === 0) continue;
      insertStmt.run([year, quarter, month, week, org, project, mc.metric, val]);
      inserted++;
    }
  }
  db.exec('COMMIT');
  insertStmt.free();

  console.log(`✅ 目标数据导入: ${inserted} 条记录`);
  return { inserted };
}

function trimEmpty(v) {
  if (v == null) return '';
  const s = String(v).trim();
  if (!s || s === 'nan' || s === 'None') return '';
  return s;
}
