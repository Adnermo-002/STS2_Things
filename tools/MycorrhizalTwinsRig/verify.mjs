import fs from 'node:fs';
import assert from 'node:assert/strict';
import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const reports=[];
for(const key of ['mycorrhizal_vanguard','mycorrhizal_bulwark']){
 const dir=`../../STS2_Things/animations/monsters/${key}`;
 const data=load(`${dir}/${key}.spjson`,`${dir}/${key}.atlas`);
 const raw=JSON.parse(fs.readFileSync(`${dir}/${key}.spjson`,'utf8'));
 const slots=data.slots.map(s=>s.name);
 const vertices=(a,t)=>slots.flatMap(n=>Array.from(worldVertices(pose(data,a,t).findSlot(n))));
 const diff=(a,b)=>Math.max(...a.map((v,i)=>Math.abs(v-b[i])));
 const setup=vertices(null,0);
 const loopError=diff(vertices('idle_loop',0),vertices('idle_loop',3.6));
 const reviveError=diff(vertices('die',1.9),vertices('revive',0));
 assert(loopError<.1);assert(reviveError<.1);
 const area=(v,tr,i)=>{let[a,b,c]=tr.slice(i,i+3).map(n=>n*2);return(v[b]-v[a])*(v[c+1]-v[a+1])-(v[b+1]-v[a+1])*(v[c]-v[a]);};
 const specs=slots.map((name,i)=>{const tri=data.defaultSkin.getAttachment(i,name).triangles,v=Array.from(worldVertices(pose(data,null,0).findSlot(name)));return{name,tri,base:tri.filter((_,i)=>i%3==0).map((_,i)=>area(v,tri,i*3))};});
 let frames=0,flips=0;const failed={};
 for(const anim of data.animations){
  if(!['die','robust','withered'].includes(anim.name))assert(diff(vertices(anim.name,anim.duration),setup)<.15,anim.name+' return');
  for(let t=0;t<=anim.duration+1e-6;t+=1/60){const sk=pose(data,anim.name,t);
   for(const s of specs){const v=Array.from(worldVertices(sk.findSlot(s.name)));assert(v.every(Number.isFinite));
    for(let i=0;i<s.base.length;i++)if(area(v,s.tri,i*3)*s.base[i]<-.01){flips++;failed[`${anim.name}/${s.name}`]=(failed[`${anim.name}/${s.name}`]??0)+1;}}
   frames++;
  }
 }
 assert.equal(flips,0,JSON.stringify(failed));
 for(const form of ['robust','withered'])assert.deepEqual(Object.keys(raw.animations[form].bones),['cap_posture']);
 assert.equal(raw.animations.attack.events[0].time,.48);assert.equal(raw.animations.exchange.events[0].time,.62);
 reports.push({key,result:'PASS',bones:data.bones.length,slots:slots.length,animations:data.animations.length,frames,invertedTriangles:flips,loopError,reviveError});
}
fs.writeFileSync('verification.json',JSON.stringify(reports,null,2));console.log(reports);
