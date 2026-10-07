import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const data=load('pkg/water_sponge.spjson','pkg/water_sponge.atlas');
const raw=JSON.parse(fs.readFileSync('pkg/water_sponge.spjson','utf8'));
const names=['idle_loop','attack','cast','soak','hurt','die','revive','summon','power_up'];
assert.deepEqual(data.animations.map(a=>a.name).sort(),names.toSorted());
assert.equal(data.bones.length,14);
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
const headX=t=>pose(data,'attack',t).findBone('head').worldX;
assert(headX(.25)>headX(0)+12,'Slap has a readable backwards windup');
assert(headX(.48)<headX(0)-90,'Slap reaches forward at its contact event');
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
assert.equal(raw.animations.attack.events[0].time,.48);
assert.equal(raw.animations.cast.events[0].time,.64);
assert.equal(raw.animations.soak.events[0].time,.56);
const report={result:'PASS',runtime:'official Spine 4.2.43',bones:data.bones.length,animations:names.length,
 frames,vertices:setup.length/2,triangles:triangles.length/3,loopError,reviveError,returnErrors,invertedTriangles:flipped,maxDisplacement};
fs.writeFileSync('pkg/verification.json',JSON.stringify(report,null,2));console.log(report);

