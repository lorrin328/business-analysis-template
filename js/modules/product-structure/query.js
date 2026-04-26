// 产品结构：SQL 查询层
//
// 仅负责构造并执行查询。返回的金额已经 / 100（元为单位），不含展示格式化。

import { buildWhere, metricCol } from '../../core/filters.js';
import { q } from '../../core/db.js';

// 按 design_cat 聚合当前选中金额指标。
// 返回：{ k: 设计分类, v: 金额（元） }[]
export function fetchStructure() {
  const { where, params } = buildWhere();
  const sql = `
    SELECT design_cat AS k, SUM(${metricCol()}) / 100.0 AS v
    FROM fact_premium
    ${where}
    GROUP BY design_cat
    ORDER BY v DESC`;
  return q(sql, params);
}
