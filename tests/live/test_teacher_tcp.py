"""Owned actual loopback HTTP faults; response fixtures are NOT a real Teacher."""
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import httpcore._backends.sync

from test_acceptance import h, jpeg, ROOT
from app.live import config, teacher


def envelope(label='opening', confidence=.9):
    return {'model':'QA_ONLY_MOCK', 'choices':[{'message':{'content':json.dumps(
            {'label':label,'confidence':confidence})}}], 'usage':{'total_tokens':9},
            'experimental_metrics':{'revision':'QA_ONLY','image_count':1}}


@contextmanager
def server(payload=None, mode='normal'):
    receipts=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
            receipts.append({'time':time.monotonic(),'path':self.path,'body':json.loads(raw)})
            body=json.dumps(payload if payload is not None else envelope()).encode()
            status=401 if mode=='401' else 200
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            if mode in {'chunked','unfinished_chunk'}:
                self.send_header('Transfer-Encoding','chunked')
            else:
                self.send_header('Content-Length','garbage' if mode=='bad_length' else str(len(body)+(50 if mode=='truncated' else 0)))
            self.send_header('Connection','close')
            self.end_headers()
            try:
                if mode=='trickle':
                    for i in range(0,len(body),16):
                        self.wfile.write(body[i:i+16]); self.wfile.flush(); time.sleep(.02)
                elif mode in {'chunked','unfinished_chunk'}:
                    self.wfile.write(f'{len(body):x}\r\n'.encode()+body+b'\r\n')
                    if mode=='chunked': self.wfile.write(b'0\r\n\r\n')
                    self.wfile.flush()
                else:
                    self.wfile.write(body); self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError): pass
            self.close_connection=True
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    httpd.daemon_threads=True
    thread=threading.Thread(target=lambda:httpd.serve_forever(poll_interval=.01),daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_address[1]}',receipts
    finally:
        httpd.shutdown(); httpd.server_close(); thread.join(timeout=2)


def probe(h,monkeypatch,url,question='Is the bottle opening?',labels=None):
    monkeypatch.setattr(config,'TEACHER_BASE_URL',url)
    monkeypatch.setattr(config,'TEACHER_TOKEN','')
    c,room,code=h.room(); judge=h.judge(code)
    room.latest_jpeg=jpeg()
    response=h.post(judge,f'/api/live/rooms/{room.room_id}/probe',
                    {'question':question,'labels':labels or ['opening','closed']})
    return response


@pytest.mark.parametrize('value',[True,False,None,'0.9',-1,2,[],{},float('nan'),float('inf'),float('-inf')])
def test_original_strict_confidence_boundary_on_actual_http(h,monkeypatch,value):
    with server(envelope(confidence=value)) as (url,receipts):
        response=probe(h,monkeypatch,url)
    assert len(receipts)==1
    assert response.status_code==200
    assert response.json()['status'] in {'error','unsupported','unknown','invalid_response'}, (
        f'invalid confidence {type(value).__name__} classified ok: {response.json()}')


def test_missing_confidence_on_actual_http(h,monkeypatch):
    payload=envelope(); payload['choices'][0]['message']['content']='{"label":"opening"}'
    with server(payload) as (url,receipts): response=probe(h,monkeypatch,url)
    assert response.status_code==200
    assert response.json()['status']!='ok'


def test_local_candidate_contract_outside_requested_labels_is_unknown(h,monkeypatch):
    # Adaptation of committed local_teacher.py's actual experimental_metrics
    # contract. Mock image-conditioned scores; these are not genuine forwards.
    payload=envelope('occupied',.9)
    payload['experimental_metrics'].update({'scoring':{
        'method':'candidate_sequence_softmax','uncalibrated':True,
        'candidate_labels':['occupied','empty'], 'model_forward_calls':2,
        'actual_model_processed_tokens':18,'output_is_generated_json':False}})
    with server(payload) as (url,receipts): response=probe(h,monkeypatch,url)
    (ROOT/'teacher-contract-fixture.json').write_text(json.dumps({
        'response':response.json(),'request':receipts[0]['body'],'QA_ONLY':True},indent=2))
    assert response.status_code==200
    assert response.json()['status'] in {'unsupported','unknown','error'}, 'occupancy score accepted as bottle-opening observation'


@pytest.mark.parametrize('value',[.9,1])
def test_valid_teacher_response_is_uncertain_control(h,monkeypatch,value):
    with server(envelope(confidence=value)) as (url,receipts): response=probe(h,monkeypatch,url)
    assert response.status_code==200
    assert response.json()['status']=='ok' and response.json()['uncertain'] is True
    assert response.json()['label']=='opening'


