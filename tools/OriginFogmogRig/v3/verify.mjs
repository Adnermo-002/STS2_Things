// Regression at the actual runtime seam: the same painted joint must stay joined
// while the vanilla IK/transform constraints and animation timelines are running.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as S from '@esotericsoftware/spine-core';
import {load, pose, worldVertices} from './runtime.mjs';

const path = process.argv[2] ?? 'out/origin_fogmog.spjson';
const atlasPath = process.argv[3] ?? 'source/origin_fogmog.atlas';
// JSON's -0 and 0 have the same transform semantics; JS serialization normalizes them.
const canonical = text => JSON.parse(JSON.stringify(JSON.parse(text)));
const raw = canonical(fs.readFileSync(path, 'utf8'));
const original = canonical(fs.readFileSync('source/origin_fogmog.spjson', 'utf8'));
const authoredMotion = process.argv.includes('--authored-motion');
const data = load(path, atlasPath);
const bind = pose(data, 'idle_loop', 0);
const problems = [];
const anchors = [];

function locate(slotName, point) {
  const slot = bind.findSlot(slotName), attachment = slot.attachment;
  const vertices = worldVertices(slot);
  const triangles = attachment instanceof S.MeshAttachment ? attachment.triangles : [0,1,2,0,2,3];
  let best;
  for (let i=0; i<triangles.length; i+=3) {
    const ids=Array.from(triangles.slice(i,i+3));
    const [a,b,c]=ids.map(k=>[vertices[k*2],vertices[k*2+1]]);
    const det=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
    if (Math.abs(det)<1e-8) continue;
    const v=((point[0]-a[0])*(c[1]-a[1])-(point[1]-a[1])*(c[0]-a[0]))/det;
    const w=((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))/det;
    const weights=[1-v-w,v,w];
    const outside=weights.reduce((sum,n)=>sum+Math.max(0,-n),0);
    if (!best || outside<best.outside) best={slotName,ids,weights,outside};
    if (outside<1e-6) break;
  }
  assert(best, `No triangles for ${slotName}`);
  return best;
}

function sample(skeleton, ref, cache) {
  let vertices=cache.get(ref.slotName);
  if (!vertices) {
    vertices=worldVertices(skeleton.findSlot(ref.slotName));
    cache.set(ref.slotName,vertices);
  }
  return [0,1].map(axis=>ref.ids.reduce((sum,id,i)=>sum+vertices[id*2+axis]*ref.weights[i],0));
}

// Use the recovered painting coordinates, independent of the repaired weights.
const reference=JSON.parse(fs.readFileSync('out/bind.json','utf8'));
for (const slot of original.slots.filter(s=>s.name.includes('finger'))) {
  const vertices=reference.attachments[slot.name][slot.attachment].world;
  const point=[(vertices[2]+vertices[4])/2,
    vertices[3]*0.88+vertices[1]*0.12];
  const host=slot.name.startsWith('top')?'top arm':'bottom arm';
  anchors.push({name:slot.name,a:locate(slot.name,point),b:locate(host,point),max:0});
}
for (const [name,a,b,point] of [
  ['front ankle','top leg','top foot',[110,60]],
  ['back ankle','bottom leg','bottom foot',[-60,61]],
]) anchors.push({name,a:locate(a,point),b:locate(b,point),max:0});

let frames=0;
for (const animation of data.animations) {
  for (let frame=0; frame<=Math.ceil(animation.duration*120); frame++) {
    const time=Math.min(frame/120,animation.duration);
    const skeleton=pose(data,animation.name,time), cache=new Map();
    for (const anchor of anchors) {
      const a=sample(skeleton,anchor.a,cache), b=sample(skeleton,anchor.b,cache);
      const error=Math.hypot(a[0]-b[0],a[1]-b[1]);
      if (error>anchor.max) Object.assign(anchor,{max:error,at:`${animation.name}@${time.toFixed(3)}`});
    }
    frames++;
  }
}
for (const anchor of anchors) {
  console.log(`${anchor.name}: max separation=${anchor.max.toFixed(3)} units ${anchor.at}`);
  if (anchor.max>1.5) problems.push(anchor.name);
}

// Original motion/VFX contract remains intact; only seven rooted claw curls are added.
assert.deepEqual(raw.bones.slice(0,original.bones.length),original.bones);
assert.deepEqual(raw.ik,original.ik);
assert.deepEqual(raw.transform,original.transform);
assert.deepEqual(raw.slots,original.slots);
const eventDefinitions={...raw.events};
if(authoredMotion) {
  delete eventDefinitions.attack_hit;
  delete eventDefinitions.ground_impact;
}
assert.deepEqual(eventDefinitions,original.events);
for (const [name,animation] of Object.entries(original.animations)) {
  if(authoredMotion && !['die','revive'].includes(name)) continue;
  for (const [section,timeline] of Object.entries(animation)) {
    if (section==='bones') {
      for (const [bone,keys] of Object.entries(timeline)) assert.deepEqual(raw.animations[name].bones[bone],keys);
    } else assert.deepEqual(raw.animations[name][section],timeline);
  }
}
if(authoredMotion) {
  const repaired=canonical(fs.readFileSync('out/origin_fogmog.spjson','utf8'));
  assert.deepEqual(raw.skins,repaired.skins,'Motion authoring must preserve repaired skin weights');
  for(const name of ['headbutt','triple_attack']) assert(raw.animations[name],`Missing ${name}`);
}
console.log(`FOGMOG_SEAMS_${problems.length?'FAIL':'PASS'} frames=${frames} failing_joints=${problems.length}`);
process.exitCode=problems.length?1:0;
