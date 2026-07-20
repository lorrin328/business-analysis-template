// seed-data.js - empty runtime containers; production data must come from authenticated APIs.
const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

const productData = {
  premium: [],
  count: []
};

const productFilters = {
  transform: true,
  jingdai: true,
  transformLines: { OTO: true, '证保': true, '蚁桥': true },
  jingdaiOrgs: {},
  orgsInitialized: false
};

const productFallbackData = {};
const teamMock = {};
