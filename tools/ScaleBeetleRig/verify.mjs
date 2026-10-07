// Check the packaged data through the official 4.2 runtime, not the authoring FK.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {load, pose, worldVertices} from './runtime.mjs';

const path=process.argv[2] ?? 'pkg/scale_beetle.spjson';
const atlas=process.argv[3] ?? 'pkg/scale_beetle.atlas';
const raw=JSON.parse(fs.readFileSync(path,'utf8'));
const data=load(path,atlas);
const required=['idle_loop','attack','whip','cast','molt','power_up','hurt','die','revive','summon'];
assert.deepEqual(data.animations.map(a=>a.name).sort(),required.toSorted());
assert.equal(data.bones.length,54);
assert.equal(data.slots.length,24);
for(const bone of data.bones) assert(data.bones.indexOf(bone.parent)<data.bones.indexOf(bone));

function vertices(sk) {
  return Object.fromEntries(sk.slots.map(slot=>[slot.data.name,worldVertices(slot)]));
}
function difference(a,b) {
  let max=0;
  for(const [name,values] of Object.entries(a)) for(let i=0;i<values.length;i++) max=Math.max(max,Math.abs(values[i]-b[name][i]));
  return max;
}
const setup=vertices(pose(data));
const idle0=vertices(pose(data,'idle_loop',0));
const idleEnd=vertices(pose(data,'idle_loop',data.findAnimation('idle_loop').duration));
const loopError=difference(idle0,idleEnd);
assert(loopError<0.01,`idle loop gap ${loopError}`);
const deathEnd=vertices(pose(data,'die',data.findAnimation('die').duration));
const reviveStart=vertices(pose(data,'revive',0));
const reviveError=difference(deathEnd,reviveStart);
assert(reviveError<0.02,`revive does not start in the held death pose: ${reviveError}`);
for(const name of required.filter(name=>!['idle_loop','die'].includes(name))) {
  const end=vertices(pose(data,name,data.findAnimation(name).duration));
  const error=difference(setup,end);
  assert(error<0.05,`${name} does not settle to setup: ${error}`);
}

const legs=['front','middle','rear','far_front','far_middle','far_rear'];
const rest=pose(data);
const planted=Object.fromEntries(legs.map(name=>{const b=rest.findBone(name+'_ankle');return[name,[b.worldX,b.worldY]];}));
const targets=JSON.parse(fs.readFileSync('out/foot-targets.json','utf8'));
const motion=[];
let maxFootError=0, frames=0, maxCoordinate=0;
for(const animation of data.animations) {
  let footError=0,groundSlide=0,minContacts=6,bodyStep=0,feelerStep=0,previous;
  const ranges={bodyX:[Infinity,-Infinity],bodyR:[Infinity,-Infinity],headY:[Infinity,-Infinity]};
  const lastFeet={};
  for(let frame=0;frame<=Math.ceil(animation.duration*120);frame++) {
    const t=Math.min(frame/120,animation.duration);
    const skeleton=pose(data,animation.name,t);
    for(const bone of skeleton.bones) {
      assert([bone.worldX,bone.worldY,bone.a,bone.b,bone.c,bone.d].every(Number.isFinite),`${animation.name}: non-finite bone`);
      maxCoordinate=Math.max(maxCoordinate,Math.abs(bone.worldX),Math.abs(bone.worldY));
      assert(Math.abs(bone.scaleX-1)<.001&&Math.abs(bone.scaleY-1)<.001,`${animation.name}: chitin stretches`);
    }
    for(const [name,bone,field] of [['bodyX','body','worldX'],['bodyR','body','rotation'],['headY','head','worldY']]) {
      const value=skeleton.findBone(bone)[field];
      ranges[name]=[Math.min(ranges[name][0],value),Math.max(ranges[name][1],value)];
    }
    const points=['body','head','antenna_near_7','antenna_far_7'].map(n=>skeleton.findBone(n));
    if(previous)points.forEach((b,i)=>{
      const d=Math.hypot(b.worldX-previous[i][0],b.worldY-previous[i][1]);
      if(i<2)bodyStep=Math.max(bodyStep,d);else feelerStep=Math.max(feelerStep,d);
    });
    previous=points.map(b=>[b.worldX,b.worldY]);
    assert(Math.abs(skeleton.findBone('ground_shadow').worldY-rest.findBone('ground_shadow').worldY)<.001,`${animation.name}: airborne shadow`);
    if(!['die','revive'].includes(animation.name)) {
      const authored=targets[animation.name],index=Math.min(Math.floor(t*60+1e-6),authored.length-1);
      const a=authored[index],b=authored[Math.min(index+1,authored.length-1)],u=Math.min(1,Math.max(0,t*60-index));
      let contacts=0;
      for(const leg of legs) {
        const offset=a.feet[leg].map((v,i)=>v*(1-u)+b.feet[leg][i]*u),foot=skeleton.findBone(leg+'_ankle');
        footError=Math.max(footError,Math.hypot(foot.worldX-planted[leg][0]-offset[0],foot.worldY-planted[leg][1]-offset[1]));
        if(offset[1]<.5)contacts++;
        const prev=lastFeet[leg];
        if(prev&&prev.lift<.1&&offset[1]<.1)groundSlide=Math.max(groundSlide,Math.abs(foot.worldX-prev.x));
        lastFeet[leg]={x:foot.worldX,lift:offset[1]};
      }
      minContacts=Math.min(minContacts,contacts);
      for(const name of ['head','jaw_near','jaw_far','antenna_near','antenna_far']) {
        const y=worldVertices(skeleton.slots.find(slot=>slot.data.name===name)).filter((_,i)=>i%2);
        assert(Math.min(...y)>0,`${animation.name}: ${name} penetrates the floor at ${t}`);
      }
    }
    if(animation.name==='idle_loop') {
      for(const name of legs) {
        if(name==='front' && t>=2.85 && t<=3.49) continue;
        if(name==='far_rear' && t>=1.25 && t<=1.87) continue;
        const b=skeleton.findBone(name+'_ankle'), expected=planted[name];
        maxFootError=Math.max(maxFootError,Math.hypot(b.worldX-expected[0],b.worldY-expected[1]));
      }
    }
    frames++;
  }
  assert(footError<1.5,`${animation.name}: unreachable foot target (${footError})`);
  assert(groundSlide<.7,`${animation.name}: planted-foot skating (${groundSlide})`);
  assert(minContacts>=3,`${animation.name}: fewer than three supporting feet`);
  assert(bodyStep<16,`${animation.name}: body discontinuity (${bodyStep})`);
  assert(feelerStep<95,`${animation.name}: feeler discontinuity (${feelerStep})`);
  const range=name=>ranges[name][1]-ranges[name][0];
  if(animation.name==='attack')assert(range('bodyX')>130&&range('headY')>90,'Bite lost its whole-body windup/lunge');
  if(animation.name==='whip')assert(range('bodyR')>14&&range('bodyX')>50,'Whip lost its body counterweight');
  if(['cast','molt','power_up','summon'].includes(animation.name))assert(range('headY')>70,`${animation.name}: display pose lost its amplitude`);
  motion.push({name:animation.name,duration:animation.duration,footError,groundSlide,minContacts,bodyStep,feelerStep,ranges});
}
assert(maxFootError<1.5,`idle planted feet drift ${maxFootError}`);
assert(maxCoordinate<2000,`unexpected runaway bone ${maxCoordinate}`);

