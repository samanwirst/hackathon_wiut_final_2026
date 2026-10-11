// Execute the exact committed inline scripts. DOM, HTTP and camera are QA_ONLY
// simulations; this does not claim browser rendering or physical phone capture.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const root='/tmp/visionflow-live-review-1-f5aeae3';
const staticRoot=process.cwd()+'/services/api/app/live/static/';
const results=[];
class Element {
  constructor(id=''){ this.id=id; this.value=''; this.textContent=''; this.innerHTML=''; this.children=[]; this.listeners={}; this.classes=new Set(); this.src=''; }
  get classList(){ return {add:c=>this.classes.add(c),remove:c=>this.classes.delete(c),contains:c=>this.classes.has(c)}; }
  addEventListener(type,fn){ this.listeners[type]=fn; }
  appendChild(x){ this.children.push(x); }
  dispatch(type){ this.listeners[type]?.(); }
}
function page(file){
  const elements=new Map(); const calls=[]; const timers=[];
  const document={cookie:'vf_live_csrf=QA_ONLY_CSRF',visibilityState:'visible',
    getElementById:id=>{ if(!elements.has(id))elements.set(id,new Element(id)); return elements.get(id); },
    createElement:tag=>new Element(tag),addEventListener(){}};
  const context={document,console,location:{protocol:'https:',host:'live.qa.invalid'},Blob,URL,
    fetch:async()=>({ok:true,json:async()=>({teacher_available:false})}),
    setTimeout:fn=>{timers.push(fn);return timers.length;},setInterval:()=>1,clearInterval(){},
    WebSocket:class {constructor(url){this.url=url;this.readyState=1;this.binaryType='';this.bufferedAmount=0;this.sent=[];calls.push({socket:this});}send(data){this.sent.push(data);}close(){this.onclose?.({code:1000});}},
    navigator:{},performance:{now:()=>1234},Date,JSON};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(staticRoot+'common.js','utf8'),context,{filename:'common.js'});
  const html=fs.readFileSync(staticRoot+file,'utf8');
  const inline=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');
  vm.runInContext(inline,context,{filename:file});
  context.api=async(path,opts={})=>{calls.push({path,opts});return {ok:true,task_version:1};};
  return {context,document,elements,calls,timers,get:id=>document.getElementById(id),
    eval:s=>vm.runInContext(s,context)};
}
async function test(name,fn){ try{await fn();results.push({name,status:'PASS'});}catch(e){results.push({name,status:'FAIL',reason:e.message});} }
const task={name:'QA_ONLY truck watch',object_class:'truck',zone:{type:'full_frame',polygon:[[0,0],[1,0],[1,1],[0,1]]},
  trigger:'dwell_in_zone',duration_seconds:17,threshold:null,action:'notify',focus:false,visual_observation:null,explanation:'QA_ONLY'};
