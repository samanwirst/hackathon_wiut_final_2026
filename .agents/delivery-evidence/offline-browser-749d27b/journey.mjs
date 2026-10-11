import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
const root='/home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/worktrees/D';
const qa='/home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/delivery/offline-browser';
const servers=JSON.parse(fs.readFileSync(path.join(qa,'servers.json')));
const credentials=JSON.parse(fs.readFileSync('/home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/delivery/public-candidate/credentials.json'));
const started=performance.now();
const {chromium,request}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || '/tmp/visionflow-browser-s4z2hln7/node_modules/playwright-core/index.mjs'));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,chromiumSandbox:true});
const context=await browser.newContext({viewport:{width:1440,height:1050},httpCredentials:credentials});
const page=await context.newPage();
const api=await request.newContext({baseURL:servers.api_url,httpCredentials:credentials});
let admission=Promise.resolve();let previous=0;
async function pacedRequest(){const ticket=admission.then(async()=>{const delay=Math.max(0,160-(Date.now()-previous));if(delay)await new Promise(r=>setTimeout(r,delay));previous=Date.now();});admission=ticket;await ticket;}
const apiGet=api.get.bind(api);api.get=async(...args)=>{await pacedRequest();return apiGet(...args);};
const result={target_sha:servers.target_sha,steps:[],probes:[],console_errors:[],request_failures:[],blocked_external_requests:[],container_network:'internal isolated Docker bridge; no external default route',qa_request_pacing_ms:160,request_pacing_note:'Automated browser and verification GETs share a 160ms admission interval to stay below the existing authenticated gateway rate limit. This is functional rehearsal, not performance measurement; the previous unpaced automation encountered the expected HTTP503 rate limit.',browser_context:'fresh Chromium profile and empty cache',harness_note:'Zone bottom .85 avoids the visible point-placement hint; earlier .95 last click landed on that hint and never reached canvas. Original failed execution is archived.',paid_compute:false,student_activated:false};
await context.route('**/*',async route=>{const url=new URL(route.request().url());if(url.origin===servers.web_url){if(url.pathname.startsWith('/api/'))await pacedRequest();return route.continue();}result.blocked_external_requests.push({origin:url.origin,resource_type:route.request().resourceType()});return route.abort('internetdisconnected');});
page.on('pageerror',e=>result.console_errors.push(e.message));
page.on('requestfailed',r=>result.request_failures.push({url:r.url(),error:r.failure()?.errorText}));
const record=(step,details={})=>{result.steps.push({step,elapsed_ms:Math.round(performance.now()-started),...details});console.log(step,JSON.stringify(details));};
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
 await page.locator('input[type=file]').setInputFiles('/home/samanwirst/Desktop/hackathon_wiut_final_2026/.agents/runtime/ten-hour/delivery/new-photo-input/result/new-photo-upper-bus.mp4');
 const source=await(await uploaded).json();result.source_id=source.id;
 await page.getByRole('heading',{name:'Zone workspace',exact:true}).waitFor();
 await page.locator('.canvas-wrap img').evaluate(img=>img.complete&&img.naturalWidth>0 || new Promise(r=>img.onload=r));
 record('Upload selects actual MP4', {source_id:source.id});
 await page.getByPlaceholder('Zone name').fill('QA Service Bay');
 await page.getByRole('button',{name:'Draw zone',exact:true}).click();
 const canvas=page.locator('canvas');await canvas.scrollIntoViewIfNeeded();
 const box=await canvas.boundingBox();assert(box&&box.width>0);
 for(const [x,y] of [[.25,.2],[.6,.2],[.6,.85],[.25,.85]])await page.mouse.click(box.x+x*box.width,box.y+y*box.height);
 await page.getByRole('button',{name:'Save zone (4)',exact:true}).waitFor();
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

 await page.locator('.canvas-wrap').scrollIntoViewIfNeeded();
 await page.locator('.canvas-wrap').screenshot({path:path.join(qa,'zone-workspace.png')});
 await page.screenshot({path:path.join(qa,'final-desktop.png')});
 const stats=await(await api.get('/api/vlm/stats')).json();assert.equal(stats.live.teacher_available,false);result.teacher_stats=stats;
 assert.deepEqual(result.console_errors,[]);
 result.total_duration_ms=Math.round(performance.now()-started);
 record('Accepted fallback journey recorded; experimental paths unavailable');
}catch(e){result.error=e.stack;await page.screenshot({path:path.join(qa,'browser-failure.png'),fullPage:true}).catch(()=>{});console.error(e.stack);process.exitCode=1;}
finally{fs.writeFileSync(path.join(qa,'journey.json'),JSON.stringify(result,null,2)+'\n');await api.dispose();await context.close();await browser.close();}
