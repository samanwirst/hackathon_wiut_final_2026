import os, subprocess, time, json
from pathlib import Path
root=Path('/tmp/visionflow-m3-emergency-review-0c877e2')
repo=Path.cwd(); py=str(repo/'services/api/.venv/bin/python')
env=os.environ.copy();env.update({'TMPDIR':'/tmp','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','VISIONFLOW_THREADS':'2','VISIONFLOW_DEMO_SAFE':'true','VLM_BASE_URL':'','VLM_MODEL':'','VLM_API_KEY':'','TORCH_HOME':str(root/'torch'),'PYTHONPATH':str(repo/'services/api')+':'+str(root)})
tests=['tests/unit/test_autolearn_core.py','tests/unit/test_autolearn_labeling_transport.py','tests/unit/test_autolearn_c_service.py','tests/unit/test_autolearn_c_transport.py','tests/unit/test_autolearn_c2_regressions.py','tests/unit/test_autolearn_emergency_regressions.py','tests/integration/test_autolearn_api.py']
jobs=[('focused',120,[py,'-m','pytest',*tests,'-q','-p','no:cacheprovider','--basetemp='+str(root/'pytest-temp')]),('safety',60,[py,'-m','pytest','tests/unit/test_config_demo_safe.py','tests/integration/test_demo_safe.py','tests/integration/test_m2_visual.py::test_geometric_workflow_makes_zero_vlm_calls','-q','-p','no:cacheprovider','--basetemp='+str(root/'pytest-safety')])]
for script in ['boundary_probes.py','multiworker_race.py','batch_label_probe.py','artifact_probes.py','version_probes.py','cleanup_probe.py','physical_provenance_probe.py','optional_overflow.py']:
    jobs.append((script,120,[py,str(root/script)]))
for script in ['ui_create.cjs','ui_all_actions.cjs','ui_detail_mismatch.cjs']:
    jobs.append((script,30,['node',str(root/script)]))
receipts=[]
for name,deadline,cmd in jobs:
    e=env.copy();e['VISIONFLOW_DATA_DIR']=str(root/('data-'+name.replace('.','-')))
    started=time.monotonic()
    try:
        with (root/(name+'.log')).open('w') as log:r=subprocess.run(cmd,env=e,stdout=log,stderr=subprocess.STDOUT,timeout=deadline)
        exit=r.returncode
    except subprocess.TimeoutExpired:exit='TIMEOUT'
    row={'name':name,'command':cmd,'exit':exit,'seconds':round(time.monotonic()-started,3),'QA_ONLY':True}
    receipts.append(row);(root/'focused-receipts.json').write_text(json.dumps(receipts,indent=2));print(json.dumps(row),flush=True)
