"""QA_ONLY two-process actual production API; owned TCP provider, no model fit."""
import os,sys,json,time,socket,threading,subprocess,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import httpx
from PIL import Image
from app import db,config
from app.autolearn import service
ROOT=Path('/tmp/visionflow-c-final-ff48ca9'); state={'calls':0,'active':0,'peak':0};lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        with lock:state['calls']+=1;state['active']+=1;state['peak']=max(state['peak'],state['active'])
        try:
            time.sleep(.4)
            body=json.dumps({'model':'QA_ONLY/actual','choices':[{'message':{'content':json.dumps({'label':'occupied','confidence':.8})}}]}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        finally:
            with lock:state['active']-=1
provider=ThreadingHTTPServer(('127.0.0.1',0),Handler);provider.daemon_threads=True
threading.Thread(target=provider.serve_forever,daemon=True).start()
config.ensure_dirs();db.init_db()
with db.get_session() as s:
    task=service.create_task(s,name='QA_ONLY multiworker',visual_prompt='occupied?',positive_label='occupied',negative_label='empty');tid=task.id
    b=io.BytesIO();Image.new('RGB',(48,48),(50,70,90)).save(b,format='JPEG');service.import_image(s,task,image_bytes=b.getvalue(),session_id='QA_ONLY')
# Two genuine production Uvicorn processes; separate ports control the exact worker.
for f in ['worker-paused.json','worker-resume']:(ROOT/f).unlink(missing_ok=True)
env=os.environ.copy();env.update({'VLM_BASE_URL':f'http://127.0.0.1:{provider.server_port}/v1','VLM_MODEL':'QA_ONLY/alias','VLM_API_KEY':'','AUTOLEARN_LABEL_BUDGET_PER_TASK':'1','AUTOLEARN_LABEL_JOB_MAX':'1','AUTOLEARN_LABEL_OVERALL_TIMEOUT':'5','VISIONFLOW_DEMO_SAFE':'true','PYTHONDONTWRITEBYTECODE':'1'})
ports=[];procs=[];logs=[]
try:
    for i in range(2):
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();ports.append(port)
        log=open(ROOT/f'race-worker-{i}.txt','w');logs.append(log)
        procs.append(subprocess.Popen([sys.executable,'-m','uvicorn','qa_race_worker:app','--app-dir',str(ROOT),'--host','127.0.0.1','--port',str(port),'--log-level','error'],env=env,stdout=log,stderr=subprocess.STDOUT))
    workers=[]
    for port in ports:
        for i in range(150):
            try:
                with httpx.Client(timeout=.3) as c:r=c.get(f'http://127.0.0.1:{port}/api/autolearn/status')
                if r.status_code==200:workers.append(r.headers['X-QA-Worker']);break
            except Exception:pass
            time.sleep(.03)
        else:raise RuntimeError('worker startup timed out')
    def call_worker(i,pause=False):
        with httpx.Client(timeout=12) as c:
            r=c.post(f'http://127.0.0.1:{ports[i]}/api/autolearn/tasks/{tid}/label',headers={'X-QA-Pause':'yes' if pause else 'no'})
            return {'worker':r.headers.get('X-QA-Worker'),'http':r.status_code,'body':r.json()}
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(call_worker,0,True)
        for i in range(400):
            if (ROOT/'worker-paused.json').exists():break
            time.sleep(.01)
        else:raise RuntimeError('did not reach durable count/slot gap')
        second=pool.submit(call_worker,1,False)
        for i in range(400):
            if state['calls']:break
            time.sleep(.01)
        else:raise RuntimeError('other worker did not send actual POST')
        (ROOT/'worker-resume').touch()
        responses=[first.result(15),second.result(15)]
    with db.get_session() as s:reservations=[{'slot':x.slot,'status':x.status,'key':x.dedupe_key} for x in s.query(db.LabelingReservation).filter_by(task_id=tid)]
    out={'disclosure':'QA_ONLY real production HTTP, 2 distinct Uvicorn processes, pause ONLY before the max-slot SQL select after count','ready_workers':workers,'responses':responses,'actual_provider_posts':state['calls'],'provider_peak':state['peak'],'ledger':reservations}
    (ROOT/'multiworker-race.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
finally:
    (ROOT/'worker-resume').touch()
    for p in procs:p.terminate()
    for p in procs:
        try:p.wait(8)
        except subprocess.TimeoutExpired:p.kill();p.wait(2)
    provider.shutdown()
    for log in logs:log.close()
