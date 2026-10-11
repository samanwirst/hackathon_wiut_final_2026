"""QA_ONLY: production HTTP compiler, absolute admission, engine and privacy controls."""
import contextlib, json, socket, threading, time
from pathlib import Path
from unittest.mock import patch
import network_probe as n
from app import pipeline
from app.db import VideoSource,get_session
from app.vlm_router import set_router
from visionflow_vision.events import ZoneEventEngine, EventType, TrackedObject
from visionflow_vision.zones import Zone
OUT=[]
def record(name,**kwargs):
    r={'name':name,**kwargs};OUT.append(r);print(json.dumps(r),flush=True)
with n.provider([{}]) as (srv,url):
    teacher=n.teacher(url,timeout=.2);router=n.routing(teacher)
    pipeline.dispatch_admission_lock.acquire()
    def release_lock():time.sleep(.13);pipeline.dispatch_admission_lock.release()
    release=threading.Thread(target=release_lock);release.start()
    start=time.monotonic()
    d=n.route(router,admit=lambda: (time.sleep(.14) or True))
    release.join()
    record('absolute_admission',elapsed=time.monotonic()-start,deadline=.2,result=d.result.model_dump(),posts=len(srv.records),attempts=router.counters.outbound_attempts)

# A permitted endpoint is server configuration. Synthetic token only; no credentials read.
with n.provider([{}]) as (srv,url):
    t=n.teacher(url,timeout=.4);t.api_key='QA_ONLY_SYNTHETIC_TOKEN'
    router=n.routing(t);d=n.route(router,image=b'QA_ONLY_IMAGE_MARKER')
    public={'decision':d.result.model_dump(),'stats':router.stats()}
    rendered=json.dumps(public)
    record('provider_public_privacy',status=d.result.status,contains_token='QA_ONLY_SYNTHETIC_TOKEN' in rendered,contains_endpoint=url in rendered,contains_image='QA_ONLY_IMAGE_MARKER' in rendered)

with n.api() as c:
    with get_session() as s:
        src=VideoSource(name='QA_ONLY-additional',path='/tmp/visionflow-m2-emergency-review-953d0e2/no-video.mp4');s.add(src);s.commit();src_id=src.id
    c.post('/api/zones',json={'source_id':src_id,'name':'Service Bay A','polygon':[[0,0],[1,0],[1,1],[0,1]]})
    texts=[
        'When a car enters Service Bay A with headlights on or off, create an alert',
        'When a car enters Service Bay A with headlights on and off, create an alert',
        'When a car enters Service Bay A with headlights off, create an alert',
        'When a car enters Service Bay A with headlights on, create an alert',
        'Create an alert for 5 minutes a car stays in Service Bay A',
        'When a car enters Service Bay A and then enters Service Bay A, create an alert',
    ]
    for text in texts:
        r=c.post('/api/workflows/compile',json={'source_id':src_id,'text':text})
        record('additional_compile',text=text,http_status=r.status_code,result=r.json())
    valid=c.post('/api/workflows/compile',json={'source_id':src_id,'text':'When a car enters Service Bay A, create an alert'}).json()['draft']
    valid['action']={'type':'send_webhook','config':{'url':'http://127.0.0.1:1/QA_ONLY'}}
    r=c.post('/api/workflows',json=valid);record('webhook_api_rejection',http_status=r.status_code)

results=json.loads(Path('/tmp/visionflow-m2-emergency-review-953d0e2/extended-results.json').read_text())['results']
r=next(x for x in results if x['name']=='ui_roundtrip' and '1.25 seconds' in x['text'])
obj=TrackedObject(track_id=91,class_name='car',confidence=.9,x1=10,y1=10,x2=40,y2=40)
zone=Zone(id=1,name='Service Bay A',polygon=[[0,0],[1,0],[1,1],[0,1]])
engine_results=[]
for label,dsl in [('original_draft',r['draft']),('ui_saved',r['stored_dsl'])]:
    engine=ZoneEventEngine(zone,object_class='car',frame_w=100,frame_h=100,event_type=EventType.DWELL,dwell_seconds=dsl['trigger']['duration_seconds'],cooldown_seconds=dsl['cooldown_seconds'],debounce_frames=1)
    engine.update([obj],now=0)
    emitted=engine.update([obj],now=1.1)
    engine_results.append({'dsl':label,'duration':dsl['trigger']['duration_seconds'],'emitted_at_1_1':len(emitted)})
record('ui_engine_semantics',results=engine_results)
Path('/tmp/visionflow-m2-emergency-review-953d0e2/additional-results.json').write_text(json.dumps({'target_sha':'953d0e275177951a71c4c8fccf6b915693e43550','results':OUT},indent=2))
