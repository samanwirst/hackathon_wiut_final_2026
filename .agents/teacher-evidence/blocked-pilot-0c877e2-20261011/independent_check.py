"""Read-only verification of one explicitly unaccepted, nonactioning pilot.

No HTTP requests, fitting, mutation, activation or alternate split is performed.
Uses the exact saved Student and genuinely pretrained frozen ResNet18 for reload.
"""
from pathlib import Path
import hashlib, json, math, os, sqlite3, subprocess, time
import numpy as np
import torch
from app.autolearn import encoder, student

ROOT = Path('/home/samanwirst/Desktop/hackathon_wiut_final_2026')
RT = ROOT / '.agents/runtime/ten-hour'
WT = RT / 'worktrees/C-emergency'
OUT = RT / 'CE/blocked-nonactioning-pilot-0c877e2'
E = OUT / 'evidence'
CONTROL = RT / 'TEACHER_EMERGENCY/blocked-pilot-control'
SHA = '0c877e227062af7d3def121490419be158cb16c4'
SCOPE = 'M3 BLOCKED / UNACCEPTED_NONACTIONING_EXPERIMENT'

def load(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def confusion(truth, predicted):
    tp = sum(t == 1 and p == 1 for t,p in zip(truth,predicted))
    fp = sum(t == 0 and p == 1 for t,p in zip(truth,predicted))
    fn = sum(t == 1 and p == 0 for t,p in zip(truth,predicted))
    tn = sum(t == 0 and p == 0 for t,p in zip(truth,predicted))
    n = tp+fp+fn+tn
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0
    return dict(confusion_matrix=dict(tp=tp,fp=fp,fn=fn,tn=tn),support=n,
                precision=round(precision,4),recall=round(recall,4),
                f1=round(f1,4),accuracy=round((tp+tn)/n,4))

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=WT,text=True).strip() == SHA
assert not subprocess.check_output(['git','status','--porcelain'],cwd=WT,text=True).strip()
assert os.environ['VISIONFLOW_DATA_DIR'] == str(OUT/'data')
prereg = load(E/'06-preregistration.json')
mapping = load(E/'sample-approval-map.json')
approval_path = RT/'dataset/human-groundtruth-approval.json'
approval = load(approval_path)
assert digest(RT/'dataset/manifest.json') == approval['manifest_sha256']
assert digest(approval_path) == load(E/'INTENT.json')['exact_human_approval_sha256']
assert prereg['before_first_fit']
db = sqlite3.connect('file:' + str(OUT/'data/visionflow.db') + '?mode=ro',uri=True)
db.row_factory = sqlite3.Row
task = dict(db.execute('SELECT * FROM autolearn_tasks').fetchone())
versions = [dict(x) for x in db.execute('SELECT * FROM autolearn_model_versions')]
assert len(versions) == 1
v = versions[0]
rows = [dict(x) for x in db.execute('SELECT * FROM autolearn_samples ORDER BY id')]
members = [dict(x) for x in db.execute('SELECT * FROM autolearn_model_version_samples ORDER BY sample_id')]
audits = [dict(x) for x in db.execute('SELECT * FROM autolearn_labeling_audit ORDER BY id')]
reservations = [dict(x) for x in db.execute('SELECT * FROM autolearn_labeling_reservations ORDER BY id')]
activations = db.execute('SELECT COUNT(*) FROM autolearn_activations').fetchone()[0]
assert task['active_version_id'] is None and activations == 0
assert len(rows) == len(members) == len(mapping) == len(audits) == len(reservations) == 24
assert all(x['status'] == 'sent' for x in reservations)
assert all(x['status'] == 'labeled' for x in audits)
assert prereg['dataset_hash'] == v['dataset_hash'] and prereg['split_hash'] == v['split_hash']
membership = []
for row,member,entry in zip(rows,members,mapping):
    assert row['id'] == member['sample_id'] == entry['sample_id']
    assert row['image_hash'] == member['image_hash'] == entry['image_sha256'] == digest(Path(row['image_path']))
    assert row['verified'] and row['verified_label'] == member['verified_label'] == entry['verified_label']
    assert row['session_id'] == entry['session_id'] and row['source_id'] is None
    assert row['split'] == member['split'] == prereg['assignments'][str(row['id'])]
    assert prereg['groups']['src:none|ses:'+row['session_id']] == row['split']
    membership.append(dict(sample_id=row['id'],approved_sample_id=entry['approved_sample_id'],
        image_sha256=row['image_hash'],session_id=row['session_id'],split=row['split'],
        verified_label=row['verified_label']))
