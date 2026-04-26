// 导入：单元格值转换与行级 transformRow
//
// 与原 经营分析模板.html 行 1008-1108 完全一致。
// 依赖：window.XLSX（CDN 全局；parseDateCell 需要 XLSX.SSF）

// 数字补零：1 → '01'
export function pad2(n) { return n < 10 ? '0' + n : '' + n; }

// 字符串/数字 → 整数（分）。空值返回 0
export function toCents(v) {
  if (v == null || v === '') return 0;
  const s = String(v).replace(/,/g, '').trim();
  const n = parseFloat(s);
  if (!isFinite(n)) return 0;
  return Math.round(n * 100);
}

// 维度字段：空、'nan'、'None' 都规范化为 '未知'
export function trimDim(v) {
  if (v == null) return '未知';
  const s = String(v).trim();
  if (!s || s === 'nan' || s === 'None') return '未知';
  return s;
}

// 字符串字段：空、'nan'、'None' 都规范化为 ''
export function trimEmpty(v) {
  if (v == null) return '';
  const s = String(v).trim();
  if (!s || s === 'nan' || s === 'None') return '';
  return s;
}

// 日期时间格式化为 'YYYY-MM-DD HH:MM:SS'；非 Date 时透传字符串
export function fmtDateTime(v) {
  if (v == null || v === '') return null;
  if (v instanceof Date && !isNaN(v)) {
    return `${v.getFullYear()}-${pad2(v.getMonth()+1)}-${pad2(v.getDate())} ${pad2(v.getHours())}:${pad2(v.getMinutes())}:${pad2(v.getSeconds())}`;
  }
  const s = String(v).trim();
  if (!s) return null;
  return s;
}

// 解析日期单元格 → { date: 'YYYY-MM-DD' | null, day: 数字 | null }
// 支持：Date、Excel 序列号（XLSX.SSF）、字符串
export function parseDateCell(v) {
  if (v == null || v === '') return { date: null, day: null };
  if (v instanceof Date && !isNaN(v)) {
    return { date: `${v.getFullYear()}-${pad2(v.getMonth() + 1)}-${pad2(v.getDate())}`, day: v.getDate() };
  }
  if (typeof v === 'number') {
    const d = XLSX.SSF.parse_date_code(v);
    if (d) return { date: `${d.y}-${pad2(d.m)}-${pad2(d.d)}`, day: d.d };
    return { date: null, day: null };
  }
  const s = String(v).trim();
  const m = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (m) {
    return { date: `${m[1]}-${pad2(+m[2])}-${pad2(+m[3])}`, day: +m[3] };
  }
  const dt = new Date(s);
  if (!isNaN(dt)) {
    return { date: `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}-${pad2(dt.getDate())}`, day: dt.getDate() };
  }
  return { date: null, day: null };
}

// 单行 → INSERT 参数数组（与 schema.INSERT_SQL 列顺序严格对应）
//   r:       原始行对象（key 为 Excel 实际列名）
//   dateCol: findDateColumn 的返回（可能为 null）
//   colMap:  标准列名 → 实际列名
export function transformRow(r, dateCol, colMap) {
  const get = (std) => {
    const key = colMap?.[std] || std;
    return r[key];
  };
  const dateInfo = dateCol ? parseDateCell(r[dateCol]) : { date: null, day: null };
  const year = (get('年') == null ? '' : String(get('年')).trim());

  // 月：支持整数或 Date（如 2024-01-01 表示 1 月）
  let monthRaw = get('月');
  let month = 0;
  if (monthRaw instanceof Date && !isNaN(monthRaw)) {
    month = monthRaw.getMonth() + 1;
  } else {
    month = parseInt(monthRaw, 10) || 0;
  }

  // 季：支持整数或字符串如 '2024-1'
  let quarterRaw = get('季');
  let quarter = 0;
  if (typeof quarterRaw === 'string' && quarterRaw.includes('-')) {
    const parts = quarterRaw.split('-');
    quarter = parseInt(parts[parts.length - 1], 10) || 0;
  } else {
    quarter = parseInt(quarterRaw, 10) || 0;
  }

  // 月标签：缺失时自动衍生
  let monthLabelRaw = get('月标签');
  let monthLabel = '';
  if (monthLabelRaw == null) {
    monthLabel = year && month ? `${year}年${month}月` : '';
  } else {
    monthLabel = String(monthLabelRaw).trim();
  }

  return [
    dateInfo.date, year, quarter, month, dateInfo.day, monthLabel,
    trimDim(get('销售机构名称')), trimDim(get('业务模式')), '未知',
    '未知', '未知', trimDim(get('长短险')),
    trimDim(get('是否商保年金产品')), trimDim(get('缴费年限')), trimDim(get('保障年限')),
    trimDim(get('产品设计分类')),
    trimEmpty(get('人员工号')), trimEmpty(get('主管工号')), trimEmpty(get('经理工号')),
    trimEmpty(get('投保单号')), trimEmpty(get('自保件标记')),
    fmtDateTime(get('投保时间')), fmtDateTime(get('承保时间')),
    fmtDateTime(get('入账时间')), fmtDateTime(get('回销时间')),
    trimEmpty(get('产品代码')), trimEmpty(get('产品名称')), trimEmpty(get('是否个人养老金')),
    toCents(get('期交保费')), toCents(get('年化规保')), toCents(get('折算保费')), toCents(get('价值规保'))
  ];
}
