"""Desired acceptance over independently recorded production-boundary evidence."""
import json
from pathlib import Path
P=Path('/tmp/visionflow-m2-emergency-review-953d0e2')
E=json.loads((P/'extended-results.json').read_text())['results']
A=json.loads((P/'additional-results.json').read_text())['results']
N=json.loads((P/'network-results.json').read_text())['results']
C=json.loads((P/'controls-results.json').read_text())['results']
def one(rows,name):return next(x for x in rows if x['name']==name)
def test_m2_001_rejects_competing_states():
    bad=[r for r in A if r['name']=='additional_compile' and ('headlights on or off' in r['text'] or 'headlights on and off' in r['text']) and r['result']['ok']]
    assert not bad,bad
def test_m2_003_actual_active_capacity_stays_bounded():
    x=one(E,'dns_actual_capacity')
    assert x['peak']<=x['limit'],x
def test_m2_003_absolute_admission_does_not_reset_deadline():
    x=one(A,'absolute_admission')
    assert x['elapsed']<=x['deadline']+.05,x
def test_m2_003_configured_connect_includes_tls():
    x=one(E,'tls_connect_phase')
    assert x['elapsed']<=x['connect_timeout']+.05,x
def test_m2_010_malformed_framing_never_authorizes():
    controls={'content_length_control','chunked_control','valid_trailer_control'}
    bad=[r for r in E if r['name']=='extended_framing' and r['mode'] not in controls and (r['routed'] or r['notifications'])]
    assert not bad,bad
def test_m2_011_ui_keeps_decimal_semantics():
    bad=[{'text':r['text'],'compiled':r['draft']['trigger']['duration_seconds'],'stored':r['stored_dsl']['trigger']['duration_seconds']} for r in E if r['name']=='ui_roundtrip' and r['draft']['trigger']['duration_seconds']!=r['stored_dsl']['trigger']['duration_seconds']]
    assert not bad,bad
def test_supported_framing_and_approval_controls():
    controls={'content_length_control','chunked_control','valid_trailer_control'}
    xs=[r for r in E if r['name']=='extended_framing' and r['mode'] in controls]
    assert len(xs)==3 and all(r['routed'] and r['notifications']==1 for r in xs)
    assert all(not r['created_enabled'] and r['explicit_enabled'] for r in E if r['name']=='ui_roundtrip')
def test_m2_007_exact_connection_and_write_races():
    a=one(N,'disable_connection_race');b=one(N,'disable_actual_send_race')
    assert a['disable_http']==200 and a['requests']==0 and a['attempts']==0 and a['notifications']==0
    assert b['disable_blocked_during_unsent_write'] and b['attempts']==1 and b['action_status']=='cancelled' and b['notifications']==0
def test_m2_008_confidence_boundaries():
    xs=[r for r in N if r['name']=='confidence_action']
    assert len(xs)==15 and all(not r['routed'] and r['notifications']==0 for r in xs[:13])
    assert all(r['routed'] and r['notifications']==1 for r in xs[13:])
def test_m2_004_preflight_write_and_retry_accounting():
    a=one(C,'raw_preflight');b=one(C,'raw_preflight_supported_control');partial=one(N,'partial_send_budget');retry=one(C,'retry_budget_1');expired=one(A,'absolute_admission')
    assert a['attempts']==0 and a['posts']==0 and not a['budget']
    assert b['status']=='ok' and b['attempts']==1 and b['posts']==1
    assert partial['received_connections']==1 and partial['received_bytes']==[8192] and partial['counters']['outbound_attempts']==1
    assert retry['attempts']==1 and retry['posts']==1
    assert expired['attempts']==0 and expired['posts']==0
def test_cache_versions_and_inflight_dedup_controls():
    a=one(C,'real_tcp_cache_invalidation');b=one(C,'real_tcp_inflight_dedup')
    assert a['statuses']==['called','cache_hit','called','called','called','called'] and a['posts']==5 and a['attempts']==5
    assert set(b['statuses'])=={'called','deduped'} and b['posts']==1 and b['attempts']==1
def test_endpoint_privacy_and_webhook_controls():
    a=one(A,'provider_public_privacy');b=one(A,'webhook_api_rejection')
    assert a['status']=='ok' and not a['contains_token'] and not a['contains_endpoint'] and not a['contains_image']
    assert b['http_status']==422
