"""Independent QA: owned loopback TCP fixtures; no models or real providers."""
import contextlib,json,os,select,socket,socketserver,threading,time
from pathlib import Path
from unittest.mock import patch
os.environ['VISIONFLOW_DATA_DIR']='/tmp/visionflow-a-qa-25bccee/data'
import httpx,numpy as np,uvicorn
from app import pipeline
from app.db import VideoSource,Workflow,TrackEvent,Notification,get_session
from app.main import app
from app.teacher import OpenAICompatibleTeacher
from app.vlm_router import VlmRouter,set_router
from visionflow_vision.events import TrackedObject
OUT=[]
def report(name,**kw):
    x={'name':name,**kw};OUT.append(x);print(json.dumps(x),flush=True)
def envelope(spec):
    label={'label':spec.get('label','yes')}
    if not spec.get('missing_confidence'):label['confidence']=spec.get('confidence',0.9)
    return json.dumps({'choices':[{'message':{'content':json.dumps(label)}}],'usage':{'total_tokens':7}}).encode()
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sock=self.request;sock.settimeout(2)
        with self.server.lock:
            idx=len(self.server.connections);self.server.connections.append(time.monotonic())
            spec=self.server.specs[min(idx,len(self.server.specs)-1)]
        mode=spec.get('mode','fast')
        rec={'at':None,'first_at':None,'complete':False,'received':0,'closed':threading.Event()}
        try:
            if mode=='tls_stall':
                sock.recv(8192);time.sleep(0.7);return
            raw=b''
            while b'\r\n\r\n' not in raw:
                d=sock.recv(8192)
                if not d:return
                if rec['first_at'] is None:
                    rec['first_at']=time.monotonic()
                    with self.server.lock:self.server.records.append(rec)
                raw+=d;rec['received']+=len(d)
                if mode=='send_stall':
                    time.sleep(0.5)
                    return
            head,_,body=raw.partition(b'\r\n\r\n')
            n=int(next(l.split(b':',1)[1] for l in head.split(b'\r\n') if l.lower().startswith(b'content-length:')))
            while len(body)<n:
                d=sock.recv(65536)
                if not d:return
                body+=d;rec['received']+=len(d)
            rec['at']=time.monotonic();rec['complete']=True
            payload=envelope(spec);status=spec.get('status',200)
            header=f'HTTP/1.1 {status} QA\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n'.encode()
            if mode=='slow_headers':
                sock.sendall(b'HTTP/1.1 200 OK\r\nX-P: ')
                for _ in range(15):time.sleep(0.04);sock.sendall(b'x')
                sock.sendall(b'\r\nContent-Length: '+str(len(payload)).encode()+b'\r\n\r\n'+payload)
            elif mode=='header_then_stall':
                time.sleep(0.16);sock.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 500\r\n\r\n')
            elif mode=='trickle':
                sock.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n')
                for _ in range(80):
                    if select.select([sock],[],[],0.02)[0] and sock.recv(1)==b'':return
                    sock.sendall(b'20\r\n'+b' '*32+b'\r\n')
            elif mode=='truncated_length':
                sock.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(payload)+500).encode()+b'\r\n\r\n'+payload);return
            elif mode=='truncated_chunked':
                sock.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+hex(len(payload))[2:].encode()+b'\r\n'+payload+b'\r\n');return
            elif mode=='bad_length':
                sock.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: garbage\r\n\r\n'+payload);return
            elif mode=='oversized':
                body=payload+b' '*4096
                sock.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);return
            elif mode=='chunked_fast':
                sock.sendall(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'+hex(len(payload))[2:].encode()+b'\r\n'+payload+b'\r\n0\r\n\r\n');return
            else:
                sock.sendall(header+payload)
            while sock.recv(8192):pass
        except OSError:pass
        finally:rec['closed_at']=time.monotonic();rec['closed'].set()
@contextlib.contextmanager
def provider(specs):
    srv=Server(('127.0.0.1',0),Handler);srv.records=[];srv.connections=[];srv.specs=specs;srv.lock=threading.Lock()
    thread=threading.Thread(target=srv.serve_forever,kwargs={'poll_interval':0.01},daemon=True);thread.start()
    try:yield srv,f'http://127.0.0.1:{srv.server_address[1]}/v1'
    finally:srv.shutdown();srv.server_close();thread.join(1)
def teacher(url,timeout=0.2,**kw):
    return OpenAICompatibleTeacher(url,'','owned-qa-fixture','v1',overall_timeout=timeout,connect_timeout=kw.pop('connect_timeout',5),read_timeout=kw.pop('read_timeout',5),max_retries=kw.pop('max_retries',0),**kw)
def timed(t,guard=None):
    start=time.monotonic()
    try:r=t.classify(b'owned-fixture','hood open?',['yes','no'],on_attempt=guard);data=r.model_dump()
    except Exception as exc:data={'raised':type(exc).__name__,'error':str(exc)}
    return data,time.monotonic()-start
def routing(t,**kw):return VlmRouter(teacher_provider=lambda:t,sample_interval_s=0,cooldown_s=0,**kw)
def route(router,image=b'owned',task='k',**kw):
    return router.route(task_key=task,scope=task,prompt='hood open?',labels=['yes','no'],image_bytes=image,**kw)
def transport_probes():
    for mode in ['slow_headers','header_then_stall','trickle']:
        with provider([{'mode':mode},{'mode':'fast'}]) as (srv,url):
            t=teacher(url);r,elapsed=timed(t)
            closed=bool(srv.records and srv.records[0]['closed'].wait(0.3))
            free=t._semaphore.acquire(blocking=False)
            if free:t._semaphore.release()
            next_result,next_elapsed=timed(t)
            report(mode,result=r,elapsed=elapsed,deadline=0.2,tcp_closed_before_next=closed,permit_free=free,subsequent_status=next_result.get('status'),requests=len(srv.records))
    with provider([{}]) as (srv,url):
        t=teacher(url,timeout=0.1);router=routing(t)
        def slow_admit():time.sleep(0.25);return True
        start=time.monotonic();d=route(router,admit=slow_admit)
        report('slow_production_admission',elapsed=time.monotonic()-start,deadline=0.1,result=d.result.model_dump(),requests=len(srv.records),attempts=router.counters.outbound_attempts)
    with provider([{}]) as (srv,url):
        t=teacher(url,timeout=0.1);original=socket.create_connection
        def slow_conn(*a,**kw):time.sleep(0.25);return original(*a,**kw)
        with patch.object(socket,'create_connection',slow_conn):r,elapsed=timed(t)
        report('slow_connect',result=r,elapsed=elapsed,deadline=0.1,requests=len(srv.records))
    for mode,delay,deadline in [('fast',0.25,0.1),('tls_stall',0.16,0.2)]:
        with provider([{'mode':mode}]) as (srv,url):
            if mode=='tls_stall':url=url.replace('http:','https:')
            t=teacher(url,timeout=deadline);original=socket.getaddrinfo;port=srv.server_address[1]
            def slow_dns(host,p,*a,**kw):
                if p==port:time.sleep(delay)
                return original(host,p,*a,**kw)
            with patch.object(socket,'getaddrinfo',slow_dns):r,elapsed=timed(t)
            report('dns_tls_deadline' if mode=='tls_stall' else 'dns_deadline',result=r,elapsed=elapsed,deadline=deadline,dns_fixture_delay=delay,requests=len(srv.records),connections=len(srv.connections))
    with provider([{},{}]) as (srv,url):
        t=teacher(url,timeout=0.5,read_timeout=0.04)
        # A stall within overall budget but beyond configured read timeout.
        srv.specs=[{'mode':'header_then_stall'}]
        r,elapsed=timed(t)
        report('read_timeout_configuration',result=r,elapsed=elapsed,read_timeout=0.04,overall_timeout=0.5)
    with provider([{'status':503},{'status':200}]) as (srv,url):
        t=teacher(url,timeout=2,max_retries=1);router=routing(t,budget_per_task=2)
        first=route(router);cached=route(router);exhausted=route(router,image=b'different')
        report('retry_cache_budget',first_status=first.result.status,cached=cached.status,exhausted=exhausted.status,requests=len(srv.records),counters=router.stats())
    for status in [401,403,422]:
        with provider([{'status':status}]) as (srv,url):
            r,elapsed=timed(teacher(url,timeout=2,max_retries=2))
            report('nonretry_error',http_status=status,result=r,requests=len(srv.records))
    with provider([{'mode':'oversized'}]) as (srv,url):
        r,elapsed=timed(teacher(url,max_response_bytes=512))
        report('response_cap',result=r,requests=len(srv.records),confirmed=r.get('status')=='ok')
    with provider([{'mode':'send_stall'}]) as (srv,url):
        t=teacher(url,timeout=0.12);router=routing(t,budget_per_task=1)
        statuses=[]
        for i in range(3):
            d=route(router,image=bytes([65+i])*(4*1024*1024));statuses.append({'route_status':d.status,'result':d.result.model_dump() if d.result else None})
        report('partial_send_budget',results=statuses,received_connections=len(srv.records),received_bytes=[r['received'] for r in srv.records],complete_requests=sum(r['complete'] for r in srv.records),counters=router.stats(),budget_used=router._budget_used)
    # Closed owned port: no external destination; direct adapter must not throw.
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    r,elapsed=timed(teacher(f'http://127.0.0.1:{port}/v1',timeout=0.3,max_retries=1))
    report('connection_refused',result=r,elapsed=elapsed)
@contextlib.contextmanager
def api():
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(64)
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,loop='asyncio',workers=1))
    worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);worker.start()
    until=time.monotonic()+3
    while not server.started and time.monotonic()<until:time.sleep(0.005)
    assert server.started
    with httpx.Client(base_url=f'http://127.0.0.1:{sock.getsockname()[1]}',timeout=3,trust_env=False) as c:
        try:yield c
        finally:server.should_exit=True;worker.join(3);sock.close()
