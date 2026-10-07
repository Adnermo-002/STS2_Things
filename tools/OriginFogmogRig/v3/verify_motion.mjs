import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load,pose,worldVertices} from './runtime.mjs';

const path=process.argv[2]??'out/origin_fogmog_boss.spjson';
const data=load(path,'source/origin_fogmog.atlas');
const bind=pose(data,'idle_loop',0);
const contract=JSON.parse(fs.readFileSync('out/motion-contract.json','utf8'));
const distance=(a,b)=>Math.hypot(a.worldX-b.worldX,a.worldY-b.worldY);
const rows=[];
for(const [name,info] of Object.entries(contract)) {
  let maxFootError=0,maxGroundSlide=0,maxStep=0,maxAcceleration=0,previous,velocity;
  let minCapX=Infinity,maxCapX=-Infinity,minBody=Infinity,maxBody=-Infinity,maxTravel=0,maxRise=0;
  const steps={f:0,b:0},clearance={f:0,b:0},lastFeet={};
  for(let i=0;i<=Math.round(info.duration*120);i++) {
    const t=Math.min(i/120,info.duration),s=pose(data,name,t);
    for(const side of ['f','b']) {
      const foot=s.findBone(`foot_${side}`),target=s.findBone(`leg_${side}_ik`);
      const lift=target.worldY-bind.findBone(`leg_${side}_ik`).worldY;
      maxFootError=Math.max(maxFootError,distance(foot,target));
      assert(lift>-.01,`${name}: foot ${side} penetrates the ground at ${t}`);
      clearance[side]=Math.max(clearance[side],lift);
      const prev=lastFeet[side];
      if(prev) {
        if(lift>.5 && prev.lift<=.5) steps[side]++;
        if(lift<.1 && prev.lift<.1)
          maxGroundSlide=Math.max(maxGroundSlide,Math.abs(foot.worldX-prev.x));
      }
      lastFeet[side]={x:foot.worldX,lift};
    }
    const points=['cog','head_pivot','arm_b_lower','arm_f_lower','bottom_finger_3_skin','top_finger_4_skin'].map(n=>s.findBone(n));
    if(previous) {
      const v=points.map((b,j)=>[b.worldX-previous[j][0],b.worldY-previous[j][1]]);
      v.forEach((v,j)=>{
        maxStep=Math.max(maxStep,Math.hypot(...v));
        if(velocity) maxAcceleration=Math.max(maxAcceleration,Math.hypot(v[0]-velocity[j][0],v[1]-velocity[j][1]));
      });
      velocity=v;
    }
    previous=points.map(b=>[b.worldX,b.worldY]);
    minCapX=Math.min(minCapX,points[1].worldX);maxCapX=Math.max(maxCapX,points[1].worldX);
    minBody=Math.min(minBody,s.findBone('bod').rotation);maxBody=Math.max(maxBody,s.findBone('bod').rotation);
    maxTravel=Math.max(maxTravel,-s.findBone('root').worldX);maxRise=Math.max(maxRise,s.findBone('root').worldY);
    assert(Math.abs(s.findBone('shadow').worldY)<.001,`${name}: shadow lifts off the floor`);
    assert(Math.abs(s.findBone('ground_dust').worldY)<.001,`${name}: dust socket lifts off the floor`);
    for(const slot of s.slots.filter(slot=>slot.data.name.includes('finger'))) {
      const y=worldVertices(slot).filter((_,i)=>i%2);
      assert(Math.min(...y)>0,`${name}: ${slot.data.name} penetrates the floor at ${t.toFixed(3)}`);
    }
    for(const bone of ['arm_b_upper','arm_b_lower','arm_f_upper','arm_f_lower']) {
      const b=s.findBone(bone),a=bind.findBone(bone);
      assert(Math.abs(b.scaleX-a.scaleX)<.0001&&Math.abs(b.scaleY-a.scaleY)<.0001,`${name}/${bone}: elastic arm scaling returned`);
    }
  }
  assert(maxFootError<1,`${name}: leg cannot reach its target (${maxFootError.toFixed(3)})`);
  assert(maxGroundSlide<.3,`${name}: a planted foot skates (${maxGroundSlide.toFixed(3)} per frame)`);
  // Large arcs may move quickly; bound displacement and velocity change so
  // enforcing smoothness never requires making the action tiny again.
  assert(maxStep<20,`${name}: joint jumps ${maxStep.toFixed(3)} units at 120 Hz`);
  assert(maxAcceleration<3,`${name}: abrupt velocity change ${maxAcceleration.toFixed(3)}`);
  const end=pose(data,name,info.duration);
  for(const bone of bind.bones) {
    const b=end.findBone(bone.data.name);
    assert(distance(bone,b)<.001,`${name}: return pose does not match idle (${bone.data.name})`);
    for(const axis of ['a','b','c','d']) assert(Math.abs(bone[axis]-b[axis])<.001,`${name}: return rotation/scale differs (${bone.data.name})`);
  }
  const capRange=maxCapX-minCapX,bodyRange=maxBody-minBody;
  const minima={attack:[45,200,40],headbutt:[85,260,45],triple_attack:[75,230,40]}[name];
  if(minima) {
    assert(maxTravel>minima[0]&&capRange>minima[1]&&bodyRange>minima[2],`${name}: full-body action lost its amplitude`);
    for(const side of ['f','b']) assert(steps[side]>=2&&clearance[side]>20,`${name}: steps lack distinct lift, plant and return`);
  } else if(name==='summon') {
    assert(maxRise>45&&Math.min(...Object.values(clearance))>60,'Summon lost its heavy hop');
    const landing=info.events.find(e=>e.name==='ground_impact');
    assert(landing,'Summon lacks a landing cue');
    const s=pose(data,name,landing.time);
    for(const side of ['f','b']) assert(Math.abs(s.findBone(`foot_${side}`).worldY-bind.findBone(`foot_${side}`).worldY)<.01,'Dust does not coincide with landing');
  } else if(name==='power_up'||name==='cast') {
    assert(bodyRange>20&&capRange>75,`${name}: exhale lost its full-body windup`);
  }
  rows.push({name,duration:info.duration,maxFootError,maxGroundSlide,maxStep,maxAcceleration,capRange,bodyRange,maxTravel,maxRise,steps,clearance});
}
const headbutt=pose(data,'headbutt',.8);
assert(headbutt.findBone('head_pivot').worldX < bind.findBone('head_pivot').worldX-190,'Headbutt does not lead with the cap');
const hitHeights=[.48,.94,1.4].map(t=>pose(data,'triple_attack',t).findBone('bottom_finger_3_skin').worldY);
assert(hitHeights[1]>hitHeights[0]+35 && hitHeights[2]<hitHeights[0]-75,'Triple attack lost the rising rake/downward chop contrast');
fs.writeFileSync('out/motion-measurements.json',JSON.stringify(rows,null,2));
console.table(rows.map(({name,maxFootError,maxStep,capRange,maxTravel,maxRise})=>({name,maxFootError,maxStep,capRange,maxTravel,maxRise})));
console.log('FOGMOG_MOTION_PASS broad body arcs, lifted steps, planted contacts, grounded shadow, continuous return');
