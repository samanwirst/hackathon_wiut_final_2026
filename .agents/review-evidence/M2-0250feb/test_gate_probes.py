"""Additional bounded QA probes; never changes application files."""
import json
import threading
import time
import httpx
import numpy as np
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
os.environ["VISIONFLOW_DATA_DIR"] = tempfile.mkdtemp(prefix="m2-exception-evidence-")
from app import db,pipeline
from app.main import app
from app.nl_compiler import compile_text
from app.teacher import OpenAICompatibleTeacher
from app.vlm_router import VlmRouter,set_router
from visionflow_vision.events import TrackedObject
@pytest.fixture
def client(tmp_path):
    with TestClient(app) as c:
        db.init_db(str(tmp_path / 'qa.db'))
        s = db.get_session()
        source = db.VideoSource(name='QA fixture', path=str(tmp_path / 'qa.mp4'), width=64, height=64, fps=30)
        s.add(source)
        s.flush()
        source_id = source.id
        for name in ('Service Bay A', 'Service Bay B'):
            s.add(db.Zone(source_id=source_id, name=name, polygon=[[0,0],[1,0],[1,1],[0,1]]))
        s.commit()
        s.close()
        yield c, source_id
    set_router(None)

def workflow_payload(source_id):
    return dict(name='QA visual workflow', source_id=source_id, object_class='car',
        trigger={'type':'object_entered_zone', 'zone_id':1},
        action={'type':'create_notification','config':{'title':'QA alert'}},
        visual_predicate={'prompt':'Is the hood open?', 'labels':['yes','no'], 'expected_label':'yes',
                          'sample_interval_seconds':0, 'cooldown_seconds':0, 'budget':10})


def test_complete_grammar_preserves_temporal_and_action_intent():
    commands=[
        'When a car enters Service Bay A for 10 minutes, create an alert',
        'When more than 3 cars are in Service Bay A for 10 minutes, create an alert',
        'When a car enters Service Bay A, log it',
        'When a car enters Service Bay A with its hood open or closed, create an alert',
    ]
    accepted=[]
    for command in commands:
        result=compile_text(command,1,[{'id':1,'name':'Service Bay A'}])
        print('GRAMMAR_PROBE',json.dumps(dict(command=command,ok=result.ok,draft=result.draft,errors=result.errors)))
        if result.ok:accepted.append(command)
    assert not accepted, 'Unsupported semantics accepted: '+repr(accepted)

def test_disable_after_grant_before_http_start(client,monkeypatch):
    c,sid=client
    wf=c.post('/api/workflows',json=workflow_payload(sid)).json()
    assert c.post(f"/api/workflows/{wf['id']}/enable").status_code==200
    teacher=OpenAICompatibleTeacher('https://qa.invalid/v1','','qa-vlm','v1',overall_timeout=3,max_retries=0)
    set_router(VlmRouter(teacher_provider=lambda:teacher,sample_interval_s=0,cooldown_s=0))
    reached,release=threading.Event(),threading.Event()
    real_post=teacher._post_with_deadline
    def paused_before_transport(*args,**kwargs):
        reached.set()
        assert release.wait(3)
        return real_post(*args,**kwargs)
    monkeypatch.setattr(teacher,'_post_with_deadline',paused_before_transport)
    posts=[]
    def post(*args,**kwargs):
        posts.append(time.monotonic())
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"label":"yes","confidence":0.9}'}}]})
    monkeypatch.setattr(httpx,'post',post)
    s=db.get_session()
    event=db.TrackEvent(source_id=sid,workflow_id=wf['id'],track_id=1,type='object_entered_zone',class_name='car',video_timestamp=1,confidence=.9,detail='gate probe',dedupe_key='post-grant-disable')
    s.add(event);s.commit();eid=event.id;s.close()
    results=[]
    def route():
        s=db.get_session()
        try:
            e=s.get(db.TrackEvent,eid);w=s.get(db.Workflow,wf['id'])
            decision=pipeline._route_visual(s,w,e,np.zeros((64,64,3),dtype=np.uint8),[TrackedObject(track_id=1,class_name='car',confidence=.9,x1=10,y1=10,x2=30,y2=30)])
            results.append(decision)
            if decision:pipeline._dispatch_action(s,w,e)
        finally:s.close()
    worker=threading.Thread(target=route);worker.start()
    try:
        assert reached.wait(3)
        assert posts==[]
        response=c.post(f"/api/workflows/{wf['id']}/disable")
        ack=time.monotonic()
        assert response.status_code==200 and response.json()['enabled'] is False
    finally:release.set()
    worker.join(4)
    assert not worker.is_alive()
    print('POST_GRANT_DISABLE',json.dumps(dict(disable_http=response.status_code,posts=len(posts),started_after_ack=bool(posts and posts[0]>ack),route=results,actions=c.get(f'/api/events/{eid}/actions').json())))
    assert posts==[], 'New Teacher HTTP request started after disable acknowledged'
