// Rebuild attack reach controls through the official Spine 4.2 runtime.
import fs from 'node:fs';
import {load,pose,worldVertices} from '../tools/ScaleBeetleRig/runtime.mjs';
const source=process.argv[2]??'source_assets/monsters/cave_god_motion/contact_base.spjson';
const destination='animations/monsters/cave_god/cave_god.spjson';
const atlas='animations/monsters/cave_god/cave_god.atlas';
const raw=JSON.parse(fs.readFileSync(source,'utf8'));
let data=load(source,atlas);
const clean=v=>Math.round(v*1e5)/1e5;
const unwrap=(value,last)=>last==null?value:last+(((value-last+180)%360+360)%360-180);
// These authored/mirrored clips did not end in the same local pose as idle.
// Settle only their recovery tails, preserving the wind-up and all hit frames.
for(const base of ['front_sweep_right','grab_slam','grab_slam_right'])for(const suffix of ['', '_angry']){
 const name=base+suffix,clip=raw.animations[name],duration=data.findAnimation(name).duration;
 const start=duration-.65,settled=duration-.12,idle=pose(data,'idle_front'+suffix,0);
 const times=[start,...Array.from({length:Math.ceil((duration-start)*120)},(_,i)=>Math.min(duration,start+(i+1)/120)),settled,duration]
  .filter((t,i,a)=>a.indexOf(t)===i).sort((a,b)=>a-b);
 const samples=times.map(t=>{const u=Math.max(0,Math.min(1,(t-start)/(settled-start)));return{t,w:u*u*u*(10-15*u+6*u*u),rig:pose(data,name,t)}});
 const lerp=(a,b,w)=>a+(b-a)*w;
 for(const setup of raw.bones){
  const name=setup.name,target=idle.findBone(name),channels=(clip.bones??={})[name]??={};
  const generated={rotate:[],translate:[],scale:[],shear:[]};
  for(const {t,w,rig} of samples){
   const b=rig.findBone(name),time=clean(t);
   generated.rotate.push({time,value:clean(lerp(b.rotation,unwrap(target.rotation,b.rotation),w)-(setup.rotation??0))});
   generated.translate.push({time,x:clean(lerp(b.x,target.x,w)-(setup.x??0)),y:clean(lerp(b.y,target.y,w)-(setup.y??0))});
   generated.scale.push({time,x:clean(lerp(b.scaleX,target.scaleX,w)/(setup.scaleX??1)),y:clean(lerp(b.scaleY,target.scaleY,w)/(setup.scaleY??1))});
   generated.shear.push({time,x:clean(lerp(b.shearX,target.shearX,w)-(setup.shearX??0)),y:clean(lerp(b.shearY,target.shearY,w)-(setup.shearY??0))});
  }
  for(const [channel,keys] of Object.entries(generated))channels[channel]=[...(channels[channel]??[]).filter(k=>(k.time??0)<start),...keys];
 }
 for(const setup of raw.ik){
  const target=idle.findIkConstraint(setup.name);
  const keys=samples.map(({t,w,rig})=>({time:clean(t),mix:clean(lerp(rig.findIkConstraint(setup.name).mix,target.mix,w)),bendPositive:setup.bendPositive??true}));
  clip.ik[setup.name]=[...(clip.ik[setup.name]??[]).filter(k=>(k.time??0)<start),...keys];
 }
}
fs.mkdirSync('build/cavegod_renew',{recursive:true});
fs.writeFileSync('build/cavegod_renew/normalized-source.spjson',JSON.stringify(raw));
data=load('build/cavegod_renew/normalized-source.spjson',atlas);
const definitions={
 alternating_jabs:[[.32,.64,.72,1.0,'arm1_3'],[1.02,1.34,1.42,1.7,'arm2_3'],[1.9,2.32,2.42,3.35,'arm1_3']],
 central_slam:[[1.05,1.88,2.10,3.6,'arm1_3','arm2_3']],
 double_fist_crush:[[.65,1.25,1.53,3.18,'arm1_3','arm2_3']],
 front_sweep:[[.76,1.35,1.48,3.22,'arm1_3']],
 front_sweep_right:[[.76,1.35,1.48,3.22,'arm2_3']],
 card_snatch:[[1,1.36,1.68,3.08,'arm1_3']],
 card_snatch_right:[[1,1.36,1.68,3.08,'arm2_3']],
 weak_attack:[[.6,1.2,1.35,2.5,'arm2_3']],
 weak_attack_right:[[.6,1.2,1.35,2.5,'arm1_3']],
 grab_player:[[.65,1.1,1.28,2.2,'arm1_3']],
 grab_player_right:[[.65,1.1,1.28,2.2,'arm2_3']],
 grab_slam:[[.22,.75,.83,1.62,'arm1_3']],
 grab_slam_right:[[.22,.75,.83,1.62,'arm2_3']],
};
const profiles=[];
for(const side of [1,2]){
 // Append: weighted Spine vertices store numeric indices of the original bones.
 raw.bones.push({name:`hand${side}_contact_rotation`,parent:'root'});
 (raw.transform??=[]).push({name:`hand${side}_contact_rotation`,order:side+1,
  bones:[`arm${side}_3`],target:`hand${side}_contact_rotation`,mixRotate:0,mixX:0,mixY:0,mixScaleX:0,mixScaleY:0,mixShearY:0});
}
// An omitted direction means positive, even at a zero-mix key. Keep the setup
// direction when disabling IK so it cannot flip while the outgoing mix is > 0.
for(const clip of Object.values(raw.animations))for(const [name,keys] of Object.entries(clip.ik??{}))
 for(const key of keys)if((key.mix??1)===0 && key.bendPositive===undefined)
  key.bendPositive=raw.ik.find(c=>c.name===name)?.bendPositive??true;
