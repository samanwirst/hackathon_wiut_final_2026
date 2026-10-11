// QA_ONLY: execute actual transpiled component with deterministic hooks/fetch.
// No production UI approval/activation and no workflow request is sent.
const fs=require('fs'),vm=require('vm');
const {createRequire}=require('module');
const req=createRequire(process.cwd()+'/apps/web/package.json');
const ts=req('typescript');
const source=fs.readFileSync('apps/web/app/autolearn/page.tsx','utf8');
const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
const A={id:1,name:'QA_ONLY A',visual_prompt:'A?',positive_label:'A_yes',negative_label:'A_no',status:'trained',active_version_id:101};
const B={id:2,name:'QA_ONLY B',visual_prompt:'B?',positive_label:'B_yes',negative_label:'B_no',status:'trained',active_version_id:201};
const detail=t=>({task:t,counts:{samples:1,verified:0,pending_teacher:1,sessions:1},versions:[{id:t.active_version_id,version:1,status:'trained',metrics:{f1:1},threshold:.5,train_count:4,val_count:2,test_count:4}]});
const sample=t=>[{id:t.id*10,session_id:'QA_ONLY',image_url:'/qa-only.jpg',teacher_status:'pending',teacher_label:null,verified:false}];
const tick=()=>new Promise(r=>setImmediate(r));
const C={...A,id:3,name:'QA_ONLY newly created',status:'collecting',active_version_id:null};
const out={disclosure:'QA_ONLY deterministic actual-component harness; owned fetch fixtures only'};
async function scenario(kind){
 let state=[],refs=[],idx=0,refIdx=0,mounted=false,effects=[],posts=[],getCalls=[],deferredResolve;
 const hooks={useState(init){const n=idx++;if(!(n in state))state[n]=init;return [state[n],x=>{state[n]=typeof x==='function'?x(state[n]):x}]},useRef(init){const n=refIdx++;return refs[n]||(refs[n]={current:init})},useCallback(fn){return fn},useEffect(fn){if(!mounted)effects.push(fn)}};
 const jsx=(type,props)=>({type,props:props||{}});
 const fakeFetch=async(url,options={})=>{
  const path=new URL(url).pathname; const search=new URL(url).search;
  if(options.method==='POST'){
   if(path==='/api/autolearn/tasks'){posts.push({path,body:options.body});return {ok:true,json:async()=>C};}
   posts.push({path,search,body:options.body instanceof FormData?Array.from(options.body.keys()):options.body});
   if(path.endsWith('/label')||path.endsWith('/classify')||path.endsWith('/images'))return new Promise(r=>{deferredResolve=payload=>r({ok:!payload.detail,json:async()=>payload})});
   return {ok:true,json:async()=>({activated:true})};
  }
  getCalls.push(path);
  if(path==='/api/autolearn/tasks/3')return {ok:true,json:async()=>({task:C,counts:{samples:0,verified:0,pending_teacher:0,sessions:0},versions:[]})};
  if(path==='/api/autolearn/tasks/3/samples')return {ok:true,json:async()=>[]};
  if(path.endsWith('/shadow'))return new Promise(r=>{deferredResolve=payload=>r({ok:!payload.detail,json:async()=>payload})});
  let val=path==='/api/autolearn/tasks'?[A,B,C]:path.endsWith('/status')?{provider_configured:true,gate:{min_f1:.75,min_test:4}}:path.endsWith('/samples')?sample(path.includes('/1/')?A:B):detail(path.endsWith('/1')?A:B);
  return {ok:true,json:async()=>val};
 };
 const sandbox={exports:{},process:{env:{NEXT_PUBLIC_API_URL:'http://QA_ONLY'}},fetch:fakeFetch,FormData,URLSearchParams,URL,console,require:n=>n==='react'?hooks:n==='react/jsx-runtime'?{jsx,jsxs:jsx,Fragment:'fragment'}:req(n)};
 vm.runInNewContext(code,sandbox);
 const render=()=>{idx=refIdx=0;const tree=sandbox.exports.default();mounted=true;return tree};
 const nodes=tree=>{let r=[];function visit(n){if(Array.isArray(n))return n.forEach(visit);if(!n||typeof n!=='object')return;r.push(n);visit(n.props?.children)}visit(tree);return r};
 const label=n=>{const v=n?.props?.children;function tx(x){if(Array.isArray(x))return x.map(tx).join('');if(x&&typeof x==='object')return tx(x.props?.children);return x==null?'':String(x)}return tx(v)};
 const button=(tree,text)=>nodes(tree).find(n=>n.type==='button'&&label(n).includes(text));
 let tree=render();effects.forEach(fn=>fn());await tick();await tick();tree=render();
 if(kind==='create'){
  nodes(tree).find(n=>n.type==='input'&&n.props.placeholder?.startsWith('Task name')).props.onChange({target:{value:'QA_ONLY newly created'}});tree=render();
  nodes(tree).find(n=>n.type==='input'&&n.props.placeholder?.startsWith('Visual prompt')).props.onChange({target:{value:'QA_ONLY is bay occupied?'}});tree=render();
  await button(tree,'Create task').props.onClick();await tick();await tick();tree=render();
  return {selected:state[2],detailTask:state[3]?.task.id,busy:state[7],disabledControls:nodes(tree).filter(n=>n.type==='button'&&n.props.disabled).map(label),posts,getCalls};
 }
 button(tree,'QA_ONLY A').props.onClick();await tick();await tick();tree=render();
 let pending;
 if(kind==='label')pending=button(tree,'Run Teacher labeling').props.onClick();
 if(kind==='shadow')pending=button(tree,'Run shadow comparison').props.onClick();
 if(kind==='upload'||kind==='upload_error'){
  const sessionInput=nodes(tree).find(n=>n.type==='input'&&String(n.props.placeholder||'').includes('Session ID'));sessionInput.props.onChange({target:{value:'QA_ONLY real upload session'}});tree=render();
  const sourceInput=nodes(tree).find(n=>n.type==='input'&&String(n.props.placeholder||'').includes('Source ID'));sourceInput.props.onChange({target:{value:'7'}});tree=render();
  const input=nodes(tree).filter(n=>n.type==='input'&&n.props.type==='file')[0];pending=input.props.onChange({target:{files:[new Blob(['QA_ONLY'],{type:'image/jpeg'})],value:'qa.jpg'}});
 }
 if(kind==='classify'){
  const input=nodes(tree).filter(n=>n.type==='input'&&n.props.type==='file')[1];
  pending=input.props.onChange({target:{files:[new Blob(['QA_ONLY'],{type:'image/jpeg'})],value:'qa.jpg'}});
 }
 button(tree,'QA_ONLY B').props.onClick();await tick();await tick();tree=render();
 const before={selected:state[2],task:state[3]?.task.id,samples:state[4].map(s=>s.id)};
 deferredResolve(kind==='upload_error'?{detail:'QA_ONLY upload rejected 413'}:kind==='label'?{status:'done'}:kind==='upload'?{imported:true}:kind==='shadow'?{version:1,items:[{task_id:1,action:'none',teacher_label:'A_yes'}]}:{task_id:1,label:'A_yes',action:'none'});
 await pending;await tick();await tick();tree=render();
 const after={selected:state[2],detailTask:state[3]?.task.id,busy:state[7],disabledControls:nodes(tree).filter(n=>n.type==='button'&&n.props.disabled).map(label),visibleReviewButtons:nodes(tree).filter(n=>n.type==='button').map(label).filter(x=>/_(yes|no)/.test(x)),shadow:state[5],classifyResult:state[11],error:state[6],visibleErrorBanner:nodes(tree).filter(n=>n.type==='div'&&n.props.className==='banner error').map(label)};
 if(kind==='label'){await button(tree,'Activate').props.onClick();await tick();}
 return {before,after,posts,getCalls};
}
(async()=>{for(const k of ['create'])out[k]=await scenario(k);fs.writeFileSync('/tmp/visionflow-m3-emergency-review-0c877e2/ui-create.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2))})().catch(e=>{console.error(e);process.exitCode=1});
