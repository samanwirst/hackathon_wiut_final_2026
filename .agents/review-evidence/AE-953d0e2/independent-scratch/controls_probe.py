"""QA_ONLY controls: real TCP preflight, versions, retries, TLS failure and dedup."""
import json,threading,time
from pathlib import Path
from unittest.mock import patch
import network_probe as n
from app import config
OUT=[]
def record(name,**kwargs):
    r={'name':name,**kwargs};OUT.append(r);print(json.dumps(r),flush=True)
with n.provider([{}]) as (srv,url):
    teacher=n.teacher(url,timeout=.4,max_image_bytes=2);r=n.routing(teacher,budget_per_task=1)
    d=n.route(r,image=b'oversize')
    record('raw_preflight',status=d.result.status,attempts=r.counters.outbound_attempts,posts=len(srv.records),connections=len(srv.connections),budget=dict(r._budget_used))
    d=n.route(r,image=b'x')
    record('raw_preflight_supported_control',status=d.result.status,attempts=r.counters.outbound_attempts,posts=len(srv.records),budget=dict(r._budget_used))
with n.provider([{}, {}, {}, {}, {}, {}]) as (srv,url):
    teacher=n.teacher(url,timeout=.4);r=n.routing(teacher,budget_per_task=20)
    statuses=[]
    for image,task in [(b'x','task1'),(b'x','task1'),(b'y','task1'),(b'x','task2')]:
        d=n.route(r,image=image,task=task);statuses.append(d.status)
    teacher.model='QA_ONLY-new-model';statuses.append(n.route(r,image=b'x',task='task1').status)
    with patch.object(config,'TEACHER_PROMPT_VERSION','QA_ONLY-new-prompt-version'):
        statuses.append(n.route(r,image=b'x',task='task1').status)
    record('real_tcp_cache_invalidation',statuses=statuses,posts=len(srv.records),attempts=r.counters.outbound_attempts)
with n.provider([{'mode':'header_then_stall'}]) as (srv,url):
    t=n.teacher(url,timeout=.08);r=n.routing(t)
    results=[]
    def work():results.append(n.route(r,image=b'x'))
    a=threading.Thread(target=work);a.start()
    until=time.monotonic()+1
    while not srv.records and time.monotonic()<until:time.sleep(.002)
    b=threading.Thread(target=work);b.start();a.join(1);b.join(1)
    assert not a.is_alive() and not b.is_alive()
    record('real_tcp_inflight_dedup',statuses=[d.status for d in results],result_statuses=[d.result.status if d.result else None for d in results],posts=len(srv.records),attempts=r.counters.outbound_attempts)
with n.provider([{'status':503},{'status':200}]) as (srv,url):
    t=n.teacher(url,timeout=1,max_retries=1);r=n.routing(t,budget_per_task=1);d=n.route(r)
    record('retry_budget_1',status=d.result.status,posts=len(srv.records),attempts=r.counters.outbound_attempts,budget=dict(r._budget_used))
with n.provider([{}]) as (srv,url):
    # Owned server understands plain HTTP, so TLS fails without external networking.
    result,elapsed=n.timed(n.teacher(url.replace('http:','https:'),timeout=.1))
    record('tls_failure_normalized',result=result,elapsed=elapsed)
Path('/tmp/visionflow-m2-emergency-review-953d0e2/controls-results.json').write_text(json.dumps({'target_sha':'953d0e275177951a71c4c8fccf6b915693e43550','results':OUT},indent=2))
