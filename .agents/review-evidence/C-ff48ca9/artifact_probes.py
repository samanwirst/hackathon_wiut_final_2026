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
ROOT=Path('/tmp/visionflow-c-final-ff48ca9');R={};torch.set_num_threads(2)
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
t=task('final artifact fault boundaries');samples(t)
v1=call('POST',f'/api/autolearn/tasks/{t}/train');id1=v1['body']['version_id']
samples(t,7);v2=call('POST',f'/api/autolearn/tasks/{t}/train');id2=v2['body']['version_id']
with db.get_session() as s:
    p1=Path(s.get(db.ModelVersion,id1).artifact_path);p2=Path(s.get(db.ModelVersion,id2).artifact_path)
    original_metrics=dict(s.get(db.ModelVersion,id1).metrics)
    row=s.query(db.TrainingSample).filter_by(task_id=t,verified_label='empty').first();blob=Path(row.image_path).read_bytes()
original1=p1.read_bytes();original2=p2.read_bytes()
def active_id():
    with db.get_session() as s:return s.get(db.AutoLearnTask,t).active_version_id
def classify():return call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',blob,'image/jpeg')})
def activate(i):return call('POST',f'/api/autolearn/versions/{i}/activate',json={'approve':True,'approver':'QA_ONLY simulated approval'})
def gate(i=id1):return call('GET',f'/api/autolearn/versions/{i}/gate')
def reevaluate(i=id1):return call('POST',f'/api/autolearn/versions/{i}/evaluate')
def rollback():return call('POST',f'/api/autolearn/tasks/{t}/rollback',json={'approver':'QA_ONLY simulated rollback'})
def reset_metrics():
    with db.get_session() as s:s.get(db.ModelVersion,id1).metrics=original_metrics;s.commit()
R['baseline']={'train1':v1,'train2':v2,'genuine_reload_evaluation':reevaluate(),'activate1':activate(id1),'activate2':activate(id2)}

# Target missing/corrupt/mismatch: exact ORIGINAL rollback boundary, correct archived target.
for kind in ['missing','corrupt','mismatched']:
    if kind=='missing':p1.unlink()
    elif kind=='corrupt':p1.write_bytes(b'QA_ONLY corrupt torch archive')
    else:
        payload=torch.load(p1,weights_only=False);payload['extra']['dataset_hash']='QA_ONLY wrong artifact hash';torch.save(payload,p1)
    R['rollback_'+kind]={'before':active_id(),'gate':gate(),'rollback':rollback(),'after':active_id(),'current_classify':classify()}
    p1.write_bytes(original1)
# Successful verified-target rollback really reloads and restores the working target.
R['rollback_good']={'response':rollback(),'after':active_id(),'classify':classify()};activate(id2)

# Metadata-free or incomplete old artifact is not a verified match to its row.
for kind in ['extra_empty','extra_missing_dataset','class_names_reversed']:
    payload=torch.load(p1,weights_only=False)
    if kind=='extra_empty':payload['extra']={}
    elif kind=='extra_missing_dataset':payload['extra'].pop('dataset_hash')
    else:payload['model']['classes']=list(reversed(payload['model']['classes']))
    torch.save(payload,p1)
    R['metadata_'+kind]={'gate':gate(),'activate':activate(id1),'rollback_target_after_reactivate2':None}
    activate(id2)
    R['metadata_'+kind]['rollback_target_after_reactivate2']=rollback()
    p1.write_bytes(original1);activate(id2)

# Replace learned weights with a different loadable model; old metrics stay at F1=1.
payload=torch.load(p1,weights_only=False);payload['model']['w']=np.zeros_like(payload['model']['w']);payload['model']['b']=-10.
torch.save(payload,p1)
R['stale_metrics_changed_artifact']={'cached_gate':gate(),'activate':activate(id1),'actual_reload_evaluation':reevaluate(),'gate_after':gate()}
p1.write_bytes(original1);reset_metrics();activate(id2)

