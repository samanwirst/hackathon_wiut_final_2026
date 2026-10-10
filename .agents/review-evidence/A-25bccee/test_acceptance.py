"""Desired acceptance assertions over independently measured owned-TCP evidence."""
import json
from pathlib import Path
import pytest
R=json.loads(Path('/tmp/visionflow-a-qa-25bccee/network-results.json').read_text())['results']
def one(name):return next(r for r in R if r['name']==name)
def test_m2_001_preserves_complete_intent():
    texts={
      'Create an alert for 5 minutes when a car stays in Service Bay A',
      'When a car enters Service Bay A with hood and trunk open, create an alert',
      'When 3 or more or 5 or more cars are in Service Bay A, create an alert',
    }
    accepted=[r['text'] for r in R if r['name']=='compile_api' and r['text'] in texts and r['result']['ok']]
    assert not accepted,accepted
def test_m2_003_one_deadline_includes_resolution_and_tls():
    xs=[one(n) for n in ['dns_deadline','dns_tls_deadline','slow_production_admission']]
    overruns=[{'name':x['name'],'elapsed':x['elapsed'],'deadline':x['deadline']} for x in xs if x['elapsed']>x['deadline']+0.05]
    assert not overruns,overruns
def test_m2_004_partial_sends_consume_attempt_budget():
    x=one('partial_send_budget')
    assert x['received_connections']<=1 and x['counters']['outbound_attempts']==1,x
def test_m2_010_invalid_http_cannot_authorize_actions():
    xs=[r for r in R if r['name']=='framing_action' and r['mode']!='chunked_fast']
    assert all(x['notifications']==0 and not x['routed'] for x in xs),xs
