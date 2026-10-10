"""Fresh QA input with declared photo reuse/synthetic motion, genuine detector."""
from pathlib import Path
import json,time,hashlib,subprocess,sys,os,tempfile
import cv2,numpy as np,httpx
root=Path('/qa');out=Path(tempfile.mkdtemp(prefix='visionflow-offline-qa-'))
asset=root/'privacy-safe-upper-bus.png';photo=cv2.imread(str(asset));assert photo.shape[:2]==(600,970)
bus=cv2.resize(photo,(360,223));w,h,fps,frames=1280,720,20,200
video=out/'new-photo-upper-bus.mp4';writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));assert writer.isOpened()
try:
 for i in range(frames):
  if i<65:x=920-(i/65)*500
  elif i<155:x=420
  else:x=420-((i-155)/44)*380
  frame=np.full((h,w,3),(75,70,65),dtype=np.uint8);x=int(x);frame[340:563,x:x+360]=bus;writer.write(frame)
finally:writer.release()
manifest={'generator':'QA_ONLY reverse movement, hold, then exit; parameters chosen before processing, no detector output used','source_asset':'Pexels photograph7666059, a distinct photo from Ultralytics fixture','source_page':'https://www.pexels.com/photo/yellow-school-bus-on-the-road-7666059/','license':'Pexels license','license_url':'https://www.pexels.com/license/','crop_xyxy':[190,490,1160,1090], 'privacy':'Inspected crop excludes license plate and recognizable faces; only this crop enters detector','canvas':[w,h],'fps':fps,'frames':frames,'bus_size':[360,223],'motion':'right to left; hold inside zone4.5s; move out','source_photo_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'limits':'Photographic content new to this application smoke, upper rear crop of a different bus photo; synthetic motion. No claim that pretraining never saw this image, or of natural-video accuracy/quality.'}
(out/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18010'],env={**os.environ,'VISIONFLOW_DATA_DIR':str(out/'data')},cwd='/app/services/api')
c=httpx.Client(base_url='http://127.0.0.1:18010',timeout=20)
startup=time.monotonic()+30
while time.monotonic()<startup:
 try:
  if c.get('/api/health').status_code==200:break
 except httpx.HTTPError:pass
 time.sleep(.2)
else:raise RuntimeError('Owned offline API startup deadline')
r=c.get('/api/health');r.raise_for_status();assert r.json()['demo_safe'] is True
with video.open('rb') as f:r=c.post('/api/sources/upload',files={'file':('QA_ONLY Pexels upper bus.mp4',f,'video/mp4')})
r.raise_for_status();source=r.json()
r=c.post('/api/zones',json={'source_id':source['id'],'name':'QA_ONLY new-photo left bay','polygon':[[.25,.2],[.6,.2],[.6,.95],[.25,.95]]});r.raise_for_status();zone=r.json()
workflows=[]
for trigger in [{'type':'object_entered_zone','zone_id':zone['id']},{'type':'dwell_in_zone','zone_id':zone['id'],'duration_seconds':2}]:
 dsl={'name':'QA_ONLY new-photo '+trigger['type'],'source_id':source['id'],'object_class':'bus','trigger':trigger,'action':{'type':'create_notification','config':{'title':'QA_ONLY real unseen event'}}}
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
(out/'actual-result.json').write_text(json.dumps(receipt,indent=2)+'\n');print('QA_RECEIPT '+json.dumps(receipt),flush=True)
server.terminate();server.wait(timeout=10)
