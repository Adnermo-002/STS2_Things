import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const data=load('pkg/silk_moth.spjson','pkg/silk_moth.atlas');
const raw=JSON.parse(fs.readFileSync('pkg/silk_moth.spjson','utf8'));
const names=['idle_loop','attack','cast','flutter','hurt','die','revive','summon','power_up'];
assert.deepEqual(data.animations.map(a=>a.name).sort(),names.toSorted());
assert.equal(data.bones.length,22);
const slots=['wing_far','wing_near','silk_a','silk_b','silk_c','body'];
const vertices=(animation,t)=>slots.flatMap(name=>Array.from(worldVertices(pose(data,animation,t).findSlot(name))));
const difference=(a,b)=>Math.max(...a.map((v,i)=>Math.abs(v-b[i])));
const loopError=difference(vertices('idle_loop',0),vertices('idle_loop',4));
const reviveError=difference(vertices('die',1.55),vertices('revive',0));
assert(loopError<.05,`Idle seam: ${loopError}`);assert(reviveError<.05,`Revive seam: ${reviveError}`);
const setup=vertices(null,0);const returnErrors={};
for(const anim of data.animations){if(anim.name==='die')continue;
 const error=difference(vertices(anim.name,anim.duration),setup);returnErrors[anim.name]=error;
 assert(error<.12,`${anim.name} rest mismatch: ${error}`);}
const headX=t=>pose(data,'attack',t).findBone('head').worldX;
assert(headX(.25)>headX(0)+10,'Backwards anticipation');
assert(headX(.48)<headX(0)-100,'Forward contact');
let frames=0,flipped=0,maxDisplacement=0,triangleCount=0;const failures={};
const signedArea=(v,tri,i)=>{const [a,b,c]=tri.slice(i,i+3).map(k=>k*2);return(v[b]-v[a])*(v[c+1]-v[a+1])-(v[b+1]-v[a+1])*(v[c]-v[a]);};
const specs=slots.map((name,index)=>{
 const triangles=data.defaultSkin.getAttachment(index,name).triangles;
 const setup=Array.from(worldVertices(pose(data,null,0).findSlot(name)));
 triangleCount+=triangles.length/3;
 return {name,triangles,baseline:Array.from({length:triangles.length/3},(_,i)=>signedArea(setup,triangles,i*3))};
});
for(const anim of data.animations)for(let t=0;t<=anim.duration+1e-6;t+=1/60){
 const skeleton=pose(data,anim.name,t);
 for(const {name,triangles,baseline} of specs){
  const v=Array.from(worldVertices(skeleton.findSlot(name)));assert(v.every(Number.isFinite));
  for(let i=0;i<baseline.length;i++)if(signedArea(v,triangles,i*3)*baseline[i]<-.01){flipped++;failures[`${anim.name}/${name}`]=(failures[`${anim.name}/${name}`]??0)+1;}
 }
 const v=vertices(anim.name,t);for(let i=0;i<v.length;i++)maxDisplacement=Math.max(maxDisplacement,Math.abs(v[i]-setup[i]));frames++;
}
assert.equal(flipped,0,JSON.stringify(failures));
assert.equal(raw.animations.attack.events[0].time,.48);assert.equal(raw.animations.cast.events[0].time,.62);
const report={result:'PASS',runtime:'official Spine 4.2.43',bones:22,slots:6,animations:names.length,
 frames,vertices:setup.length/2,triangles:triangleCount,loopError,reviveError,returnErrors,invertedTriangles:flipped,maxDisplacement};
fs.writeFileSync('pkg/verification.json',JSON.stringify(report,null,2));console.log(report);
