"""QA_ONLY local version/ML probes. Genuine frozen CPU encoder and real fitted
Students, own procedural images and simulated review/approval fixtures only.
No actual GPU/provider, root images/signoff, or workflow actions.
"""
import hashlib,json,threading,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, torch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import config,db
from app.autolearn import api,service,fixtures,student,encoder
ROOT=Path('/tmp/visionflow-m3-emergency-review-0c877e2');R={};torch.set_num_threads(2)
config.ensure_dirs();db.init_db();app=FastAPI();app.include_router(api.router)
client=TestClient(app,raise_server_exceptions=False)
def call(method,path,**kw):
    r=client.request(method,path,**kw)
    try:b=r.json()
    except Exception:b=r.text[:200]
    return {'http':r.status_code,'body':b}
def task(name):return call('POST','/api/autolearn/tasks',json={'name':'QA_ONLY '+name,'visual_prompt':'is it occupied?','positive_label':'occupied','negative_label':'empty'})['body']['id']
def samples(t,n=5):
    generated=fixtures.generate_sessions(n_sessions=n,per_class_per_session=3,task_slug=f't{t}')
    with db.get_session() as s:
        task=s.get(db.AutoLearnTask,t)
        for x in generated:
            row=service.import_image(s,task,image_bytes=x.image_bytes,session_id=x.session_id,group_key=x.group_key,origin='qa_synthetic')
            if row is not None:service.review_sample(s,row,verified_label=x.label,reviewer='QA_ONLY procedural signoff fixture')

def manifest(vid):
    with db.get_session() as s:return sorted((x.sample_id,x.image_hash,x.verified_label,x.split) for x in s.query(db.ModelVersionSample).filter_by(model_version_id=vid))
def filehash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# QA_ONLY genuine train/save/load/evaluation; no realprovider; all approvals simulated.

# QA_ONLY fault cleanup ownership after two preexisting genuine versions.
t=task('cleanup only owned files');samples(t)
a=call('POST',f'/api/autolearn/tasks/{t}/train');b=call('POST',f'/api/autolearn/tasks/{t}/train')
with db.get_session() as s:
 paths=[Path(x.artifact_path) for x in s.query(db.ModelVersion).filter_by(task_id=t)]
hashes={str(p):filehash(p) for p in paths};model_dir=paths[0].parent
sentinel=model_dir/'.QA_ONLY-other-job-owned.tmp';sentinel.write_bytes(b'QA_ONLY do not clean another job')
original_eval=service._evaluate_rows
service._evaluate_rows=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('QA_ONLY post-save failure'))
failure=call('POST',f'/api/autolearn/tasks/{t}/train');service._evaluate_rows=original_eval
with db.get_session() as s:rows=[{'id':x.id,'version':x.version,'status':x.status,'exists':Path(x.artifact_path).exists()} for x in s.query(db.ModelVersion).filter_by(task_id=t)]
out={'failure':failure,'previous_artifacts_unchanged':{p:filehash(p)==h for p,h in hashes.items()},'other_temp_preserved':sentinel.read_bytes()==b'QA_ONLY do not clean another job','rows':rows,'files':[p.name for p in model_dir.iterdir()]}
(ROOT/'cleanup-ownership.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
