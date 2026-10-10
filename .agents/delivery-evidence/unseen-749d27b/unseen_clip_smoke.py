"""Fresh QA input with declared photo reuse/synthetic motion, genuine detector."""
from pathlib import Path
import json,time,hashlib
import cv2,numpy as np,httpx
from ultralytics.utils import ASSETS
root=Path.cwd();out=root/'.agents/runtime/ten-hour/delivery/container/unseen';out.mkdir(exist_ok=True)
photo=cv2.imread(str(ASSETS/'bus.jpg'));assert photo.shape[:2]==(1080,810)
bus=cv2.resize(photo[220:665,350:755],(288,316));w,h,fps,frames=1280,720,20,200
video=out/'reverse-hold-unseen.mp4';writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));assert writer.isOpened()
try:
 for i in range(frames):
  if i<65:x=920-(i/65)*500
  elif i<155:x=420
  else:x=420-((i-155)/44)*380
  frame=np.full((h,w,3),(75,70,65),dtype=np.uint8);x=int(x);frame[310:626,x:x+288]=bus;writer.write(frame)
finally:writer.release()
manifest={'generator':'QA_ONLY reverse movement, hold, then exit; parameters chosen before processing, no detector output used','source_asset':'ultralytics/assets/bus.jpg','crop_xyxy':[350,220,755,665],'canvas':[w,h],'fps':fps,'frames':frames,'bus_size':[288,316],'motion':'right to left; hold inside zone4.5s; move out','source_photo_sha256':hashlib.sha256((ASSETS/'bus.jpg').read_bytes()).hexdigest(),'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'limits':'New video bytes/path/resolution/timing, same upstream photo. This is NOT unseen natural footage or natural-video quality evidence.'}
(out/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
c=httpx.Client(base_url='http://127.0.0.1:18085',timeout=20)
r=c.get('/api/health');r.raise_for_status();assert r.json()['demo_safe'] is True
with video.open('rb') as f:r=c.post('/api/sources/upload',files={'file':('QA_ONLY unseen reverse-hold.mp4',f,'video/mp4')})
r.raise_for_status();source=r.json()
r=c.post('/api/zones',json={'source_id':source['id'],'name':'QA_ONLY unseen left bay','polygon':[[.25,.2],[.6,.2],[.6,.95],[.25,.95]]});r.raise_for_status();zone=r.json()
workflows=[]
for trigger in [{'type':'object_entered_zone','zone_id':zone['id']},{'type':'dwell_in_zone','zone_id':zone['id'],'duration_seconds':2}]:
 dsl={'name':'QA_ONLY unseen '+trigger['type'],'source_id':source['id'],'object_class':'bus','trigger':trigger,'action':{'type':'create_notification','config':{'title':'QA_ONLY real unseen event'}}}
 r=c.post('/api/workflows',json=dsl);r.raise_for_status();wf=r.json();assert not wf['enabled'];workflows.append(wf)
 r=c.post(f"/api/workflows/{wf['id']}/enable",json={'approve':True});r.raise_for_status()
r=c.post(f"/api/sources/{source['id']}/process");r.raise_for_status();deadline=time.monotonic()+90
while time.monotonic()<deadline:
 r=c.get(f"/api/sources/{source['id']}");r.raise_for_status();status=r.json()
 if status['status']=='failed':raise RuntimeError(status)
 if status['status']=='processed':break
 time.sleep(.3)
else:raise RuntimeError('Unseen QA processing deadline')
r=c.get('/api/events',params={'source_id':source['id']});r.raise_for_status();events=r.json();checks=[]
for wf in workflows:
 hits=[e for e in events if e['workflow_id']==wf['id']];assert hits,{'missing_trigger':wf['dsl']['trigger'] if 'dsl'in wf else wf}
 for e in hits:
  r=c.get(e['evidence_url']);r.raise_for_status();assert r.content[:2]==b'\xff\xd8'
  evidence_hash=hashlib.sha256(r.content).hexdigest();r=c.get(f"/api/events/{e['id']}/actions");r.raise_for_status();a=r.json();assert len(a)==1 and a[0]['status']=='success'
  checks.append({'event':e,'actions':a,'evidence_sha256':evidence_hash})
r=c.get('/api/notifications');r.raise_for_status();notes=r.json();assert all(len([n for n in notes if n['event_id']==x['event']['id']])==1 for x in checks)
r=c.get('/api/vlm/stats');r.raise_for_status();stats=r.json();assert stats['live']['teacher_available'] is False
receipt={'actual_yolo':True,'container_source_snapshot':'749d27b','input':manifest,'source':status,'workflows':workflows,'events':checks,'teacher_stats':stats,'student_activation':False,'limits':manifest['limits']}
(out/'actual-result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'actual_yolo':True,'frames_processed':status['frames_processed'],'mean_inference_ms':status['avg_inference_ms'],'events':len(checks),'teacher_disabled':True}))
