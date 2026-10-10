"""QA_ONLY residual failure-state probes; own DB and artifacts from version_probes.
No provider requests and no real-world model-quality claim.
"""
import io,json,hashlib
from pathlib import Path
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from app import db,config
from app.autolearn import service,api,student,dataset
ROOT=Path('/tmp/visionflow-c-qa-5938b6d');R={};db.init_db()
app=FastAPI();app.include_router(api.router);c=TestClient(app,raise_server_exceptions=False)
def call(method,path,**kw):
 r=c.request(method,path,**kw)
 try:b=r.json()
 except Exception:b=r.text[:200]
 return {'http':r.status_code,'body':b}
# Insert nonfinite outputs into a real trained model's boundary; preserve
# positive/negative polarity so NaNs yield apparently perfect finite metrics.
real_load=student.StudentClassifier.load
class InvalidOutputs:
 def __init__(self,p):self.clf=real_load(p)
 def predict_proba(self,X):
  p=self.clf.predict_proba(X);return np.where(p>=.5,1.,np.nan)
student.StudentClassifier.load=staticmethod(lambda p:InvalidOutputs(p))
R['nonfinite_predictions_evaluation']=call('POST','/api/autolearn/versions/3/evaluate')
R['nonfinite_predictions_gate']=call('GET','/api/autolearn/versions/3/gate')
# Attach actual QA trained version to its own QA task to reach offline classify.
with db.get_session() as s:
 t=s.get(db.AutoLearnTask,2);t.active_version_id=3;s.commit()
with db.get_session() as s:
 row=s.query(db.TrainingSample).filter_by(task_id=2,verified_label='empty').first();blob=Path(row.image_path).read_bytes()
R['nonfinite_predictions_offline']=call('POST','/api/autolearn/tasks/2/classify',files={'file':('QA.jpg',blob,'image/jpeg')})
student.StudentClassifier.load=real_load
# Actual upload validation and provenance persist; invalid bytes are refused.
r=call('POST','/api/autolearn/tasks',json={'name':'QA_ONLY upload checks','visual_prompt':'occupied?','positive_label':'occupied','negative_label':'empty'});tid=r['body']['id']
b=io.BytesIO();Image.new('RGB',(48,48),(78,98,118)).save(b,format='PNG');blob=b.getvalue()
R['upload_provenance']=call('POST',f'/api/autolearn/tasks/{tid}/images?session_id=QA_ONLY-upload&group_key=QA_ONLY-group&source_id=123&video_timestamp=1.25',files={'file':('QA.png',blob,'image/png')})
R['exact_duplicate']=call('POST',f'/api/autolearn/tasks/{tid}/images?session_id=another-name',files={'file':('QA.png',blob,'image/png')})
R['unreadable_image']=call('POST',f'/api/autolearn/tasks/{tid}/images?session_id=QA_ONLY',files={'file':('bad.jpg',b'QA_ONLY invalid','image/jpeg')})
R['invalid_source_id']=call('POST',f'/api/autolearn/tasks/{tid}/images?session_id=QA_ONLY&source_id=nope',files={'file':('QA.png',blob,'image/png')})
with db.get_session() as s:
 row=s.query(db.TrainingSample).filter_by(task_id=tid).one();R['stored_provenance']={'session_id':row.session_id,'source_id':row.source_id,'group_key':row.group_key,'video_timestamp':row.video_timestamp,'image_hash':row.image_hash}
# Near-duplicate gate checks genuine reencoding and insufficient groups.
img=Image.open(io.BytesIO(blob)).convert('RGB');bb=io.BytesIO();img.save(bb,format='JPEG',quality=50);reenc=bb.getvalue()
rows=[dataset.SampleRow(1,'a',hashlib.sha256(blob).hexdigest(),'occupied',service._fingerprint(blob)),dataset.SampleRow(2,'b',hashlib.sha256(reenc).hexdigest(),'empty',service._fingerprint(reenc))]
for name,items in [('decoded_reencoding',rows),('insufficient_independence',[dataset.SampleRow(1,'one','h1','occupied'),dataset.SampleRow(2,'one','h2','empty')])]:
 try:dataset.build_split(items,min_train_groups=2,min_val_groups=1,min_test_groups=1,near_dup_max_mad=5.)
 except dataset.DatasetError as e:R[name]={'refused':True,'detail':str(e)}
R['fixed_threshold']=config.AUTOLEARN_NEAR_DUP_MAX_MAD
(ROOT/'extra-probes.json').write_text(json.dumps(R,indent=2));print(json.dumps(R,indent=2))
