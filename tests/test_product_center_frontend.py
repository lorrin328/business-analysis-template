"""Shell/asset checks plus executable browser-state security regressions."""
from pathlib import Path
import re
import shutil
import subprocess

from fastapi.testclient import TestClient

from main import app

ROOT = Path(__file__).resolve().parents[1]


def test_shell_and_every_declared_local_asset_are_served_without_business_data():
    client = TestClient(app)
    shell = client.get("/product-center")
    assert shell.status_code == 200
    assert "no-store" in shell.headers["cache-control"]
    assert "管理员登录" in shell.text
    assert re.search(r'<main[^>]+id="workspace"[^>]+hidden', shell.text)
    assert 'data-stage="formal"' in shell.text
    assert "开发稿，不代表已批准或在售" in shell.text
    assert "合成产品" not in shell.text
    paths = re.findall(r'(?:src|href)="(/(?:js|css)/[^"?#]+)', shell.text)
    assert "/js/api-client.js" in paths
    assert "/js/product-center.js" in paths
    assert "/css/product-center.css" in paths
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content, path


def test_page_is_in_the_docker_source_allowlist():
    rules = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "!product-center.html" in rules
    assert "**" in rules
    assert "**/*.db*" in rules
    assert "**/.env*" in rules


# A deliberately small DOM adapter executes the production script without
# exporting private implementation functions or adding a test hook to the app.
HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const mode = process.argv[2];
const roots = new Map();
class Element {
  constructor(tag='div') {
    this.tagName=tag.toUpperCase(); this.children=[]; this.events={}; this.dataset={};
    this.hidden=false; this.value=''; this.open=false; this.files=[]; this.className='';
    this.classList={toggle(){}}; this._text='';
  }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(x=>x.textContent || '').join(''); }
  set innerHTML(_) { throw new Error('Untrusted markup must not enter innerHTML'); }
  get firstChild() { return this.children[0]; }
  get options() { return this.children; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text=''; this.children=[...nodes]; }
  add(node) { this.append(node); if(this.children.length===1) this.value=node.value; }
  addEventListener(name,fn) { (this.events[name] ||= []).push(fn); }
  setAttribute(name,value) { this[name]=value; }
  removeAttribute(name) { delete this[name]; }
  showModal() { this.open=true; }
  close() { this.open=false; for(const fn of this.events.close||[]) fn({}); }
  reset() { this.value=''; }
  async fire(name, event={}) { for(const fn of this.events[name]||[]) await fn({preventDefault(){},...event}); }
}
function walk(node) { return [node,...node.children.flatMap(walk)]; }
function all() { return [...roots.values()].flatMap(walk); }
const get = id => all().find(node=>node.id===id) || (()=>{const node=new Element();node.id=id;roots.set(id,node);return node;})();
const formal=new Element('button');formal.dataset.stage='formal';
const draft=new Element('button');draft.dataset.stage='development';
const document={getElementById:get,createElement:tag=>new Element(tag),querySelectorAll(selector){
  if(selector==='[data-stage]') return [formal,draft];
  if(selector==='[data-compare-id]') return all().filter(x=>x.dataset.compareId);
  if(selector==='.product-card') return all().filter(x=>x.className.includes('product-card'));
  return [];
}};
const injection='<img src=x onerror="globalThis.injected=true">';
const product={id:'v1',name:injection,code:'SYNTHETIC',channel:'OTO',stage:'formal',
  insurer:'合成测试公司',revision:'测试',identityStatus:'confirmed',saleStatus:'unknown',sourceIds:['s1']};
const source={id:'s1',filename:injection+'.pdf',mediaType:'application/pdf',locator:'第1页'};
let token='synthetic-session'; const calls=[]; const revoked=[]; let resolver;
const response=data=>({ok:true,status:200,json:async()=>({success:true,data}),
  headers:{get:()=> 'application/pdf'},blob:async()=>new Blob(['%PDF-1.4 synthetic'])});
const authFetch=async url=>{
  calls.push(url); assert(!url.includes(token) && !/[?&](token|authorization)=/i.test(url));
  if(url==='/api/auth/me') return response({username:'synthetic',role:mode==='nonadmin'?'senior':'admin'});
  if(url.endsWith('/imports/preview')) return response({batch:{id:'synthetic-batch',status:'preview'},
    report:{counts:{versions:27,facts:339,sources:70,scenarios:790,guarantee:527,pendingIrr:16},
      coverage:{passed:true,baselineCount:165,indexCount:159,baselineHashVerifiedCount:165},
      arithmetic:{passed:true,numericCount:774,passedCount:774,failureCount:0,pendingCount:16,
        maxIrrDifference:1e-10,irrTolerance:1e-8,maxNpvResidual:1e-6,npvToleranceYuan:0.01,
        rows:Array.from({length:774},(_,i)=>({id:'SUCCESS-ROW-SENTINEL-'+i,passed:true,computedIrr:0.05}))}},
    diff:{addedVersions:27,removedVersions:0,retainedVersions:0},
    gaps:[{type:'identity',message:'合成身份待核提示'}]});
  if(url.endsWith('/imports')) return response({items:[]});
  if(url.includes('/sources/s1/text?page=')) {
    const page=Number(url.split('page=')[1]);
    const payload={source,page,pageCount:2,text:'分页原文 '+page+' '+injection};
    if(mode==='pdflate') return new Promise(resolve=>{resolver=()=>resolve(response(payload));});
    return response(payload);
  }
  if(url.includes('/sources/')) return response({});
  if(url.includes('/scenarios?')) return response({items:[]});
  if(url.includes('/products/v1')) return response({product,sources:[source],facts:[
    {dimension:'利益水平',label:'利益事实',text:'有来源的合成利益分支',sourceIds:['s1'],status:'已确认'}]});
  if(url.includes('/products?')) {
    if(mode==='stale') return new Promise(resolve=>{resolver=()=>resolve(response({items:[product],total:1,facets:{}}));});
    return response({items:[product],total:1,facets:{channels:['OTO']}});
  }
  throw new Error('Unexpected endpoint '+url);
};
const window={authFetch,apiUrl:path=>path,getAuthToken:()=>token,
  clearAuthSession:()=>{token='';},setAuthSession:(t)=>{token=t;},
  unwrapApiResponse:p=>p.data,events:{},addEventListener(name,fn){this.events[name]=fn;},confirm:()=>true};
