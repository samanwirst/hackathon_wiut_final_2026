"""QA_ONLY two-process actual production API; owned TCP provider, no model fit."""
import os,sys,json,time,socket,threading,subprocess,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import httpx
from PIL import Image
from app import db,config
from app.autolearn import service
ROOT=Path('/tmp/visionflow-c-qa-5938b6d'); state={'calls':0,'active':0,'peak':0};lock=threading.Lock()
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
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
env=os.environ.copy();env.update({'VLM_BASE_URL':f'http://127.0.0.1:{provider.server_port}/v1','VLM_MODEL':'QA_ONLY/alias','VLM_API_KEY':'','AUTOLEARN_LABEL_BUDGET_PER_TASK':'1','AUTOLEARN_LABEL_JOB_MAX':'1','AUTOLEARN_LABEL_OVERALL_TIMEOUT':'5','VISIONFLOW_DEMO_SAFE':'true','PYTHONDONTWRITEBYTECODE':'1'})
log=open(ROOT/'multiworker-server.txt','w')
p=subprocess.Popen([sys.executable,'-m','uvicorn','qa_worker_app:app','--app-dir',str(ROOT),'--host','127.0.0.1','--port',str(port),'--workers','2','--log-level','error'],env=env,stdout=log,stderr=subprocess.STDOUT)
base=f'http://127.0.0.1:{port}'
try:
    seen=set()
    for i in range(150):
        try:
            with httpx.Client(timeout=.4) as c:r=c.get(base+'/api/autolearn/status');seen.add(r.headers.get('X-QA-Worker'))
            if len(seen)>=2:break
        except Exception:pass
        time.sleep(.03)
    start=threading.Barrier(8)
    def job(i):
        start.wait(3)
        with httpx.Client(timeout=8) as c:
            r=c.post(base+f'/api/autolearn/tasks/{tid}/label')
            return {'http':r.status_code,'worker_pid':r.headers.get('X-QA-Worker'),'body':r.json()}
    with ThreadPoolExecutor(8) as pool:responses=list(pool.map(job,range(8)))
    with httpx.Client(timeout=3) as c:audit=c.get(base+f'/api/autolearn/tasks/{tid}/audit').json()
    result={'disclosure':'QA_ONLY actual production app, 2 Uvicorn worker processes; response header only wrapper','ready_workers':sorted(seen),'responses':responses,'actual_provider_posts':state['calls'],'provider_peak':state['peak'],'audit_count':len(audit)}
    (ROOT/'multiworker-probes.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:
    p.terminate()
    try:p.wait(8)
    except subprocess.TimeoutExpired:p.kill();p.wait(2)
    provider.shutdown();log.close()
