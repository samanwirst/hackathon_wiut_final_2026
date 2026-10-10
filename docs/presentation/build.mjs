import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile,layers,text,shape} from '@oai/artifact-tool';

const ROOT=process.env.VISIONFLOW_REPO_ROOT || path.resolve(path.dirname(new URL(import.meta.url).pathname),'../..');
const OUT=path.dirname(new URL(import.meta.url).pathname);
await fs.mkdir(path.join(OUT,'preview'),{recursive:true});
await fs.mkdir(path.join(OUT,'layout'),{recursive:true});
const p=Presentation.create({slideSize:{width:1280,height:720}});
const frame={left:0,top:0,width:1280,height:720};
let n=0;
const tx=(name,copy,x,y,w,h,size=28,color='#000000')=>text([copy],{name,position:{left:x,top:y},width:w,height:h,style:{fontSize:`${size}px`,typeface:'Arial',color,alignment:'left',verticalAlignment:'top',autoFit:'none',insets:{top:0,right:0,bottom:0,left:0}}});
const ln=(name,x,y,w)=>shape({name,geometry:'rect',fill:'#CCCCCC',position:{left:x,top:y},width:w,height:1});
function slide(title,items=[]){const s=p.slides.add();s.background.fill='#FFFFFF';n++;s.compose(layers({name:`visionflow-${n}`,width:'fill',height:'fill'},[tx('title',title,48,40,1184,90,48),...items,tx('page',String(n),1180,665,52,30,22,'#555555')]),{frame,baseUnit:1});return s;}
async function img(s,name,file,x,y,w,h,crop){const b=await fs.readFile(file);s.images.add({name,blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:name,fit:'cover',position:{left:x,top:y,width:w,height:h},crop,geometry:'rect'});}

const s1=p.slides.add();s1.background.fill='#FFFFFF';n++;
s1.compose(layers({name:'visionflow-cover',width:'fill',height:'fill'},[
tx('mode','STARTUP MODE · VISIONFLOW AI',48,48,1184,42,24),
tx('brand','Visual operations.\nHuman-controlled.',48,240,1184,230,80),
tx('promise','Approve a visual rule. Inspect every event.\nTeach a small model for one repeatable task.',48,545,1184,94,32),
]),{frame,baseUnit:1});

const s2=slide('Know why an alert fired.',[
tx('buyer','For service-centre operators',48,190,550,44,32),
tx('pain','Recorded footage needs an operational rule, a clear approval boundary, and evidence that a manager can inspect.',48,270,500,185,30),
tx('result','A real geometric event\nwith a saved evidence frame\nand a local notification.',48,493,500,125,28),
]);
await img(s2,'Actual verified event evidence',`${ROOT}/.agents/demo-evidence/99e8670/evidence-desktop.png`,610,150,620,470,{left:.175,top:.15,right:.175,bottom:.15});
const s3=slide('Configure, approve, observe.',[
tx('journey','1  Select a recorded MP4\n\n2  Draw a polygon and set a rule\n\n3  Review the validated JSON\n\n4  Approve, run, inspect evidence',48,180,485,390,30),
tx('controls','Edit · disable · review and re-enable',48,615,1184,40,26),
]);
await img(s3,'Actual polygon workspace from recorded browser journey',`${ROOT}/docs/presentation/assets/actual-zone-workspace.png`,580,154,650,367);

slide('Observe cheaply. Learn selectively.',[
ln('pipeline',80,328,1100),
tx('stage1','Observe',48,210,340,50,36),tx('stage2','Understand',445,210,340,50,36),tx('stage3','Specialize',842,210,340,50,36),
tx('observe','Detector + tracker\nTemporal rules\nSelected candidate events',48,372,340,144,28),
tx('understand','Private image Teacher\nStrict label validation\nHuman review and correction',445,372,340,144,28),
tx('specialize','Frozen image embeddings\nSmall fitted Student\nShadow → manual activation',842,372,340,144,28),
tx('status1','Verified geometric demo',48,555,340,70,24),
tx('status2','24 human-verified images;\n12 Teacher corrections',445,555,340,70,24),
tx('status3','Real fit + reload + shadow;\nQA corrections still required',842,555,340,70,24),
]);

