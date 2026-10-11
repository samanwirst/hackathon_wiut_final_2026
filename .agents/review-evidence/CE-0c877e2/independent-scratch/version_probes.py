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

t=task('sequential immutable versions');samples(t)
v1=call('POST',f'/api/autolearn/tasks/{t}/train');id1=v1['body']['version_id'];m1=manifest(id1)
with db.get_session() as s:p1=s.get(db.ModelVersion,id1).artifact_path
h1=filehash(p1);samples(t,7)
v2=call('POST',f'/api/autolearn/tasks/{t}/train');id2=v2['body']['version_id']
ev1=call('POST',f'/api/autolearn/versions/{id1}/evaluate')
R['sequential_version_snapshot']={'train1':v1,'train2':v2,'old_evaluation':ev1,'old_manifest_unchanged':m1==manifest(id1),'old_artifact_unchanged':h1==filehash(p1),'old_test_ids':[r[0] for r in m1 if r[3]=='test']}
R['declined_activation']=call('POST',f'/api/autolearn/versions/{id1}/activate',json={'approve':False,'approver':'QA_ONLY simulated decision'})
# Simulated decisions affect reviewer-owned QA_ONLY models only.
a1=call('POST',f'/api/autolearn/versions/{id1}/activate',json={'approve':True,'approver':'QA_ONLY simulated decision'})
a2=call('POST',f'/api/autolearn/versions/{id2}/activate',json={'approve':True,'approver':'QA_ONLY simulated decision'})
rb=call('POST',f'/api/autolearn/tasks/{t}/rollback',json={'approver':'QA_ONLY simulated rollback'})
R['normal_gates_rollback']={'activate1':a1,'activate2':a2,'rollback':rb,'classify':call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',fixtures.generate_sessions(n_sessions=1,per_class_per_session=1)[0].image_bytes,'image/jpeg')})}

# Lost manifest row is not checked by activation; cached metrics remain passing.
with db.get_session() as s:
    row=s.query(db.ModelVersionSample).filter_by(model_version_id=id2,split='test').first();s.delete(row);s.commit()
R['lost_manifest_gate']=call('GET',f'/api/autolearn/versions/{id2}/gate')
R['lost_manifest_activate']=call('POST',f'/api/autolearn/versions/{id2}/activate',json={'approve':True,'approver':'QA_ONLY inconsistent snapshot fixture'})
R['lost_manifest_evaluate']=call('POST',f'/api/autolearn/versions/{id2}/evaluate')
R['lost_manifest_gate_after_evaluate']=call('GET',f'/api/autolearn/versions/{id2}/gate')
# Gate accepts old metrics even if artifact no longer exists; rollback likewise.
Path(p1).rename(Path(p1+'.QA_ONLY-missing'))
R['missing_artifact_rollback']=call('POST',f'/api/autolearn/tasks/{t}/rollback',json={'approver':'QA_ONLY missing artifact fixture'})
R['missing_artifact_classify']=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',fixtures.generate_sessions(n_sessions=1,per_class_per_session=1)[0].image_bytes,'image/jpeg')})

# Nonfinite probabilities are silently converted to class predictions.
old_load=student.StudentClassifier.load
class Nonfinite:
    def predict_proba(self,X):return np.full(len(X),np.nan)
student.StudentClassifier.load=staticmethod(lambda p:Nonfinite())
R['nan_student_offline']=call('POST',f'/api/autolearn/tasks/{t}/classify',files={'file':('QA.jpg',fixtures.generate_sessions(n_sessions=1,per_class_per_session=1)[0].image_bytes,'image/jpeg')})
student.StudentClassifier.load=old_load

# Deterministic race at actual save boundary; real fit/load/save, no fake metrics.
t=task('concurrent training');samples(t)
barrier=threading.Barrier(2);first_at_save=threading.Event();save_lock=threading.Lock();paths=[]
original_save=student.StudentClassifier.save
original_embed=service._embed
# Row embedding/fitting remain genuine. Delay only makes the naturally concurrent
# count()+1 / unreserved vN.pt allocation reproducible.
def gated_save(self,path,*,extra=None):
    paths.append({'thread':threading.get_ident(),'path':path,'dataset_hash':extra['dataset_hash'],'split_hash':extra['split_hash']})
    first_at_save.set();barrier.wait(timeout=15)
    with save_lock:original_save(self,path,extra=extra)
student.StudentClassifier.save=gated_save
with ThreadPoolExecutor(2) as pool:
    first=pool.submit(call,'POST',f'/api/autolearn/tasks/{t}/train')
    assert first_at_save.wait(15),'first train not at artifact boundary'
    samples(t,7)
    second=pool.submit(call,'POST',f'/api/autolearn/tasks/{t}/train')
    outs=[first.result(30),second.result(30)]
student.StudentClassifier.save=original_save
with db.get_session() as s:
    rows=s.query(db.ModelVersion).filter_by(task_id=t).all()
    registry=[{'id':v.id,'version':v.version,'artifact_path':v.artifact_path,'dataset_hash':v.dataset_hash,'split_hash':v.split_hash,'status':v.status} for v in rows]
    extra=torch.load(rows[0].artifact_path,weights_only=False)['extra'] if rows else None
R['concurrent_train_collision']={'responses':outs,'save_paths':paths,'registry':registry,'actual_artifact_metadata':extra}
# Failure after save leaves an unregistered artifact; task advertises no failure.
t=task('failed training');samples(t)
original_eval=service._evaluate_rows
service._evaluate_rows=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('QA_ONLY injected held-out failure after save'))
R['post_save_training_failure']={'response':call('POST',f'/api/autolearn/tasks/{t}/train'),'detail':call('GET',f'/api/autolearn/tasks/{t}'),'orphan_artifacts':[str(p) for p in (config.AUTOLEARN_MODEL_DIR/f'task_{t}').glob('*')]}
service._evaluate_rows=original_eval
(ROOT/'version-probes.json').write_text(json.dumps(R,indent=2,default=str));print(json.dumps(R,indent=2,default=str))
