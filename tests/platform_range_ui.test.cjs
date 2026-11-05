const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const read = name => fs.readFileSync(`js/${name}.js`, 'utf8');
const extract = (text, start, end) => text.slice(text.indexOf(start), text.indexOf(end, text.indexOf(start)));
function harness(range) {
  const c = vm.createContext({ console, URLSearchParams, setTimeout, clearTimeout,
    getDashboardRange: () => range,
    document: {getElementById: () => null}, echarts: {init: () => ({setOption(){},clear(){}})},
    DEFAULT_DASHBOARD_YEAR:2026, months:Array.from({length:12},(_,i)=>`${i+1}月`),
    platformMock:{}, apiCache:{}, dashboardCacheKey:y=>String(y),
    fetchJson:async()=>({}), unwrapApiResponse:x=>x });
  c.window=c;
  vm.runInContext(read('platform-trend'),c);
  const source=read('platform-trend-main');
  vm.runInContext(source.slice(0,source.indexOf('    if (!window.ALLOW_LOCAL_FALLBACK)'))
    +source.slice(source.indexOf('    // 根据机构筛选获取某渠道某月的数值')),c);
  vm.runInContext(extract(read('data-integration'),'    function convertApiToPlatformMock(', '    function mergeProductRows('),c);
  return c;
}
test('annual plot uses selected period, preserves negative/zero months and same-date prior',()=>{
 const c=harness({startDate:'2026-05-20',endDate:'2026-06-10'});
 c.input={rangeApplied:true,period:{startCutoff:{month:5,day:20},endCutoff:{month:6,day:10}},
   performance:[{month:5,channel:'OTO',qj_premium:20,gm_premium:40,zs_premium:10},
    {month:6,channel:'OTO',qj_premium:-5,gm_premium:-10,zs_premium:-2.5}]};
 vm.runInContext(`Object.assign(platformMock,convertApiToPlatformMock(input,2026),convertApiToPlatformMock(input,2025));
 Object.keys(selectedSeries).forEach(key=>selectedSeries[key]=key==='OTO');`,c);
 const option=c.getPlatformOption();
 assert.deepEqual(Array.from(option.xAxis.data),['5月','6月']);
 assert.deepEqual(Array.from(option.series[0].data),[20,15]);
 assert.deepEqual(Array.from(option.series[1].data),[20,15]);
 assert.deepEqual(Array.from(option.series[2].data),[20,-5]);
 c.input.performance[1].qj_premium=0;
 vm.runInContext(`Object.assign(platformMock,convertApiToPlatformMock(input,2026));`,c);
 assert.deepEqual(Array.from(c.getPlatformOption().series[0].data),[20,20]);
});
test('daily curve and sales-platform filter exclude both sides of custom range',()=>{
 const c=harness({startDate:'2026-06-05',endDate:'2026-06-10'});
 vm.runInContext(`selectedJingdaiPlatforms=['甲'];
 jingdaiPlatformCache[2026]={daily:[
 {platform:'甲',month:6,day:4,qj_premium:999},
 {platform:'甲',month:6,day:5,qj_premium:10},
 {platform:'甲',month:6,day:10,qj_premium:-2},
 {platform:'甲',month:6,day:11,qj_premium:999}]};
 platformMock[2026]={year:{qj:{'经代':Array(12).fill(0)}}};`,c);
 assert.equal(c.getChannelValue(2026,'qj','经代',5),8);
 vm.runInContext(`Object.keys(selectedSeries).forEach(key=>selectedSeries[key]=key==='经代');`,c);
 const curve=c.getSelectedMonthSetTrendData(2026,[6]);
 assert.deepEqual(Array.from(curve.labels),Array.from({length:6},(_,i)=>`6月${i+5}日`));
 assert.deepEqual(Array.from(curve.values),[10,10,10,10,10,8]);
});
test('all organizations unchecked never revives national transform total',()=>{
 const c=harness({startDate:'2026-01-01',endDate:'2026-06-10'});
 vm.runInContext(`Object.keys(selectedPlatformOrgs).forEach(org=>selectedPlatformOrgs[org]=false);
 platformMock[2026]={year:{qj:{OTO:[100]}}};`,c);
 assert.equal(c.hasPlatformOrgFilter(),true);
 assert.equal(c.getChannelValue(2026,'qj','OTO',0),null);
});
test('comparison mapping clamps leap day and aligns daily values by date label',()=>{
 const c=harness({startDate:'2024-02-28',endDate:'2024-03-01'});
 assert.equal(c.platformDateInRange(2023,2,28),true);
 assert.equal(c.platformDateInRange(2023,3,2),false);
 vm.runInContext(`selectedYear=2024; selectedSeries['经代']=false;
 platformMock[2023]={};
 getSelectedMonthSetTrendData=(year)=>year===2024
 ? {labels:['2月28日','2月29日','3月1日'],values:[1,2,3]}
 : {labels:['2月28日','3月1日'],values:[10,30]};`,c);
 const option=c.buildDailyTrendOption([2,3],'当年','上年','空');
 assert.deepEqual(Array.from(option.series[1].data),[10,'-',30]);
});
test('unknown premium does not become a partial mixed-source total',()=>{
 const c=harness({startDate:'2026-06-01',endDate:'2026-06-10'});
 c.input={rangeApplied:true,performance:[{month:6,channel:'OTO',qj_premium:null,gm_premium:null,zs_premium:null}],
 jingdai:[{month:6,qj_premium:10,gm_premium:10,zs_premium:5}]};
 vm.runInContext(`Object.assign(platformMock,convertApiToPlatformMock(input,2026));
 Object.keys(selectedSeries).forEach(key=>selectedSeries[key]=['OTO','经代'].includes(key));`,c);
 assert.deepEqual(Array.from(c.getPlatformOption().series[0].data),['-']);
});
test('zero-premium valid product result retains independent nonzero policy counts',()=>{
 const c=vm.createContext({apiData:{product:{premium:[],count:[{name:'产品',value:2}],countBasis:'policy',topProducts:[]}},
 productData:{},renderProductJingdaiOrgs(){},updateProductAppliedScope(){},renderProductTopTable(){},
 applyProductFallback(){throw Error('valid empty result must not fall back');}});
 vm.runInContext(extract(read('data-integration'),'    function updateProductDataFromApi()', '    let productRequestSequence'),c);
 assert.equal(c.updateProductDataFromApi(),true);
 assert.equal(c.productData.count[0].value,2);
});
test('an obsolete failed range request cannot erase the newer successful chart',async()=>{
 let finish;
 const c=vm.createContext({dashboardLoadGeneration:0,selectedYear:2026,apiCache:{},platformMock:{2026:{newest:true},2025:{newest:true}},
   dashboardCacheKey:y=>String(y),fetchAPIData:()=>new Promise(resolve=>{finish=resolve;}),
   clearRuntimeFallbackYear(){throw Error('obsolete request must not change visible status');}});
 vm.runInContext(extract(read('platform-trend-main'),'    async function loadYearFromApi(', '    async function switchYear('),c);
 const old=c.loadYearFromApi(2026);
 c.dashboardLoadGeneration++;
 finish(false);
 assert.equal(await old,false);
 assert.equal(c.platformMock[2026].newest,true);
 assert.equal(c.platformMock[2025].newest,true);
});
test('team-only year loading cannot change the dashboard period or KPI context',async()=>{
 const requests=[];
 const c=vm.createContext({dashboardLoadGeneration:0,selectedYear:2026,productRequestSequence:0,
   dashboardCacheKey:y=>String(y),apiCache:{},apiData:{kpi:'current'},
   dashboardAsOfQuery:()=> '&rangeType=day&endDate=2026-06-10',buildProductQuery:y=>`/api/product-analysis?year=${y}`,
   syncDashboardAsOf(){throw Error('team must not normalize the dashboard period');},
   unwrapApiResponse:x=>x,fetchJson:async url=>{requests.push(url);return {};},setDataSourceStatus(){}});
 vm.runInContext(extract(read('data-integration'),'    async function fetchAPIData(', '    function getLatestMonthForYear('),c);
 assert.equal(await c.fetchAPIData(2025,{updateKpi:false}),true);
 assert.equal(c.apiData.kpi,'current');
 assert.ok(requests.includes('/api/platform-data?year=2025'));
 assert.ok(requests.includes('/api/platform-data?year=2025&rangeType=day&endDate=2026-06-10'));
});
test('daily fallback never fills past the comparison year actual data coverage',()=>{
 const c=harness({startDate:'2026-06-01',endDate:'2026-06-10'});
 c.getPlatformTrendPeriod=year=>year===2025 ? {startDate:'2025-06-01',endDate:'2025-06-05'} : null;
 assert.equal(c.dailyDisplayEndDay(2025,6),5);
 assert.equal(c.dailyDisplayEndDay(2026,6),10);
 assert.equal(c.platformDateInRange(2025,6,6),false);
});
