// node verify_eye.mjs <ref>/eye_with_teeth <out>/origin_eye_with_teeth.spjson <out>/origin_eye_with_teeth.atlas
// checks the v3 rig against the vanilla binary: geometry of idle/attack/die, hurt = idle 0..0.5 (+cog recoil), revive = reversed die
import * as S from '@esotericsoftware/spine-core'; import fs from 'fs';
function loadSkel(sp, ap){ const atlas=new S.TextureAtlas(fs.readFileSync(ap,'utf8'));
  for(const p of atlas.pages) p.setTexture({setFilters(){},setWraps(){},dispose(){},getImage(){return{width:p.width,height:p.height}}});
  const L=new S.AtlasAttachmentLoader(atlas);
  const sd= sp.endsWith('.skel')? new S.SkeletonBinary(L).readSkeletonData(new Uint8Array(fs.readFileSync(sp))) : new S.SkeletonJson(L).readSkeletonData(JSON.parse(fs.readFileSync(sp,'utf8')));
  return {sd}; }
const [,,V,jp,ap]=process.argv;
const A=loadSkel(V+'.skel',V+'.atlas').sd, B=loadSkel(jp,ap).sd;
console.log('v3 loaded: bones',B.bones.length,'slots',B.slots.length,'path',B.pathConstraints.length,'tc',B.transformConstraints.length,'anims',B.animations.map(a=>a.name+':'+a.duration.toFixed(3)).join(' '));
function pose(sd,an,t){const sk=new S.Skeleton(sd);sk.setToSetupPose();sd.findAnimation(an).apply(sk,0,t,false,[],1,S.MixBlend.setup,S.MixDirection.mixIn);
 const loc={}; for(const b of sk.bones) loc[b.data.name]=[b.x,b.y,b.rotation,b.scaleX,b.scaleY,b.shearX,b.shearY];
 sk.updateWorldTransform(S.Physics.none);
 const o={};for(const s of sk.slots){const at=s.attachment;let v=null;
  if(at instanceof S.RegionAttachment){v=new Float32Array(8);at.computeWorldVertices(s,v,0,2);}else if(at instanceof S.MeshAttachment){v=new Float32Array(at.worldVerticesLength);at.computeWorldVertices(s,0,at.worldVerticesLength,v,0,2);}
  o[s.data.name]={att:at?at.name:null,v,a:s.color.a,c:[s.color.r,s.color.g,s.color.b]};}
 return {o,loc};}
function vdiff(a,b,skipAlpha0){let e=0,w='',natt=0; for(const k in a){ if(!b[k]) continue; if(a[k].att!==b[k].att){ if(!(skipAlpha0 && a[k].a<0.01 && b[k].a<0.01)) natt++; continue;} if(a[k].v) for(let i=0;i<a[k].v.length;i++){const d=Math.abs(a[k].v[i]-b[k].v[i]); if(d>e){e=d;w=k;}}} return [e,w,natt];}
// 1) vanilla anims: geometry identical
for(const an of ['idle_loop','attack','die']){const d=A.findAnimation(an).duration; let E=0,W='',N=0;
 for(let f=0;f<d*120-1;f++){const t=(f+0.5)/120; const [e,w,n]=vdiff(pose(A,an,t).o,pose(B,an,t).o); if(e>E){E=e;W=w+'@'+t.toFixed(3);} N+=n;}
 console.log('geometry',an.padEnd(9),'max vertex err',E.toFixed(4),W,'att mismatches',N);}
// 2) hurt = idle 0..0.5 (except cog), recoil only on cog
{let E=0,W=''; for(let f=0;f<60;f++){const t=(f+0.5)/120; const a=pose(B,'idle_loop',t).loc, b=pose(B,'hurt',t).loc;
  for(const k in a){ if(k==='cog') continue; for(let i=0;i<7;i++){const d=Math.abs(a[k][i]-b[k][i]); if(d>E){E=d;W=k+'['+i+']@'+t.toFixed(3);}}}}
 const end=pose(B,'hurt',0.5).loc.cog, idle05=pose(B,'idle_loop',0.5).loc; let E2=0; const h05=pose(B,'hurt',0.4999).loc; for(const k in idle05){ if(k==='cog') continue; for(let i=0;i<7;i++) E2=Math.max(E2,Math.abs(idle05[k][i]-h05[k][i]));}
 const peak=pose(B,'hurt',0.0667).loc.cog;
 console.log('hurt vs idle local max err',E.toFixed(5),W,'| @0.5 err',E2.toFixed(4),'| cog@0.0667 rot',peak[2].toFixed(1),'x',(peak[0]).toFixed(1),'sx',peak[3].toFixed(2),'| cog@0.5',end.map(v=>v.toFixed(2)).join(','));}
// 3) revive(tau) == die(D - tau/s)
{const D=A.findAnimation('die').duration, R=B.findAnimation('revive').duration, s=R/D; let E=0,W='',N=0,EA=0;
 for(let f=0;f<R*120-1;f++){const tau=(f+0.5)/120; const a=pose(B,'die',D-tau/s).o, b=pose(B,'revive',tau).o; const [e,w,n]=vdiff(a,b,true); if(e>E){E=e;W=w+'@'+tau.toFixed(3);} N+=n;
   for(const k in a) if(b[k]) EA=Math.max(EA,Math.abs(a[k].a-b[k].a));}
 console.log('revive vs reversed die: max vertex err',E.toFixed(4),W,'| visible att mismatches',N,'| max alpha err',EA.toFixed(4));
 const r0=pose(B,'revive',0).o, rEnd=pose(B,'revive',R).o, i0=pose(B,'idle_loop',0).o; console.log('revive@0 petals alpha',r0['back petals'].a.toFixed(2),'death_still',r0.death_still.att,'| revive@end petals alpha',rEnd['back petals'].a.toFixed(2),'vs idle0',i0['back petals'].a.toFixed(2),'| end-vs-idle0 geometry err',vdiff(rEnd,i0)[0].toFixed(1));}
// 4) colours at a few moments
for(const [an,t] of [['idle_loop',0.5],['attack',0.35],['hurt',0.0333],['die',1.0],['die',1.8]]){const o=pose(B,an,t).o; console.log('colour',an,t, ['back petals','eyeball','pupil','death_still','eyeball2'].map(k=>k+':'+(o[k].att?'':'(none)')+o[k].c.map(v=>v.toFixed(2)).join('/')+' a'+o[k].a.toFixed(2)).join('  '));}
