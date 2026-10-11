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

import io
from PIL import Image
from app.autolearn import dataset,metrics
# Actual near-duplicate re-encoding refusal and no quality assertion.
a=io.BytesIO();Image.new('RGB',(48,48),(78,98,118)).save(a,format='PNG');blob=a.getvalue()
b=io.BytesIO();Image.open(io.BytesIO(blob)).convert('RGB').save(b,format='JPEG',quality=50);reencoded=b.getvalue()
rows=[dataset.SampleRow(1,'a',hashlib.sha256(blob).hexdigest(),'occupied',service._fingerprint(blob)),dataset.SampleRow(2,'b',hashlib.sha256(reencoded).hexdigest(),'empty',service._fingerprint(reencoded))]
try:dataset.build_split(rows,min_train_groups=2,min_val_groups=1,min_test_groups=1,near_dup_max_mad=config.AUTOLEARN_NEAR_DUP_MAX_MAD)
except dataset.DatasetError as e:R['near_duplicate']={'refused':True,'detail':str(e),'fixed_mad':config.AUTOLEARN_NEAR_DUP_MAX_MAD}
# Genuine CPU training observed without changing fit/threshold/evaluation algorithms.
t=task('heldout control');samples(t)
original_embed=service._embed;original_fit=student.StudentClassifier.fit;original_select=metrics.select_threshold;original_predict=student.StudentClassifier.predict_proba
record={};phase={'ids':[]};embedded={}
def embed_trace(rows):
    X,lat=original_embed(rows);ids=[r.id for r in rows];embedded[hashlib.sha256(X.tobytes()).hexdigest()]=ids
    return X,lat
def fit_trace(self,X,y,**kw):
    record['fit_ids']=embedded[hashlib.sha256(X.tobytes()).hexdigest()];return original_fit(self,X,y,**kw)
def predict_trace(self,X):
    phase['ids']=embedded.get(hashlib.sha256(X.tobytes()).hexdigest(),[]);return original_predict(self,X)
def select_trace(probs,y):
    record['threshold_input_count']=len(probs);record['threshold_ids']=list(phase['ids']);return original_select(probs,y)
service._embed=embed_trace;student.StudentClassifier.fit=fit_trace;metrics.select_threshold=select_trace;student.StudentClassifier.predict_proba=predict_trace
trained=call('POST',f'/api/autolearn/tasks/{t}/train');vid=trained['body']['version_id']
service._embed=original_embed;student.StudentClassifier.fit=original_fit;metrics.select_threshold=original_select;student.StudentClassifier.predict_proba=original_predict
with db.get_session() as s:
    v=s.get(db.ModelVersion,vid);info=service._frozen_manifest(s,v);split_ids={k:[r.id for r in rows] for k,rows in info['by_split'].items()};groups={k:sorted({service._canonical_group(r) for r in rows}) for k,rows in info['by_split'].items()}
    clf=student.StudentClassifier.load(v.artifact_path);X,_=original_embed(info['by_split']['test']);raw=clf.predict_proba(X)
    y=np.array([1 if r.verified_label=='occupied' else 0 for r in info['by_split']['test']]);pred=(raw>=v.threshold).astype(int)
    tp=int(((pred==1)&(y==1)).sum());fp=int(((pred==1)&(y==0)).sum());fn=int(((pred==0)&(y==1)).sum());tn=int(((pred==0)&(y==0)).sum())
    expected_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
R['heldout_training']={'train':trained,'record':record,'split_ids':split_ids,'canonical_groups':groups,'fit_exactly_train':set(record['fit_ids'])==set(split_ids['train']),'threshold_exactly_validation':set(record['threshold_ids'])==set(split_ids['val']),'test_probabilities':raw.tolist(),'test_ground_truth':y.tolist(),'independent_confusion':{'tp':tp,'fp':fp,'fn':fn,'tn':tn},'independent_f1':round(expected_f1,4),'encoder_frozen_after':encoder.get_encoder().frozen()}
R['decision_control']=call('POST',f'/api/autolearn/versions/{vid}/activate',json={'approve':False,'approver':'QA_ONLY simulated decline'})
R['approved_control']=call('POST',f'/api/autolearn/versions/{vid}/activate',json={'approve':True,'approver':'QA_ONLY simulated approval'})
# A new DB engine/session simulates application reopen; no root state accessed.
before=call('GET',f'/api/autolearn/tasks/{t}/activations');db.init_db(str(config.DB_PATH));after=call('GET',f'/api/autolearn/tasks/{t}/activations')
R['db_reopen_history']={'unchanged':before==after,'before':before,'after':after}
R['shadow']=call('GET',f'/api/autolearn/tasks/{t}/shadow')
(ROOT/'supported-controls-trace.json').write_text(json.dumps(R,indent=2));print(json.dumps(R,indent=2))