const s5=slide('A measured synthetic pilot.',[
tx('head1','Local GPU Teacher',48,156,566,44,32),tx('head2','CPU Student',690,156,542,44,32),
ln('rowrule',48,213,1184),
tx('teacherresult','3 / 6 correct · recall 1.0\n432.8 ms mean wall latency\n18 requests · 36 model forwards',48,245,566,132,28),
tx('studentresult','6 / 6 correct · recall 1.0\n40.2 ms mean wall latency\n0 Teacher requests',690,245,542,132,28),
tx('limit','6 unique synthetic inputs; 18 timing samples. Experimental QA: CHANGES_REQUIRED. Natural quality / costs: UNVERIFIED.',48,642,1110,60,20,'#555555'),
]);
await img(s5,'Actual trained Student version; manual activation not performed',`${ROOT}/docs/presentation/assets/actual-trained-student-panel.png`,48,393,1184,241);

slide('Price the operational benefit.',[
 tx('revenuehead','Pricing hypothesis',48,170,550,50,32),
 tx('revenue','Per-camera / site subscription.\nOne repeatable workflow first.\n\nWillingness to pay and pricing\nremain UNVERIFIED.',48,270,550,260,28),
 tx('costhead','Measure the unit cost',690,170,542,50,32),
 tx('cost','GPU rental + storage + network.\nCPU inference + support.\n\nCost per event from actual\nruntime and processed events.',690,270,542,260,28),
 tx('cap','Vast closed: $0.001 rounded disk charge. Final invoice UNVERIFIED; no remote inference.',48,574,1130,42,24),
 tx('roi','ROI = observed staff time saved × actual labour rate − measured system expense.',48,632,1130,36,22,'#555555'),
]);

slide('A three-month pilot.',[
ln('pilot',48,332,1184),
tx('month1','Month 1',48,250,340,45,28),tx('month2','Month 2',445,250,340,45,28),tx('month3','Month 3',842,250,340,45,28),
tx('pilot1','Define one task',48,390,340,45,32),tx('pilot2','Validate in shadow',445,390,340,45,32),tx('pilot3','Approve a rollout',842,390,340,45,32),
tx('pilotbody1','Partner footage and consent\nAgree event definitions\nCollect reviewed examples',48,464,340,145,26),
tx('pilotbody2','Held-out sessions\nMeasure missed/false events\nMeasure GPU cost and latency',445,464,340,145,26),
tx('pilotbody3','Manual activation gate\nPersist the prior version\nVerify rollback and support',842,464,340,145,26),
tx('pilotfoot','Proposed pilot. Adoption, willingness to pay, and ROI have not been measured.',48,636,1130,33,22,'#555555'),
]);

slide('Start with one accountable task.',[
tx('ask','Pilot a repeatable service-bay event\nwith a manager who owns the decision.',48,215,1184,145,48),
tx('scope','Today: approved geometric analytics and inspectable evidence.\nExperimental: local Teacher and human-gated AutoLearn.\nUnavailable: unsafe agent actions and public integrations.',48,424,1184,156,28),
tx('claim','A reliable demo first. Adaptive automation earns activation through measured quality.',48,625,1130,42,24),
]);

for(const [i,s] of p.slides.items.entries()){
 const stem=`slide-${String(i+1).padStart(2,'0')}`;
 const png=await p.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(OUT,'preview',stem+'.png'),new Uint8Array(await png.arrayBuffer()));
 const layout=await s.export({format:'layout'});await fs.writeFile(path.join(OUT,'layout',stem+'.json'),await layout.text());
}
const pptx=await PresentationFile.exportPptx(p);await pptx.save(path.join(OUT,'VisionFlow-defense.pptx'));
console.log(JSON.stringify({slides:p.slides.items.length,draft:path.join(OUT,'VisionFlow-defense.pptx')}));
