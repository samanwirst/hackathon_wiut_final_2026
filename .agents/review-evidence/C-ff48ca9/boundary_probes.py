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

ROOT=Path('/tmp/visionflow-c-final-ff48ca9')
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

# QA_ONLY additional production HTTP + SQL scheduling, actual transport preserved.
from sqlalchemy import event
from sqlalchemy.orm import Session

def ledger(t):
    with db.get_session() as s:
        return [{'slot':x.slot,'status':x.status,'key':x.dedupe_key} for x in s.query(db.LabelingReservation).filter_by(task_id=t).order_by(db.LabelingReservation.slot)]

def force_interleave(name, same_key=False):
    config.AUTOLEARN_LABEL_BUDGET_PER_TASK=1 if not same_key else 5
    t=task(name);activate_fixture(t);upload(t,1)
    P.reset(.25)
    gap=threading.Event();resume=threading.Event();once={'blocked':False}
    def sql_gap(conn,cursor,statement,parameters,context,executemany):
        if 'ORDER BY autolearn_labeling_reservations.slot DESC' in statement and not once['blocked']:
            once['blocked']=True;gap.set()
            assert resume.wait(5),'QA_ONLY slot-read scheduling timeout'
    event.listen(db._engine,'before_cursor_execute',sql_gap)
    try:
        with ThreadPoolExecutor(2) as pool:
            paused=pool.submit(call,'POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',jpeg(1 if same_key else 2),'image/jpeg')})
            assert gap.wait(5),'classify did not reach slot-read gap'
            other=pool.submit(call,'POST',f'/api/autolearn/tasks/{t}/label')
            assert P.started.wait(5),'label did not actually send'
            resume.set()
            responses=[paused.result(8),other.result(8)]
        return {'responses':responses,'actual_provider_posts':P.calls,'provider_peak':P.peak,'ledger':ledger(t),'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}
    finally:event.remove(db._engine,'before_cursor_execute',sql_gap);resume.set()

RESULT['budget_count_before_other_insert']=force_interleave('count read races newest slot')
RESULT['inflight_same_key_count_slot_gap']=force_interleave('same key races insert',same_key=True)

# Same ACTUAL local server JSON envelope, no server/model imports or GPU access.
P.reset(.01)
P.payload={'model':'QA_ONLY/verified-actual-model','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}],
'usage':{'prompt_tokens':12,'completion_tokens':0,'total_tokens':12},
'experimental_metrics':{'revision':'QA_ONLY/pinned-revision','image_count':1,'input_tokens':12,'output_tokens':0,
'scoring':{'method':'candidate_sequence_softmax','uncalibrated':True,'candidate_labels':['occupied','empty'],
'candidate_token_ids':[[10,11],[12]],'candidate_log_likelihoods':[-2.,-3.38629436112],'normalized_probabilities':[.8,.2],
'model_forward_calls':2,'actual_model_processed_tokens':27,'output_is_generated_json':False}}}
t=task('actual local scoring envelope');upload(t,3)
RESULT['actual_local_scoring']={'label':call('POST',f'/api/autolearn/tasks/{t}/label'),'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}
with db.get_session() as s:RESULT['actual_local_scoring']['teacher_raw']=s.query(db.TrainingSample).filter_by(task_id=t).one().teacher_raw
RESULT['actual_local_scoring']['candidate']=asdict(labeling.classify_sync(jpeg(3),prompt='QA_ONLY same envelope',labels=['occupied','empty']))

# Attempted transport timeout must stay spent; admission timeout is in original.
config.AUTOLEARN_LABEL_BUDGET_PER_TASK=1;config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=.1
P.reset(.4);t=task('sent timeout durable');upload(t,4)
out=call('POST',f'/api/autolearn/tasks/{t}/label');time.sleep(.45)
RESULT['sent_timeout_not_released']={'response':out,'actual_provider_posts':P.calls,'ledger':ledger(t),'retry':call('POST',f'/api/autolearn/tasks/{t}/label')}
config.AUTOLEARN_LABEL_OVERALL_TIMEOUT=4.

# Local invalid URL never sends. Capacity was acquired but that is not HTTP spend.
P.reset(.01);t=task('local invalid configuration');upload(t,5)
real_url=config.VLM_BASE_URL;config.VLM_BASE_URL='QA_ONLY-invalid-scheme://provider'
RESULT['invalid_local_config']={'response':call('POST',f'/api/autolearn/tasks/{t}/label'),'actual_provider_posts':P.calls,'ledger':ledger(t)}
config.VLM_BASE_URL=real_url

# Committed reservation survives actual job audit commit failure (production DB).
P.reset(.01);t=task('audit commit fault');upload(t,6)
def fail_audit_commit(s):
    if any(isinstance(x,db.LabelingAudit) and x.task_id==t for x in s.new):
        raise RuntimeError('QA_ONLY injected job audit commit failure after actual HTTP response')
event.listen(Session,'before_commit',fail_audit_commit)
try:response=call('POST',f'/api/autolearn/tasks/{t}/label')
finally:event.remove(Session,'before_commit',fail_audit_commit)
RESULT['DB_fault_spend_survives']={'response':response,'actual_provider_posts':P.calls,'ledger':ledger(t),'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}

# Bounded strict optional envelope fields: bad usage/provenance must be honest.
P.reset(.01);config.AUTOLEARN_LABEL_BUDGET_PER_TASK=5
base_payload={'model':'QA_ONLY/actual','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}]}
variants={'usage_wrong_types':{'usage':{'prompt_tokens':True,'completion_tokens':'3','total_tokens':float('nan'),'unbounded_extra':'X'*10000}},
'oversize_model':{'model':'M'*200},
'oversize_scoring':{'providerexperimental_classification':{'method':'two_candidate_likelihood','candidate_scores':{f'candidate{i}':float(i) for i in range(1000)},'model_revision':'r','forward_passes':2}}}
RESULT['optional_envelope_types']={}
for name,fields in variants.items():
    P.payload={**base_payload,**fields};cand=labeling.classify_sync(jpeg(7),prompt='QA_ONLY malformed optional',labels=['occupied','empty'])
    RESULT['optional_envelope_types'][name]={'status':cand.status,'model':cand.model,'raw_bytes':len(json.dumps(cand.raw,default=str)),'usage':cand.raw.get('usage') if cand.raw else None,'score_count':len(cand.candidate_scores or {})}

# Cache retains original confidence/model/method and validates data on reuse.
P.payload=base_payload;P.reset(.01);t=task('cache metadata');activate_fixture(t)
first=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',jpeg(8),'image/jpeg')})
second=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',jpeg(8),'image/jpeg')})
with db.get_session() as s:
    cache=s.query(db.LabelingCache).filter_by(task_id=t).one()
    stored={'model':cache.model,'confidence':cache.confidence,'has_method':hasattr(cache,'method')}
    cache.label='QA_ONLY unsupported corrupted cached label';cache.confidence=2.;s.commit()
third=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',jpeg(8),'image/jpeg')})
RESULT['cache_provenance_validation']={'first':first,'second':second,'stored':stored,'after_invalid_cache':third,'actual_provider_posts':P.calls}

server.should_exit=True;thread.join(2);P.server.shutdown()
(ROOT/'boundaries.json').write_text(json.dumps(RESULT,indent=2,default=str));print(json.dumps(RESULT,indent=2,default=str))
