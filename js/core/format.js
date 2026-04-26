// 数值显示格式化
//
// 规则：金额以「元」传入；超过 1 亿显示「X.XX 亿」，超过 1 万显示「X.XX 万」，否则保留 2 位小数。
// 与原 经营分析模板.html 793-805 行保持完全一致的表现。

export function formatNum(n) {
  if (n == null) return '-';
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万';
  return n.toFixed(2);
}

export function formatShort(n) {
  if (n == null) return '-';
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(1) + '亿';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(0) + '万';
  return n.toFixed(0);
}