// Rigid carapace: one bone per vertex; original gold patterns never rubber-sheet.
for(const name of ['shell_near','shell_far','collar','neck_shield']) {
  const mesh=raw.skins[0].attachments[name][name];
  for(let i=0;i<mesh.vertices.length;) {
    const n=mesh.vertices[i++];
    assert.equal(n,1,`${name} has a flexible chitin vertex`);
    assert.equal(mesh.vertices[i+3],1);
    i+=4;
  }
}
// Glow attachments use the identical host topology and skin weights.
for(const name of ['antenna_near','antenna_far','eye','shell_near','shell_far','collar']) {
  const host=raw.skins[0].attachments[name][name];
  const glow=raw.skins[0].attachments[name+'_glow'][name+'_glow'];
  for(const key of ['uvs','triangles','vertices']) assert.deepEqual(glow[key],host[key],`${name}: glow drifts off surface`);
}
for(const [name,event,times] of [['attack','bite_contact',[.68]],['whip','whip_contact',[.60,1.12,1.68]],['cast','reconstruct_release',[.76]],['molt','molt_release',[.80]]]) {
  assert.deepEqual(raw.animations[name].events.filter(key=>key.name===event).map(key=>key.time),times);
}
const windup=pose(data,'attack',0.3).findBone('jaw_near').rotation;
const contact=pose(data,'attack',0.68).findBone('jaw_near').rotation;
assert(windup-contact>40,'bite does not close at the gameplay hit time');
const whipNeutral=pose(data).findBone('antenna_near_7').worldX;
const whipContact=pose(data,'whip',0.60).findBone('antenna_near_7').worldX;
for(const [side,t] of [['near',.60],['far',1.12],['near',1.68],['far',1.68]]) {
  const neutral=rest.findBone(`antenna_${side}_7`).worldX,tip=pose(data,'whip',t).findBone(`antenna_${side}_7`);
  assert(neutral-tip.worldX>500,`${side} whip does not reach forward at ${t}`);
}

const report={frames,loop_error:loopError,revive_join_error:reviveError,
  planted_foot_max_error:maxFootError,whip_forward_reach:whipNeutral-whipContact,
  bones:data.bones.length,slots:data.slots.length,animations:required,motion};
fs.writeFileSync('out/verification.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
console.log('SCALE_BEETLE_RIG_PASS');
