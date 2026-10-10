import fs from 'node:fs';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
const qa=path.resolve(process.env.DEMO_QA_DIR || '.agents/runtime/demo/qa-reproduction'),cfg=JSON.parse(fs.readFileSync(`${qa}/servers.json`));
const {chromium,request}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || path.join(process.cwd(),'node_modules/playwright-core/index.mjs')));
const b=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',chromiumSandbox:true});
const p=await b.newPage({viewport:{width:1440,height:1050}});
const api=await request.newContext({baseURL:cfg.api_url});
const result={target_sha:cfg.target_sha,viewports:[],known_limitations:[]};
try{
 const s=await(await api.get('/api/sources/1')).json();assert.equal(s.status,'processed');
 const events=await(await api.get('/api/events?source_id=1')).json();
 assert.equal(events.length,2);assert(events.every(e=>e.action_status==='done'&&e.visual_status===null));
 for(const event of events){
  const actions=await(await api.get(`/api/events/${event.id}/actions`)).json();
  assert.equal(actions.length,1);assert.equal(actions[0].status,'success');
 }
 assert.deepEqual(JSON.parse(fs.readFileSync(`${qa}/teacher-egress.json`)),[]);
 result.legacy_processing_completed=true;result.local_actions=2;result.teacher_http_requests=0;
 await p.goto(cfg.web_url);await p.getByText('Demo-safe · verified',{exact:true}).waitFor();
 await p.getByRole('button',{name:'Select',exact:true}).last().click();
 await p.getByRole('row').filter({hasText:'QA Bus dwell v2'}).first().waitFor();
 await p.locator('tr.selected').filter({hasText:'processed'}).waitFor();
 for(const width of [1440,1280,1024,390]){
  await p.setViewportSize({width,height:1050});await p.waitForTimeout(500);
  const dims=await p.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
  result.viewports.push({...dims,passed:dims.document<=dims.viewport+1});
  if(width>=1024)assert(dims.document<=dims.viewport+1);
  if(width===390&&dims.document>width+1)result.known_limitations.push({severity:'P2',scope:'Phone layout after a real source is selected',reproduction:'Select the uploaded 960x540 recording at viewport width 390px; the zone/builder grid expands the page to 1011px.',workaround:'Use the validated desktop viewport (1024px or wider) for this demo.'});
 }
 await p.setViewportSize({width:1440,height:1050});await p.waitForTimeout(500);
 await p.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
 await p.screenshot({path:`${qa}/workspace-desktop.png`,fullPage:true});
 await p.getByAltText('evidence frame',{exact:true}).last().click();
 await p.getByAltText('full evidence frame',{exact:true}).waitFor();
 await p.screenshot({path:`${qa}/evidence-desktop.png`});
 console.log(JSON.stringify(result));
}finally{fs.writeFileSync(`${qa}/viewport-validation.json`,JSON.stringify(result,null,2)+'\n');await api.dispose();await b.close();}