# Wrong row/artifact association: classifier route ignores the verified loader.
activate(id1)
with db.get_session() as s:s.get(db.ModelVersion,id1).artifact_path=str(p2);s.commit()
R['offline_wrong_artifact']={'classify':classify(),'evaluate':reevaluate(),'gate_after':gate()}
with db.get_session() as s:s.get(db.ModelVersion,id1).artifact_path=str(p1);s.commit()
reset_metrics();activate(id2)

# Actual file bytes differ from frozen image hash, while cached DB hash is untouched.
with db.get_session() as s:
    r=s.query(db.TrainingSample).filter_by(task_id=t,verified_label='empty').first();file=Path(r.image_path);expected=r.image_hash
saved=file.read_bytes();other=fixtures.generate_sessions(n_sessions=1,per_class_per_session=1,task_slug='QA_ONLY changed bytes')[1].image_bytes;file.write_bytes(other)
R['changed_image_bytes']={'expected':expected,'actual':filehash(file),'gate':gate(),'activate':activate(id1),'evaluation':reevaluate()}
file.write_bytes(saved);reset_metrics();activate(id2)

# Changed manifest membership is correctly rejected, with counts held constant.
with db.get_session() as s:
    test=s.query(db.ModelVersionSample).filter_by(model_version_id=id1,split='test').first();train=s.query(db.ModelVersionSample).filter_by(model_version_id=id1,split='train').first()
    mids=(test.id,train.id);test.split='train';train.split='test';s.commit()
R['changed_manifest_same_counts']={'gate':gate(),'activate':activate(id1)}
with db.get_session() as s:s.get(db.ModelVersionSample,mids[0]).split='test';s.get(db.ModelVersionSample,mids[1]).split='train';s.commit()
# Existing snapshot without provenance digest is fail-closed until actual reevaluation.
with db.get_session() as s:m=dict(original_metrics);m.pop('manifest_digest');s.get(db.ModelVersion,id1).metrics=m;s.commit()
R['old_metric_provenance']={'gate_before':gate(),'genuine_evaluation':reevaluate(),'gate_after':gate()}

# Fault at real reloaded classifier prediction boundary, metadata preserved.
real_load=student.StudentClassifier.load
class Outputs:
    def __init__(self,path,kind):self.clf=real_load(path);self.extra=self.clf.extra;self.kind=kind
    def predict_proba(self,X):
        p=self.clf.predict_proba(X)
        if self.kind=='bool':return p>=.5
        if self.kind=='column':return p.reshape(-1,1)
        if self.kind=='row':return p.reshape(1,-1)
        if self.kind=='strings':return np.array([str(x) for x in p])
        if self.kind=='bad_string':return ['QA_ONLY invalid probability']*len(p)
        if self.kind=='nan':return np.full(len(p),np.nan)
        if self.kind=='inf':return np.full(len(p),np.inf)
        if self.kind=='out_of_range':return np.full(len(p),2.)
        if self.kind=='wrong_count':return np.zeros(len(p)+1)
        raise AssertionError(self.kind)
R['prediction_boundary']={}
activate(id1)
for kind in ['bool','column','row','strings','bad_string','nan','inf','out_of_range','wrong_count']:
    reset_metrics();student.StudentClassifier.load=staticmethod(lambda path,kind=kind:Outputs(path,kind))
    R['prediction_boundary'][kind]={'evaluate':reevaluate(),'gate':gate(),'classify':classify()}
student.StudentClassifier.load=real_load;reset_metrics()

# Malformed persisted metrics should never pass or make a JSON response with NaN.
R['malformed_metric_gate']={}
for value in [True,2.,float('nan'),float('inf')]:
    with db.get_session() as s:m=dict(original_metrics);m['f1']=value;s.get(db.ModelVersion,id1).metrics=m;s.commit()
    R['malformed_metric_gate'][str(value)]={'gate':gate(),'activate':activate(id1)}
reset_metrics()
(ROOT/'artifacts.json').write_text(json.dumps(R,indent=2,default=str));print(json.dumps(R,indent=2,default=str))