const plan={status:'ok',task,original_text:'QA_ONLY watch a truck for seventeen seconds',provenance:{model:'QA_ONLY'}};
(async()=>{
  await test('common API sends backend CSRF cookie and exact typed task',async()=>{
    const p=page('judges.html');let request;
    // Restore actual common.js api after replacing it in page().
    vm.runInContext(fs.readFileSync(staticRoot+'common.js','utf8').replace('const CSRF_COOKIE =','var CSRF_COOKIE_REEXEC =').replaceAll('getCookie(CSRF_COOKIE)','getCookie(CSRF_COOKIE_REEXEC)'),p.context);
    p.context.fetch=async(path,opts)=>{request={path,opts};return {ok:true,json:async()=>({ok:true})};};
    await p.context.api('/api/live/rooms/QA_ONLY/task/activate',{method:'POST',body:{task}});
    assert.equal(request.opts.headers['X-CSRF-Token'],'QA_ONLY_CSRF');
    assert.equal(request.opts.credentials,'same-origin');
    assert.deepEqual(JSON.parse(request.opts.body),{task});
  });
  await test('canonical JSON is shown and draft does not auto-activate',async()=>{
    const p=page('judges.html');p.context.showDraft(plan);
    assert.equal(p.get('draftJson').textContent,JSON.stringify(task,null,2));
    assert.equal(p.calls.filter(c=>c.path?.endsWith('/activate')).length,0);
    await p.get('activateBtn').onclick();
    assert.deepEqual(p.calls.find(c=>c.path?.endsWith('/activate')).opts.body.task,task);
  });
  await test('editing a displayed draft invalidates approval control',async()=>{
    const p=page('judges.html');p.context.showDraft(plan);p.get('prompt').dispatch('input');
    await p.get('activateBtn').onclick();
    assert.equal(p.calls.filter(c=>c.path?.endsWith('/activate')).length,0);
    assert.ok(p.get('activateBtn').classList.contains('hidden'));
  });
  await test('editing while plan is inflight invalidates the late result',async()=>{
    const p=page('judges.html');p.get('prompt').value=plan.original_text;
    let resolvePlan;p.context.api=()=>new Promise(resolve=>{resolvePlan=resolve;});
    const pending=p.get('planBtn').onclick();
    p.get('prompt').value='QA_ONLY new different request';p.get('prompt').dispatch('input');
    resolvePlan(plan);await pending;
    assert.ok(p.get('activateBtn').classList.contains('hidden'),'stale plan becomes approvable after prompt edit');
  });
  await test('disabled task offers re-enable without phone reset',async()=>{
    const p=page('judges.html');p.context.renderState({task,task_version:2,task_enabled:false,task_paused:false,
      metrics:{},events:[],notifications:[]});
    assert.ok(p.get('taskControls').children.some(c=>/enable|resume/i.test(c.textContent)),'disabled task has no re-enable control');
  });
  await test('unknown model cost stays unknown in the UI',async()=>{
    const p=page('judges.html');p.context.showDraft(plan);
    assert.ok(!p.get('planMeta').textContent.includes('$0.0000'),'missing cost rendered as $0.0000');
  });
  await test('unsupported response cannot be approved and text is escaped',async()=>{
    const p=page('judges.html');p.context.showDraft({status:'unsupported',unsupported_reason:'<img src=x onerror=x>',provenance:{}});
    assert.ok(p.get('activateBtn').classList.contains('hidden'));
    assert.ok(p.get('draftNote').innerHTML.includes('&lt;img'));
  });
  await test('camera invokes getUserMedia, draws actual source, pairs metadata and bytes',async()=>{
    const p=page('camera.html');const requests=[],draws=[];
    const stream={getTracks:()=>[{stop(){}}]};
    p.context.navigator.mediaDevices={getUserMedia:async(opts)=>{requests.push(opts);return stream;}};
    const video=p.get('video');video.play=async()=>{};video.videoWidth=1280;video.videoHeight=720;
    const canvas=p.get('canvas');canvas.getContext=()=>({drawImage:(...a)=>draws.push(a)});
    canvas.toBlob=(fn,type,quality)=>fn(new Blob(['QA_ONLY_BYTES'],{type}));
    await p.context.startStreaming();
    assert.equal(requests.length,1);assert.equal(requests[0].audio,false);
    const socket=p.calls.find(c=>c.socket).socket;
    assert.equal(socket.url,'wss://live.qa.invalid/api/live/ws/camera');
    await p.context.captureAndSend();
    assert.equal(draws[0][0],video);assert.equal(canvas.width,640);assert.equal(canvas.height,360);
    assert.equal(JSON.parse(socket.sent[0]).seq,1);assert.equal(socket.sent[1].byteLength,13);
    p.context.stopStreaming();
  });
  await test('camera permission refusal surfaces a retryable error',async()=>{
    const p=page('camera.html');p.context.navigator.mediaDevices={getUserMedia:async()=>{throw new Error('QA_ONLY denied');}};
    await p.context.startStreaming();
    assert.ok(p.get('banner').textContent.includes('permission failed'));
    assert.equal(p.calls.filter(c=>c.socket).length,0);
  });
  await test('expired camera session stops reconnect loop and shows reauthentication',async()=>{
    const p=page('camera.html');const stream={getTracks:()=>[{stop(){}}]};
    p.context.navigator.mediaDevices={getUserMedia:async()=>stream};p.get('video').play=async()=>{};
    await p.context.startStreaming();
    p.calls.find(c=>c.socket).socket.onclose({code:4401});
    assert.equal(p.timers.length,0,'4401 schedules automatic reconnect with expired cookie');
    assert.ok(/auth|expir|PIN/.test(p.get('banner').textContent));
  });
  fs.writeFileSync(root+'/frontend-results.json',JSON.stringify({QA_ONLY:true,method:'exact scripts in node:vm with simulated DOM/HTTP/media',results},null,2));
  console.log(JSON.stringify(results,null,2));
  console.log(`${results.filter(r=>r.status==='PASS').length} passed, ${results.filter(r=>r.status==='FAIL').length} failed`);
  process.exitCode=results.some(r=>r.status==='FAIL')?1:0;
})();
