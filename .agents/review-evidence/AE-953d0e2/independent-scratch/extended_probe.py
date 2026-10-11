"""QA_ONLY: original helpers + extended real TCP, capacity, and UI boundary checks."""
import json, socket, socketserver, threading, time, contextlib, subprocess
from pathlib import Path
from unittest.mock import patch
import network_probe as n
from app.db import VideoSource, Workflow, TrackEvent, Notification, get_session
from app import pipeline
from app.vlm_router import set_router
import numpy as np
from visionflow_vision.events import TrackedObject
OUT=[]
def record(name, **kwargs):
    r={"name":name,**kwargs}; OUT.append(r); print(json.dumps(r),flush=True)

# Retain the original resolver fault boundary; do not simulate sendall.
with n.provider([{}]) as (srv,url):
    t=n.teacher(url,timeout=.06,max_concurrency=1); real=socket.getaddrinfo
    lock=threading.Lock(); active=0; peak=0; started=0; completed=0
    def slow_dns(host,port,*args,**kwargs):
        global active,peak,started,completed
        if port==srv.server_address[1]:
            with lock: active+=1;started+=1;peak=max(peak,active)
            try: time.sleep(.5);return real(host,port,*args,**kwargs)
            finally:
                with lock: active-=1;completed+=1
        return real(host,port,*args,**kwargs)
    with patch.object(socket,'getaddrinfo',slow_dns):
        results=[]
        for i in range(4):
            result,elapsed=n.timed(t)
            free=t._semaphore.acquire(blocking=False)
            if free:t._semaphore.release()
            results.append({'result':result,'elapsed':elapsed,'permit_free':free,'active_helpers':active})
        record('dns_actual_capacity',limit=1,peak=peak,started=started,active_after_timeouts=active,results=results)
        time.sleep(.55)
    record('dns_helpers_terminated',completed=completed,active=active,posts=len(srv.records),tcp_connections=len(srv.connections))
with n.provider([{'mode':'tls_stall'}]) as (srv,url):
    r,elapsed=n.timed(n.teacher(url.replace('http:','https:'),timeout=.5,connect_timeout=.04))
    record('tls_connect_phase',result=r,elapsed=elapsed,connect_timeout=.04,overall_timeout=.5)

class RawHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2); raw=b''
        try:
            while b'\r\n\r\n' not in raw:
                part=self.request.recv(8192)
                if not part:return
                raw+=part
            head,_,body=raw.partition(b'\r\n\r\n')
            length=int(next(x.split(b':',1)[1] for x in head.split(b'\r\n') if x.lower().startswith(b'content-length:')))
            while len(body)<length:
                part=self.request.recv(65536)
                if not part:return
                body+=part
            self.server.posts+=1
            self.request.sendall(self.server.response)
        except OSError:pass
@contextlib.contextmanager
def raw_provider(response):
    srv=n.Server(('127.0.0.1',0),RawHandler);srv.response=response;srv.posts=0
    th=threading.Thread(target=srv.serve_forever,kwargs={'poll_interval':.01},daemon=True);th.start()
    try:yield srv,f'http://127.0.0.1:{srv.server_address[1]}/v1'
    finally:srv.shutdown();srv.server_close();th.join(1)
