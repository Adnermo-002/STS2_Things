import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const data=load('pkg/lantern_fish.spjson','pkg/lantern_fish.atlas');
const raw=JSON.parse(fs.readFileSync('pkg/lantern_fish.spjson','utf8'));
const names=['idle_loop','attack','tail_swipe','cast','guard','hurt','die','revive','summon','power_up'];
assert.deepEqual(data.animations.map(a=>a.name).sort(),names.toSorted());
assert.equal(data.bones.length,24);
function verts(anim,t){const s=pose(data,anim,t);return worldVertices(s.findSlot('skin'));}
function diff(a,b){return Math.max(...a.map((v,i)=>Math.abs(v-b[i])));}
const loopError=diff(verts('idle_loop',0),verts('idle_loop',4));
assert(loopError<.05,`Idle seam ${loopError}`);
const reviveError=diff(verts('die',1.8),verts('revive',0));
assert(reviveError<.05,`Revive seam ${reviveError}`);
const setup=verts(null,0),triangles=data.defaultSkin.getAttachment(0,'skin').triangles;
const area=(v,i)=>{const [a,b,c]=triangles.slice(i,i+3).map(k=>k*2);return (v[b]-v[a])*(v[c+1]-v[a+1])-(v[b+1]-v[a+1])*(v[c]-v[a]);};
const restAreas=Array.from({length:triangles.length/3},(_,i)=>area(setup,i*3));
let frames=0,flipped=0,maxDisplacement=0;
for(const anim of data.animations){
 for(let t=0;t<=anim.duration+1e-6;t+=1/60){
  const s=pose(data,anim.name,t),v=worldVertices(s.findSlot('skin'));
  assert(v.every(Number.isFinite),`${anim.name}: finite geometry`);
  for(let j=0;j<restAreas.length;j++) if(area(v,j*3)*restAreas[j]<-.01)flipped++;
  for(let i=0;i<v.length;i++)maxDisplacement=Math.max(maxDisplacement,Math.abs(v[i]-setup[i]));
  const glow=worldVertices(s.findSlot('lantern_glow'));assert(diff(v,glow)<.01,'Glow follows exact skin');
  const lamp=s.findBone('lamp'),parent=lamp.parent;
  const dx=lamp.worldX-parent.worldX,dy=lamp.worldY-parent.worldY;
  const expectedLength=Math.hypot(parent.a*lamp.x+parent.b*lamp.y,parent.c*lamp.x+parent.d*lamp.y);
  assert(Math.abs(Math.hypot(dx,dy)-expectedLength)<.1,'Lamp stays attached under inherited scale');
  frames++;
 }
}
assert.equal(flipped,0,'No inverted skin triangles');
assert(maxDisplacement>150,'Motion has readable deformation');
assert.equal(raw.animations.cast.events[0].time,.72);
assert.equal(raw.animations.attack.events[0].time,.48);
assert.equal(raw.animations.tail_swipe.events[0].time,.36);
const report={result:'PASS',runtime:'official Spine 4.2.43',bones:data.bones.length,animations:names.length,
 frames,loopError,reviveError,invertedTriangles:flipped,maxDisplacement};
fs.writeFileSync('pkg/verification.json',JSON.stringify(report,null,2));console.log(report);
