"""QA_ONLY independent production-route probes; owned loopback only.
All data, labels and activation records below are reviewer-owned fixtures.
No actual Teacher/GPU, root data, or workflow actions are used.
"""
import asyncio, hashlib, io, json, socket, threading, time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import httpx, numpy as np, uvicorn
from PIL import Image
from fastapi import FastAPI
from app import config, db
from app.autolearn import api, labeling, service, fixtures, student, encoder

ROOT=Path('/tmp/visionflow-c-qa-5938b6d')
RESULT={}
class Provider:
    def __init__(self):
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                with owner.lock:
                    owner.calls+=1; owner.active+=1; owner.peak=max(owner.peak, owner.active)
                    owner.requests.append(body); owner.started.set()
                try:
                    if owner.mode=='trickle':
                        payload=json.dumps(owner.payload).encode()
                        self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
                        for byte in payload:
                            try: self.wfile.write(bytes([byte]));self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError): break
                            time.sleep(.02)
                    else:
                        time.sleep(owner.delay)
                        payload=json.dumps(owner.payload).encode()
                        self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
                        try:self.wfile.write(payload)
                        except (BrokenPipeError,ConnectionResetError): pass
                finally:
                    with owner.lock: owner.active-=1
        self.lock=threading.Lock(); self.calls=0;self.active=0;self.peak=0;self.requests=[]
        self.delay=.3;self.started=threading.Event();self.mode='normal'
        self.payload={'model':'QA_ONLY/actual-revision','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}],'usage':{'total_tokens':8}}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        config.VLM_BASE_URL=f'http://127.0.0.1:{self.server.server_port}/v1';config.VLM_MODEL='QA_ONLY/alias';config.VLM_API_KEY=''
    def reset(self,delay=.3):
        self.delay=delay;self.started.clear()
        with self.lock:self.calls=0;self.peak=0;self.requests=[]
P=Provider()
config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=4.;config.AUTOLEARN_LABEL_READ_TIMEOUT=4.
config.AUTOLEARN_LABEL_BUDGET_PER_TASK=1
config.AUTOLEARN_LABEL_JOB_MAX=1
config.AUTOLEARN_STUDENT_MIN_MARGIN=.1
config.ensure_dirs();db.init_db()
app=FastAPI();app.include_router(api.router)
# The actual router and service run through Uvicorn/AnyIO workers with real SQLite.
# Only the offline Student boundary uses a disclosed low-margin QA fixture.
class QAEncoder:
    weights_tag='QA_ONLY';
    def embed_bytes(self, blobs):return np.zeros((len(blobs),512),dtype=np.float32),[1.]*len(blobs)
class QAClassifier:
    def predict_proba(self,X):return np.full(len(X),.5)
real_get_encoder=encoder.get_encoder; real_load=student.StudentClassifier.load
encoder.get_encoder=lambda:QAEncoder()
student.StudentClassifier.load=staticmethod(lambda path:QAClassifier())
sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
port=sock.getsockname()[1]
server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.01)
base=f'http://127.0.0.1:{port}'
def call(method,path,**kw):
    with httpx.Client(timeout=8.) as c:
        r=c.request(method,base+path,**kw)
        try:out=r.json()
        except Exception:out=r.text[:300]
        return {'http':r.status_code,'body':out}
def jpeg(i):
    b=io.BytesIO();Image.new('RGB',(48,48),(10+i*20,20,35+i)).save(b,format='JPEG');return b.getvalue()
def task(name):
    return call('POST','/api/autolearn/tasks',json={'name':'QA_ONLY '+name,'visual_prompt':'is it occupied?','positive_label':'occupied','negative_label':'empty'})['body']['id']
