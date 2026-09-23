const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const read = name => fs.readFileSync(`js/${name}.js`, 'utf8');
function extract(source, start, end) { return source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start))); }
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;});return {promise,resolve,reject}; }
function context(code, props) {const ctx=vm.createContext(props);vm.runInContext(code,ctx);return ctx;}
test('empty product organization selection is explicit and differs from all', () => {
 const c=context(extract(read('data-integration'),'    function buildProductQuery(', '    async function fetchAPIData('),{URLSearchParams,appendDashboardAsOf(){},productFilters:{transform:true,jingdai:false,transformLines:{OTO:true},jingdaiOrgs:{},orgs:{all:false,A:false},timeDim:'year'}});
 assert.equal(new URL(c.buildProductQuery(2026),'https://test').searchParams.get('orgs'),'__none__');
 c.productFilters.orgs={all:true,A:true};assert.equal(new URL(c.buildProductQuery(2026),'https://test').searchParams.has('orgs'),false);
 c.productFilters.orgs={all:false,A:true};assert.equal(new URL(c.buildProductQuery(2026),'https://test').searchParams.get('orgs'),'A');
});
test('missing product count remains unavailable instead of copying premium', () => {
 const code=extract(read('data-integration'),'    function updateProductDataFromApi()', '    let productRequestSequence =');
 const productData={};
 const c=context(code,{apiData:{product:{premium:[{name:'合成产品',value:12.5}],count:[],countBasis:'policy'}},productData,
   renderProductJingdaiOrgs(){},renderProductTopTable(){},selectedYear:2026,DEFAULT_DASHBOARD_YEAR:2026,applyProductFallback(){throw Error('unexpected fallback');}});
 assert.equal(c.updateProductDataFromApi(),true);
 assert.equal(productData.premium[0].value,12.5);
 assert.deepEqual(Array.from(productData.count),[]);
});
test('mixed policy and agency record counts do not form one pie', () => {
 const code=extract(read('product-analysis'),'    function getPieOption(type)', '    let currentPieType =');
 const productData={premium:[{name:'转型-产品',value:12},{name:'经代-产品',value:8}],count:[{name:'转型-产品',value:2},{name:'经代-产品',value:4}],countBasis:'mixed'};
 const c=context(code,{productData});
 assert.equal(c.getPieOption('premium').series.length,1);
 assert.equal(c.getPieOption('count').series.length,0);
 assert.match(c.getPieOption('count').title.text,/口径不同/);
});
for (const name of ['zhituo-analysis','branch-analysis','customer-analysis']) {
 test(`${name}: late success and late errors cannot overwrite newest query`, async () => {
  const source=read(name), isCustomer=name==='customer-analysis';
  const code=extract(source,isCustomer?'  async function loadOverview()':'  async function load(',isCustomer?'  async function loadCohort()':name==='zhituo-analysis'?'  async function applyFilters(':'  function bind()');
  const pending=[], errors=[], rendered=[];const nodes={};
  const c=context('let loadSequence=0;\n'+code,{URLSearchParams,state:{charts:{}},el:id=>nodes[id]||=( {value:'2026',classList:{remove(){}},textContent:''}),analysisQuery:()=>'',renderAliasCoverage(){},syncOptions(){},setOverviewContext(){},rebuildPeriodOptions(){},window:{fetchJson:()=>{const d=deferred();pending.push(d);return d.promise;},unwrapApiResponse:x=>x},showError:e=>errors.push(e.message),render(){if(c.state.data) rendered.push(c.state.data.id);}});
  const load=()=>isCustomer?c.loadOverview():c.load();
  const a=load(),b=load();pending[1].resolve({id:'new',meta:{year:2026}});await b;pending[0].resolve({id:'old',meta:{year:2025}});await a;assert.equal(c.state.data.id,'new');assert.deepEqual(rendered,['new']);
  const d=load(),e=load();pending[3].resolve({id:'newer',meta:{year:2026}});await e;pending[2].reject(Error('old failure'));await d;assert.deepEqual(errors,[]);
  const f=load();pending[4].reject(Error('current failure'));await f;assert.deepEqual(errors,['current failure']);
 });
}
function importer() {
 const file={name:'synthetic.csv',size:10,slice:(a,b)=>`${a}:${b}`};const input={files:[file]};const requests=[];const create=deferred();let fail=false, renders=0;
 const source=read('customer-analysis');
 const code=extract(source,'  async function previewImport()', '  async function downloadTemplate(');
 const c=context(code,{state:{tab:'import',importBusy:false,importFiles:[],importPreview:null},el:()=>input,window:{confirm:()=>true},integer:String,updateImportProgress(){},render(){renders++},loadImportBatches:async()=>{},waitImportJob:async()=>{c.state.importPreview={canImport:true,uploadId:'test',status:'ready'};return c.state.importPreview;},importRequest:async(path,opts)=>{requests.push({path,opts});if(fail)throw Error('network');if(path.endsWith('/uploads'))return create.promise;return {};}});
 return {c,input,requests,create,get renders(){return renders},setFail:v=>fail=v};
}
test('customer preview ignores duplicate click, keeps immutable files, and updates without full render',async()=>{
 const h=importer(),a=h.c.previewImport();h.input.files=[];await h.c.previewImport();h.c.state.importFiles=[];
 h.create.resolve({uploadId:'test',chunkBytes:8,totalBytes:10});await a;
 assert.equal(h.requests.filter(x=>x.path.endsWith('/uploads')).length,1);assert.equal(h.requests.filter(x=>x.path.includes('/chunks')).length,2);assert.equal(h.renders,0);assert.equal(h.c.state.importBusy,false);
});
test('customer preview failure unlocks and can retry selected files',async()=>{
 const h=importer();h.setFail(true);await assert.rejects(h.c.previewImport(),/network/);assert.equal(h.c.state.importBusy,false);
 h.setFail(false);h.create.resolve({uploadId:'test',chunkBytes:8,totalBytes:10});await h.c.previewImport();assert.equal(h.c.state.importPreview.canImport,true);
});
test('customer commit locks before network request and never reuses failed confirmation',async()=>{
 const h=importer();h.c.state.importFiles=[{}];h.c.state.importPreview={uploadId:'test',canImport:true};
 const wait=deferred();h.c.importRequest=()=>wait.promise;
 const first=h.c.commitImport();assert.equal(h.c.state.importBusy,true);await h.c.commitImport();wait.reject(Error('network'));await first;
 assert.equal(h.c.state.importBusy,false);assert.equal(h.c.state.importPreview.canImport,false);assert.match(h.c.state.importMessage,/待核实/);await assert.rejects(h.c.commitImport(),/预检/);
});
test('file selection change invalidates preview before confirmation',()=>{
 const source=read('customer-analysis');const code=extract(source,"    el('content').addEventListener('change'", "    el('content').addEventListener('click'");let handler;
 const c=context(code,{el:()=>({addEventListener:(kind,fn)=>handler=fn}),state:{importBusy:false,importFiles:[{}],importPreview:{canImport:true}},updateImportProgress(){}});
 handler({target:{id:'customerImportFiles'}});assert.equal(c.state.importPreview,null);assert.equal(c.state.importFiles.length,0);
});