session_splits = {}
for m in membership:
    session_splits.setdefault(m['session_id'],set()).add(m['split'])
assert len(session_splits) == 12 and all(len(x) == 1 for x in session_splits.values())
actual_counts = {s:sum(x['split']==s for x in membership) for s in ('train','val','test')}
assert actual_counts == prereg['counts'] == {'train':14,'val':4,'test':6}
artifact = Path(v['artifact_path'])
artifact_before = digest(artifact)
clf = student.StudentClassifier.load(str(artifact))
stored_metrics = json.loads(v['metrics'])
api_eval = load(E/'08-reloaded-heldout-evaluation.json')['response']['metrics']
assert clf.extra['threshold'] == v['threshold'] == stored_metrics['threshold'] == api_eval['threshold'] == 0.5
assert artifact_before == stored_metrics['artifact_sha256'] == api_eval['artifact_sha256']
assert clf.classes == ['empty','occupied']
assert clf.extra['class_mapping'] == json.loads(v['class_mapping']) == {'empty':0,'occupied':1}
for key in ('encoder_name','encoder_weights_version','preprocess_version','dataset_hash','split_hash'):
    assert clf.extra[key] == v[key]
weights = Path(torch.hub.get_dir())/'checkpoints/resnet18-f37072fd.pth'
before_encoder = load(CONTROL/'encoder-before.json')
assert digest(weights) == before_encoder['sha256'] == 'f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec'
enc = encoder.get_encoder()
assert enc.frozen() and enc.weights_tag == v['encoder_weights_version']
assert encoder.ENCODER_NAME == v['encoder_name'] and encoder.PREPROCESS_VERSION == v['preprocess_version']
def state_digest():
    h=hashlib.sha256()
    for key,val in enc.model.state_dict().items():
        h.update(key.encode());h.update(val.cpu().numpy().tobytes())
    return h.hexdigest()
frozen_before = state_digest()
X,embedding_latency = enc.embed_paths([r['image_path'] for r in rows])
frozen_after = state_digest()
assert frozen_before == frozen_after and enc.frozen()
start = time.perf_counter();probs = clf.predict_proba(X);classifier_ms=(time.perf_counter()-start)*1000
independent_probs = 1/(1+np.exp(-(((X.astype(np.float64)-clf._mean)/clf._std) @ clf._w + clf._b)))
assert np.isfinite(probs).all() and np.allclose(probs,independent_probs,atol=1e-6,rtol=1e-6)
test_indices = [i for i,r in enumerate(rows) if r['split']=='test']
y = [int(rows[i]['verified_label']=='occupied') for i in test_indices]
pred = [int(float(independent_probs[i])>=v['threshold']) for i in test_indices]
teacher_pred = [int(rows[i]['teacher_label']=='occupied') for i in test_indices]
student_metrics = confusion(y,pred);teacher_metrics=confusion(y,teacher_pred)
for key,val in student_metrics.items():
    assert stored_metrics[key] == api_eval[key] == val
shadow = load(E/'09-shadow.json')['response']
assert len(shadow['items']) == 6
test_predictions=[]
for i,p in zip(test_indices,pred):
    r=rows[i];si=next(x for x in shadow['items'] if x['sample_id']==r['id'])
    assert si['action']=='none' and si['student_label']==('occupied' if p else 'empty')
    test_predictions.append(dict(sample_id=r['id'],image_sha256=r['image_hash'],
        session_id=r['session_id'],verified_label=r['verified_label'],
        student_probability=float(independent_probs[i]),student_label=si['student_label'],
        teacher_label=r['teacher_label'],teacher_probability=r['teacher_confidence'],
        embedding_latency_ms=embedding_latency[i],action='none'))
all_teacher = confusion([int(r['verified_label']=='occupied') for r in rows],
                       [int(r['teacher_label']=='occupied') for r in rows])