def upload(t,i):return call('POST',f'/api/autolearn/tasks/{t}/images?session_id=QA_ONLY-{i}',files={'file':('qa.jpg',jpeg(i),'image/jpeg')})
def activate_fixture(t):
    # Deliberately seeded QA_ONLY record to reach the fallback endpoint, never a human approval.
    with db.get_session() as s:
        mv=db.ModelVersion(task_id=t,version=1,artifact_path='QA_ONLY stub',encoder_name='QA_ONLY',encoder_weights_version='QA_ONLY',preprocess_version='QA_ONLY',class_mapping={'empty':0,'occupied':1},dataset_hash='QA_ONLY',split_hash='QA_ONLY',train_count=4,val_count=2,test_count=4,threshold=.5,train_duration_ms=1,environment={'disclosure':'QA_ONLY fallback boundary stub'},status='active')
        s.add(mv);s.flush();s.get(db.AutoLearnTask,t).active_version_id=mv.id;s.commit()
def concurrent_pair(path, kw=None):
    P.reset(.4)
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(call,'POST',path,**(kw or {}))
        assert P.started.wait(2),'first provider request missing'
        second=pool.submit(call,'POST',path,**(kw or {}))
        out=[first.result(7),second.result(7)]
    return {'responses':out,'actual_provider_posts':P.calls,'provider_peak':P.peak}

# Actual API sync workers serialize HTTP but read budget before the first audit commits.
t=task('parallel labeling');upload(t,1)
RESULT['label_budget1_two_API_workers']=concurrent_pair(f'/api/autolearn/tasks/{t}/label')
RESULT['label_budget1_two_API_workers']['audit']=call('GET',f'/api/autolearn/tasks/{t}/audit')['body']
t=task('parallel fallback');activate_fixture(t)
RESULT['fallback_budget1_two_API_workers']=concurrent_pair(f'/api/autolearn/tasks/{t}/classify',{'files':{'file':('qa.jpg',jpeg(3),'image/jpeg')}})
RESULT['fallback_budget1_two_API_workers']['audit']=call('GET',f'/api/autolearn/tasks/{t}/audit')['body']

# New identical classify inputs are not stored in TrainingSample cache.
config.AUTOLEARN_LABEL_BUDGET_PER_TASK=5
P.reset(.01);t=task('repeat fallback');activate_fixture(t)
out=[call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('same.jpg',jpeg(4),'image/jpeg')}) for _ in range(3)]
RESULT['repeated_identical_fallback']={'responses':out,'actual_provider_posts':P.calls}

# Admission timeout has no provider post but is counted as spent.
config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=2.
config.AUTOLEARN_LABEL_READ_TIMEOUT=2.
P.reset(.6);t1=task('blocking admission');t2=task('queued admission');upload(t1,5);upload(t2,6)
with ThreadPoolExecutor(2) as pool:
    first=pool.submit(call,'POST',f'/api/autolearn/tasks/{t1}/label')
    assert P.started.wait(2)
    config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=.1  # QA_ONLY later caller has shorter admission deadline
    second=pool.submit(call,'POST',f'/api/autolearn/tasks/{t2}/label')
    outs=[first.result(4),second.result(4)]
RESULT['admission_timeout_accounting']={'responses':outs,'actual_provider_posts':P.calls,'audits':[call('GET',f'/api/autolearn/tasks/{t}/audit')['body'] for t in (t1,t2)]}
time.sleep(1.)
# Local oversized preflight is an error but has zero HTTP attempts.
config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=4.;P.reset(.01);t=task('oversized local preflight');upload(t,7)
original_cap=config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES;config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES=1
out=call('POST',f'/api/autolearn/tasks/{t}/label')
with db.get_session() as s:spent=service._teacher_attempts_spent(s,s.get(db.AutoLearnTask,t))
RESULT['local_preflight_accounting']={'response':out,'actual_provider_posts':P.calls,'budget_spent':spent}
config.AUTOLEARN_LABEL_MAX_IMAGE_BYTES=original_cap

