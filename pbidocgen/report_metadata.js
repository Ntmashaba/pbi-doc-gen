/* Portable user-maintained documentation. Never stored only in browser storage. */
function cleanDocumentation(value){
 const fields=['sourceType','server','database','username','authentication','connectionName'];
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['reportLocation','folder','connections'].includes(k))) throw Error('Unsupported documentation fields');
 const out={reportLocation:value.reportLocation||'',folder:value.folder||'',connections:value.connections||[]};
 if(typeof out.reportLocation!=='string'||typeof out.folder!=='string'||!Array.isArray(out.connections)) throw Error('Invalid documentation metadata');
 out.connections=out.connections.map(c=>{
  if(!c||typeof c!=='object'||Array.isArray(c)||Object.keys(c).some(k=>!fields.includes(k))||Object.values(c).some(v=>typeof v!=='string')) throw Error('Connections accept identity and username fields only; no passwords or tokens');
  return Object.fromEntries(fields.map(k=>[k,c[k]||'']));
 });
 return out;
}
let documentation=cleanDocumentation(JSON.parse(document.getElementById('pbi-documentation-metadata')?.textContent||'{}'));
const connectionIdentity=c=>JSON.stringify([c.sourceType||'',c.server||'',c.database||'']);
for(const source of DATA.sourceObjects||[]){
 if(source.status==='Not applicable') continue;
 if(!documentation.connections.some(c=>connectionIdentity(c)===connectionIdentity(source))) documentation.connections.push(Object.fromEntries(['sourceType','server','database','username','authentication','connectionName'].map(k=>[k,source[k]||''])));
}
function documentationInput(label,id,value){return `<label style="display:block;margin:1rem 0">${esc(label)}<input class="search" style="display:block;width:100%;max-width:900px" id="${id}" value="${esc(value)}" oninput="captureDocumentation()"></label>`;}
function captureDocumentation(){
 documentation.reportLocation=document.getElementById('doc-location').value;
 documentation.folder=document.getElementById('doc-folder').value;
 documentation.connections.forEach((c,i)=>Object.keys(c).forEach(k=>{c[k]=document.getElementById(`doc-${i}-${k}`).value;}));
 document.getElementById('doc-status').textContent='Unsaved edits — download updated HTML to keep these details.';
}
function addDocumentationConnection(){captureDocumentation();documentation.connections.push({sourceType:'',server:'',database:'',username:'',authentication:'',connectionName:''});switchTab('report-details');}
function removeDocumentationConnection(i){captureDocumentation();documentation.connections.splice(i,1);switchTab('report-details');}
function rDocumentation(){return `<h1>Report details</h1><p class="sub">Keep the original report location and connection account references with this document. Enter usernames or service account names only. Do not enter passwords, tokens or secret-bearing URLs.</p>
${documentationInput('Original report URL or file path','doc-location',documentation.reportLocation)}
${documentationInput('Catalogue folder (optional override, e.g. Finance / Monthly)','doc-folder',documentation.folder)}
<p class="mut">The home page groups by this folder, or by the parent of the report location. Without either, it lists the document under Ungrouped.</p>
<h2>Connections and account references</h2><p class="mut">Detected connections are starting points. Account details are entered manually; the generator does not retrieve credentials from Power BI. Saved references may need updating when sources change.</p>
${documentation.connections.map((c,i)=>`<details style="padding:1rem;border:1px solid var(--line);margin-bottom:1rem" open><summary>${esc(c.connectionName||c.server||'Connection '+(i+1))}</summary>${Object.entries({connectionName:'Connection name',sourceType:'Source type',server:'Server / location',database:'Database / service',username:'Username / service account',authentication:'Authentication method (reference only)'}).map(([k,label])=>documentationInput(label,`doc-${i}-${k}`,c[k])).join('')}<button onclick="removeDocumentationConnection(${i})">Remove reference</button></details>`).join('')}
<p><button onclick="addDocumentationConnection()">Add connection reference</button> <button class="xl" onclick="saveDocumentationHtml()">Download updated HTML</button></p>
<p id="doc-status" role="status">Save an updated HTML after editing. Replace the original file in your documentation folder, then refresh the home page catalogue.</p>`;}
function saveDocumentationHtml(){
 captureDocumentation();
 const clone=document.documentElement.cloneNode(true);
 clone.querySelector('#pbi-documentation-metadata').textContent=JSON.stringify(cleanDocumentation(documentation)).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
 clone.querySelector('#main').innerHTML='';clone.querySelector('#nav').innerHTML='';
 const blob=new Blob(['<!DOCTYPE html>\n'+clone.outerHTML],{type:'text/html;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;
 a.download=DATA.documentationFilename||'report.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.getElementById('doc-status').textContent='Download requested. Replace the original HTML with the downloaded file to keep these details, then refresh the home page catalogue.';
}
TABS.push({id:'report-details',label:'Report details',group:'Documentation',avail:true});
RENDER['report-details']=rDocumentation;
