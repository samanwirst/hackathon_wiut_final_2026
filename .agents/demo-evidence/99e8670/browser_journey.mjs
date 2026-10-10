import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
const root=process.cwd();
const qa=path.resolve(process.env.DEMO_QA_DIR || path.join(root,'.agents/runtime/demo/qa-reproduction'));
const servers=JSON.parse(fs.readFileSync(path.join(qa,'servers.json')));
const {chromium,request}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || path.join(root,'node_modules/playwright-core/index.mjs')));
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,chromiumSandbox:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const api=await request.newContext({baseURL:servers.api_url});
const result={target_sha:servers.target_sha,steps:[],probes:[],console_errors:[],request_failures:[]};
page.on('pageerror',e=>result.console_errors.push(e.message));
page.on('requestfailed',r=>result.request_failures.push({url:r.url(),error:r.failure()?.errorText}));
const record=(step,details={})=>{result.steps.push({step,...details});console.log(step,JSON.stringify(details));};
const check=(name,passed,details={})=>{result.probes.push({name,passed,...details});console.log('PROBE',name,passed,JSON.stringify(details));};
const workflows=async(id)=>(await api.get(`/api/workflows?source_id=${id}`)).json();
async function saveDraft(){
 const response=page.waitForResponse(r=>r.url().endsWith('/api/workflows')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Save draft for review',exact:true}).click();
 const r=await response;assert.equal(r.status(),201,await r.text());
 const wf=await r.json();assert.equal(wf.enabled,false);
 await page.locator('pre.code').waitFor();
 assert.deepEqual(JSON.parse(await page.locator('pre.code').innerText()),wf.dsl);
 return wf;
}
async function approve(wf){
 const response=page.waitForResponse(r=>r.url().endsWith(`/api/workflows/${wf.id}/enable`));
 await page.getByRole('button',{name:'Approve & activate',exact:true}).click();
 assert.equal((await response).status(),200);
 await page.locator('pre.code').waitFor({state:'hidden'});
 assert.equal((await workflows(wf.source_id)).find(w=>w.id===wf.id).enabled,true);
}
const row=(name)=>page.getByRole('row').filter({hasText:name}).first();
async function waitProcessed(id){
 const deadline=Date.now()+180000;
 await new Promise(r=>setTimeout(r,100));
 while(Date.now()<deadline){
  const s=await(await api.get(`/api/sources/${id}`)).json();
  if(s.status==='failed')throw Error(s.error);
  if(s.status==='processed')return s;
  await new Promise(r=>setTimeout(r,400));
 }
 throw Error('Actual YOLO analysis timed out');
}
try{
 await page.goto(servers.web_url);
 await page.getByRole('heading',{name:'Video sources',exact:true}).waitFor();
 await page.getByText('Loading sources…',{exact:true}).waitFor({state:'hidden'});
 await page.getByText('Demo-safe · verified',{exact:true}).waitFor();
 record('Workspace loads with verified safe backend');
 const uploaded=page.waitForResponse(r=>r.url().endsWith('/api/sources/upload'));
 await page.locator('input[type=file]').setInputFiles(path.join(root,'data/demo/demo_bus_private_crop.mp4'));
 const source=await(await uploaded).json();result.source_id=source.id;
 await page.getByRole('heading',{name:'Zone workspace',exact:true}).waitFor();
 await page.locator('.canvas-wrap img').evaluate(img=>img.complete&&img.naturalWidth>0 || new Promise(r=>img.onload=r));
 record('Upload selects actual MP4', {source_id:source.id});
 await page.getByPlaceholder('Zone name').fill('QA Service Bay');
 await page.getByRole('button',{name:'Draw zone',exact:true}).click();
 const canvas=page.locator('canvas');await canvas.scrollIntoViewIfNeeded();
 const box=await canvas.boundingBox();assert(box&&box.width>0);
 for(const [x,y] of [[.6,.02],[.98,.02],[.98,.98],[.6,.98]])await page.mouse.click(box.x+x*box.width,box.y+y*box.height);
 const zoneResponse=page.waitForResponse(r=>r.url().endsWith('/api/zones')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Save zone (4)',exact:true}).click();
 const zone=await(await zoneResponse).json();result.zone_id=zone.id;
 record('Polygon persisted', {polygon:zone.polygon});
 await page.getByLabel('Rule name',{exact:true}).fill('QA Bus entry');
 await page.getByLabel(/^Object class/).selectOption('bus');
 await page.getByLabel(/^Zone/).selectOption(String(zone.id));
 assert.equal(await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).isDisabled(),true);
 record('Analysis unavailable until an approved rule exists');
 const draft=await saveDraft();result.first_workflow_id=draft.id;
 record('Canonical JSON shown; draft disabled',{workflow_id:draft.id});
 // A builder edit must invalidate this newly-saved unapproved draft.
 await page.getByLabel('Rule name',{exact:true}).fill('QA Bus entry revised');
 await page.locator('pre.code').waitFor({state:'hidden'});
 assert.equal((await workflows(source.id)).find(w=>w.id===draft.id).enabled,false);
 record('New-draft approval reset after field edit');
 const wf=await saveDraft();result.active_workflow_id=wf.id;
 await approve(wf);record('Explicit human approval activates saved JSON',{workflow_id:wf.id});
 await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).click();
 const complete=await waitProcessed(source.id);result.source=complete;
 const events=await(await api.get(`/api/events?source_id=${source.id}`)).json();
 const event=events.find(e=>e.workflow_id===wf.id&&e.type==='object_entered_zone');
 assert(event,'Real bus entry missing');assert.equal(event.class_name,'bus');assert.equal(event.action_status,'done');assert.equal(event.visual_status,null);
 assert.equal((await api.get(event.evidence_url)).status(),200);
 const actions=await(await api.get(`/api/events/${event.id}/actions`)).json();assert.equal(actions.length,1);assert.equal(actions[0].status,'success');
 const notes=await(await api.get('/api/notifications')).json();assert.equal(notes.filter(n=>n.event_id===event.id).length,1);
 result.event=event;result.actions=actions;
 await page.getByText(event.detail,{exact:true}).first().waitFor();
 await page.getByAltText('evidence frame',{exact:true}).first().click();
 await page.getByAltText('full evidence frame',{exact:true}).waitFor();
 await page.screenshot({path:path.join(qa,'evidence-desktop.png')});
 await page.locator('.modal-head button').click();
 record('Real YOLO -> event -> JPEG -> one local action',{frames:complete.frames_processed,avg_inference_ms:complete.avg_inference_ms,event_id:event.id,timestamp:event.video_timestamp,confidence:event.confidence});
 await page.screenshot({path:path.join(qa,'workspace-desktop.png'),fullPage:true});
 // Disable/re-enable uses the stored JSON and a fresh explicit approval click.
 await row(wf.name).getByRole('button',{name:'Disable',exact:true}).click();
 await row(wf.name).getByRole('button',{name:'Review & arm',exact:true}).waitFor();
 await row(wf.name).getByRole('button',{name:'Review & arm',exact:true}).click();
 await page.locator('pre.code').waitFor();
 assert.deepEqual(JSON.parse(await page.locator('pre.code').innerText()),wf.dsl);
 await approve(wf);record('Disable and reviewed re-enable work');
 await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).click();
 await waitProcessed(source.id);
 const replayActions=await(await api.get(`/api/events/${event.id}/actions`)).json();
 assert.equal(replayActions.length,1);
 const replayNotes=await(await api.get('/api/notifications')).json();assert.equal(replayNotes.filter(n=>n.event_id===event.id).length,1);
 record('Re-enabled replay preserves local action deduplication');
 // Editing creates a disabled replacement and leaves prior evidence intact.
 await row(wf.name).getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByText(/^Editing “/).waitFor();
 await page.getByLabel('Rule name',{exact:true}).fill('QA Bus dwell v2');
 await page.getByLabel(/^Trigger/).selectOption('dwell_in_zone');
 await page.getByLabel('Dwell seconds (≥)',{exact:true}).fill('1');
 const replacement=await saveDraft();
 assert.notEqual(replacement.id,wf.id);
 assert.equal((await workflows(source.id)).find(w=>w.id===wf.id).enabled,false);
 assert.equal((await api.get(event.evidence_url)).status(),200);
 await approve(replacement);result.replacement_workflow_id=replacement.id;
 record('Edit disables original; new reviewed version preserves old evidence',{old_id:wf.id,new_id:replacement.id});
 await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).click();
 await waitProcessed(source.id);
 const editedEvents=await(await api.get(`/api/events?source_id=${source.id}`)).json();
 const dwell=editedEvents.find(e=>e.workflow_id===replacement.id&&e.type==='dwell_in_zone');
 assert(dwell&&dwell.action_status==='done','Edited dwell rule did not produce a real executed event');
 result.edited_event=dwell;record('Edited dwell rule works with real YOLO',{event_id:dwell.id,timestamp:dwell.video_timestamp});
 // Independent UI probes; collect material defects without masking successful real inference.
 await row(wf.name).getByRole('button',{name:'Review & arm',exact:true}).click();
 await page.locator('pre.code').waitFor();
 await page.getByLabel('Rule name',{exact:true}).fill('A changed builder intent');
 check('Any builder change clears re-enable review',(await page.locator('pre.code').count())===0);
 if(await page.getByRole('button',{name:'Discard',exact:true}).count())await page.getByRole('button',{name:'Discard',exact:true}).click();
 await page.getByLabel('Rule name',{exact:true}).fill('QA fractional dwell');
 await page.getByLabel(/^Trigger/).selectOption('dwell_in_zone');
 await page.getByLabel('Dwell seconds (≥)',{exact:true}).fill('1.5');
 const fractional=await saveDraft();
 if(await page.getByRole('button',{name:'Discard',exact:true}).count())await page.getByRole('button',{name:'Discard',exact:true}).click();
 await row(fractional.name).getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByText(/^Editing “QA fractional dwell”/).waitFor();
 const value=await page.getByLabel('Dwell seconds (≥)',{exact:true}).inputValue();
 check('Editing preserves fractional geometric dwell',Number(value)===1.5,{saved:1.5,editor:value});
 // The QA-only DB insertion represents a persisted pre-demo visual workflow.
 const legacyCode=`from app.db import get_session,Workflow,init_db\nimport json\ninit_db();s=get_session()\nd=${JSON.stringify(JSON.stringify({...wf.dsl,name:'QA Legacy Teacher',visual_predicate:{prompt:'Is the bus hood open?',labels:['yes','no'],expected_label:'yes'}}))}\nw=Workflow(source_id=${source.id},name='QA Legacy Teacher',dsl=json.loads(d),enabled=True)\ns.add(w);s.commit();print(w.id);s.close()`;
 const legacyId=Number(execFileSync(path.join(root,'services/api/.venv/bin/python'),['-c',legacyCode],{encoding:'utf8',env:{...process.env,VISIONFLOW_DATA_DIR:servers.data,PYTHONPATH:path.join(root,'services/api'),VISIONFLOW_DEMO_SAFE:'true'}}).trim());
 await row('QA Legacy Teacher').waitFor();
 const legacyRow=row('QA Legacy Teacher');
 const edit=legacyRow.getByRole('button',{name:'Edit',exact:true});
 const unsafeEdit=(await edit.count())>0&&!await edit.isDisabled();
 check('Legacy Teacher workflow cannot be silently edited as geometric',!unsafeEdit,{workflow_id:legacyId,row:await legacyRow.innerText()});
 if(unsafeEdit){
  await edit.click();const downgraded=await saveDraft();
  result.legacy_downgrade={legacy_id:legacyId,saved_id:downgraded.id,visual_predicate:downgraded.dsl.visual_predicate};
 }
 // Backend rejects the blocked compiler and visual actions, even with provider configured.
 const compiled=await(await api.post('/api/workflows/compile',{data:{source_id:source.id,text:'When a bus enters QA Service Bay, open its hood'}})).json();
 assert.equal(compiled.ok,false);assert.equal(compiled.draft,null);
 const visual=await api.post('/api/workflows',{data:{...wf.dsl,visual_predicate:{prompt:'Is the hood open?',labels:['yes','no'],expected_label:'yes'}}});assert.equal(visual.status(),403);
 const stats=await(await api.get('/api/vlm/stats')).json();assert.equal(stats.live.teacher_available,false);
 record('Blocked compiler and Teacher creation; stats unavailable',{compiler_errors:compiled.errors,visual_status:visual.status()});
 // A new source must clear review and source-scoped history.
 let releaseStale, announceStale;let heldOnce=false;
 const staleGate=new Promise(r=>releaseStale=r);const staleReady=new Promise(r=>announceStale=r);
 await page.route(`**/api/workflows?source_id=${source.id}`,async route=>{
  if(heldOnce){await route.continue();return;}heldOnce=true;
  const response=await route.fetch();announceStale();await staleGate;await route.fulfill({response});
 });
 await staleReady;
 let releaseNew;const newGate=new Promise(r=>releaseNew=r);
 await page.route('**/api/workflows?source_id=*',async route=>{
  if(new URL(route.request().url()).searchParams.get('source_id')===String(source.id)){await route.fallback();return;}
  const response=await route.fetch();await newGate;await route.fulfill({response});
 });
 const secondUpload=page.waitForResponse(r=>r.url().endsWith('/api/sources/upload'));
 await page.locator('input[type=file]').setInputFiles({name:'QA second recording.mp4',mimeType:'video/mp4',buffer:fs.readFileSync(path.join(root,'data/demo/demo_bus_private_crop.mp4'))});
 const second=await(await secondUpload).json();result.second_source_id=second.id;
 await page.locator('tr.selected').filter({hasText:'QA second recording.mp4'}).waitFor();
 check('New source cannot inherit approval while its data loads',await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).isDisabled());
 releaseNew();
 await page.unroute('**/api/workflows?source_id=*');
 await page.locator('pre.code').waitFor({state:'hidden'});
 await page.getByText('No events yet',{exact:true}).waitFor();
 record('Switching source clears draft and previous events',{new_source_id:second.id});
 releaseStale();await page.waitForTimeout(400);
 check('Delayed old-source response cannot restore old workflows',(await page.getByRole('row').filter({hasText:replacement.name}).count())===0);
 assert.equal(await page.locator('tr.selected').getByRole('button',{name:'Run',exact:true}).isDisabled(),true);
 await page.unroute(`**/api/workflows?source_id=${source.id}`);
 await page.setViewportSize({width:390,height:844});
 await new Promise(r=>setTimeout(r,300));
 const dimensions=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
 check('Phone viewport has no page-wide horizontal overflow',dimensions.document<=dimensions.viewport+1,dimensions);
 const aligned=await page.locator('.canvas-wrap').evaluate(w=>{let i=w.querySelector('img').getBoundingClientRect(),c=w.querySelector('canvas').getBoundingClientRect();return Math.abs(i.width-c.width)<1&&Math.abs(i.height-c.height)<1;});
 check('Polygon overlay stays aligned on resize',aligned);
 await page.screenshot({path:path.join(qa,'workspace-mobile.png'),fullPage:true});
 // Real HTTP-error rendering and explicit non-safe/unverified backend UI admission tests.
 const errorPage=await browser.newPage();const errorMessages=[];errorPage.on('pageerror',e=>errorMessages.push(e.message));
 await errorPage.route('**/api/sources',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'QA simulated API outage'})}));
 await errorPage.goto(servers.web_url);await errorPage.getByText(/Cannot reach the API/).waitFor();
 check('HTTP failure is visible without a browser crash',errorMessages.length===0);await errorPage.close();
 for(const state of [false,null]){
  const locked=await browser.newPage();
  await locked.route('**/api/health',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(state===null?{status:'ok'}:{status:'ok',demo_safe:state})}));
  await locked.goto(servers.web_url);await locked.getByText('Loading sources…',{exact:true}).waitFor({state:'hidden'});
  check(`Demo mutations blocked for ${state===null?'unverified':'experimental'} backend`,await locked.locator('input[type=file]').isDisabled());
  await locked.close();
 }
 const egress=JSON.parse(fs.readFileSync(path.join(qa,'teacher-egress.json')));assert.deepEqual(egress,[]);record('Configured provider trap received zero HTTP requests');
 assert.deepEqual(result.console_errors,[]);record('No browser JavaScript errors');
 if(result.probes.some(p=>!p.passed)){result.validation_failed=true;process.exitCode=1;}
}catch(e){result.error=e.stack;await page.screenshot({path:path.join(qa,'browser-failure.png'),fullPage:true}).catch(()=>{});console.error(e.stack);process.exitCode=1;}
finally{fs.writeFileSync(path.join(qa,'journey.json'),JSON.stringify(result,null,2)+'\n');await api.dispose();await browser.close();}