test('cohort response and failure are ignored after tab invalidates the request',async()=>{
 const source=read('customer-analysis');const code=extract(source,'  async function loadCohort()', '  async function loadImportBatches()');
 const pending=[],errors=[];const c=context('let loadSequence=0;function leaveTab(){++loadSequence;}\n'+code,{URLSearchParams,state:{cohortData:null},el:()=>({value:'',textContent:''}),analysisQuery:()=>new URLSearchParams(),render(){},window:{fetchJson:()=>{const d=deferred();pending.push(d);return d.promise;},unwrapApiResponse:x=>x},syncCohortOptions(){},windowLabels:{},showError:e=>errors.push(e.message)});
 const a=c.loadCohort();c.leaveTab();pending[0].resolve({meta:{},summary:{}});await a;assert.equal(c.state.cohortData,null);
 const b=c.loadCohort();c.leaveTab();pending[1].reject(Error('old'));await b;assert.deepEqual(errors,[]);
});
test('progress preserves file control and does not change unrelated tabs',()=>{
 const code=extract(read('customer-analysis'),'  function updateImportProgress()', '  const delay =');
 const file={files:[{}]},nodes={customerImportFiles:file,customerImportMessage:{},customerImportSummary:{}};const buttons={};
 const c=context(code,{state:{tab:'import',importBusy:true,importFiles:[{}],importPreview:{canImport:true},importMessage:'50%'},el:id=>nodes[id],can:()=>true,renderImportSummary:()=>'<p>progress</p>',document:{querySelector:key=>buttons[key]||={}}});
 c.updateImportProgress();assert.equal(nodes.customerImportFiles,file);assert.equal(file.disabled,true);assert.equal(nodes.customerImportMessage.textContent,'50%');
 c.state.tab='overview';c.state.importMessage='100%';c.updateImportProgress();assert.equal(nodes.customerImportMessage.textContent,'50%');
});
