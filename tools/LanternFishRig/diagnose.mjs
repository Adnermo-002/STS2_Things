import {load,pose,worldVertices} from '../ScaleBeetleRig/runtime.mjs';
const d=load('pkg/lantern_fish.spjson','pkg/lantern_fish.atlas'),s=pose(d,null,0),r=worldVertices(s.findSlot('skin')),tr=s.findSlot('skin').attachment.triangles;
const area=(v,i)=>{let a=tr[i]*2,b=tr[i+1]*2,c=tr[i+2]*2;return(v[b]-v[a])*(v[c+1]-v[a+1])-(v[b+1]-v[a+1])*(v[c]-v[a]);};
for(let an of d.animations){let max=0,at=0,points=[];for(let t=0;t<=an.duration;t+=.05){let v=worldVertices(pose(d,an.name,t).findSlot('skin')),bad=[];for(let i=0;i<tr.length;i+=3)if(area(v,i)*area(r,i)<-.01){let a=tr[i]*2;bad.push([Math.round(r[a]+800),Math.round(1180-r[a+1])]);}if(bad.length>max){max=bad.length;at=t;points=bad;}}console.log(an.name,max,at.toFixed(2),JSON.stringify(points.slice(0,15)));}
