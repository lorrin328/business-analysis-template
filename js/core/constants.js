// 应用常量
//
// 业务无关的字面量集中在此。修改任何一项需评估对所有模块的影响。

// 基准年：年度对比（YoY、KPI 卡片、趋势图色阶）所锚定的「当前年」
// 跟随系统时间自动滚动，跨年无需手工维护
export const BASE_YEAR = String(new Date().getFullYear());

export const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

export const QUARTER_LABELS = ['Q1', 'Q2', 'Q3', 'Q4'];

// 顶部筛选器：UI 标签 ↔ DOM id ↔ 数据库列
export const FILTER_KEYS = [
  { key: '销售机构名称',     sel: 'selOrg',     col: 'org' },
  { key: '业务模式',         sel: 'selMode',    col: 'biz_mode' },
  { key: '长短险',           sel: 'selTerm',    col: 'term_type' },
  { key: '是否商保年金产品', sel: 'selAnnuity', col: 'is_annuity' },
  { key: '缴费年限',         sel: 'selPayYear', col: 'pay_years' },
  { key: '保障年限',         sel: 'selCovYear', col: 'cov_years' },
  { key: '产品设计分类',     sel: 'selDesign',  col: 'design_cat' }
];

// 主图金额指标：UI 名称 ↔ 数据库列
export const METRIC_MAP = {
  '折算保费': 'zhsf_cents',
  '期交保费': 'qj_cents',
  '年化规保': 'ghgb_cents'
};

// 视图维度切换：state.view 值 ↔ 分组列
export const VIEW_DIM_COL = {
  org:  'org',
  mode: 'biz_mode'
};
