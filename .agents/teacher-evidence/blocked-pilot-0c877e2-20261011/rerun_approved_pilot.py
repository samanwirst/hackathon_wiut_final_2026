"""One fresh exact-hash-approved pilot: real Teacher, verified labels, fit/eval/shadow.
Never activates a Student; old metrics remain historical. Run only after exact
CE commit is independently accepted and served in a fresh private data directory.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, time
import httpx
ROOT=Path(__file__).resolve().parents[3];RT=ROOT/'.agents/runtime/ten-hour'
p=argparse.ArgumentParser();p.add_argument('--worktree',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--base-url',required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--isolated-blocked-experiment',action='store_true');a=p.parse_args()
assert a.base_url.startswith('http://127.0.0.1:'), 'Private owned API only'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.worktree,text=True).strip()==a.sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=a.worktree,text=True).strip()
review=json.loads((RT/'CE/m3-emergency-review/review.json').read_text());assert review['target_sha']==a.sha
if a.isolated_blocked_experiment:
 closed=json.loads((RT/'CE/FINAL_STATUS.json').read_text())
 assert review['verdict']=='CHANGES_REQUIRED' and closed['owner_exception_exhausted'] and not closed['accepted_for_integration']
else:assert review['verdict']=='PASS'
a.evidence.mkdir(parents=True,exist_ok=False)
def write(name,value):
 (a.evidence/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
manifest_path=RT/'dataset/manifest.json';approval_path=RT/'dataset/human-groundtruth-approval.json'
manifest=json.loads(manifest_path.read_text());approval=json.loads(approval_path.read_text())
assert hashlib.sha256(manifest_path.read_bytes()).hexdigest()==approval['manifest_sha256']
by_id={x['sample_id']:x for x in approval['labels']};rows=manifest['samples'];assert len(rows)==len(by_id)==24
for row in rows:
 approved=by_id[row['sample_id']]
 assert row['image_sha256']==approved['image_sha256']==hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()
 assert row['session_id']==approved['session_id'] and approved['verified_label'] in ('occupied','empty')
scope={'independent_review_verdict':review['verdict'],'accepted_for_integration':not a.isolated_blocked_experiment,'scope':'ISOLATED_UNACCEPTED_NONACTIONING_EXPERIMENT' if a.isolated_blocked_experiment else 'ACCEPTED_PRIVATE_PILOT','full_adaptive_workflow_accepted':False}
write('INTENT.json',{'target_sha':a.sha,'started_epoch':time.time(),'dataset_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'exact_human_approval_sha256':hashlib.sha256(approval_path.read_bytes()).hexdigest(),'images':24,'sessions':12,'one_labeling_job_maximum':24,'source':'original procedural synthetic drawings; NOT natural videos','student_activation_authorized':False,'phase':'pre-Teacher/pre-fit','reuses_old_metrics':False,**scope})
client=httpx.Client(base_url=a.base_url,timeout=90)
def req(method,path,name,**kw):
 start=time.perf_counter();r=client.request(method,path,**kw)
 record={'target_sha':a.sha,'method':method,'path':path,'status':r.status_code,'wall_ms':(time.perf_counter()-start)*1000}
 try:record['response']=r.json()
 except Exception:record['response_text']=r.text[:2048]
 write(name,record);r.raise_for_status();return record['response']
assert client.get('/api/autolearn/tasks').json()==[], 'Fresh owned data required; no existing experiment mutation'
prompt='Is a visible motor vehicle present in the marked synthetic service bay? Label occupied means at least one visible motor vehicle; label empty means none.'
task=req('POST','/api/autolearn/tasks','01-task.json',json={'name':'Human-approved 24-image synthetic recovery pilot','visual_prompt':prompt,'positive_label':'occupied','negative_label':'empty','teacher_model':'HuggingFaceTB/SmolVLM-500M-Instruct'})
tid=task['id'];mapping=[]
for n,row in enumerate(rows):
 blob=Path(row['path']).read_bytes()
 imported=req('POST',f'/api/autolearn/tasks/{tid}/images',f'02-import-{n:02d}.json',params={'session_id':row['session_id'],'group_key':row['session_id'],'video_timestamp':row['video_timestamp']},files={'file':(row['sample_id']+'.png',blob,'image/png')})
 assert imported['imported'];mapping.append({'approved_sample_id':row['sample_id'],'sample_id':imported['sample_id'],'image_sha256':row['image_sha256'],'session_id':row['session_id'],'verified_label':by_id[row['sample_id']]['verified_label']})
write('sample-approval-map.json',mapping)
# This invocation is deliberately one job, with no invisible retries on failure.
req('POST',f'/api/autolearn/tasks/{tid}/label','03-real-teacher-labeling.json',params={'limit':24})
samples=req('GET',f'/api/autolearn/tasks/{tid}/samples','04-teacher-samples.json')
assert len(samples)==24
for entry in mapping:
 sample=next(s for s in samples if s['id']==entry['sample_id']);assert sample['image_hash']==entry['image_sha256']
 assert sample['teacher_status']=='labeled' and sample['teacher_label'] in ('occupied','empty'), 'Real Teacher result unavailable: do not fabricate'
 req('POST',f"/api/autolearn/samples/{entry['sample_id']}/review",f"05-human-review-{entry['sample_id']:02d}.json",json={'verified_label':entry['verified_label'],'reviewer':'human-user exact24 sheet approval; hash '+hashlib.sha256(approval_path.read_bytes()).hexdigest()[:16]})
# Pre-register exact prospective membership BEFORE any fresh fit. Production
# build_split_plan is read-only here; same owned fresh DB, no model activation.
code='''import json,hashlib\nfrom pathlib import Path\nfrom app.db import init_db,get_session,AutoLearnTask,TrainingSample\nfrom app.autolearn import service\ninit_db();db=get_session();t=db.get(AutoLearnTask,TASK_ID)\nrows=db.query(TrainingSample).filter(TrainingSample.task_id==t.id).all()\nassert len(rows)==24 and all(r.verified and hashlib.sha256(Path(r.image_path).read_bytes()).hexdigest()==r.image_hash for r in rows)\np=service.build_split_plan(db,t)\nprint(json.dumps(dict(counts=p.counts,class_counts=p.class_counts,assignments=p.assignments,groups=p.group_split,dataset_hash=p.dataset_hash,split_hash=p.split_hash),allow_nan=False))\ndb.close()'''.replace('TASK_ID',str(tid))
prereg=json.loads(subprocess.check_output([str(a.worktree/'services/api/.venv/bin/python'),'-c',code],cwd=a.worktree,env=os.environ,text=True))
prereg.update(target_sha=a.sha,before_first_fit=True,recorded_epoch=time.time(),split_policy='production source/session grouping, no outcome-based repartitioning',old_metrics_reused=False)
write('06-preregistration.json',prereg)
trained=req('POST',f'/api/autolearn/tasks/{tid}/train','07-genuine-training.json');vid=trained['version_id']
assert trained['dataset_hash']==prereg['dataset_hash'] and trained['split_hash']==prereg['split_hash']
evaluated=req('POST',f'/api/autolearn/versions/{vid}/evaluate','08-reloaded-heldout-evaluation.json')
shadow=req('GET',f'/api/autolearn/tasks/{tid}/shadow','09-shadow.json')
gate=req('GET',f'/api/autolearn/versions/{vid}/gate','10-gate-nonactivating.json')
audit=req('GET',f'/api/autolearn/tasks/{tid}/audit','11-teacher-provenance-audit.json')
final=req('GET',f'/api/autolearn/tasks/{tid}','12-final-task.json')
activations=req('GET',f'/api/autolearn/tasks/{tid}/activations','13-activation-history.json')
assert activations==[] and final['task']['active_version_id'] is None
write('RESULT.json',{'target_sha':a.sha,'task_id':tid,'version_id':vid,'fresh_teacher_results':24,'human_approved_images':24,'corrections':sum(s['teacher_label']!=next(x['verified_label'] for x in mapping if x['sample_id']==s['id']) for s in samples),'split':prereg,'training':trained,'reloaded_evaluation':evaluated,'shadow':shadow,'gate_observed_only_untrusted_until_independent_artifact_check':gate,'student_active':False,'activation_rows':0,'source':'small synthetic pilot; NOT natural-world accuracy',**scope,'limits':['M3 remains BLOCKED; experiment does not grant acceptance or integration','No real Student activation','Old metrics not reused','Not full video baseline versus optimized pipeline','Natural-video quality, foveated improvements, GPU billed cost/event and savings UNVERIFIED']})
print(json.dumps({'target_sha':a.sha,'task_id':tid,'version_id':vid,'counts':trained['counts'],'evaluation':evaluated,'student_active':False},allow_nan=False));client.close()