def api_probes():
    with api() as c:
        with get_session() as s:
            src=VideoSource(name='owned-non-model-fixture',path='/tmp/owned-fixture-no-video.mp4');s.add(src);s.commit();src_id=src.id
        assert c.post('/api/zones',json={'source_id':src_id,'name':'Service Bay A','polygon':[[0,0],[1,0],[1,1],[0,1]]}).status_code==201
        for p in json.loads(Path('/tmp/visionflow-a-qa-25bccee/grammar-results.json').read_text())['probes']:
            resp=c.post('/api/workflows/compile',json={'source_id':src_id,'text':p['text']})
            report('compile_api',text=p['text'],http_status=resp.status_code,result=resp.json())
        draft=c.post('/api/workflows/compile',json={'source_id':src_id,'text':'When a car enters Service Bay A with hood open, create an alert'}).json()['draft']
        wf=c.post('/api/workflows',json=draft).json();wf_id=wf['id']
        assert wf['enabled'] is False
        assert c.post(f'/api/workflows/{wf_id}/enable').status_code==200
        report('explicit_approval',created_enabled=wf['enabled'],enabled_after_approval=True)
        def route_dispatch(key):
            with get_session() as s:
                wf=s.get(Workflow,wf_id)
                ev=TrackEvent(source_id=src_id,workflow_id=wf_id,track_id=1,type='object_entered_zone',class_name='car',video_timestamp=1,confidence=0.9,detail='owned',dedupe_key=key,action_status='pending')
                s.add(ev);s.commit()
                routed=pipeline._route_visual(s,wf,ev,np.full((100,100,3),40,dtype=np.uint8),[TrackedObject(track_id=1,class_name='car',confidence=0.9,x1=10,y1=10,x2=40,y2=40)])
                if routed:pipeline._dispatch_action(s,wf,ev)
                s.refresh(ev)
                return {'routed':routed,'visual_status':ev.visual_status,'action_status':ev.action_status,'notifications':s.query(Notification).filter(Notification.event_id==ev.id).count()}
        invalid=[True,False,None,'0.9',float('nan'),float('inf'),float('-inf'),-0.1,1.1,[],{}]
        for i,spec in enumerate([{'confidence':v} for v in invalid]+[{'missing_confidence':True},{'confidence':0.1},{'confidence':0.9},{'confidence':1}]):
            with provider([spec]) as (srv,url):
                t=teacher(url,timeout=1);set_router(routing(t));result=route_dispatch(f'confidence-{i}')
                expected='invalid_response' if i<12 else ('low_confidence' if i==12 else 'ok')
                assert result['visual_status']==expected,(i,result)
                assert result['notifications']==(1 if i>=13 else 0),(i,result)
                report('confidence_action',confidence=repr(spec),requests=len(srv.records),**result)
        for mode in ['chunked_fast','truncated_length','truncated_chunked','bad_length']:
            with provider([{'mode':mode}]) as (srv,url):
                set_router(routing(teacher(url,timeout=1)));result=route_dispatch(f'framing-{mode}')
                report('framing_action',mode=mode,requests=len(srv.records),**result)
        # Actual old connection race: pause socket creation before a POST exists.
        with provider([{}]) as (srv,url):
            t=teacher(url,timeout=2);router=routing(t);set_router(router)
            paused,release=threading.Event(),threading.Event();original=socket.create_connection;port=srv.server_address[1];out={}
            def paused_conn(addr,*a,**kw):
                if addr[1]==port:paused.set();assert release.wait(2)
                return original(addr,*a,**kw)
            def work():out.update(route_dispatch('disable-connect'))
            with patch.object(socket,'create_connection',paused_conn):
                th=threading.Thread(target=work);th.start();assert paused.wait(2)
                before=len(srv.records);start=time.monotonic();resp=c.post(f'/api/workflows/{wf_id}/disable');ack=time.monotonic()
                release.set();th.join(3)
            assert not th.is_alive()
            report('disable_connection_race',disable_http=resp.status_code,disable_elapsed=ack-start,requests_before_ack=before,requests=len(srv.records),attempts=router.counters.outbound_attempts,**out)
        assert c.post(f'/api/workflows/{wf_id}/enable').status_code==200
        # Pause the actual socket.sendall, after approval has been read. The
        # disable must BLOCK until this already-admitted write exits its lock.
        with provider([{}]) as (srv,url):
            t=teacher(url,timeout=2);router=routing(t);set_router(router)
            paused,release=threading.Event(),threading.Event();original=socket.create_connection;port=srv.server_address[1];out={};disable={}
            class PausedSendSocket:
                def __init__(self,sock):self.sock=sock
                def __getattr__(self,n):return getattr(self.sock,n)
                def sendall(self,data):paused.set();assert release.wait(2);return self.sock.sendall(data)
            def wrap_conn(addr,*a,**kw):
                conn=original(addr,*a,**kw)
                return PausedSendSocket(conn) if addr[1]==port else conn
            def work():out.update(route_dispatch('disable-send'))
            def disabler():
                with httpx.Client(base_url=str(c.base_url),timeout=3,trust_env=False) as cc:
                    r=cc.post(f'/api/workflows/{wf_id}/disable');disable.update(http_status=r.status_code,ack=time.monotonic())
            with patch.object(socket,'create_connection',wrap_conn):
                th=threading.Thread(target=work);th.start();assert paused.wait(2)
                dt=threading.Thread(target=disabler);dt.start();time.sleep(0.06)
                blocked=dt.is_alive();before=len(srv.records);release.set();th.join(3);dt.join(3)
            assert not th.is_alive() and not dt.is_alive()
            report('disable_actual_send_race',disable_blocked_during_unsent_write=blocked,requests_before_release=before,requests=len(srv.records),disable_http=disable.get('http_status'),attempts=router.counters.outbound_attempts,**out)
        set_router(None)
if __name__=='__main__':
    transport_probes();api_probes()
    Path('/tmp/visionflow-a-qa-25bccee/network-results.json').write_text(json.dumps({'target_sha':'25bccee269bde978745c168852a716670b7f999b','results':OUT},indent=2))