// Every incoming clip needs the helper directions too. Otherwise the helper
// rotates toward setup zero while its transform constraint simultaneously fades
// out, briefly bending the wrist away from both the outgoing and incoming pose.
for(const [name,clip] of Object.entries(raw.animations)){
 const duration=data.findAnimation(name).duration;
 for(const side of [1,2]){
  const keys=[];let last;
  for(let frame=0;frame<=Math.ceil(duration*120);frame++){
   const t=Math.min(frame/120,duration),s=pose(data,name,t),b=s.findBone(`arm${side}_3`),root=s.findBone('root');
   const angle=Math.atan2(b.c,b.a)*180/Math.PI-Math.atan2(root.c,root.a)*180/Math.PI;
   last=unwrap(angle,last);keys.push({time:clean(t),value:clean(last)});
  }
  (clip.bones??={})[`hand${side}_contact_rotation`]={rotate:keys};
 }
}
for(const [base,impacts] of Object.entries(definitions))for(const suffix of ['', '_angry']){
 const name=base+suffix,clip=raw.animations[name];if(!clip)continue;
 const duration=data.findAnimation(name).duration;
 const active=new Set(impacts.flatMap(p=>p.slice(4)));
 for(const side of [1,2].filter(side=>active.has(`arm${side}_3`))){
  const targets=[];
  const targetSetup=raw.bones.find(b=>b.name===`arm${side}_IK`);
  for(let frame=0;frame<=Math.ceil(duration*120);frame++){
   const t=Math.min(frame/120,duration),s=pose(data,name,t),b=s.findBone(`arm${side}_3`),root=s.findBone('root');
   const forearm=s.findBone(`arm${side}_2`);
   const endpoint=root.worldToLocal(forearm.localToWorld({x:forearm.data.length,y:0}));
   targets.push({time:clean(t),x:clean(endpoint.x-targetSetup.x),y:clean(endpoint.y-targetSetup.y)});
  }
  clip.bones[`arm${side}_IK`].translate=targets;
  (clip.transform??={})[`hand${side}_contact_rotation`]=[{mixRotate:1,mixX:0,mixY:0,mixScaleX:0,mixScaleY:0,mixShearY:0}];
 }
 // Explicit bend direction on all keys prevents elbow flips across transitions.
 for(const [name,keys] of Object.entries(clip.ik)){
  if(!active.has(name==='arm2_IK'?'arm1_3':'arm2_3'))continue;
  for(const key of keys){key.mix=1;key.bendPositive=name==='arm2_IK';}
 }
 for(const [start,hit,hold,end,...hands] of impacts){
  const sk=pose(data,name,hit);
  for(const hand of hands){
   const verts=worldVertices(sk.findSlot(hand));
   const xs=verts.filter((_,i)=>i%2===0),ys=verts.filter((_,i)=>i%2===1);
   const min=[Math.min(...xs),Math.min(...ys)],max=[Math.max(...xs),Math.max(...ys)];
   const b=sk.findBone(hand),center=min.map((v,i)=>(v+max[i])/2);
   profiles.push({clip:name,start,hit,hold,end,hand,paired:hands.length===2,
    center:center.map(clean),offset:[center[0]-b.worldX,center[1]-b.worldY].map(clean),
    size:min.map((v,i)=>clean(max[i]-v)),grab:base.startsWith('grab_')});
  }
 }
}
fs.writeFileSync(destination,JSON.stringify(raw,null,2)+'\n');
fs.writeFileSync('source_assets/monsters/cave_god_motion/contact_profiles.json',JSON.stringify(profiles,null,2)+'\n');
const f=n=>`${Number(n).toFixed(5)}f`;
const v=values=>`new Vector2(${values.map(f).join(', ')})`;
const lines=profiles.map(p=>`        new("${p.clip}", ${f(p.start)}, ${f(p.hit)}, ${f(p.hold)}, ${f(p.end)}, ${p.hand==='arm1_3'?'true':'false'}, ${p.paired}, ${p.grab}, ${v(p.center)}, ${v(p.offset)}, ${v(p.size)}),`);
fs.writeFileSync('STS2_Things/Visuals/CaveGodContactProfiles.cs',`// Generated by scripts/build_cavegod_contact.mjs from the original Spine mesh poses.\nusing Godot;\n\nnamespace STS2_Things.Visuals;\n\ninternal readonly record struct CaveGodContactProfile(string Clip, float Start, float Hit, float Hold, float End, bool Left, bool Paired, bool Grab, Vector2 Center, Vector2 PalmOffset, Vector2 Size);\n\ninternal static class CaveGodContactProfiles\n{\n    internal static readonly CaveGodContactProfile[] All =\n    [\n${lines.join('\n')}\n    ];\n}\n`);
console.log(`Built ${profiles.length} contact profiles and world-oriented wrist controls.`);
