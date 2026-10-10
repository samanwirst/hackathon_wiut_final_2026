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


# QA_ONLY ordinary multi-sample label job, all real HTTP and SQLite.
config.AUTOLEARN_LABEL_BUDGET_PER_TASK=5
config.AUTOLEARN_LABEL_JOB_MAX=3
P.reset(.01)
t=task('ordinary batch transaction boundary')
for i in [1,2,3]:upload(t,i)
start=time.monotonic()
response=call('POST',f'/api/autolearn/tasks/{t}/label')
with db.get_session() as s:
 rows=[{'id':x.id,'status':x.teacher_status,'label':x.teacher_label} for x in s.query(db.TrainingSample).filter_by(task_id=t)]
 reservations=[{'slot':x.slot,'status':x.status} for x in s.query(db.LabelingReservation).filter_by(task_id=t)]
out={'response':response,'seconds':time.monotonic()-start,'actual_provider_posts':P.calls,'samples':rows,'ledger':reservations,'audit':call('GET',f'/api/autolearn/tasks/{t}/audit')['body']}
server.should_exit=True;thread.join(2);P.server.shutdown()
(ROOT/'batch-label.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps(out,indent=2,default=str))
