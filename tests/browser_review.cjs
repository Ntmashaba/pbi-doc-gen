// Real Chromium gate. Requires Playwright and its Chromium binary.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),os=require('node:os');
const {pathToFileURL}=require('node:url');
const {execFileSync}=require('node:child_process');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({acceptDownloads:true,viewport:{width:1440,height:1000}});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  for(const id of await page.evaluate(()=>TABS.filter(t=>t.avail).map(t=>t.id))){await page.locator('#nav-'+id).click();}
  await page.locator('#nav-columns').click();await page.locator('#column-search').fill('Amount');
  await page.locator('#global-page').selectOption('p2');await page.locator('#nav-tables').click();
  assert.equal(await page.locator('#global-page').inputValue(),'p2');
  await page.locator('#nav-columns').click();assert.equal(await page.locator('#column-search').inputValue(),'Amount');
  assert.equal(await page.locator('#column-rows tr').count(),1);
  await page.locator('#global-page').selectOption('*');
  await page.locator('#nav-impact').click();
  await page.locator('#impact-field').selectOption('["c","Sales","Amount"]');
  await page.locator('#nav-cleanup').click();
  await page.evaluate(()=>inspectNode(nodeId('m','Sales','Total')));
  await page.locator('#inspector').getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#nav-impact').click();
  assert.equal(await page.locator('#impact-field').inputValue(),'["m","Sales","Total"]');
  assert.match(await page.locator('#impact-details').innerText(),/Sales\[Total\]/);
  await page.locator('#nav-lineage').click();
  // SVG labels are truncated; match its safely encoded full handler instead.
  await page.locator('#lineage-board g[onclick*="reviewMarker"]').click();
  await page.locator('#lineage-board g[onclick*="reviewMarker"]').click();
  assert.equal(await page.evaluate(()=>globalThis.reviewMarker),undefined);
  await page.locator('details[open]').waitFor();
  assert.equal(await page.locator('details[open]').count(),1);
  await page.locator('#nav-rels').click();
  const names=await page.evaluate(()=>[slug('Sales-US'),slug('Sales US')]);assert.notEqual(names[0],names[1]);
  await page.locator('#nav-layout').click();await page.locator('.visual-box').first().click();
  assert.ok(await page.locator('#inspector').isVisible());await page.keyboard.press('Tab');
  await page.locator('#inspector').getByRole('button',{name:'Close',exact:true}).click();
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'pbi-browser-'));
  const exports=[['columns','Export filtered CSV','column-page-usage.csv'],['tables','Export source summary CSV','report-table-sources.csv'],['sources','Export all M queries CSV','source-queries.csv'],['sources','Export source objects CSV (with code)','source-objects.csv'],['sources','Export source objects CSV (no code)','source-objects-no-code.csv'],['primary-sources','Export primary sources CSV','primary-sources.csv'],['cleanup','Export evidence at column/page grain','cleanup-column-page-usage.csv']];
  for(const [tab,label,suffix] of exports){
   await page.locator('#nav-'+tab).click();
   const pending=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:true}).click();const download=await pending;
   assert.equal(download.suggestedFilename(),'Sales-'+suffix);
   const file=path.join(tmp,suffix);await download.saveAs(file);
   if(suffix==='source-queries.csv') execFileSync('python',['-c','import csv,sys; f=open(sys.argv[1],encoding="utf-8-sig",newline=""); r=csv.reader(f); assert next(r)==["report","query name","query m code"]; assert any(row[1]=="Stage" and "\\n" in row[2] for row in r)',file]);
  }
  const baseline=JSON.parse(fs.readFileSync('/tmp/pbidocgen-browser.json','utf8'));baseline.model.expressions[0].expression='changed';
  await page.locator('#nav-compare').click();await page.locator('input[type=file]').setInputFiles({name:'before.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(baseline))});
  await page.locator('tbody th').filter({hasText:'Shared expression'}).waitFor();
  const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Export changes by page',exact:true}).click();
  assert.equal((await pending).suggestedFilename(),'Sales-extract-changes-by-page.csv');
  await page.setViewportSize({width:768,height:900});await page.locator('#nav-matrix').click();
  assert.ok(await page.locator('.matrix').isVisible());
  assert.deepEqual(errors,[]);
  fs.rmSync(tmp,{recursive:true,force:true});console.log('Chromium regression checks passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
