"""Serve accepted CE commit privately with a NEW isolated pilot database."""
from pathlib import Path
import argparse,json,os,signal,socket,subprocess,time
ROOT=Path(__file__).resolve().parents[3];RT=ROOT/'.agents/runtime/ten-hour'
p=argparse.ArgumentParser();p.add_argument('--sha',required=True);p.add_argument('--port',type=int,default=8096);p.add_argument('--isolated-blocked-experiment',action='store_true');a=p.parse_args()
wt=Path(json.loads((RT/'plan.json').read_text())['streams']['CE']['worktree'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip()==a.sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=wt,text=True).strip()
review=json.loads((RT/'CE/m3-emergency-review/review.json').read_text());assert review['target_sha']==a.sha
if a.isolated_blocked_experiment:
 closed=json.loads((RT/'CE/FINAL_STATUS.json').read_text())
 assert review['verdict']=='CHANGES_REQUIRED' and closed['owner_exception_exhausted'] and not closed['accepted_for_integration']
else:assert review['verdict']=='PASS'
with socket.socket() as s:s.bind(('127.0.0.1',a.port))
out=RT/'CE'/(('blocked-nonactioning-pilot-' if a.isolated_blocked_experiment else 'approved-pilot-')+a.sha[:7]);out.mkdir(exist_ok=False);data=out/'data';data.mkdir()
env={**os.environ,'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1','VISIONFLOW_DEMO_SAFE':'true','VISIONFLOW_DATA_DIR':str(data),'VLM_BASE_URL':'http://127.0.0.1:18081/v1','VLM_MODEL':'HuggingFaceTB/SmolVLM-500M-Instruct','VLM_API_KEY':'','AUTOLEARN_LABEL_MAX_TOKENS':'64','AUTOLEARN_LABEL_BUDGET_PER_TASK':'24','AUTOLEARN_LABEL_JOB_MAX':'24','PYTHONPATH':str(wt/'services/api')+':'+str(wt/'packages/vision')}
log=(out/'private-api.txt').open('w');child=subprocess.Popen([str(wt/'services/api/.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port',str(a.port),'--workers','1'],cwd=wt/'services/api',env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt={'owner_pid':os.getpid(),'child_pid':child.pid,'target_sha':a.sha,'api':f'http://127.0.0.1:{a.port}','data':str(data),'evidence':str(out/'evidence'),'started_epoch':time.time(),'student_activation_authorized':False,'independent_verdict':review['verdict'],'accepted_for_integration':not a.isolated_blocked_experiment,'scope':'ISOLATED_UNACCEPTED_NONACTIONING_EXPERIMENT' if a.isolated_blocked_experiment else 'ACCEPTED_PRIVATE_PILOT'};(out/'server-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
def stop(*_):
 if child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=8)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 log.close();raise SystemExit(0)
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
while child.poll() is None:time.sleep(2)
log.close();raise SystemExit(child.returncode)
