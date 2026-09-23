// Stateful DOM adapter for generated JavaScript. Does not verify browser layout.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2],'utf8');
const nodes=new Map();let mounted=[];
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
function node(id){
  if(!nodes.has(id)){
    let content='';
    nodes.set(id,{id,value:'',hidden:false,style:{},classList:{add(){},remove(){}},setAttribute(){},focus(){},querySelectorAll(){return []},
      get innerHTML(){return content;},set innerHTML(s){content=s;if(id==='main') mount(s);}});
  }
  return nodes.get(id);
}
function mount(html){
  mounted=[];
  for(const m of html.matchAll(/<(input|select|details)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
    const el=node(m[3]);el.value=decode(m[2].match(/\bvalue="([^"]*)"/)?.[1]||'');el.tagName=m[1].toUpperCase();
    if(el.tagName==='SELECT'){
      const body=html.slice(m.index).split('</select>')[0];
      const options=[...body.matchAll(/<option(?: value="([^"]*)")?([^>]*)>([^<]*)<\/option>/g)];
      const o=options.find(x=>x[2].includes('selected'))||options[0];el.value=decode(o?.[1]??o?.[3]??'');
    }
    mounted.push(el);
  }
}
const context=vm.createContext({console,setTimeout,document:{getElementById:node,
 querySelectorAll:s=>s.startsWith('#main input')?mounted.filter(e=>['INPUT','SELECT'].includes(e.tagName)):[],
 createElement:()=>({}),body:{appendChild(){}}},window:{scrollTo(){}}});
vm.runInContext(html.match(/<script>([\s\S]*)<\/script>/)[1],context);
const run=s=>vm.runInContext(s,context);
const same=(a,b)=>assert.equal(JSON.stringify(a),JSON.stringify(b));
// Every available view must render in every supported extraction mode.
for(const tab of run('TABS.filter(t=>t.avail).map(t=>t.id)')) run(`switchTab(${JSON.stringify(tab)})`);
if(!run('has.model&&has.report')){console.log('Available mode views rendered');process.exit(0);}
run("switchTab('columns')");node('column-search').value='Amount';run('filterColumns()');
run("setPageScope('p2');switchTab('tables')");assert.equal(node('global-page').value,'p2');
assert.equal(run("sourceRows('Orders').length"),1);
run("switchTab('columns')");assert.equal(node('column-search').value,'Amount');assert.equal(run('visibleColumns.length'),1);
assert.equal(run('visibleColumns[0].pageId'),'p2');
run("switchTab('pages')");assert.ok(!node('main').innerHTML.includes('id="pg-70_31"'));assert.ok(node('main').innerHTML.includes('id="pg-70_32"'));
run("switchTab('matrix');toggleMatrixTable('Sales')");assert.match(node('main').innerHTML,/matrix-column/);assert.ok(!run('rMatrix()').includes('<div class="mut">p1</div>'));assert.equal(run("matrixKinds({kinds:['Possible relationship dependency']}).kinds.length"),0);run('matrixRelOnly=true');assert.equal(run("matrixKinds({kinds:['Possible relationship dependency']}).kinds.length"),1);assert.match(run('rMatrix()'),/id="matrix-rel" checked/);run('matrixRelOnly=false');
run("inspectCell('Sales','Amount','p2')");assert.match(node('inspector').innerHTML,/v1/);
const amount='["c","Sales","Amount"]';
same(run(`impactConsumers(${JSON.stringify(amount)}).map(c=>c.pageId)`),['p2']);
same(run(`impactConsumers(${JSON.stringify(amount)})[0].path.map(id=>graphNodes.get(id).name)`),['Amount','Base','Total']);
run(`inspectNode(${JSON.stringify(amount)})`);assert.match(node('inspector').innerHTML,/Amount.*→.*Base.*→.*Total/);
run("inspectNode(nodeId('m','Sales','Total'))");assert.match(node('inspector').innerHTML,/Reads these fields/);assert.match(node('inspector').innerHTML,/Sales\[Base\]/);
run("inspectVisual('p2','v1')");assert.match(node('inspector').innerHTML,/p2/);assert.match(node('inspector').innerHTML,/Resolved fields/);
// A graph cycle must terminate and preserve shortest paths.
run("reverseGraph.set(nodeId('m','Sales','Total'),[nodeId('m','Sales','Base')])");assert.equal(run(`downstreamPaths(${JSON.stringify(amount)}).size`),4);
run("switchTab('cleanup')");assert.match(node('main').innerHTML,/3 distinct columns/);assert.equal(run('cleanupRows().length'),3);assert.match(node('main').innerHTML,/<h2>Measures<\/h2>/);assert.ok(run("cleanupMeasureRows().every(r=>r.decision==='Deletion candidate')"));
run("setPageScope('');switchTab('columns')");node('column-search').value='';run('filterColumns()');assert.ok(run("visibleColumns.every(r=>r.pageId==='')"));
run("setPageScope('*');switchTab('layout')");assert.match(node('main').innerHTML,/without usable coordinates/);
same(run("layoutGeometry({width:100,height:100,visuals:[{x:-10,y:0,width:20,height:30},{x:null,y:0,width:20,height:30}]}).unplaced.length"),1);
// Same extract produces no changes even if generated time or JSON key order differs.
run("comparison=JSON.parse(JSON.stringify(DATA));comparison.generated='earlier';comparisonName='baseline.json'");assert.equal(run('comparisonRows().length'),0);
run("comparison.model.measures.find(m=>m.name==='Base').expression='SUM(Sales[Amount])*2'");
assert.equal(run('comparisonRows().length'),1);same(run('comparisonRows()[0].pages.map(p=>p.pageId)'),['p1','p2']);
run("setPageScope('p2');switchTab('compare')");assert.ok(!run('rCompare()').includes('Same / page [p1]'));
run("setPageScope('*');comparison.report.pages.push({id:'removed-page',name:'Old page',visuals:[],filters:[]})");assert.ok(run("comparisonRows().some(r=>r.change==='Removed'&&r.kind==='Page')"));
run("setPageScope('removed-page')");assert.equal(run('comparisonRows().length'),1);
assert.throws(()=>run('validateExtract({report:{}})'),/incomplete/);
assert.throws(()=>run('validateExtract([])'),/JSON extract/);
run("comparison.report.pages[2].name='<img src=x onerror=alert(1)>';switchTab('compare')");assert.ok(!node('main').innerHTML.includes('<img src=x'));
console.log('Explorer checks passed: scope, state, paths, layout, cleanup, comparison and escaping.');

// Regression assertions for comparison completeness, identity and state.
run("setPageScope('*')");
assert.ok(run("slug('Sales-US') !== slug('Sales US')"));
assert.throws(()=>run('validateExtract({schemaVersion:999,model:{tables:[],measures:[]}})'),/Unsupported/);
assert.equal(run(`(()=>{const a=JSON.parse(JSON.stringify(DATA)),b=JSON.parse(JSON.stringify(DATA));
 a.model.expressions=[{name:'Stage',kind:'m',expression:'1'}];b.model.expressions=[{name:'Stage',kind:'m',expression:'2'}];
 return compareExtracts(a,b).filter(r=>r.kind==='Shared expression').length})()`),1);
assert.equal(run(`(()=>{const a=JSON.parse(JSON.stringify(DATA)),b=JSON.parse(JSON.stringify(DATA));
 a.model.tables[0].calculationGroupDefinition={precedence:1,calculationItems:[{name:'X',expression:'1',formatStringDefinition:{expression:'"0"'}}]};
 b.model.tables[0].calculationGroupDefinition={precedence:2,calculationItems:[{name:'X',expression:'2',formatStringDefinition:{expression:'"0.0"'}}]};
 return compareExtracts(a,b).filter(r=>r.kind==='Calculation group').length})()`),1);
run("impactNode=nodeId('c','Sales','Amount');switchTab('impact');switchTab('cleanup');inspectNode(nodeId('m','Sales','Total'));switchTab('impact')");
assert.equal(node('impact-field').value,run('impactNode'));
assert.match(node('main').innerHTML,/<p>measure · Sales\[Total\]<\/p>/);
run("impactQuery='no match';switchTab('impact')");assert.equal(run('impactNode'),'');
// Actual HTML handler, entity-decoded as in a browser, must not execute names.
run(`M.tables[0].name="x');globalThis.reviewMarker=1;//";drawLineage()`);
const handler=[...node('lineage-board').innerHTML.matchAll(/onclick="([^"]*)"/g)].map(m=>m[1]).find(s=>s.includes('reviewMarker'));
run(decode(handler));assert.equal(run('globalThis.reviewMarker'),undefined);
