const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=process.argv[2] || process.cwd();
function read(name){return fs.readFileSync(path.join(root,name),'utf8');}
const out=[];function log(v){out.push(JSON.stringify(v));console.log(JSON.stringify(v));}
function orgRepro(withStreak){
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',style:{},dataset:{},hidden:false,setAttribute(){},addEventListener(){},classList:{add(){},remove(){}}});return elements.get(id);};
 const payload={year:2026,perf:{'上海|OTO':{qj_premium:50}},perf_prev:{},value:{},value_prev:{},longterm:{}};
 if(withStreak)payload.zeroStreak={year:{cutoff:'2026-08-31',projects:{'上海|证保':{days:8,status:'ok'}},orgs:{}}};
 const context=vm.createContext({window:{},document:{readyState:'loading',addEventListener(){},getElementById:element,querySelectorAll:()=>[],querySelector:()=>null},targetData:{orgTargets:{'上海|OTO':{qjPremium:{year:100}},'上海|证保':{qjPremium:{year:100}}}},selectedYear:2026,DEFAULT_DASHBOARD_YEAR:2026,getLatestMonthForYear:()=>8,MonthMultiSelect:{normalizeMonths:m=>m,defaultMonths:()=>[8],render:(_,o)=>o.selectedMonths},console,payload});
 vm.runInContext(read('js/org-analysis.js'),context);vm.runInContext("orgKpiData=payload;selectedOrgs=['上海'];renderOrgTable()",context);
 const tbody=element('orgTableWrapper').innerHTML.match(/<tbody>([\s\S]*?)<\/tbody>/)[1];
 const rows=Array.from(tbody.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g),m=>Array.from(m[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g),c=>c[1].trim()));
 const total=rows.at(-1),org=rows.find(r=>r[0]==='上海');
 assert.equal(total[1],'100');assert.equal(total[2],'50');assert.equal(total[3],'50.0%');
 log({test:'zero_actual_target_omission',withStreak,syntheticInputs:{A:{target:100,actual:50},B:{target:100,actual:0,previousActual:0}},expected:{target:200,actual:50,rate:'25.0%'},observed:{totalTarget:total[1],totalActual:total[2],totalRate:total[3],organizationTarget:org[2],organizationRate:org[4]}});
}
async function raceRepro(kind){
 const pending=[];let selected='A';const c={console,unwrapApiResponse:x=>x,fetchJson:q=>new Promise(resolve=>pending.push({q,resolve})),apiData:{},payPeriodData:{},buildProductQuery:()=>selected,buildPayPeriodQuery:()=>selected,updateProductDataFromApi:()=>true,applyProductFallback:()=>false,applyPayPeriodFallback:()=>{},renderPayPeriodChart:()=>{}};
 vm.createContext(c);
 const source=read(kind==='product'?'js/data-integration.js':'js/payperiod-chart.js');
 const start=kind==='product'?'async function fetchProductData(':'async function fetchPayPeriodData(';
 const end=kind==='product'?'function createCheckboxLabel(':'function refreshPayPeriodChart(';
 vm.runInContext(source.slice(source.indexOf(start),source.indexOf(end)),c);
 const fn=kind==='product'?c.fetchProductData:c.fetchPayPeriodData;
 const a=fn(2026);selected='B';const b=fn(2026);
 pending[1].resolve({premium:[{name:'B',value:2}]});await b;pending[0].resolve({premium:[{name:'A',value:1}]});await a;
 const actual=kind==='product'?c.apiData.product.premium[0].name:c.payPeriodData.premium[0].name;
 assert.equal(actual,'A');log({test:kind+'_out_of_order_response',selected:'B',completionOrder:['B','A'],observedResult:actual});
}
(async()=>{orgRepro(false);orgRepro(true);await raceRepro('product');await raceRepro('payperiod');fs.writeFileSync(path.join(__dirname,'ui_repro.txt'),out.join('\n')+'\n','utf8');})().catch(e=>{console.error(e);process.exitCode=1;});
