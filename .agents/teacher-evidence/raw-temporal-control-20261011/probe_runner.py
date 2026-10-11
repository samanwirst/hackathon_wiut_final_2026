from pathlib import Path
import os,sys,json,signal,subprocess,time,hashlib,urllib.request,urllib.error,base64,datetime
root=Path('/home/samanwirst/Desktop/hackathon_wiut_final_2026')
rt=root/'.agents/runtime/ten-hour'
out=rt/'TEACHER_EMERGENCY/temporal-capability-probe'
py=rt/'worktrees/B/.agents/runtime/local-teacher/.venv/bin/python'
harness=rt/'worktrees/B/scripts/experiments/local_teacher.py'
source=rt/'worktrees/B/.agents/runtime/local-teacher/cache/pinned-smolvlm'
image=rt/'TEACHER_EMERGENCY/nps-el-capitan-original.jpg'
model='HuggingFaceTB/SmolVLM-500M-Instruct'
revision='a7da5b986cb59b408707209984f360a5f4ad7e47'
start=time.monotonic(); proc=None; attempts=[]
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,data):(out/name).write_text(json.dumps(data,indent=2)+'\n')
def stop_signal(signum,frame): raise TimeoutError('bounded supervisor signal')
signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal);signal.signal(signal.SIGALRM,stop_signal);signal.alarm(240)
# An explicit isolated environment omits all credentials and disables downloads.
env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/home/samanwirst','LANG':'C.UTF-8','LOCAL_TEACHER_HOST':'127.0.0.1','LOCAL_TEACHER_PORT':'18082','LOCAL_TEACHER_MODEL_DIR':str(source),'LOCAL_TEACHER_EVIDENCE':str(out/'server-evidence'),'LOCAL_TEACHER_SCORING_LABELS':'','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','CUDA_VISIBLE_DEVICES':'0'}
argv=[str(py),str(harness)]
raw=image.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
save('PRECHECK.json',{'started_utc':utc(),'existing_pid':989679,'existing_service_preserved':Path('/proc/989679').exists(),'model':model,'revision':revision,'argv':argv,'explicit_environment':env,'harness_sha256':hashlib.sha256(harness.read_bytes()).hexdigest(),'input':{'path':str(image),'sha256':digest,'bytes':len(raw),'license':'Public domain; NPS provenance in parent input-provenance.json'},'previous_agent_probe_actual_calls':0,'max_probe_HTTP_attempts':2,'native_video_input':False,'temporal_positive_fixture_available':False})
def get_models(port):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models',timeout=2) as r:return json.load(r)
try:
 save('existing-models-before.json',get_models(18081))
 log=(out/'server.log').open('wb')
 proc=subprocess.Popen(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 save('START_RECEIPT.json',{'owned_pid':proc.pid,'supervisor_pid':os.getpid(),'started_utc':utc(),'argv':argv,'environment':env})
 while time.monotonic()-start<75:
  if proc.poll() is not None:raise RuntimeError(f'owned server exited {proc.returncode}')
  try:
   metadata=get_models(18082);save('raw-models-before.json',metadata);break
  except (urllib.error.URLError,TimeoutError):time.sleep(1)
 else:raise TimeoutError('startup exceeded75seconds; no inference attempted')
 if metadata['data'][0]['revision']!=revision or metadata['experimental']['output_mode']!='raw_generation':raise RuntimeError('incorrect actual model/revision/mode')
 dataurl='data:image/jpeg;base64,'+base64.b64encode(raw).decode()
 cases=[
 ('caption', [{'type':'image_url','image_url':{'url':dataurl}},{'type':'text','text':'Describe only what is visibly present in this image in one concise sentence. Do not infer events or actions.'}],1),
 ('identical-pair-no-change', [{'type':'text','text':'Frame A (earlier observation):'},{'type':'image_url','image_url':{'url':dataurl}},{'type':'text','text':'Frame B (later observation):'},{'type':'image_url','image_url':{'url':dataurl}},{'type':'text','text':'Compare the two supplied images. Is there a visibly supported physical state change of any object between Frame A and Frame B? Return JSON with decision MATCH, NO_MATCH, or UNCERTAIN; supporting_frames as A/B identifiers; evidence as a concise visible explanation. MATCH requires an actual visibly changed object. Identical images are NO_MATCH. If the evidence is insufficient choose UNCERTAIN. Do not infer an action from object presence or movement unless the images support it.'}],2)
 ]
 for name,content,count in cases:
  payload={'model':model,'messages':[{'role':'user','content':content}],'max_tokens':96,'stream':False}
  body=json.dumps(payload).encode();(out/f'{name}-request-wire.json').write_bytes(body)
  save(f'{name}-request-manifest.json',{'model':model,'revision':revision,'input_image_count':count,'input_sha256':[digest]*count,'source':'One unmodified natural photograph repeated; not distinct real temporal captures','text_parts':[p['text'] for p in content if p['type']=='text'],'max_tokens':96,'request_body_sha256':hashlib.sha256(body).hexdigest(),'request_body_bytes':len(body),'request_utc':utc(),'network':'loopback only','video_native':False,'no_positive_temporal_accuracy_claim':True})
  attempt={'case':name,'started_utc':utc(),'attempt':1,'retry':False};attempts.append(attempt);save('HTTP_ATTEMPTS.json',attempts)
  before=time.monotonic()
  request=urllib.request.Request('http://127.0.0.1:18082/v1/chat/completions',data=body,headers={'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(request,timeout=70) as response:status=response.status;response_body=response.read()
  except urllib.error.HTTPError as error:status=error.code;response_body=error.read()
  attempt.update(status=status,elapsed_seconds=time.monotonic()-before,finished_utc=utc());save('HTTP_ATTEMPTS.json',attempts)
  (out/f'{name}-response-wire.json').write_bytes(response_body)
  parsed=json.loads(response_body);save(f'{name}-response.json',parsed)
  if status==200:
   attempt['actual_model_generated_content']=parsed['choices'][0]['message']['content'];attempt['experimental_metrics']=parsed.get('experimental_metrics');save('HTTP_ATTEMPTS.json',attempts)
   print(json.dumps({'case':name,'status':status,'elapsed_seconds':attempt['elapsed_seconds'],'content':attempt['actual_model_generated_content'],'experimental_metrics':attempt['experimental_metrics']}),flush=True)
  else:print(json.dumps({'case':name,'status':status,'elapsed_seconds':attempt['elapsed_seconds'],'error':parsed}),flush=True)
 save('RESULT.json',{'status':'EXECUTED','HTTP_attempt_count':len(attempts),'successful_real_inferences':sum(x.get('status')==200 for x in attempts),'cases':attempts,'model':model,'revision':revision,'output_mode':'raw_generation','native_video_tested':False,'real_temporal_positive_tested':False,'bottle_opening_tested':False,'confidence_calibrated':False,'limitation':'Caption and repeated-static-image no-change control only. This cannot establish generic temporal action accuracy.'})
except BaseException as error:
 save('RESULT.json',{'status':'INCOMPLETE','error':f'{type(error).__name__}: {error}','actual_HTTP_attempt_count':len(attempts),'cases':attempts,'no_fabricated_result':True});print(f'{type(error).__name__}: {error}',flush=True)
finally:
 signal.alarm(0)
 if proc and proc.poll() is None:
  os.killpg(proc.pid,signal.SIGTERM)
  try:proc.wait(timeout=7)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
 cleanup={'stopped_utc':utc(),'owned_secondary_pid':proc.pid if proc else None,'owned_secondary_returncode':proc.poll() if proc else None,'existing_pid989679_alive':Path('/proc/989679').exists(),'total_elapsed_seconds':time.monotonic()-start}
 try:save('existing-models-after.json',get_models(18081));cleanup['existing_models_responding']=True
 except Exception as error:cleanup['existing_models_responding']=False;cleanup['existing_models_error']=type(error).__name__
 save('CLEANUP.json',cleanup)
 print(json.dumps(cleanup),flush=True)
