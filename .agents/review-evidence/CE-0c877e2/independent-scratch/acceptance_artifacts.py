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

from sqlalchemy import text
# Fresh genuine CPU Student: all approvals and labels are QA_ONLY simulations.
t=task('independent complete identity acceptance');samples(t)
train1=call('POST',f'/api/autolearn/tasks/{t}/train');vid=train1['body']['version_id']
train2=call('POST',f'/api/autolearn/tasks/{t}/train');vid2=train2['body']['version_id']
with db.get_session() as s:
    v=s.get(db.ModelVersion,vid);path=Path(v.artifact_path);original_metrics=dict(v.metrics);threshold=v.threshold
    p2=Path(s.get(db.ModelVersion,vid2).artifact_path)
    row=s.query(db.TrainingSample).filter_by(task_id=t,verified_label='empty').first();blob=Path(row.image_path).read_bytes()
original=path.read_bytes()
enc=encoder.get_encoder()
R['baseline']={'train1':train1,'train2':train2,'encoder_frozen':enc.frozen(),'artifact_sha256':filehash(path),'reevaluation':call('POST',f'/api/autolearn/versions/{vid}/evaluate')}
with db.get_session() as s:original_metrics=dict(s.get(db.ModelVersion,vid).metrics)
def gate():return call('GET',f'/api/autolearn/versions/{vid}/gate')
def evaluate():return call('POST',f'/api/autolearn/versions/{vid}/evaluate')
def activate():return call('POST',f'/api/autolearn/versions/{vid}/activate',json={'approve':True,'approver':'QA_ONLY simulated'})
def classify():return call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA_ONLY.jpg',blob,'image/jpeg')})
def restore():
    path.write_bytes(original)
    with db.get_session() as s:
        v=s.get(db.ModelVersion,vid);v.metrics=dict(original_metrics);v.threshold=threshold;v.artifact_path=str(path);s.commit()
R['normal_activation']=activate()
# Same actual artifact and manifest; threshold is a different decision rule.
with db.get_session() as s:s.get(db.ModelVersion,vid).threshold=0.;s.commit()
R['threshold_binding']={'stored_threshold':original_metrics['threshold'],'new_threshold':0.,'gate':gate(),'activate':activate(),'actual_reevaluation':evaluate()}
restore();activate()
# Disappeared input bytes are not verified by the gate.
with db.get_session() as s:member=s.query(db.ModelVersionSample).filter_by(model_version_id=vid,split='test').first();file=Path(s.get(db.TrainingSample,member.sample_id).image_path)
saved=file.read_bytes();file.unlink()
R['missing_input_bytes']={'gate':gate(),'activate':activate(),'evaluate':evaluate()};file.write_bytes(saved);restore();activate()
# Mandatory loader for active inference: real archives, not bare mocks.
for kind in ['empty','missing_dataset','missing_encoder','missing_threshold']:
    payload=torch.load(path,weights_only=False)
    if kind=='empty':payload['extra']={}
    else:payload['extra'].pop({'missing_dataset':'dataset_hash','missing_encoder':'encoder_weights_version','missing_threshold':'threshold'}[kind])
    torch.save(payload,path)
    R['active_metadata_'+kind]={'classify':classify(),'gate':gate(),'evaluate':evaluate()};restore();activate()
# Active artifact byte replacement must not continue reporting an evaluated model.
payload=torch.load(path,weights_only=False);payload['model']['w']=np.zeros_like(payload['model']['w']);payload['model']['b']=10.;torch.save(payload,path)
R['active_weights_tampered']={'gate':gate(),'classify':classify()};restore();activate()
with db.get_session() as s:s.get(db.ModelVersion,vid).artifact_path=str(p2);s.commit()
R['active_same_dataset_v2_archive']={'v1_archive_sha256':filehash(path),'v2_archive_sha256':filehash(p2),'gate':gate(),'classify':classify()};restore();activate()
# Persist actual JSON types, avoiding SQLAlchemy True == 1.0 no-op dirty check.
R['actual_persisted_metric_types']={}
for val in [True,'1.0','bad',2.,float('nan'),float('inf'),10**400]:
    m=dict(original_metrics);m['f1']=val
    with db.get_session() as s:s.execute(text('UPDATE autolearn_model_versions SET metrics=:metrics WHERE id=:id'),{'metrics':json.dumps(m),'id':vid});s.commit()
    with db.get_session() as s:stored=s.get(db.ModelVersion,vid).metrics['f1'];stored_type=type(stored).__name__
    R['actual_persisted_metric_types'][str(val)]={'stored_type':stored_type,'gate':gate(),'activate':activate()};restore()
# Invalid raw prediction boundaries with real metadata/artifact unchanged.
real_load=student.StudentClassifier.load
class Outputs:
    def __init__(self,p,kind):
        self.clf=real_load(p);self.extra=self.clf.extra;self.classes=self.clf.classes;self.kind=kind
    def predict_proba(self,X):
        if self.kind=='ragged':return [[.2],.8]+[.2]*(len(X)-2) if len(X)>1 else [[.2],.8]
        if self.kind=='raises_valueerror':raise ValueError('QA_ONLY prediction conversion fault')
        probs=self.clf.predict_proba(X).tolist();probs[0]=bool(probs[0]>=.5);return probs
R['extended_raw_outputs']={}
for kind in ['mixed_bool_numeric','ragged','raises_valueerror']:
    restore();student.StudentClassifier.load=staticmethod(lambda p,k=kind:Outputs(p,k))
    R['extended_raw_outputs'][kind]={'evaluate':evaluate(),'gate':gate(),'classify':classify()}
student.StudentClassifier.load=real_load;restore()
R['shadow_no_actions']=call('GET',f'/api/autolearn/tasks/{t}/shadow')
R['restart_history']=call('GET',f'/api/autolearn/tasks/{t}/activations')
(ROOT/'acceptance-artifacts.json').write_text(json.dumps(R,indent=2,default=str));print(json.dumps(R,indent=2,default=str))
