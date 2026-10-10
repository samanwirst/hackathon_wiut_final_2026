"""Isolated one-run production browser QA; SIGTERM stops only owned servers."""
from pathlib import Path
import http.server
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time

ROOT = Path.cwd()
QA = Path(os.environ.get('DEMO_QA_DIR', str(ROOT / '.agents/runtime/demo/qa-reproduction'))).resolve()
QA.mkdir(parents=True, exist_ok=True)
sha = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
web = Path(tempfile.mkdtemp(prefix='visionflow-demo-web-'))
tracked = subprocess.check_output(['git','ls-files','apps/web'], cwd=ROOT, text=True).splitlines()
for name in tracked:
    source = ROOT/name
    dest = web/source.relative_to(ROOT/'apps/web')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)
(web/'node_modules').symlink_to(ROOT/'apps/web/node_modules', target_is_directory=True)
env = {**os.environ, 'NEXT_PUBLIC_API_URL':'http://127.0.0.1:8092',
       'NEXT_TELEMETRY_DISABLED':'1', 'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2',
       'OPENBLAS_NUM_THREADS':'2'}
with (QA/'frontend-build.log').open('w') as log:
    build = subprocess.run(['npm','run','build'], cwd=web, env=env, stdout=log,
                           stderr=subprocess.STDOUT, timeout=900)
if build.returncode:
    raise SystemExit('Frontend build failed; inspect frontend-build.log')
hits = []
class Trap(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        hits.append({'path':self.path, 'time':time.time()})
        (QA/'teacher-egress.json').write_text(json.dumps(hits,indent=2)+'\n')
        self.send_response(503); self.end_headers(); self.wfile.write(b'QA trap; unavailable')
    def log_message(self, *_):
        pass
trap=http.server.ThreadingHTTPServer(('127.0.0.1',8093),Trap)
threading.Thread(target=trap.serve_forever,daemon=True).start()
(QA/'teacher-egress.json').write_text('[]\n')
data = Path(tempfile.mkdtemp(prefix='visionflow-demo-browser-data-'))
api_env = {**env, 'VISIONFLOW_DEMO_SAFE':'true','VISIONFLOW_DATA_DIR':str(data),
           'VLM_BASE_URL':'http://127.0.0.1:8093/v1','VLM_MODEL':'qa-trap-model',
           'VLM_API_KEY':'', 'CORS_ORIGINS':'http://127.0.0.1:3092,http://localhost:3092'}
children=[]
logs=[]
def stop(*_):
    for child in children:
        if child.poll() is None: child.terminate()
    for child in children:
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill();child.wait()
    trap.shutdown()
    for log in logs: log.close()
    raise SystemExit(0)
for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,stop)
for label,argv,cwd,child_env in [
    ('api',[str(ROOT/'services/api/.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port','8092'],ROOT/'services/api',api_env),
    ('web',['node','node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3092'],web,env),
]:
    log=(QA/f'{label}.log').open('w');logs.append(log)
    children.append(subprocess.Popen(argv,cwd=cwd,env=child_env,stdout=log,stderr=subprocess.STDOUT))
(QA/'servers.json').write_text(json.dumps({'target_sha':sha,'pid':os.getpid(),
    'children':[c.pid for c in children], 'web':str(web),'data':str(data),
    'frontend_build_exit':build.returncode,'api_url':'http://127.0.0.1:8092',
    'web_url':'http://127.0.0.1:3092'},indent=2)+'\n')
print('Owned isolated browser servers starting: http://127.0.0.1:3092; receipt',QA/'servers.json',flush=True)
while True: signal.pause()
