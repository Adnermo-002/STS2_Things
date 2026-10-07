import * as S from '@esotericsoftware/spine-core'; import fs from 'fs';
const atlas=new S.TextureAtlas(fs.readFileSync('../ref/eye_with_teeth.atlas','utf8'));
for(const p of atlas.pages) p.setTexture({setFilters(){},setWraps(){},dispose(){},getImage(){return{width:1,height:1}}});
const L=new S.AtlasAttachmentLoader(atlas);
const A=new S.SkeletonBinary(L).readSkeletonData(new Uint8Array(fs.readFileSync('../ref/eye_with_teeth.skel')));
const B=new S.SkeletonJson(L).readSkeletonData(JSON.parse(fs.readFileSync('eye_baked.json','utf8')));
function verts(sd,an,t){const sk=new S.Skeleton(sd);sk.setToSetupPose();const a=sd.findAnimation(an);a.apply(sk,0,t,false,[],1,S.MixBlend.setup,S.MixDirection.mixIn);sk.updateWorldTransform(S.Physics.none);
 const o={};for(const s of sk.slots){const at=s.attachment;if(!at)continue;let v;
 if(at instanceof S.RegionAttachment){v=new Float32Array(8);at.computeWorldVertices(s,v,0,2);}else if(at instanceof S.MeshAttachment){v=new Float32Array(at.worldVerticesLength);at.computeWorldVertices(s,0,at.worldVerticesLength,v,0,2);}else continue;
 o[s.data.name]=[at.name,v,s.color.a];}return o;}
for(const an of ['idle_loop','attack','die']){let mx=0,worst='';const d=A.findAnimation(an).duration;
 for(let t=0;t<=d;t+=d/37){const a=verts(A,an,t),b=verts(B,an,t);
  for(const k in a){if(!b[k]){if(a[k][2]>0.01){worst='missing '+k;mx=1e9;}continue;}if(a[k][0]!==b[k][0]){worst='att '+k;continue;}
   for(let i=0;i<a[k][1].length;i++){const e=Math.abs(a[k][1][i]-b[k][1][i]);if(e>mx){mx=e;worst=k+' t='+t.toFixed(2);}}}}
 console.log(an,'max vertex err',mx.toFixed(3),worst);}
{const t=0.5;const a=verts(A,'attack',t),b=verts(B,'attack',t);console.log('A pupil2',a.pupil2&&a.pupil2[0],a.pupil2&&a.pupil2[2],'B',b.pupil2&&b.pupil2[0]);
const j=JSON.parse(fs.readFileSync('eye_baked.json','utf8'));console.log(JSON.stringify(j.animations.attack.slots.pupil2||{}).slice(0,300));console.log(JSON.stringify(j.slots.find(s=>s.name=='pupil2')));}
