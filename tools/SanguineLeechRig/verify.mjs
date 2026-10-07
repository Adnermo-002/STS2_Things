import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const data=load('pkg/sanguine_leech.spjson','pkg/sanguine_leech.atlas');
const raw=JSON.parse(fs.readFileSync('pkg/sanguine_leech.spjson','utf8'));
const names=['idle_loop','attack','cast','curl','feed','hurt','die','revive','summon','power_up'];
assert.deepEqual(data.animations.map(a=>a.name).sort(),names.toSorted());
assert.equal(data.bones.length,17);
const vertices=(animation,t)=>worldVertices(pose(data,animation,t).findSlot('skin'));
const difference=(a,b)=>Math.max(...a.map((v,i)=>Math.abs(v-b[i])));
const loopError=difference(vertices('idle_loop',0),vertices('idle_loop',4));
const reviveError=difference(vertices('die',1.5),vertices('revive',0));
assert(loopError<.05,`Idle loop seam: ${loopError}`);
assert(reviveError<.05,`Death/revive seam: ${reviveError}`);
const setup=vertices(null,0),triangles=data.defaultSkin.getAttachment(0,'skin').triangles;
const returnErrors={};
for(const anim of data.animations){
 if(anim.name==='die')continue;
 const error=difference(vertices(anim.name,anim.duration),setup);returnErrors[anim.name]=error;
 assert(error<.12,`${anim.name} does not settle to rest: ${error}`);
}
const headX=t=>pose(data,'attack',t).findBone('mouth').worldX;
assert(headX(.22)>headX(0)+25,'Bite visibly retracts before extending');
assert(headX(.46)<headX(0)-100,'Bite extends its mouth at contact');
const planted=pose(data,null).findBone('sucker');let suckerDrift=0;
for(const anim of data.animations){
 if(['die','revive','summon'].includes(anim.name))continue;
 for(let t=0;t<=anim.duration;t+=1/60){const bone=pose(data,anim.name,t).findBone('sucker');suckerDrift=Math.max(suckerDrift,Math.hypot(bone.worldX-planted.worldX,bone.worldY-planted.worldY));}
}
assert(suckerDrift<.2,`Rear sucker slips: ${suckerDrift}`);
function area(v,i){const [a,b,c]=triangles.slice(i,i+3).map(k=>k*2);return(v[b]-v[a])*(v[c+1]-v[a+1])-(v[b+1]-v[a+1])*(v[c]-v[a]);}
const baseline=Array.from({length:triangles.length/3},(_,i)=>area(setup,i*3));
let frames=0,flipped=0,maxDisplacement=0;
const failures={};
for(const anim of data.animations){
 for(let t=0;t<=anim.duration+1e-6;t+=1/60){
  const v=vertices(anim.name,t);assert(v.every(Number.isFinite),'finite vertices');
  for(let i=0;i<baseline.length;i++)if(area(v,i*3)*baseline[i]<-.01){flipped++;failures[anim.name]=(failures[anim.name]??0)+1;}
  for(let i=0;i<v.length;i++)maxDisplacement=Math.max(maxDisplacement,Math.abs(v[i]-setup[i]));
  frames++;
 }
}
assert.equal(flipped,0,JSON.stringify(failures));
assert(maxDisplacement>120,'Readable deformation');
assert.equal(raw.animations.attack.events[0].time,.46);
assert.equal(raw.animations.cast.events[0].time,.62);
assert.equal(raw.animations.curl.events[0].time,.38);
const report={result:'PASS',runtime:'official Spine 4.2.43',bones:data.bones.length,animations:names.length,
 frames,vertices:setup.length/2,triangles:triangles.length/3,loopError,reviveError,returnErrors,suckerDrift,invertedTriangles:flipped,maxDisplacement};
fs.writeFileSync('pkg/verification.json',JSON.stringify(report,null,2));console.log(report);
