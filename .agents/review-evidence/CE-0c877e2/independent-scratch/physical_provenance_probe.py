"""QA_ONLY physical-video provenance probe. One locally generated AVI, decoded
frames, procedural review fixtures. Not a model quality benchmark."""
import hashlib,json
from pathlib import Path
import cv2,numpy as np
from app import db,config
from app.autolearn import service
ROOT=Path('/tmp/visionflow-m3-emergency-review-0c877e2');path=ROOT/'QA_ONLY-one-video.avi'
w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),2.,(128,128))
assert w.isOpened()
for i in range(12):w.write(np.full((128,128,3),(35+i,20,10+(i+1)*20),dtype=np.uint8))
w.release();config.ensure_dirs();db.init_db()
with db.get_session() as s:
 t=service.create_task(s,name='QA_ONLY one physical video',visual_prompt='occupied?',positive_label='occupied',negative_label='empty')
 src=db.VideoSource(name='QA_ONLY one physical AVI',path=str(path),type='upload',frame_count=12,fps=2.);s.add(src);s.commit()
 cap=cv2.VideoCapture(str(path));n=0
 while True:
  ok,frame=cap.read()
  if not ok:break
  ok,jpg=cv2.imencode('.jpg',frame);assert ok
  row=service.import_image(s,t,image_bytes=jpg.tobytes(),source_id=src.id,session_id=f'arbitrary-{n//2}',group_key=f'arbitrary-{n//2}',video_timestamp=n/2,origin='qa_synthetic')
  service.review_sample(s,row,verified_label='occupied' if n%2==0 else 'empty',reviewer='QA_ONLY procedural fixture');n+=1
 cap.release()
 try:plan=service.build_split_plan(s,t)
 except Exception as exc:
  out={'refused':True,'decoded_frames':n,'source_id':src.id,'error_type':type(exc).__name__,'detail':str(exc)}
  (ROOT/'physical-provenance.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2));raise SystemExit(0)
 rows=s.query(db.TrainingSample).filter_by(task_id=t.id).all()
 out={'disclosure':'QA_ONLY one actual generated video; no quality claim','video_path':str(path),'video_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_id':src.id,'decoded_frames':n,'counts':plan.counts,'group_split':plan.group_split,'rows':[{'sample_id':r.id,'source_id':r.source_id,'session_id':r.session_id,'timestamp':r.video_timestamp,'split':plan.assignments[r.id]} for r in rows]}
(ROOT/'physical-provenance.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
