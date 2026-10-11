"""Owned loopback deployment test. Mock CV only; no provider/phone/YOLO."""
import json
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from websockets.sync.client import connect

from app.live import auth, config, planner, rooms, teacher, worker
from app.live.app import app
from test_acceptance import QADetector, jpeg, proposal
from app.live.planner import PlannerResult

ROOT=Path('/tmp/visionflow-live-review-1-f5aeae3')
origin='https://live.qa.invalid'
config.DEMO_PIN=secrets.token_urlsafe(16)
config.COOKIE_SECURE=False  # explicit local QA exception only
config.ALLOWED_ORIGINS=[origin]
config.TEACHER_BASE_URL='';config.TEACHER_TOKEN='';config.PLANNER_ENABLED=False
teacher.transport=None;planner.transport=None
auth._reset_for_tests();rooms._reset_for_tests();worker._reset_for_tests()
detector=QADetector();worker.detector_factory=lambda:detector
worker_errors=[]
production_loop=worker._loop
def observed_loop():
    try: production_loop()
    except Exception as exc:
        worker_errors.append({'type':type(exc).__name__,'message':str(exc)})
worker._loop=observed_loop  # external exception recorder; does NOT recover worker
sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen()
port=sock.getsockname()[1]
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_config=None,
                    access_log=False,proxy_headers=True,forwarded_allow_ips='*'))
thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()

def wait_for(predicate,timeout=3):
    until=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>=until: raise RuntimeError('QA bounded wait expired')
        time.sleep(.01)

def post(c,path,data):
    return c.post(path,json=data,headers={'Origin':origin,'X-CSRF-Token':c.cookies.get(config.CSRF_COOKIE_NAME,'')})

results={'QA_ONLY':True,'method':'actual uvicorn + TCP HTTP/WebSocket; generated JPEG, scripted CV, local insecure QA cookies','port':port}
try:
    wait_for(lambda:server.started)
    with httpx.Client(base_url=f'http://127.0.0.1:{port}') as camera, httpx.Client(base_url=f'http://127.0.0.1:{port}') as judge:
        assert post(camera,'/api/live/login',{'role':'camera','pin':config.DEMO_PIN}).status_code==200
        created=post(camera,'/api/live/rooms',{}).json();room=rooms.get_room(created['room_id'])
        assert post(judge,'/api/live/login',{'role':'judge','pin':config.DEMO_PIN}).status_code==200
        assert post(judge,'/api/live/rooms/join',{'join_code':created['join_code']}).status_code==200
        task=planner._finalize(PlannerResult(status='ok',proposal=proposal())).task
        assert post(judge,f'/api/live/rooms/{room.room_id}/task/activate',{'task':task}).status_code==200
        cam_cookie='; '.join(f'{c.name}={c.value}' for c in camera.cookies.jar)
        judge_cookie='; '.join(f'{c.name}={c.value}' for c in judge.cookies.jar)
        with connect(f'ws://127.0.0.1:{port}/api/live/ws/camera',additional_headers={'Cookie':cam_cookie,'Origin':origin}) as camws, \
             connect(f'ws://127.0.0.1:{port}/api/live/ws/judge',additional_headers={'Cookie':judge_cookie,'Origin':origin}) as judgews:
            for seq in [1,2]:
                camws.send(json.dumps({'seq':seq,'w':320,'h':240,'capture_ts':time.time()}));camws.send(jpeg())
                wait_for(lambda:room.frames_inferred>=seq)
            wait_for(lambda:len(room.events)==1)
            state=judge.get(f'/api/live/rooms/{room.room_id}/state').json()
            evidence=judge.get(state['events'][0]['evidence_url'])
            results['valid_control']={'events':len(state['events']),'notifications':len(state['notifications']),
                'evidence_status':evidence.status_code,'evidence_bytes':len(evidence.content),
                'decoded_sizes':detector.sizes.copy(),'worker_threads':1,'teacher_calls':len(teacher._room_calls)}
            assert len(state['notifications'])==1 and evidence.status_code==200
            # Real camera socket continues after authenticated HTTP logout.
            assert post(camera,'/api/live/logout',{}).status_code==200
            assert camera.get('/api/live/me').status_code==401
            before=room.frames_received
            camws.send(json.dumps({'seq':3,'w':320,'h':240,'capture_ts':time.time()}));camws.send(jpeg(shade=75))
            wait_for(lambda:room.frames_received>before)
            wait_for(lambda:room.frames_inferred>=3)
            results['camera_frames_after_logout']=room.frames_received-before
            # Drain to the current pre-logout judge output before updating it.
            target=room.annotated_jpeg
            for _ in range(5):
                if judgews.recv(timeout=2)==target: break
            assert post(judge,'/api/live/logout',{}).status_code==200
            assert judge.get(f'/api/live/rooms/{room.room_id}/state').status_code==401
            camws.send(json.dumps({'seq':4,'w':320,'h':240,'capture_ts':time.time()}));camws.send(jpeg(shade=90))
            wait_for(lambda:room.frames_inferred>=4)
            target=room.annotated_jpeg
            got=judgews.recv(timeout=2)
            results['judge_received_new_frame_after_logout']=(got==target)
            # Empty WS binary reaches the actual one-thread worker loop.
            camws.send(b'');wait_for(lambda:bool(worker_errors))
            results['worker_fatal_error']=worker_errors[0]
            results['worker_alive_after_empty_binary']=worker._worker_thread.is_alive()
            results['health_after_dead_worker']=camera.get('/api/live/health').json()
        unauthorized=[]
        inventory=json.loads((ROOT/'endpoint-inventory.json').read_text())
        for item in inventory:
            if item['path'].startswith('/api/live/'):
                continue
            r=camera.request(item['method'],item['path'],json={} if item['method']=='POST' else None)
            unauthorized.append({'path':item['path'],'method':item['method'],'status':r.status_code})
            assert r.status_code==404
        results['legacy_actual_tcp_inventory']=unauthorized
        statuses=[]
        for i in range(config.LOGIN_MAX_FAILURES+2):
            statuses.append(camera.post('/api/live/login',json={'role':'judge','pin':'QA_ONLY-wrong'},
                headers={'Origin':origin,'X-Forwarded-For':f'198.51.100.{i}'}).status_code)
        results['same_peer_rotated_xff_login_statuses']=statuses
finally:
    worker.stop()
    if worker._worker_thread: worker._worker_thread.join(timeout=2)
    server.should_exit=True;thread.join(timeout=3)
    sock.close()
    (ROOT/'live-tcp-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
