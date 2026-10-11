import os, subprocess, sys, time, json
from pathlib import Path
root=Path('/tmp/visionflow-m3-emergency-review-0c877e2');repo=Path.cwd();py=str(repo/'services/api/.venv/bin/python')
env=os.environ.copy();env.update({'TMPDIR':'/tmp','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','VISIONFLOW_THREADS':'2','VISIONFLOW_DEMO_SAFE':'true','VLM_BASE_URL':'','VLM_MODEL':'','VLM_API_KEY':'','TORCH_HOME':str(root/'torch'),'PYTHONPATH':str(repo/'services/api')+':'+str(root)})
receipt_path=root/'additional-receipts.json'
rows=json.loads(receipt_path.read_text()) if receipt_path.exists() else []
for script in sys.argv[1:]:
    cmd=[py,str(root/script)] if script.endswith('.py') else ['node',str(root/script)]
    e=env.copy();e['VISIONFLOW_DATA_DIR']=str(root/('data-'+script.replace('.','-')))
    start=time.monotonic()
    with (root/(script+'.log')).open('w') as log:
        try:exit=subprocess.run(cmd,env=e,stdout=log,stderr=subprocess.STDOUT,timeout=150).returncode
        except subprocess.TimeoutExpired:exit='TIMEOUT'
    row={'script':script,'command':cmd,'exit':exit,'seconds':round(time.monotonic()-start,3),'QA_ONLY':True};rows.append(row)
    receipt_path.write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