const context={window,document,URLSearchParams,Blob,FormData,
  URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL:url=>revoked.push(url)},
  Option:function(text,value){const node=new Element('option');node.textContent=text;node.value=value;return node;},
  fetch:async()=>response({}),console,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'), context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick(); await tick();
  if(mode==='nonadmin') {
    assert.equal(get('workspace').hidden,true);
    assert(!calls.some(url=>url.startsWith('/api/product-center')));
    return;
  }
  assert(calls.some(url=>url.includes('/products?') && url.includes('stage=formal')));
  if(mode==='previewreport') {
    const file=new Blob(['synthetic import']);Object.defineProperty(file,'name',{value:'synthetic.zip'});
    get('packageFile').files=[file];await get('uploadForm').fire('submit');await tick();
    const content=get('previewPanel').textContent;
    assert(content.includes('独立复算 774 条'));
    assert(content.includes('通过 774 条'));
    assert(content.includes('分类基线 165 份'));
    assert(content.includes('合成身份待核提示'));
    assert(!content.includes('SUCCESS-ROW-SENTINEL'));
    for(const rawKey of ['numericCount','computedIrr','maxIrrDifference','baselineHashVerifiedCount']) assert(!content.includes(rawKey));
    assert(all().filter(node=>node.tagName==='DETAILS').every(node=>node.open===false));
    return;
  }
  if(mode==='stale') {
    await get('logout').fire('click'); resolver(); await tick(); await tick();
    assert.equal(get('workspace').hidden,true);
    assert.equal(get('productList').children.length,0);
    return;
  }
  const productButton=all().find(node=>node.tagName==='BUTTON'&&node.textContent===injection);
  assert(productButton, 'Product names render as inert text');
  await productButton.fire('click'); await tick(); await tick();
  assert(get('productDetail').textContent.includes('有来源的合成利益分支'));
  assert(get('productDetail').textContent.includes('当前可售待核'));
  const sourceButton=all().find(node=>node.tagName==='BUTTON'&&node.textContent===source.filename);
  assert(sourceButton);
  const previewRequest=sourceButton.fire('click'); await tick(); await tick();
  if(mode==='pdflate') {
    await get('logout').fire('click'); resolver(); await previewRequest; await tick();
    assert.equal(get('sourceDialog').open,false);
    assert.equal(get('sourceBody').children.length,0);
    assert.equal(get('workspace').hidden,true);
    assert(revoked.includes('blob:synthetic'));
    return;
  }
  await previewRequest;
  assert.equal(get('sourceDialog').open,true);
  assert(get('sourceBody').textContent.includes('分页原文 1'));
  const nextPage=all().find(node=>node.tagName==='BUTTON'&&node.textContent==='下一页');
  await nextPage.fire('click');
  assert(get('sourceBody').textContent.includes('分页原文 2'));
  assert(nextPage.disabled);
  assert.equal(context.injected,undefined);
  const originalMode=all().find(node=>node.tagName==='BUTTON'&&node.textContent==='PDF原件预览');
  await originalMode.fire('click');
  assert(all().some(node=>node.tagName==='IFRAME'&&node.src==='blob:synthetic'));
  assert(all().some(node=>node.tagName==='A'&&node.href==='blob:synthetic'));
  await get('logout').fire('click');
  assert.equal(get('sourceDialog').open,false);
  assert.equal(get('sourceBody').children.length,0);
  assert.equal(get('productDetail').children.length,0);
  assert.equal(get('productList').children.length,0);
  assert.equal(get('workspace').hidden,true);
  assert(revoked.includes('blob:synthetic'));
  assert.equal(context.injected,undefined);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""


def run_harness(mode):
    node = shutil.which("node")
    assert node, "Node.js is required for browser-state security checks"
    result = subprocess.run(
        [node, "-e", HARNESS, str(ROOT / "js" / "product-center.js"), mode],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_renders_evidence_as_text_and_revokes_previews_on_logout():
    run_harness("preview")


def test_browser_discards_inflight_results_after_logout():
    run_harness("stale")


def test_browser_discards_inflight_pdf_text_after_logout():
    run_harness("pdflate")


def test_browser_refuses_nonadministrator_session_before_data_fetch():
    run_harness("nonadmin")


def test_preview_summarizes_large_success_report_without_expanding_raw_arithmetic_rows():
    run_harness("previewreport")