payload=n.envelope({});length=str(len(payload)).encode()
head=b'HTTP/1.1 200 OK\r\n';cl=b'Content-Length: '+length+b'\r\n\r\n'
chhead=head+b'Transfer-Encoding: chunked\r\n\r\n'
chunk=hex(len(payload))[2:].encode()+b'\r\n'+payload+b'\r\n'
cases={
 'content_length_control':head+cl+payload,
 'chunked_control':chhead+chunk+b'0\r\n\r\n',
 'valid_trailer_control':chhead+chunk+b'0\r\nX-QA: owned\r\n\r\n',
 'conflicting_duplicate_lengths':head+b'Content-Length: 99999\r\nContent-Length: '+length+b'\r\n\r\n'+payload,
 'negative_length':head+b'Content-Length: -1\r\n\r\n'+payload,
 'comma_conflicting_length':head+b'Content-Length: 99999, '+length+b'\r\n\r\n'+payload,
 'length_and_chunked':head+b'Content-Length: '+length+b'\r\nTransfer-Encoding: chunked\r\n\r\n'+chunk+b'0\r\n\r\n',
 'missing_trailer_blank_line':chhead+chunk+b'0\r\nX-QA: owned\r\n',
 'invalid_trailer':chhead+chunk+b'0\r\nNOT A HEADER\r\n\r\n',
 'invalid_data_crlf':chhead+hex(len(payload))[2:].encode()+b'\r\n'+payload+b'XX0\r\n\r\n',
 'empty_terminal_size':chhead+chunk+b'\r\n\r\n',
 'signed_chunk_size':chhead+b'+'+hex(len(payload))[2:].encode()+b'\r\n'+payload+b'\r\n0\r\n\r\n',
 'negative_terminal_size':chhead+chunk+b'-0\r\n\r\n',
 'invalid_status_line':b'GARBAGE 200 OK\r\n'+cl+payload,
 'invalid_transfer_encoding':head+b'Transfer-Encoding: notchunked\r\n\r\n'+chunk+b'0\r\n\r\n',
}
with n.api() as c:
    with get_session() as s:
        src=VideoSource(name='QA_ONLY-extended',path='/tmp/visionflow-m2-emergency-review-953d0e2/not-video.mp4');s.add(src);s.commit();src_id=src.id
    zone=c.post('/api/zones',json={'source_id':src_id,'name':'Service Bay A','polygon':[[0,0],[1,0],[1,1],[0,1]]}).json()
    text='When a car enters Service Bay A with hood open, create an alert'
    draft=c.post('/api/workflows/compile',json={'source_id':src_id,'text':text}).json()['draft']
    wf=c.post('/api/workflows',json=draft).json();wf_id=wf['id'];assert not wf['enabled']
    assert c.post(f'/api/workflows/{wf_id}/enable').status_code==200
    for mode,response in cases.items():
        with raw_provider(response) as (srv,url):
            router=n.routing(n.teacher(url,timeout=.6));set_router(router)
            with get_session() as s:
                wf=s.get(Workflow,wf_id)
                ev=TrackEvent(source_id=src_id,workflow_id=wf_id,track_id=1,type='object_entered_zone',class_name='car',video_timestamp=1,confidence=.9,detail='QA_ONLY',dedupe_key='extended-'+mode,action_status='pending')
                s.add(ev);s.commit()
                routed=pipeline._route_visual(s,wf,ev,np.full((100,100,3),40,dtype=np.uint8),[TrackedObject(track_id=1,class_name='car',confidence=.9,x1=10,y1=10,x2=40,y2=40)])
                if routed:pipeline._dispatch_action(s,wf,ev)
                s.refresh(ev)
                record('extended_framing',mode=mode,routed=routed,visual_status=ev.visual_status,action_status=ev.action_status,notifications=s.query(Notification).filter(Notification.event_id==ev.id).count(),posts=srv.posts,attempts=router.counters.outbound_attempts)
    set_router(None)
    extra=[
      'When a car enters Service Bay A with hood open or flashing, create an alert',
      'When a car enters Service Bay A with hood open or off, create an alert',
      'When a car enters Service Bay A with hood open and up, create an alert',
      'When a car stays in Service Bay A for 1.4 seconds, create an alert',
      'When a car stays in Service Bay A for 1.25 seconds, create an alert',
      'When a car stays in Service Bay A for 0.024 minutes, create an alert',
      'Create an alert for 5 minutes a car stays in Service Bay A',
      'When a car enters Service Bay A with hood open or closed, create an alert',
      'When a car enters Service Bay A, open the gate',
      'When a car enters Service Bay A, bake a cake',
    ]
    for text in extra:
        resp=c.post('/api/workflows/compile',json={'source_id':src_id,'text':text})
        record('extended_compile',text=text,http_status=resp.status_code,result=resp.json())
    for duration in ['1.4 seconds','1.25 seconds','0.024 minutes','2.5 minutes']:
        text=f'When a car stays in Service Bay A for {duration}, create an alert'
        d=c.post('/api/workflows/compile',json={'source_id':src_id,'text':text}).json()['draft']
        result=subprocess.run(['node','/tmp/visionflow-m2-emergency-review-953d0e2/ui_roundtrip.js'],input=json.dumps({'draft':d}),text=True,capture_output=True,check=True)
        ui=json.loads(result.stdout);stored=c.post('/api/workflows',json=ui['payload']).json()
        enabled=c.post(f"/api/workflows/{stored['id']}/enable").json()
        record('ui_roundtrip',text=text,draft=d,ui=ui,stored_dsl=stored['dsl'],created_enabled=stored['enabled'],explicit_enabled=enabled['enabled'])
Path('/tmp/visionflow-m2-emergency-review-953d0e2/extended-results.json').write_text(json.dumps({'target_sha':'953d0e275177951a71c4c8fccf6b915693e43550','results':OUT},indent=2))
