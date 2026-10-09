"""Check the complete weighted mesh playback; not a substitute for visual QA."""
import json
import pickle
from collections import defaultdict
from pathlib import Path
import numpy as np
from rigkit import Renderer
renderer=Renderer()
parts={}
for name,mesh in renderer.rig['mesh'].items():
    groups=defaultdict(list)
    for i,bindings in enumerate(renderer.binds[name]):
        for bone,local,weight in bindings:groups[bone].append((i,local[0],local[1],weight))
    parts[name]=(len(mesh['world']),np.array(mesh['tris']).reshape(-1,3),
        {b:np.array(values) for b,values in groups.items()})
def vertices(part,world):
    n,_,groups=part; points=np.zeros((n,2))
    for bone,values in groups.items():
        ids=values[:,0].astype(int)
        local=np.column_stack([values[:,1:3],np.ones(len(values))])
        np.add.at(points,ids,(local@world[bone][:2,:].T)*values[:,3,None])
    return points
def area(points,tri):
    a,b,c=points[tri[:,0]],points[tri[:,1]],points[tri[:,2]]
    return (b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0])
setup=renderer.sk.world({})
baseline={n:area(vertices(p,setup),p[1]) for n,p in parts.items()}
frames=pickle.load(open('out/frames.pkl','rb')); failures=[]; count=0
for clip,values in frames.items():
    for index,frame in enumerate(values):
        world=renderer.sk.world(frame['pose']);count+=1
        for name,part in parts.items():
            current=area(vertices(part,world),part[1]); base=baseline[name]
            flips=np.where((current*base<-1e-5)&(abs(base)>1e-4))[0]
            if len(flips):failures.append({'clip':clip,'frame':index,'part':name,'flips':int(len(flips))})
report={'frames':count,'parts':len(parts),'failures':failures}
def difference(first,last):
    a=renderer.sk.world(first['pose']);b=renderer.sk.world(last['pose'])
    return max(float(np.linalg.norm(vertices(part,a)-vertices(part,b),axis=1).max())
               for part in parts.values())
closures={name:difference(values[-1],frames['idle_loop'][0])
          for name,values in frames.items() if name not in ('die',)}
closures['die_to_revive']=difference(frames['die'][-1],frames['revive'][0])
report['closure_error_source_pixels']=closures
assert all(value<1e-5 for value in closures.values()),closures
assert all(abs(sum(w for _,w in vertex)-1)<1e-6
           for mesh in renderer.rig['mesh'].values() for vertex in mesh['wts'])
Path('out/mesh-review.json').write_text(json.dumps(report,indent=2))
assert not failures, failures[:5]
print(f'Weighted mesh review: PASS, {count} frames, no inversions; closed loops, recovery and revival.')
