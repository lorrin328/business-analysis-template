// 导入：列名常量与 SQL schema
//
// 与原 经营分析模板.html 行 903-961 完全一致；为后续模块共享，集中导出。
// 修改任何字段或别名都会影响全部数据导入路径。

// 必需的时间维度列
export const REQUIRED_TIME_COLS = ['年', '月', '季'];

// 日期列候选——按优先级匹配；未匹配到也允许（仅日明细浮层不可用）
export const DATE_COL_CANDIDATES = ['日期', '投保日期', '签单日期', '成交日期', '年月日'];

// 核心维度（新表必需）
export const CORE_DIM_COLS = [
  '销售机构名称', '业务模式', '长短险', '是否商保年金产品',
  '缴费年限', '保障年限', '产品设计分类'
];

// 扩展维度（新表特有，入库备用）
export const EXT_DIM_COLS = [
  '人员工号', '主管工号', '经理工号', '投保单号', '自保件标记',
  '投保时间', '承保时间', '入账时间', '回销时间',
  '产品代码', '产品名称', '是否个人养老金'
];

export const ALL_DIM_COLS = [...CORE_DIM_COLS, ...EXT_DIM_COLS];

// 金额指标列名
export const METRIC_COLS_ZH = ['期交保费', '年化规保', '折算保费', '价值规保'];

// 列名别名（容错：标准列 → 实际可接受的列名）
export const COL_ALIASES = {
  '月': ['年月'],
  '季': ['年季'],
  '日期': ['年月日']
};

// fact_premium 表 schema（含索引）
export const SCHEMA_SQL = `
  CREATE TABLE fact_premium (
    id INTEGER PRIMARY KEY,
    date TEXT, year TEXT NOT NULL, quarter INTEGER NOT NULL, month INTEGER NOT NULL,
    day INTEGER, month_label TEXT NOT NULL,
    org TEXT, biz_mode TEXT, is_operating TEXT, is_dividend TEXT, innovate TEXT,
    term_type TEXT, is_annuity TEXT, pay_years TEXT, cov_years TEXT, design_cat TEXT,
    staff_id TEXT, supervisor_id TEXT, manager_id TEXT, policy_no TEXT, self_mark TEXT,
    app_date TEXT, underwrite_date TEXT, entry_date TEXT, cancel_date TEXT,
    product_code TEXT, product_name TEXT, is_pension TEXT,
    qj_cents INTEGER NOT NULL DEFAULT 0,
    ghgb_cents INTEGER NOT NULL DEFAULT 0,
    zhsf_cents INTEGER NOT NULL DEFAULT 0,
    jzgb_cents INTEGER NOT NULL DEFAULT 0
  );
  CREATE INDEX ix_ym   ON fact_premium(year, month);
  CREATE INDEX ix_yq   ON fact_premium(year, quarter);
  CREATE INDEX ix_ymd  ON fact_premium(year, month, day);
  CREATE INDEX ix_org  ON fact_premium(org);
  CREATE INDEX ix_mode ON fact_premium(biz_mode);
  CREATE INDEX ix_dsg  ON fact_premium(design_cat);
`;

// 全字段 INSERT（与 transformRow 返回数组的顺序严格对应）
export const INSERT_SQL = `INSERT INTO fact_premium
  (date, year, quarter, month, day, month_label, org, biz_mode, is_operating,
   is_dividend, innovate, term_type, is_annuity, pay_years, cov_years, design_cat,
   staff_id, supervisor_id, manager_id, policy_no, self_mark,
   app_date, underwrite_date, entry_date, cancel_date,
   product_code, product_name, is_pension,
   qj_cents, ghgb_cents, zhsf_cents, jzgb_cents)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`;
