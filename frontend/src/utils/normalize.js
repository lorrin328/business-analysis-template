export function normalizeMonth(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  if (number >= 1 && number <= 12) return number;
  const text = String(value).trim();
  if (/^\d{6,8}$/.test(text)) {
    const month = Number(text.slice(4, 6));
    return month >= 1 && month <= 12 ? month : null;
  }
  return null;
}

export function safeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
