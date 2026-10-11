import dataclasses, json
from pathlib import Path
from app.nl_compiler import compile_text
from app.schemas import WorkflowDSL
Z=[{'id':7,'name':'Service Bay A'}]
controls=[]
for cls in ['car','truck','bus','motorcycle','bicycle','person']:
    for trig,typ,param in [('enters','object_entered_zone',{}),('exits','object_exited_zone',{}),('stays in','dwell_in_zone',{'duration_seconds':150}),('count','object_count_exceeded',{'threshold':3})]:
        for cond,desc in [('',None),(' with hood open','hood'),(' with trunk open','trunk'),(' with door open','door'),(' with headlights on','lights')]:
            if trig=='count':
                plural={'bus':'buses','person':'people'}.get(cls,cls+'s')
                trigger=f'more than 3 {plural} are in Service Bay A{cond}'
            elif typ=='dwell_in_zone':
                trigger=f'a {cls} stays in Service Bay A for 2.5 minutes{cond}'
            else:
                trigger=f'a {cls} {trig} Service Bay A{cond}'
            for text in [f'When {trigger}, create an alert',f'Notify me when {trigger}']:
                r=compile_text(text,1,Z)
                correct=r.ok and r.draft['trigger']=={'type':typ,'zone_id':7,**param}
                if correct:
                    WorkflowDSL.model_validate(r.draft)
                    pred=r.draft.get('visual_predicate')
                    correct=(pred is None if desc is None else pred is not None and desc in pred['description'])
                controls.append({'text':text,'correct':bool(correct),'result':dataclasses.asdict(r)})
texts=[
 'When a car enters Service Bay A, then open hood',
 'When a car enters Service Bay A with hood open and trunk up, create an alert',
 'When a car stays in Service Bay A for .5 minutes, create an alert',
 'When a car stays in Service Bay A for -5 minutes, create an alert',
 'When more than 3 or more than 5 cars are in Service Bay A, create an alert',
 'When a car stays in Service Bay A, create an alert for 5 minutes',
 'Create an alert for 5 minutes when a car stays in Service Bay A',
 'When a car enters Service Bay A with hood and trunk open, create an alert',
 'When a car enters Service Bay A with hood open and lights, create an alert',
 'When a car enters Service Bay A with hood, create an alert',
 'When a car enters Service Bay A with lights off, create an alert',
 'When a car enters Service Bay A with hood not open, create an alert',
 'When a car does not enter Service Bay A, create an alert',
 'When a car enters or exits Service Bay A, create an alert',
 'When fewer than 3 cars are in Service Bay A, create an alert',
 'When a car stays in Service Bay A for less than 5 minutes, create an alert',
 'When a car enters Service Bay A, delete the video',
 'When a car enters Service Bay A, send a webhook',
 'When a car enters Service Bay A, execute a shell script',
 'When 3 or more or 5 or more cars are in Service Bay A, create an alert',
 'Notify me for 5 minutes when a car stays in Service Bay A',
 'When a car stays in Service Bay A for more than 2.5 minutes, create an alert',
 'When a car stays in Service Bay A for 5 minutes with hood open for 10 seconds, create an alert',
]
probes=[{'text':x,'result':dataclasses.asdict(compile_text(x,1,Z))} for x in texts]
out={'target_sha':'25bccee269bde978745c168852a716670b7f999b','supported_count':len(controls),'supported_correct':sum(c['correct'] for c in controls),'control_failures':[x for x in controls if not x['correct']],'probes':probes}
Path('/tmp/visionflow-m2-emergency-review-953d0e2/grammar-results.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'supported_count':out['supported_count'],'supported_correct':out['supported_correct'],'failures':out['control_failures'],'accepted_probes':[{'text':p['text'],'trigger':p['result']['draft']['trigger'],'visual':p['result']['draft'].get('visual_predicate')} for p in probes if p['result']['ok']]},indent=2))
