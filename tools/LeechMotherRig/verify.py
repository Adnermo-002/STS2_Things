"""Dense weighted-mesh checks for sleep/wake continuity and heavy-body animations."""
import json,pickle
from pathlib import Path
import numpy as np
from rigkit import Renderer
renderer=Renderer();parts=renderer.rig['mesh'];frames=pickle.load(open('out/frames.pkl','rb'))
groups={}
for name,bindings in renderer.binds.items():
    values={}
    for i,vertex in enumerate(bindings):
        for bone,local,weight in vertex:values.setdefault(bone,[]).append((i,local[0],local[1],weight))
    groups[name]={b:np.array(v) for b,v in values.items()}
def vertices(name,pose):
    world=renderer.sk.world(pose)
    result=np.zeros((len(renderer.binds[name]),2))
    for bone,values in groups[name].items():
        local=np.column_stack([values[:,1:3],np.ones(len(values))])
        np.add.at(result,values[:,0].astype(int),(local@world[bone][:2,:].T)*values[:,3,None])
    return result
def area(v,tri):
    a,b,c=v[tri[:,0]],v[tri[:,1]],v[tri[:,2]]
    return(b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0])
baseline={};triangles={}
for name,mesh in parts.items():
    triangles[name]=np.array(mesh['tris']).reshape(-1,3)
    baseline[name]=area(vertices(name,{}),triangles[name])
flips=[];count=0
for clip,values in frames.items():
    for i,frame in enumerate(values):
        count+=1
        for name in parts:
            v=vertices(name,frame['pose']);assert np.isfinite(v).all()
            bad=np.where(area(v,triangles[name])*baseline[name]<-1e-5)[0]
            if len(bad):flips.append((clip,i,name,int(len(bad)),np.array(parts[name]['world'])[triangles[name][bad]].mean(axis=1).tolist()))
def diff(a,b):return max(float(np.linalg.norm(vertices(name,a)-vertices(name,b),axis=1).max()) for name in parts)
closures={name:diff(values[-1]['pose'],frames['idle_loop'][0]['pose']) for name,values in frames.items()
          if name not in ('sleep_loop','retreat','die')}
closures['sleep_loop']=diff(frames['sleep_loop'][0]['pose'],frames['sleep_loop'][-1]['pose'])
closures['sleep_to_wake']=diff(frames['sleep_loop'][0]['pose'],frames['wake_up'][0]['pose'])
Path('out/mesh-failures.json').write_text(json.dumps(flips,indent=2))
assert not flips,flips[:3]
assert max(closures.values())<1e-5,closures
assert frames['sleep_loop'][0]['glow']['lid_far']==1 and frames['wake_up'][-1]['glow']['lid_far']==0
report={'passed':True,'bones':len(renderer.sk.bones),'frames':count,'mesh_flips':0,'closures':closures}
Path('out/verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
