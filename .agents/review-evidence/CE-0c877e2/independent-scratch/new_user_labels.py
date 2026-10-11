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

for name,pos,neg in [('positive_sorts_first','damaged','undamaged'),('positive_sorts_last','occupied','empty'),('reversed_supported_labels','empty','occupied')]:
    created=call('POST','/api/autolearn/tasks',json={'name':'QA_ONLY '+name,'visual_prompt':'is the condition present?','positive_label':pos,'negative_label':neg});t=created['body']['id']
    generated=fixtures.generate_sessions(n_sessions=5,per_class_per_session=3,task_slug=name)
    with db.get_session() as s:
        taskrow=s.get(db.AutoLearnTask,t)
        for x in generated:
            row=service.import_image(s,taskrow,image_bytes=x.image_bytes,session_id=x.session_id,group_key=x.group_key,origin='qa_synthetic')
            if row:service.review_sample(s,row,verified_label=pos if x.label=='occupied' else neg,reviewer='QA_ONLY simulated reviewer')
    trained=call('POST',f'/api/autolearn/tasks/{t}/train');vid=trained['body']['version_id']
    with db.get_session() as s:
        v=s.get(db.ModelVersion,vid);clf=student.StudentClassifier.load(v.artifact_path)
        provenance={'registry_class_mapping':v.class_mapping,'actual_saved_classes':clf.classes,'extra':clf.extra}
    R[name]={'create':created,'train':trained,'provenance':provenance,'gate':call('GET',f'/api/autolearn/versions/{vid}/gate'),'evaluate':call('POST',f'/api/autolearn/versions/{vid}/evaluate'),'activate':call('POST',f'/api/autolearn/versions/{vid}/activate',json={'approve':True,'approver':'QA_ONLY simulated approval'})}
(ROOT/'new-user-labels.json').write_text(json.dumps(R,indent=2));print(json.dumps(R,indent=2))
