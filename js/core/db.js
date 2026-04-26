// SQLite 数据库句柄与查询包装
//
// 本模块管理 sql.js（SQL.Database 实例）的引用，并提供薄包装供其它模块调用。
// 设计上不关心 db 是从何创建（来自 IndexedDB 缓存反序列化、或从 Excel 现场构建）；
// 只要 bootstrap 调用 setDb() 注入即可。

let _db = null;

export function setDb(db) {
  _db = db;
}

export function getDb() {
  return _db;
}

export function isReady() {
  return _db !== null;
}

// 执行一条 SQL，返回所有行（getAsObject 形式）
export function q(sql, params) {
  if (!_db) {
    throw new Error('数据库未就绪：请先调用 setDb()');
  }
  const stmt = _db.prepare(sql);
  if (params) stmt.bind(params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

// 一次性执行多条 SQL（如 schema 创建）
export function exec(sql) {
  if (!_db) {
    throw new Error('数据库未就绪：请先调用 setDb()');
  }
  return _db.exec(sql);
}

// 导出当前 db 的二进制快照（用于 IndexedDB 持久化）
export function exportSnapshot() {
  if (!_db) {
    throw new Error('数据库未就绪：请先调用 setDb()');
  }
  return _db.export();
}
