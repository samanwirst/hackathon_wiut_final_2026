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

ROOT=Path('/tmp/visionflow-m3-emergency-review-0c877e2')
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

from sqlalchemy import text
from copy import deepcopy
def ledger(t):
    with db.get_session() as s:return [{'id':r.id,'slot':r.slot,'status':r.status} for r in s.query(db.LabelingReservation).filter_by(task_id=t)]
def stored_sample(t):
    with db.get_session() as s:
        row=s.query(db.TrainingSample).filter_by(task_id=t).one()
        return {'status':row.teacher_status,'label':row.teacher_label,'confidence':row.teacher_confidence,'raw':row.teacher_raw}
real_url=config.VLM_BASE_URL
RESULT['preflight']={}
for name,url in [('bad_port','http://127.0.0.1:notaport/v1'),('out_of_range_port','http://127.0.0.1:70000/v1'),('control_character_url','http://127.0.0.1:1234/\x00'),('missing_model','')]:
    P.reset(.01);t=task('preflight '+name);upload(t,1)
    if name=='missing_model':config.VLM_MODEL=''
    else:config.VLM_BASE_URL=url
    RESULT['preflight'][name]={'response':call('POST',f'/api/autolearn/tasks/{t}/label'),'actual_provider_posts':P.calls,'ledger':ledger(t),'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}
    config.VLM_BASE_URL=real_url;config.VLM_MODEL='QA_ONLY/alias'
P.reset(.01);t=task('invalidimage upload')
RESULT['preflight']['invalid_image_upload']={'response':call('POST',f'/api/autolearn/tasks/{t}/images?session_id=QA_ONLY',files={'file':('QA_ONLY.jpg',b'not an image','image/jpeg')}),'actual_provider_posts':P.calls,'ledger':ledger(t)}
P.reset(.01);t=task('invalidimage replaced before label');upload(t,1)
with db.get_session() as s:Path(s.query(db.TrainingSample).filter_by(task_id=t).one().image_path).write_bytes(b'QA_ONLY invalid image data')
RESULT['preflight']['invalid_stored_image']={'response':call('POST',f'/api/autolearn/tasks/{t}/label'),'actual_provider_posts':P.calls,'ledger':ledger(t),'sample':stored_sample(t)}
# Actual read-only server contract mirrored in owned TCP response. Not genuine Teacher evidence.
scoring_payload={'model':'QA_ONLY/actual-model','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}],
'usage':{'prompt_tokens':12,'completion_tokens':0,'total_tokens':12},
'experimental_metrics':{'revision':'QA_ONLY/actual-revision','scoring':{'method':'candidate_sequence_softmax','uncalibrated':True,'candidate_labels':['occupied','empty'],'candidate_token_ids':[[10,11],[12]],'candidate_log_likelihoods':[-2.,-3.38629436112],'normalized_probabilities':[.8,.2],'model_forward_calls':2,'actual_model_processed_tokens':27,'output_is_generated_json':False}}}
P.payload=deepcopy(scoring_payload);P.reset(.01);t=task('scoring fallback provenance');activate_fixture(t)
first=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA_ONLY.jpg',jpeg(2),'image/jpeg')})
second=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA_ONLY.jpg',jpeg(2),'image/jpeg')})
with db.get_session() as s:
    cache=s.query(db.LabelingCache).filter_by(task_id=t).one()
    cache_fields={col.name:getattr(cache,col.name) for col in db.LabelingCache.__table__.columns}
RESULT['fallback_scoring_provenance']={'first':first,'cache_hit':second,'cache_fields':cache_fields,'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body'],'actual_provider_posts':P.calls}
# Persisted cache requires full validation; none of these can be received from strict adapter.
RESULT['cache_validation']={}
for kind in ['missing_confidence','wrong_model','wrong_image_hash']:
    P.payload=deepcopy(scoring_payload);P.reset(.01);t=task('cache '+kind);activate_fixture(t)
    first=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA_ONLY.jpg',jpeg(3),'image/jpeg')})
    with db.get_session() as s:
        cache=s.query(db.LabelingCache).filter_by(task_id=t).one()
        if kind=='missing_confidence':cache.confidence=None
        elif kind=='wrong_model':cache.model='QA_ONLY unrelated model'
        else:cache.image_hash='QA_ONLY unrelated image bytes'
        s.commit()
    after=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA_ONLY.jpg',jpeg(3),'image/jpeg')})
    RESULT['cache_validation'][kind]={'first':first,'after':after,'actual_provider_posts':P.calls}
# Actual scoring metadata is untrusted: malformed probabilities must not be persisted as valid scores.
RESULT['scoring_validation']={}
variants={
    'invalid_probabilities':{'normalized_probabilities':[2.,-1.]},
    'wrong_candidate_labels':{'candidate_labels':['unrelated','bogus']},
    'unequal_lengths':{'normalized_probabilities':[.8]},
    'missing_tokens_logs':{'candidate_token_ids':None,'candidate_log_likelihoods':None},
    'overflow_optional':{'normalized_probabilities':[10**400,True],'model_forward_calls':True,'actual_model_processed_tokens':10**400},
    'oversize_optional':{'candidate_labels':['occupied']*1000,'normalized_probabilities':[.5]*1000,'candidate_token_ids':[[1]]*1000,'candidate_log_likelihoods':[float('nan')]*1000},
}
for name,fields in variants.items():
    P.payload=deepcopy(scoring_payload);P.payload['experimental_metrics']['scoring'].update(fields);P.reset(.01)
    t=task('scoring '+name);upload(t,4)
    response=call('POST',f'/api/autolearn/tasks/{t}/label')
    RESULT['scoring_validation'][name]={'response':response,'actual_provider_posts':P.calls,'sample':stored_sample(t),'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body'],'ledger':ledger(t)}
# Batch partial results remain durable after second sample receives malformed envelope.
P.reset(.01);config.AUTOLEARN_LABEL_BUDGET_PER_TASK=5;config.AUTOLEARN_LABEL_JOB_MAX=3
P.payload=deepcopy(scoring_payload);t=task('partial batch results')
for i in [1,2,3]:upload(t,i)
real_classify=labeling.classify_sync
counter={'i':0}
def intermittent(*a,**kw):
    counter['i']+=1
    P.payload=deepcopy(scoring_payload)
    if counter['i']==2:P.payload['choices'][0]['message']['content']='QA_ONLY invalid JSON'
    return real_classify(*a,**kw)
labeling.classify_sync=intermittent
RESULT['partial_batch']={'response':call('POST',f'/api/autolearn/tasks/{t}/label'),'actual_provider_posts':P.calls,'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body'],'ledger':ledger(t)}
with db.get_session() as s:RESULT['partial_batch']['samples']=[{'id':r.id,'label':r.teacher_label,'status':r.teacher_status,'raw':r.teacher_raw} for r in s.query(db.TrainingSample).filter_by(task_id=t)]
labeling.classify_sync=real_classify
server.should_exit=True;thread.join(2);P.server.shutdown()
(ROOT/'acceptance-transport.json').write_text(json.dumps(RESULT,indent=2,default=str));print(json.dumps(RESULT,indent=2,default=str))