@pytest.mark.parametrize('mode',['truncated','401','unfinished_chunk','bad_length'])
def test_actual_http_faults_nonconfirming_no_retry_controls(h,monkeypatch,mode):
    with server(mode=mode) as (url,receipts): response=probe(h,monkeypatch,url)
    assert response.status_code==200
    assert response.json()['status']=='error'
    assert len(receipts)==1


def test_correct_chunked_teacher_response_control(h,monkeypatch):
    with server(mode='chunked') as (url,receipts): response=probe(h,monkeypatch,url)
    assert response.status_code==200 and response.json()['status']=='ok'
    assert response.json()['uncertain'] is True and len(receipts)==1


def test_teacher_slow_body_obeys_overall_deadline(h,monkeypatch):
    monkeypatch.setattr(config,'TEACHER_TIMEOUT_SECONDS',.06)
    with server(mode='trickle') as (url,receipts):
        start=time.monotonic(); response=probe(h,monkeypatch,url); elapsed=time.monotonic()-start
    (ROOT/'teacher-trickle.json').write_text(json.dumps({'configured_timeout_s':.06,
        'elapsed_s':elapsed,'status':response.status_code,'result':response.json(),'requests':len(receipts),'QA_ONLY':True},indent=2))
    assert response.json()['status']=='error', f'success after {elapsed:.3f}s for .06s timeout'
    assert elapsed < .16


def test_teacher_admission_expiry_prevents_late_actual_request(h,monkeypatch):
    monkeypatch.setattr(config,'TEACHER_TIMEOUT_SECONDS',.04)
    gate=threading.Semaphore(0); monkeypatch.setattr(teacher,'_concurrency',gate)
    timer=threading.Timer(.12,gate.release); timer.start()
    with server() as (url,receipts):
        start=time.monotonic(); response=probe(h,monkeypatch,url); elapsed=time.monotonic()-start
    timer.join()
    assert receipts==[], f'{len(receipts)} request started after admission wait for .04s deadline, elapsed={elapsed:.3f}s'
    assert response.json()['status']=='error'


def test_original_actual_write_revocation_boundary(h,monkeypatch):
    c,room,code=h.room(); judge=h.judge(code); h.activate(room,judge,semantic=True,cls='bottle')
    acknowledgements=[]
    original=httpcore._backends.sync.SyncStream.write
    def write_after_revoke(stream,buffer,timeout=None):
        if buffer.startswith(b'POST /v1/chat/completions') and not acknowledgements:
            r=h.post(judge,f'/api/live/rooms/{room.room_id}/task/state',{'enabled':False})
            assert r.status_code==200
            acknowledgements.append(time.monotonic())
        return original(stream,buffer,timeout)
    monkeypatch.setattr(httpcore._backends.sync.SyncStream,'write',write_after_revoke)
    with server() as (url,receipts):
        monkeypatch.setattr(config,'TEACHER_BASE_URL',url)
        monkeypatch.setattr(config,'TEACHER_TOKEN','')
        h.frame(room,1); h.frame(room,2)
    assert acknowledgements and len(room.notifications)==0
    (ROOT/'teacher-disable-send.json').write_text(json.dumps({'disable_ack':acknowledgements[0],
        'actual_request_times':[r['time'] for r in receipts],'requests_after_ack':len(receipts),
        'notifications':len(room.notifications),'QA_ONLY':True},indent=2))
    assert receipts==[], 'actual POST/image bytes sent after acknowledged disable'


def test_cache_labels_model_and_room_are_in_identity(h,monkeypatch):
    with server(envelope()) as (url,receipts):
        monkeypatch.setattr(config,'TEACHER_BASE_URL',url)
        a=teacher.observe('QA_ONLY-roomA','same question',['opening','closed'],[jpeg()])
        monkeypatch.setattr(config,'TEACHER_MODEL','QA_ONLY_OTHER_MODEL')
        b=teacher.observe('QA_ONLY-roomB','same question',['occupied','empty'],[jpeg()])
    assert len(receipts)==2, 'second room/model/label schema reused first room observation'
    assert b is not a


def test_attempt_budget_counts_real_failed_http_control(h,monkeypatch):
    monkeypatch.setattr(config,'TEACHER_ROOM_BUDGET',1)
    with server(mode='401') as (url,receipts):
        monkeypatch.setattr(config,'TEACHER_BASE_URL',url)
        a=teacher.observe('QA_ONLY-room','question one',['a','b'],[jpeg()])
        b=teacher.observe('QA_ONLY-room','question two',['a','b'],[jpeg()])
    assert a.status=='error' and b.status=='budget'
    assert len(receipts)==1
