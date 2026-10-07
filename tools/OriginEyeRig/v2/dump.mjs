// dump render triangles for frames: node dump.mjs <json> <atlas> <anim> <n> <out>
import * as S from '@esotericsoftware/spine-core'; import fs from 'fs';
const [,,jp,ap,an,N,out]=process.argv;
const atlas=new S.TextureAtlas(fs.readFileSync(ap,'utf8'));
for(const p of atlas.pages) p.setTexture({setFilters(){},setWraps(){},dispose(){},getImage(){return{width:p.width,height:p.height}}});
const L=new S.AtlasAttachmentLoader(atlas);
const sd= jp.endsWith('.skel')? new S.SkeletonBinary(L).readSkeletonData(new Uint8Array(fs.readFileSync(jp))) : new S.SkeletonJson(L).readSkeletonData(JSON.parse(fs.readFileSync(jp,'utf8')));
const sk=new S.Skeleton(sd);const a=sd.findAnimation(an);const res=[];
for(let k=0;k<+N;k++){const t=a.duration*k/(+N-1);sk.setToSetupPose();a.apply(sk,0,t,false,[],1,S.MixBlend.setup,S.MixDirection.mixIn);sk.updateWorldTransform(S.Physics.none);
 const fr={t,items:[]};
 for(const s of sk.drawOrder){const at=s.attachment;if(!at)continue;let v,uv,tri;
  if(at instanceof S.RegionAttachment){v=new Float32Array(8);at.computeWorldVertices(s,v,0,2);uv=Array.from(at.uvs);tri=[0,1,2,2,3,0];}
  else if(at instanceof S.MeshAttachment){v=new Float32Array(at.worldVerticesLength);at.computeWorldVertices(s,0,at.worldVerticesLength,v,0,2);uv=Array.from(at.uvs);tri=Array.from(at.triangles);} else continue;
  const c=s.color, c2=at.color;
  fr.items.push({v:Array.from(v),uv,tri,col:[c.r*c2.r,c.g*c2.g,c.b*c2.b,c.a*c2.a],add:s.data.blendMode==1,page:at.region.page.name});}
 res.push(fr);}
fs.writeFileSync(out,JSON.stringify(res));
