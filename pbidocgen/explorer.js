/* Offline exploration. Source data remains immutable when a page is selected. */
let pageScope = '*', activeTab = '', viewState = new Map();
const expandedTables = new Set();
let matrixQuery = '', impactQuery = '', impactNode = '', cleanupDecision = 'Deletion candidate';
let comparison = null, comparisonName = '', comparisonError = '';
const graph = DATA.columns?.dependencyGraph || {nodes:[],edges:[],consumers:[],wholeTableDependencies:[]};
const graphNodes = new Map(graph.nodes.map(n=>[n.id,n]));
const reverseGraph = new Map();
for(const e of graph.edges){
  if(!reverseGraph.has(e.dependency)) reverseGraph.set(e.dependency,[]);
  reverseGraph.get(e.dependency).push(e.dependent);
}
const inPageScope = r => pageScope==='*'||(r.pageId||'')===pageScope;
const scopedPages = () => (R?.pages||[]).filter(p=>pageScope==='*'||p.id===pageScope);
const tableInScope = name => pageScope==='*'||(DATA.columns?.tablePages||[]).some(r=>r.table===name&&inPageScope(r));
const scopedTables = () => (M?.tables||[]).filter(t=>tableInScope(t.name));
const action = (fn,...args) => esc(fn+'('+args.map(a=>JSON.stringify(a)).join(',')+')');
const nodeId = (kind,table,name) => JSON.stringify([kind,table,name]);
const listText = a => a?.length?a.map(esc).join('<br>'):'—';
function rememberView(){
  if(!activeTab) return;
  const state={inputs:[],details:[]};
  document.querySelectorAll('#main input[id]:not([type=file]), #main select[id]').forEach(el=>{
    if(!['global-page','column-page','table-page'].includes(el.id)) state.inputs.push([el.id,el.value]);
  });
  document.querySelectorAll('#main details[id][open]').forEach(el=>state.details.push(el.id));
  viewState.set(activeTab,state);
}
function restoreView(id){
  const state=viewState.get(id);
  for(const [key,value] of state?.inputs||[]){const el=document.getElementById(key);if(el) el.value=value;}
  for(const key of state?.details||[]){const el=document.getElementById(key);if(el) el.open=true;}
  for(const key of ['global-page','column-page','table-page']){const el=document.getElementById(key);if(el) el.value=pageScope;}
}
function scopeBar(id){
  const globalViews=['overview','rels','security','warnings','cleanup'];
  const pages=[...(R?.pages||[])];
  if(id==='compare') for(const p of comparison?.report?.pages||[]) if(!pages.some(x=>x.id===p.id)) pages.push(p);
  const note=globalViews.includes(id)?'This view covers the whole extract. Your page selection is retained for usage views.':
    id==='compare'?'Page changes follow this selection; model changes without page usage remain visible.':
    'Usage and CSV exports follow this selection. Deletion assessments always cover the whole extract.';
  return `<div class="scope-bar"><div><b>Report: ${esc(R?.name||'Not supplied')}</b><div class="mut">${esc(note)}</div></div>
    <label>Report page <select id="global-page" onchange="setPageScope(this.value)">
    <option value="*">All pages</option><option value="">No specific page</option>
    ${pages.map(p=>`<option value="${esc(p.id)}">${esc(p.name)} [${esc(p.id)}]${p.hidden?' · hidden':''}</option>`).join('')}</select></label></div>`;
}
function setPageScope(id){
  pageScope=id;
  closeInspector();
  switchTab(activeTab||'columns');
}
function openInspector(title,html){
  let panel=document.getElementById('inspector');
  if(!panel){panel=document.createElement('aside');panel.id='inspector';document.body.appendChild(panel);}
  panel.hidden=false;
  panel.innerHTML=`<button class="chip" onclick="closeInspector()" aria-label="Close details">Close</button><h2 id="inspector-title">${esc(title)}</h2>${html}`;
  panel.setAttribute('role','region');panel.setAttribute('aria-labelledby','inspector-title');
  panel.setAttribute('tabindex','-1');panel.focus();
}
function closeInspector(){const panel=document.getElementById('inspector');if(panel) panel.hidden=true;}
function usageCell(rows){
  if(!rows.length) return {label:'—',cls:'empty-cell'};
  const kinds=new Set(rows.flatMap(r=>r.kinds||[r.pageUsage]));
  const direct=[...kinds].some(k=>k.includes('Direct'));
  const indirect=[...kinds].some(k=>/Via measures|Via calculations|Table expression/.test(k));
  return {label:direct?(indirect?'Direct + indirect':'Direct'):indirect?'Indirect':'Possible',cls:direct?'cell-direct':indirect?'cell-indirect':'cell-possible'};
}
function toggleMatrixTable(name){expandedTables.has(name)?expandedTables.delete(name):expandedTables.add(name);switchTab('matrix');}
function matrixRows(){
  const q=matrixQuery.trim().toLowerCase();
  const rows=[];
  for(const t of scopedTables()){
    const cols=t.columns.filter(c=>!q||`${t.name} ${c.name}`.toLowerCase().includes(q));
    if(q&&!cols.length&&!t.name.toLowerCase().includes(q)) continue;
    rows.push({table:t.name,column:null});
    if(expandedTables.has(t.name)||q) for(const c of cols) rows.push({table:t.name,column:c.name});
  }
  return rows;
}
function rMatrix(){
  const pages=scopedPages();
  const slots=[...pages.map(p=>({pageId:p.id,page:p.name,report:R.name}))];
  if(pageScope==='*'||pageScope==='') slots.push({pageId:'',page:'No specific page',report:R.name});
  return `<h1>Usage matrix</h1><p class="sub">Expand a table to see its columns across individual pages. Select a cell for its evidence. A dash means no page reference was detected, not that deletion is safe.</p>
    <input id="matrix-search" class="search" value="${esc(matrixQuery)}" placeholder="Search tables or columns…" aria-label="Search usage matrix" oninput="matrixQuery=this.value;renderMatrixBody()">
    <p class="mut">Direct = visual or filter binding · Indirect = measure, calculation or table expression · Possible = relationship dependency. Hidden pages are included.</p>
    <div class="column-scroll"><table class="t matrix"><thead><tr><th>Table / column</th>${slots.map(p=>`<th>${esc(p.page)}<div class="mut">${esc(p.pageId)}</div></th>`).join('')}</tr></thead><tbody id="matrix-body">${matrixBody(slots)}</tbody></table></div>`;
}
function matrixBody(slots){
  return matrixRows().map(r=>`<tr><th>${r.column===null?`<button class="xl" aria-expanded="${expandedTables.has(r.table)}" onclick="${action('toggleMatrixTable',r.table)}">${expandedTables.has(r.table)?'−':'+'} ${esc(r.table)}</button>`:`<span class="matrix-column">${esc(r.column)}</span>`}</th>
    ${slots.map(p=>{
      const matches=(r.column===null?DATA.columns.tablePages:DATA.columns.rows).filter(x=>x.table===r.table&&(r.column===null||x.column===r.column)&&x.pageId===p.pageId);
      const cell=usageCell(matches.filter(x=>r.column===null?x.kinds.length:x.evidence.length));
      const label=!p.pageId&&matches.length?(matches.some(x=>x.evidence.length)?'Unassigned usage':'No page usage'):cell.label;
      return `<td class="${cell.cls}"><button class="xl" aria-label="${esc((r.column||r.table)+' on '+p.page+' ['+p.pageId+']: '+label)}" onclick="${action('inspectCell',r.table,r.column,p.pageId)}">${esc(label)}</button></td>`;
    }).join('')}</tr>`).join('')||`<tr><td colspan="${slots.length+1}">No tables match this selection.</td></tr>`;
}
function renderMatrixBody(){
  const slots=scopedPages().map(p=>({pageId:p.id,page:p.name}));
  if(pageScope==='*'||pageScope==='') slots.push({pageId:'',page:'No specific page'});
  document.getElementById('matrix-body').innerHTML=matrixBody(slots);
}
function inspectCell(table,column,pageId){
  const rows=(column===null?DATA.columns.tablePages:DATA.columns.rows).filter(r=>r.table===table&&(column===null||r.column===column)&&r.pageId===pageId);
  const page=(R.pages||[]).find(p=>p.id===pageId);
  const evidence=[...new Set(rows.flatMap(r=>r.evidence))];
  const columns=DATA.columns.rows.filter(r=>r.table===table&&r.pageId===pageId&&(column===null||r.column===column));
  openInspector(column===null?table:`${table}[${column}]`, `<p>${esc(R.name)} / ${esc(page?.name||'No specific page')} ${esc(pageId)}</p>
    <h3>Evidence on this page</h3><p>${listText(evidence)||'—'}</p>${!evidence.length?'<p>No usage evidence detected for this cell.</p>':''}
    <h3>Column assessments (whole extract)</h3>${columns.map(r=>`<p><button class="xl" onclick="${action('inspectNode',nodeId('c',r.table,r.column),pageId)}">${esc(r.column)}</button> · ${esc(r.decision)}</p>`).join('')||'<p>No resolved column references.</p>'}
    ${column!==null?`<button class="chip" onclick="${action('inspectNode',nodeId('c',table,column),pageId)}">Trace dependency paths</button>`:''}`);
}
// A breadth-first walk gives one shortest, explicit reference path per dependent.
// All reachable dependents are returned, including cycles, without inventing edges.
function downstreamPaths(id){
  const paths=new Map([[id,[id]]]), queue=[id];
  for(let i=0;i<queue.length;i++) for(const next of reverseGraph.get(queue[i])||[]){
    if(paths.has(next)) continue;
    paths.set(next,[...paths.get(queue[i]),next]);queue.push(next);
  }
  return paths;
}
function impactConsumers(id,scope=pageScope){
  const paths=downstreamPaths(id);
  return graph.consumers.filter(c=>paths.has(c.node)&&(scope==='*'||c.pageId===scope)).map(c=>({...c,path:paths.get(c.node)}));
}
function impactDetails(id,scope=pageScope){
  const n=graphNodes.get(id);if(!n) return '<p>No resolved field selected.</p>';
  const paths=downstreamPaths(id), consumers=impactConsumers(id,scope);
  const col=DATA.columns.rows.find(r=>r.table===n.table&&r.column===n.name&&n.kind==='column');
  const expression=n.kind==='measure'?M.measures.find(m=>m.table===n.table&&m.name===n.name)?.expression:col?.expression;
  const dependencies=graph.edges.filter(e=>e.dependent===id).map(e=>graphNodes.get(e.dependency));
  const wholeTables=graph.wholeTableDependencies.filter(e=>e.node===id).map(e=>e.table);
  const dependent=[...paths.keys()].filter(k=>k!==id).map(k=>graphNodes.get(k));
  const sources=[...new Map(DATA.tableSources.filter(r=>r.table===n.table).map(r=>[r.partition,r])).values()];
  const pathHtml=consumers.map(c=>`<li><b>${esc(pageLabel(c))}</b><div>${esc(c.evidence)}</div><p class="path">${c.path.map(k=>esc(graphNodes.get(k)?.label||k)).join(' → ')}</p>${c.visualId?`<button class="xl" onclick="${action('inspectVisual',c.pageId,c.visualId)}">Inspect visual ${esc(c.visualId)}</button>`:''}</li>`).join('');
  return `<p>${esc(n.kind)} · ${esc(n.label)}</p>${col?`<p><b>${esc(col.decision)}</b> · ${esc(col.reason)}</p>`:''}
    <h3>Where it is used</h3><p class="mut">${consumers.length} binding locations in the selected scope. One shortest detected path per binding is shown; DAX is not executed.</p><ul class="impact-paths">${pathHtml||'<li>No resolved usage in this page scope.</li>'}</ul>
    <h3>Reads these fields</h3><p>${dependencies.map(d=>`<button class="xl" onclick="${action('inspectNode',d.id,scope)}">${esc(d.label)}</button>`).join(', ')||'No explicit field dependencies detected'}</p>
    ${wholeTables.length?`<p>Whole-table references: ${listText(wholeTables)}. Individual column use cannot be confirmed from these references alone.</p>`:''}
    <h3>Dependent calculations (whole model)</h3><p>${dependent.map(d=>`<button class="xl" onclick="${action('inspectNode',d.id,scope)}">${esc(d.label)}</button>`).join(', ')||'None detected'}</p>
    ${col?`<h3>Other dependencies and uncertainty</h3><p>${listText(col.modelDependencies)}</p><p>${listText(col.reviewNotes)}</p>`:''}
    ${expression?`<h3>Expression</h3><pre class="code">${esc(expression)}</pre>`:''}
    <h3>Home table sources</h3><p class="mut">For measures, the home table is organisational. Follow “Reads these fields” above to trace data sources.</p>
    ${sources.map(r=>`<p>${esc([r.server,r.database,r.object||r.partition].filter(Boolean).join(' / '))}</p>${r.query?`<details><summary>${esc(r.queryKind)} query</summary><pre class="code">${esc(r.query)}</pre></details>`:''}`).join('')}
    ${col?`<p>Model input column: ${esc(col.sourceColumn)||'Unknown'}</p>`:''}<p class="mut">${esc(DATA.columns.sourceNote)}</p>`;
}
function inspectNode(id,scope=pageScope){impactNode=id;openInspector(graphNodes.get(id)?.label||'Field details',impactDetails(id,scope));}
function rImpact(){
  const nodes=graph.nodes.filter(n=>!impactQuery||n.label.toLowerCase().includes(impactQuery.toLowerCase()));
  return `<h1>Impact inspector</h1><p class="sub">Choose a column or measure to see downstream calculations and the specific report pages and visuals that consume it.</p>
    <input id="impact-search" class="search" value="${esc(impactQuery)}" placeholder="Search a column or measure…" aria-label="Search dependency fields" oninput="impactQuery=this.value;renderImpactOptions()">
    <label>Field <select id="impact-field" class="search" onchange="impactNode=this.value;renderImpactDetails()">${impactOptions(nodes)}</select></label>
    <div id="impact-details">${impactDetails(impactNode||nodes[0]?.id)}</div>`;
}
function impactOptions(nodes){return nodes.map(n=>`<option value="${esc(n.id)}"${n.id===impactNode?' selected':''}>${esc(n.label)} · ${n.kind}</option>`).join('');}
function renderImpactOptions(){
  const nodes=graph.nodes.filter(n=>n.label.toLowerCase().includes(impactQuery.toLowerCase()));
  if(!nodes.some(n=>n.id===impactNode)) impactNode=nodes[0]?.id||'';
  document.getElementById('impact-field').innerHTML=impactOptions(nodes);renderImpactDetails();
}
function renderImpactDetails(){document.getElementById('impact-details').innerHTML=impactDetails(impactNode);}
function layoutGeometry(page){
  const valid=v=>['x','y','width','height'].every(k=>typeof v[k]==='number'&&Number.isFinite(v[k]))&&v.width>0&&v.height>0;
  const placed=page.visuals.filter(valid), unplaced=page.visuals.filter(v=>!valid(v));
  const left=Math.min(0,...placed.map(v=>v.x)), top=Math.min(0,...placed.map(v=>v.y));
  const width=Math.max(1,Number(page.width)||0,...placed.map(v=>v.x+v.width))-left;
  const height=Math.max(1,Number(page.height)||0,...placed.map(v=>v.y+v.height))-top;
  return {placed,unplaced,left,top,width,height};
}
function rLayout(){
  return `<h1>Page layout</h1><p class="sub">A schematic from saved visual positions, not rendered charts or live data. Select a visual to inspect its bindings. Hidden visuals and pages are labelled.</p>`+
    (scopedPages().map(p=>{
      const g=layoutGeometry(p);
      return `<div class="card"><h2>${esc(p.label||p.name)} ${p.hidden?'· hidden page':''}</h2>
      ${g.placed.length?`<div class="page-canvas" style="aspect-ratio:${g.width}/${g.height}">${g.placed.map(v=>`<button class="visual-box${v.hidden?' hidden-visual':''}" style="left:${100*(v.x-g.left)/g.width}%;top:${100*(v.y-g.top)/g.height}%;width:${100*v.width/g.width}%;height:${100*v.height/g.height}%" title="${esc((v.title||v.type)+' ['+v.id+']')}" onclick="${action('inspectVisual',p.id,v.id)}">${esc(v.title||v.type)}<small>${esc(v.id)}${v.hidden?' · hidden':''}</small></button>`).join('')}</div>`:'<p>No usable visual coordinates in this extract.</p>'}
      <details><summary>All visuals (${p.visuals.length}); ${g.unplaced.length} without usable coordinates</summary><div class="body">${p.visuals.map(v=>`<p><button class="xl" onclick="${action('inspectVisual',p.id,v.id)}">${esc(v.title||v.type)} [${esc(v.id)}]${v.hidden?' · hidden':''}</button></p>`).join('')}</div></details></div>`;
    }).join('')||'<p>No pages in this selection.</p>');
}
function inspectVisual(pageId,visualId){
  const p=R?.pages.find(p=>p.id===pageId), v=p?.visuals.find(v=>v.id===visualId);if(!v) return;
  const roots=graph.consumers.filter(c=>c.pageId===pageId&&c.visualId===visualId);
  openInspector(v.title||v.type,`<p>${esc(p.label||p.name)} · ${esc(v.id)}${v.hidden?' · hidden':''}</p><h3>Declared bindings</h3>
    <p>${v.fields.map(f=>esc(`${f.table||'?'}[${f.field}] (${f.kind})`)).join('<br>')||'No field bindings detected.'}</p>
    <h3>Resolved fields</h3>${[...new Set(roots.map(c=>c.node))].map(id=>`<p><button class="xl" onclick="${action('inspectNode',id,pageId)}">${esc(graphNodes.get(id)?.label)}</button></p>`).join('')||'<p>No resolved model fields.</p>'}
    <h3>Visual filters</h3><p>${v.filters.map(f=>esc(`${f.table||'?'}[${f.field}] ${f.raw||''}`)).join('<br>')||'None detected'}</p>`);
}
function cleanupRows(){return DATA.columns.rows.filter(r=>!cleanupDecision||r.decision===cleanupDecision);}
function rCleanup(){
  const rows=[...new Map(cleanupRows().map(r=>[nodeId('c',r.table,r.column),r])).values()];
  return `<h1>Cleanup review</h1><p class="sub">Whole-extract assessments, independent of the page selector. ${esc(DATA.columns.scope)}</p>
    <label>Assessment <select id="cleanup-decision" class="search" onchange="cleanupDecision=this.value;switchTab('cleanup')">${['Deletion candidate','Review','Keep',''].map(d=>`<option value="${d}"${cleanupDecision===d?' selected':''}>${d||'All assessments'}</option>`).join('')}</select></label>
    <p>${rows.length} distinct columns · <button class="xl" onclick="exportCsvFile(columnCsv(cleanupRows()),'cleanup-column-page-usage.csv')">Export evidence at column/page grain</button></p>
    <table class="t"><thead><tr><th>Column</th><th>Assessment</th><th>Why / evidence</th><th>Pages</th></tr></thead><tbody>${rows.map(r=>{
      const pages=DATA.columns.rows.filter(x=>x.table===r.table&&x.column===r.column&&x.pageId);
      return `<tr><th><button class="xl" onclick="${action('inspectNode',nodeId('c',r.table,r.column),'*')}">${esc(r.table)}[${esc(r.column)}]</button></th><td>${esc(r.decision)}</td><td>${esc(r.reason)}<details><summary>Dependencies and review notes</summary><p>${listText(r.modelDependencies)}</p><p>${listText(r.reviewNotes)}</p></details></td><td>${pages.map(p=>esc(pageLabel(p))).join('<br>')||esc(r.pageScope)}</td></tr>`;
    }).join('')||'<tr><td colspan="4">No columns have this assessment.</td></tr>'}</tbody></table>`;
}
function exportCsvFile(csv,name){
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
// Comparison uses definitions and bindings, not volatile timestamps or generated prose.
function canonical(value){
  if(Array.isArray(value)) return value.map(canonical);
  if(value&&typeof value==='object') return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));
  return value;
}
const stable = value => JSON.stringify(canonical(value));
function snapshot(payload){
  const result=new Map(), report=payload.report?.name||'Not supplied';
  const columns=payload.columns?.rows||[], tablePages=payload.columns?.tablePages||[], measurePages=payload.columns?.measurePages||[];
  const put=(kind,key,label,value,pages=[])=>result.set(stable([kind,...key]),{kind,label,value:stable(value),pages:[...new Map(pages.filter(r=>r.pageId).map(r=>[r.pageId,{report:r.report||report,page:r.page,pageId:r.pageId}])).values()]});
  for(const t of payload.model?.tables||[]){
    const pages=tablePages.filter(r=>r.table===t.name);
    put('Table',[t.name],t.name,{hidden:t.isHidden,description:t.description},pages);
    for(const c of t.columns||[]) put('Column',[t.name,c.name],`${t.name}[${c.name}]`,{type:c.dataType,expression:c.expression,sourceColumn:c.sourceColumn,hidden:c.isHidden,sortBy:c.sortByColumn,isKey:c.isKey},columns.filter(r=>r.table===t.name&&r.column===c.name));
    for(const p of t.partitions||[]) put('Source',[t.name,p.name],`${t.name} / ${p.name}`,{mode:p.mode,type:p.type,expression:p.expression,source:p.source},pages);
    for(const h of t.hierarchies||[]) put('Hierarchy',[t.name,h.name],`${t.name} / ${h.name}`,h,pages);
  }
  for(const m of payload.model?.measures||[]) put('Measure',[m.table,m.name],`${m.table}[${m.name}]`,{expression:m.expression,format:m.formatString,dynamicFormat:m.formatStringExpression,hidden:m.isHidden},measurePages.filter(r=>r.table===m.table&&r.measure===m.name));
  for(const rel of payload.model?.relationships||[]) put('Relationship',[rel.name],rel.name,rel,tablePages.filter(r=>[rel.fromTable,rel.toTable].includes(r.table)));
  for(const role of payload.model?.roles||[]) put('Security role',[role.name],role.name,role);
  if(payload.report){
    const r=payload.report,allPages=r.pages.map(p=>({report:r.name,page:p.name,pageId:p.id}));
    put('Report filters',[],r.name,{filters:r.reportFilters,fields:r.otherFields},allPages);
    for(const b of r.bookmarks||[]) put('Bookmark',[b.name],b.name,b);
    for(const p of r.pages){
      const pages=[{report:r.name,page:p.name,pageId:p.id}];
      put('Page',[p.id],`${p.name} [${p.id}]`,{name:p.name,hidden:p.hidden,width:p.width,height:p.height,filters:p.filters,fields:p.otherFields},pages);
      for(const v of p.visuals||[]) put('Visual',[p.id,v.id],`${p.name} [${p.id}] / ${v.title||v.type} [${v.id}]`,v,pages);
    }
  }
  return result;
}
function compareExtracts(before,after){
  const a=snapshot(before),b=snapshot(after), rows=[];
  for(const key of new Set([...a.keys(),...b.keys()])){
    const old=a.get(key),current=b.get(key);
    if(old?.value===current?.value) continue;
    const item=current||old;
    rows.push({kind:item.kind,item:item.label,change:!old?'Added':!current?'Removed':'Changed',before:old?.value||'',after:current?.value||'',
      pages:[...new Map([...(old?.pages||[]),...(current?.pages||[])].map(r=>[stable([r.report,r.pageId]),r])).values()]});
  }
  return rows.sort((a,b)=>a.kind.localeCompare(b.kind)||a.item.localeCompare(b.item));
}
function validateExtract(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||(!value.model&&!value.report)) throw new Error('Choose a JSON extract produced by --json.');
  if(value.model&&(!Array.isArray(value.model.tables)||!Array.isArray(value.model.measures))) throw new Error('The model definition is incomplete.');
  if(value.report&&(!Array.isArray(value.report.pages)||value.report.pages.some(p=>!p||typeof p.id!=='string'||!Array.isArray(p.visuals)))) throw new Error('The report pages are incomplete.');
  snapshot(value); // Reject malformed nested definitions before replacing an existing comparison.
  return value;
}
async function loadComparison(input){
  const file=input.files?.[0];if(!file) return;
  try{
    if(file.size>50*1024*1024) throw new Error('Choose an extract smaller than 50 MB.');
    const value=validateExtract(JSON.parse(await file.text()));
    comparison=value;comparisonName=file.name;comparisonError='';
  }catch(error){comparisonError='Could not compare this file: '+error.message;}
  switchTab('compare');
}
function comparisonRows(){return comparison?compareExtracts(comparison,DATA).filter(r=>pageScope==='*'||!r.pages.length||r.pages.some(inPageScope)):[];}
function rCompare(){
  const rows=comparisonRows();
  const mismatch=comparison&&(comparison.model?.name!==M?.name||comparison.report?.name!==R?.name||comparison.mode!==MODE);
  return `<h1>Compare extracts</h1><p class="sub">Choose an earlier JSON extract as the baseline. This document is the current extract. Files are read locally; no upload is made. Compares definitions, sources, DAX, filters, relationships, bookmarks and visual bindings, not data values.</p>
    <label>Earlier extract (.json) <input type="file" accept=".json,application/json" onchange="loadComparison(this)"></label>
    <p role="status">${esc(comparisonError)}</p>${comparison?`<p>Baseline: <b>${esc(comparisonName)}</b> (${esc(comparison.generated||'date unknown')}) → Current: ${esc(DATA.generated)}</p>
    ${mismatch?'<div class="card">The report/model names or extraction modes differ. Changes may reflect different projects or missing input files; confirm that these extracts are comparable.</div>':''}
    ${!comparison.columns?.tablePages?'<p class="mut">The baseline lacks page-level model usage; affected pages for removed model objects may be incomplete.</p>':''}
    <p>${rows.length} changes in this scope · <button class="xl" onclick="exportComparison()">Export changes by page</button></p>
    <table class="t"><thead><tr><th>Change</th><th>Object</th><th>Affected report pages</th><th>Definition</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.change)}</td><th>${esc(r.kind)}<br>${esc(r.item)}</th><td>${r.pages.filter(inPageScope).map(p=>esc(pageLabel(p))).join('<br>')||'No resolved page / model scope'}</td><td><details><summary>Before / after</summary><b>Before</b><pre class="code">${esc(r.before)||'Absent'}</pre><b>After</b><pre class="code">${esc(r.after)||'Absent'}</pre></details></td></tr>`).join('')||'<tr><td colspan="4">No definition changes detected in this scope.</td></tr>'}</tbody></table>`:''}`;
}
function exportComparison(){
  const rows=comparisonRows().flatMap(r=>(r.pages.length?r.pages.filter(inPageScope):[{report:R?.name||'Not supplied',page:'',pageId:''}]).map(p=>({...r,...p})));
  exportCsvFile(inventoryCsv(rows,[['change','Change'],['kind','Object type'],['item','Object'],['report','Report'],['page','Report page'],['pageId','Page ID'],['before','Before'],['after','After']]),'extract-changes-by-page.csv');
}
TABS.splice(2,0,
  {id:'matrix',label:'Usage matrix',group:'Start',avail:has.model&&has.report},
  {id:'impact',label:'Impact inspector',group:'Start',avail:has.model});
TABS.splice(TABS.findIndex(t=>t.id==='filters'),0,{id:'layout',label:'Page layout',group:'Report',avail:has.report});
TABS.push({id:'cleanup',label:'Cleanup review',group:'Quality',avail:has.model},
  {id:'compare',label:'Compare extracts',group:'Quality',avail:true});
Object.assign(RENDER,{matrix:rMatrix,impact:rImpact,layout:rLayout,cleanup:rCleanup,compare:rCompare});