# Supported direct async callers on two loops bypass process sync capacity.
P.reset(.25)
def async_worker():return asyncio.run(labeling.classify(jpeg(8),prompt='QA_ONLY async',labels=['occupied','empty'])).status
with ThreadPoolExecutor(2) as pool:statuses=list(pool.map(lambda _:async_worker(),range(2)))
RESULT['two_async_event_loops']={'statuses':statuses,'actual_provider_posts':P.calls,'provider_peak':P.peak}

# Transport cancellation closes a genuine trickle and a subsequent request succeeds.
P.mode='trickle';P.reset(0);config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=.2
start=time.monotonic();cand=labeling.classify_sync(jpeg(9),prompt='QA_ONLY trickle',labels=['occupied','empty'])
RESULT['trickle_deadline']={'status':cand.status,'seconds':time.monotonic()-start}
time.sleep(.1);P.mode='normal';P.delay=.01;config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=4.
RESULT['post_cancellation_reuse']=labeling.classify_sync(jpeg(9),prompt='QA_ONLY recovery',labels=['occupied','empty']).status

# Main-provider scoring envelope is represented as chat generation and loses raw scoring/revision.
P.payload={'model':'QA_ONLY/scoring-alias','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}],'usage':{'total_tokens':8},'providerexperimental_classification':{'method':'two_candidate_likelihood','confidence_calibrated':False,'candidate_scores':{'occupied':-2.,'empty':-3.},'forward_passes':2,'model_revision':'QA_ONLY/revision-pinned'}}
cand=labeling.classify_sync(jpeg(10),prompt='QA_ONLY scoring metadata',labels=['occupied','empty'])
RESULT['scoring_provenance']=asdict(cand)
# Numeric content + invalid confidences all explicitly fail; malformed model envelope still passes.
malformed=[]
for content in [42,{},True,json.dumps({'label':'occupied','confidence':True}),json.dumps({'label':'occupied','confidence':'0.9'}),json.dumps({'label':'occupied','confidence':float('nan')})]:
    P.payload={'model':'QA_ONLY/real','choices':[{'message':{'content':content}}]}
    malformed.append(labeling.classify_sync(jpeg(10),prompt='QA_ONLY malformed',labels=['occupied','empty']).status)
RESULT['malformed_content_confidence']=malformed
P.payload={'model':{'invalid':'object'},'choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}]}
RESULT['malformed_model']=asdict(labeling.classify_sync(jpeg(10),prompt='QA_ONLY malformed model',labels=['occupied','empty']))
P.reset(.01);t=task('malformed model route');upload(t,11)
RESULT['malformed_model_API']={'response':call('POST',f'/api/autolearn/tasks/{t}/label'),'actual_provider_posts':P.calls,'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}

# Physical one-video identity is split simply by arbitrary session names.
t=task('single physical video')
with db.get_session() as s:
    src=db.VideoSource(name='QA_ONLY ONE VIDEO',path='QA_ONLY fixture',type='upload');s.add(src);s.flush()
    for i in range(6):
        for j,lab in enumerate(['occupied','empty']):
            blob=jpeg(1+i*2+j);p=ROOT/f'physical-{i}-{j}.jpg';p.write_bytes(blob)
            s.add(db.TrainingSample(task_id=t,source_id=src.id,session_id=f'caller-name-{i}',group_key=f'caller-group-{i}',image_path=str(p),image_hash=hashlib.sha256(blob).hexdigest(),verified=True,verified_label=lab,verified_by='QA_ONLY fixture',origin='qa_synthetic'))
    s.commit();plan=service.build_split_plan(s,s.get(db.AutoLearnTask,t))
    RESULT['one_video_arbitrary_sessions']={'source_id':src.id,'counts':plan.counts,'group_split':plan.group_split,'dataset_hash':plan.dataset_hash,'split_hash':plan.split_hash}
server.should_exit=True;thread.join(2);P.server.shutdown()
(ROOT/'api-probes.json').write_text(json.dumps(RESULT,indent=2,default=str))
print(json.dumps(RESULT,indent=2,default=str))
