"""Check continuous painted-mesh motion, not just skeleton JSON syntax."""
from pathlib import Path
import json,pickle,sys
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'CaveMawRig'))
from rigkit import Skel,S
rig=json.loads((HERE/'out/rig_static.json').read_text('utf-8'))
frames=pickle.loads((HERE/'out/frames.pkl').read_bytes())
meta=json.loads((HERE/'parts/meta.json').read_text('utf-8'))
sk=Skel(rig['bones']);bpos={b['name']:b['pos'] for b in rig['bones']}
meshes={}
for name,m in rig['mesh'].items():
    local=[]
    for point,row in zip(m['world'],m['wts']):
        assert abs(sum(w for _,w in row)-1)<.001,'Non-normalized weights'
        local.append([(b,np.array(S(point))-np.array(S(bpos[b])),w) for b,w in row])
    tri=np.array(m['tris']).reshape(-1,3)
    base=np.array([S(p) for p in m['world']])
    def area(v):
        d=v[tri[:,1]]-v[tri[:,0]];e=v[tri[:,2]]-v[tri[:,0]]
        return d[:,0]*e[:,1]-d[:,1]*e[:,0]
    a0=area(base)
    uv=np.array(m['uvs']);al=np.array(Image.open(HERE/'parts'/(name+'.png')))[...,3]
    at=uv[tri].mean(axis=1)*np.array([al.shape[1]-1,al.shape[0]-1])
    visible=(al[np.clip(at[:,1].astype(int),0,al.shape[0]-1),np.clip(at[:,0].astype(int),0,al.shape[1]-1)]>150)&(abs(a0)>5)
    ids=[];bind=[];bone_ids=[];ws=[]
    for i,row in enumerate(local):
        for bone,p,w in row:
            ids.append(i);bind.append([*p,1]);bone_ids.append(sk.idx[bone]);ws.append(w)
    meshes[name]=(np.array(ids),np.array(bind),np.array(bone_ids),np.array(ws),len(local),tri,a0,visible)
report={};problems=[]
for clip,sequence in frames.items():
    smallest=1.;flips=0;bad=[];xmin=ymin=float('inf');xmax=ymax=-float('inf')
    for f in sequence:
        if f['tint'][3]<.08:continue
        matrices=sk.world(f['pose'])
        bank=np.array([matrices[b['name']] for b in rig['bones']])
        for name,(ids,bind,bone_ids,ws,n,tri,a0,visible) in meshes.items():
            transformed=np.einsum('nij,nj->ni',bank[bone_ids],bind)[:,:2]*ws[:,None]
            v=np.zeros((n,2));np.add.at(v,ids,transformed)
            d=v[tri[:,1]]-v[tri[:,0]];e=v[tri[:,2]]-v[tri[:,0]]
            ratio=(d[:,0]*e[:,1]-d[:,1]*e[:,0])/np.where(abs(a0)>.001,a0,1)
            if visible.any():smallest=min(smallest,float(ratio[visible].min()))
            count=int(np.count_nonzero((ratio<0)&visible));flips+=count
            if count and len(bad)<8:
                which=np.flatnonzero((ratio<0)&visible)[0]
                centre=np.array(rig['mesh'][name]['world'])[tri[which]].mean(axis=0)
                bad.append({'part':name,'t':f['t'],'triangles':count,'first_painted_centroid':centre.tolist()})
            xmin=min(xmin,float(v[:,0].min()));xmax=max(xmax,float(v[:,0].max()))
            ymin=min(ymin,float(v[:,1].min()));ymax=max(ymax,float(v[:,1].max()))
    if flips:problems.append(clip+': visible triangle reversal')
    report[clip]={'frames':len(sequence),'visible_triangle_reversals':flips,
                  'minimum_area_ratio':round(smallest,4),'examples':bad,
                  'bounds_in_source_units':[round(v,2) for v in [xmin,ymin,xmax,ymax]]}
first,last=frames['idle_loop'][0]['pose'],frames['idle_loop'][-1]['pose']
assert first==last,'Idle loop is not closed'
out=HERE.parents[1]/'build/fleeting_echo/animation-polish/motion-check.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'passed':not problems,'bones':len(rig['bones']),'clips':report,'problems':problems},indent=2),'utf-8')
print(json.dumps(report,indent=2))
if problems:raise SystemExit('; '.join(problems))
print('Continuous painted-mesh motion: PASS')
