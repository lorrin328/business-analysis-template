// 平台趋势：SQL 查询层
//
// aggregate()  按当前 state.view + state.gran 聚合 fact_premium，
//              产出 periodMap（含 cumulative 累计值），供 view-* 渲染。
// queryDaily() 单期间日明细，供 daily-tip 浮层。

import { VIEW_DIM_COL } from '../../core/constants.js';
import { state } from '../../core/state.js';
import { q } from '../../core/db.js';
import { buildWhere, metricCol } from '../../core/filters.js';

// 按 state.view + state.gran 聚合：返回 periodMap
//   形状：{ "<year>||<dimKey>": { year, dimKey, dimLabel, periods, cumulative } }
//   periods   { 1..N: amount }
//   cumulative[1..N]   累计金额（元）
export function aggregate() {
  const view = state.view;
  const gran = state.gran;
  const periodCol = gran === 'quarter' ? 'quarter' : 'month';
  const dimCol = VIEW_DIM_COL[view] || null;
  const mc = metricCol();

  const { where, params } = buildWhere();
  const dimSelect = dimCol ? `, ${dimCol} AS dim_key` : `, '' AS dim_key`;
  const groupBy = dimCol ? `year, ${periodCol}, ${dimCol}` : `year, ${periodCol}`;

  const sql = `
    SELECT year, ${periodCol} AS period${dimSelect},
           SUM(${mc}) / 100.0 AS amount
    FROM fact_premium
    ${where}
    GROUP BY ${groupBy}
    ORDER BY year, period`;

  const rows = q(sql, params);

  const periodMap = {};
  rows.forEach(r => {
    const dimKey = r.dim_key || '';
    const gkey = r.year + '||' + dimKey;
    if (!periodMap[gkey]) periodMap[gkey] = { year: r.year, dimKey, dimLabel: dimKey, periods: {} };
    periodMap[gkey].periods[r.period] = r.amount;
  });

  const maxPeriods = gran === 'quarter' ? 4 : 12;
  Object.values(periodMap).forEach(g => {
    g.cumulative = [];
    let cum = 0;
    for (let i = 1; i <= maxPeriods; i++) {
      cum += (g.periods[i] || 0);
      g.cumulative[i] = cum;
    }
  });

  return periodMap;
}

// 单一年份 + 单一期间的日明细
export function queryDaily(year, period) {
  const periodWhereCol = state.gran === 'quarter' ? 'quarter' : 'month';
  const { where, params } = buildWhere(
    [`year = $y`, `${periodWhereCol} = $p`, `day IS NOT NULL`],
    { $y: year, $p: period }
  );
  const sql = `
    SELECT day, SUM(${metricCol()}) / 100.0 AS amount
    FROM fact_premium
    ${where}
    GROUP BY day
    ORDER BY day`;
  return q(sql, params);
}
