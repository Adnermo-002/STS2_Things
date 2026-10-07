"""Authoring diagnostic: inspect visible mesh triangles throughout exported clips.

Reads CPU skeleton samples; does not launch a native runtime or gameplay test.
"""
import os,sys,pickle,json
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
name=sys.argv[1];os.chdir(HERE/name);sys.path.insert(0,str(HERE/name))
from rigkit import load_rig,S
rig,sk=load_rig();frames=pickle.load(open('out/frames.pkl','rb'))
meta=json.load(open('parts/meta.json'))
parts={}
for layer,m in rig['mesh'].items():
    p=np.asarray(m['world']);tri=np.asarray(m['tris']).reshape(-1,3)
    uv=np.asarray(m['uvs']);alpha=np.asarray(Image.open(f'parts/{layer}.png'))[...,3]
    centroid=uv[tri].mean(axis=1)
    px=np.clip((centroid[:,0]*alpha.shape[1]).astype(int),0,alpha.shape[1]-1)
    py=np.clip((centroid[:,1]*alpha.shape[0]).astype(int),0,alpha.shape[0]-1)
    visible=alpha[py,px]>200
    tri=tri[visible];data=[]
    for j,bone in enumerate(rig['bones']):
        indices=[];weights=[]
        for i,row in enumerate(m['wts']):
            for b,w in row:
                if b==bone['name']:indices.append(i);weights.append(w)
        if not indices:continue
        q=np.array([S(point) for point in p[indices]])-S(bone['pos'])
        data.append((bone['name'],np.array(indices),np.c_[q,np.ones(len(q))],np.array(weights)))
    parts[layer]=(tri,data,len(p),p[tri].mean(axis=1))
report={'name':name,'clips':{},'method':'60 Hz offline weighted-mesh sample; opaque triangle centres only'}
for clip,sequence in frames.items():
    bad={};minimum=1e9;worst=None
    for frame in sequence:
        world=sk.world(frame['pose'])
        for layer,(tri,data,size,centres) in parts.items():
            v=np.zeros((size,2))
            for b,index,q,w in data:v[index]+=((q@world[b].T)[:,:2])*w[:,None]
            a,b,c=v[tri[:,0]],v[tri[:,1]],v[tri[:,2]]
            # Source meshes are built clockwise after the Spine Y flip.
            area=-((b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0]))
            if len(area) and area.min()<minimum:
                minimum=float(area.min());worst=(layer,frame['t'],centres[np.argmin(area)].round(2).tolist())
            if np.any(area<=0):bad[layer]=bad.get(layer,0)+int(np.sum(area<=0))
    report['clips'][clip]=dict(flipped_triangle_samples=bad,minimum_signed_double_area=round(minimum,3),minimum_at=worst)
dest=ROOT/'build/depths_snails_polish';dest.mkdir(exist_ok=True)
(dest/f'{name}-mesh-review.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report,indent=2),flush=True)