precheck = load(CONTROL/'PRECHECK.json')
log_path=Path(precheck['teacher_log_path']);log_bytes=log_path.read_bytes()
assert hashlib.sha256(log_bytes[:precheck['teacher_log_start_bytes']]).hexdigest()==precheck['teacher_log_start_sha256']
new_log=log_bytes[precheck['teacher_log_start_bytes']:]
records=[json.loads(line) for line in new_log.splitlines()]
assert len(records)==24 and len({x['request_id'] for x in records})==24
teacher_trace=[]
for rec,row,audit in zip(records,rows,audits):
    s=rec['scoring'];assert s['method']=='candidate_sequence_softmax' and s['output_is_generated_json'] is False and s['uncalibrated'] is True
    assert rec['revision']=='a7da5b986cb59b408707209984f360a5f4ad7e47'
    assert s['candidate_labels']==['occupied','empty'] and len(s['candidate_token_ids'])==len(s['candidate_log_likelihoods'])==len(s['normalized_probabilities'])==2
    scores=np.array(s['candidate_log_likelihoods']);normalized=np.exp(scores-scores.max());normalized/=normalized.sum()
    assert np.allclose(normalized,s['normalized_probabilities'],atol=1e-14)
    best=int(np.argmax(normalized));assert row['teacher_label']==s['candidate_labels'][best] and math.isclose(row['teacher_confidence'],float(normalized[best]),abs_tol=1e-14)
    assert s['model_forward_calls']==2 and rec['image_count']==1 and not rec['deadline_reached']
    assert audit['sample_id']==row['id'] and audit['image_hash']==row['image_hash'] and audit['method']=='candidate_sequence_softmax'
    teacher_trace.append(dict(sample_id=row['id'],image_sha256=row['image_hash'],session_id=row['session_id'],
        prompt=row['teacher_prompt'],teacher_label=row['teacher_label'],teacher_confidence=row['teacher_confidence'],
        raw_content_preview=json.loads(row['teacher_raw'])['content_preview'],client_wall_latency_ms=audit['latency_ms'],
        raw_server_record=rec,correlation='exclusive sequential job; TrainingSample.id ordering; exact candidate label/probability match; application does not persist request_id'))
(E/'teacher-server-requests.jsonl').write_bytes(new_log)
(E/'complete-teacher-trace.json').write_text(json.dumps(teacher_trace,indent=2,allow_nan=False)+'\n')
assert digest(artifact)==artifact_before and digest(weights)==before_encoder['sha256']
result=dict(scope=SCOPE,independent_review_verdict='CHANGES_REQUIRED',accepted_for_integration=False,
    target_sha=SHA,recorded_epoch=time.time(),source='24 owner-verified original procedural synthetic images, 12 sessions; NOT natural videos',
    production_preregistration_unchanged=True,session_disjoint=True,membership=membership,counts=actual_counts,
    artifact_sha256=artifact_before,artifact_bytes=artifact.stat().st_size,artifact_threshold=clf.extra['threshold'],
    registry_threshold=v['threshold'],evaluated_threshold=api_eval['threshold'],class_mapping=json.loads(v['class_mapping']),
    artifact_extra=clf.extra,encoder_weights_sha256=digest(weights),encoder_parameters_frozen=True,
    encoder_state_sha256_before=frozen_before,encoder_state_sha256_after=frozen_after,
    input_hashes_before_and_after_match=True,fresh_teacher_requests=24,teacher_model_forward_calls=sum(x['scoring']['model_forward_calls'] for x in records),
    actual_model_processed_tokens=sum(x['scoring']['actual_model_processed_tokens'] for x in records),
    teacher_server_inference_seconds=sum(x['inference_seconds'] for x in records),
    teacher_all24_metrics=all_teacher,student_same_heldout_metrics=student_metrics,teacher_same_heldout_metrics=teacher_metrics,
    student_teacher_disagreements=sum(p!=t for p,t in zip(pred,teacher_pred)),test_predictions=test_predictions,
    reloaded_classifier_total24_ms=classifier_ms,embedding_latency_ms=embedding_latency,
    student_active_pointer=task['active_version_id'],activation_rows=activations,actions='none',
    limits=['M3 remains BLOCKED and unaccepted; a successful experiment is not an acceptance verdict',
           'Teacher JSON is serialized image-conditioned candidate likelihood, not successful generated JSON; confidence is uncalibrated',
           'Student evaluation has only 6 original synthetic images, 3 held-out sessions; no natural-video quality claim',
           'Exact provider raw scoring log preserved; application omitted some provenance and did not persist full HTTP wire body',
           'GPU kernel execution time, power cost, rental cost/event, full baseline-versus-optimized video savings and foveated gains UNVERIFIED',
           'No Student activation, external action, retraining, alternate split, app correction or additional Teacher job'])
(E/'INDEPENDENT_RELOAD.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ('scope','artifact_sha256','student_same_heldout_metrics','teacher_same_heldout_metrics','activation_rows','fresh_teacher_requests')}))
db.close()
