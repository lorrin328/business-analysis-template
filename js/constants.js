// constants.js — 全局常量，所有模块共享
(function (window) {
  const C = {
    ORG_LIST: ['上海', '湖北', '四川', '辽宁', '山东', '广东', '福建', '浙江', '河南', '北京'],
    CHANNEL_LIST: ['OTO', '证保', '蚁桥'],
    MONTHS: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
    MONTH_LABELS: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
    QUARTER_LABELS: ['Q1', 'Q2', 'Q3', 'Q4'],
    QUARTER_MONTHS: { 1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12] },

    DEFAULT_YEAR: 2026,
    DEFAULT_MONTH: 4,
    DEFAULT_QUARTER: 2,

    PREMIUM_TYPES: { qj: '期交保费', gm: '规模保费', zs: '折算保费' },

    SERIES_COLORS: {
      '经代': '#8b5cf6',
      'OTO': '#3b82f6',
      '证保': '#10b981',
      '蚁桥': '#f59e0b',
    },

    METRIC_NAMES: {
      headcount: '在职人力',
      activity: '活动率',
      perCapitaPremium: '人均保费',
      perCapitaCapacity: '人均产能',
    },
    METRIC_UNITS: {
      headcount: '人',
      activity: '%',
      perCapitaPremium: '万元',
      perCapitaCapacity: '万元',
    },

    TARGET_STORAGE_KEY: 'business_targets_v1',

    MONTHLY_FACTORS: [0.07, 0.07, 0.08, 0.08, 0.09, 0.09, 0.08, 0.08, 0.09, 0.09, 0.09, 0.09],
    QUARTERLY_FACTORS: [0.22, 0.25, 0.26, 0.27],
  };

  window.CONSTANTS = C;
})(window);
