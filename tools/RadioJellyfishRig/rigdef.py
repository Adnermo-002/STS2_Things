"""A buoyant bell with six independently skinned spline ribbons and two aerials."""
import json,math
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image

NAME='radio_jellyfish'
ORIGIN=(576,1364)
VIEW=dict(scale=.36,W=650,H=620,ox=325,oy=574)
PARTS=Path(__file__).resolve().parent/'parts'
META=json.loads((PARTS/'meta.json').read_text('utf-8'))
ORDER=['tentacle_1','tentacle_3','tentacle_5','tentacle_0','tentacle_2','tentacle_4',
       'antenna_right','antenna_left','bell','channel_0','channel_1','eye_0','eye_1']
SPACING={n:17 for n in ORDER}
SPACING.update(bell=19,antenna_left=13,antenna_right=13,eye_0=5,eye_1=5,channel_0=14,channel_1=14)
CHAINS={}


def smooth(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)


def s(p):return np.array([p[0]-ORIGIN[0],ORIGIN[1]-p[1]],float)


def centre(name):
    m=META[name]
    return (m['x']+m['w']/2,m['y']+m['h']/2)


CURVES={}
for index in range(6):
    name=f'tentacle_{index}';m=META[name]
    alpha=np.asarray(Image.open(PARTS/f'{name}.png'))[...,3]
    rows=np.arange(alpha.shape[0])+m['y']
    xs=[]
    for row in alpha:
        values=np.where(row>80)[0]
        xs.append(float(values.mean()+m['x']) if len(values) else np.nan)
    valid=np.isfinite(xs)
    y=np.linspace(755,m['y']+m['h']-10,9)
    x=np.interp(y,rows[valid],np.asarray(xs)[valid])
    CURVES[name]=np.c_[x,y]
CURVES['antenna_left']=np.array([(420,309),(401,267),(397,208),(370,151),(330,110),(275,98)],float)
CURVES['antenna_right']=np.array([(860,348),(882,292),(903,243),(938,221),(987,232),(1043,269)],float)

BODY={
    'dome':(594,336),'face':(482,496),'flank_left':(292,489),
    'flank_right':(889,514),'skirt_middle':(594,705),'mouth':(441,604),
}
for i in range(6):BODY[f'skirt_{i}']=tuple(CURVES[f'tentacle_{i}'][0]-(0,30))
BONES=[('root',None,ORIGIN),('mantle','root',(594,521))]
BONES += [(name,'mantle',p) for name,p in BODY.items()]
for name,points in CURVES.items():
    BONES.append((name+'_socket','root',tuple(points[0])))
    BONES += [(f'{name}_{i}',name+'_socket',tuple(p)) for i,p in enumerate(points)]
FEATURES={name:centre(name) for name in ('channel_0','channel_1','eye_0','eye_1')}
for name,p in FEATURES.items():
    BONES.append((name,'root',p))
    if name.startswith('eye_'):BONES.append((name+'_lid',name,(p[0],p[1]+META[name]['h']*.35)))
BONES += [('voice','face',(458,542)),('shield_vfx','mantle',(578,493))]
BPOS={name:np.asarray(p,float) for name,_,p in BONES}
SKIN={name:[('root',(0,0),(0,0))] for name in ORDER}


def normalized(row):
    row={k:v for k,v in row.items() if v>.0001};total=sum(row.values())
    return [(k,v/total) for k,v in row.items()]


def body_weights(points):
    names=['mantle',*BODY]
    anchors=np.asarray([BPOS[n] for n in names])
    p=np.asarray(points)
    d2=np.sum((p[:,None,:]-anchors[None,:,:])**2,axis=2)
    radius=np.array([200,175,142,138,145,120,72,*([73]*6)])
    energy=d2/(2*radius[None,:]**2)
    weights=np.exp(-(energy-energy.min(axis=1,keepdims=True)))
    weights[:,0]*=.45
    weights/=weights.sum(axis=1,keepdims=True)
    return [normalized({name:float(v) for name,v in zip(names,row)}) for row in weights]


def curve_coordinate(name,point):
    points=CURVES[name]
    if name.startswith('tentacle_'):
        value=float(np.clip(point[1],points[0,1],points[-1,1]))
        i=min(len(points)-2,max(0,np.searchsorted(points[:,1],value,side='right')-1))
        u=(value-points[i,1])/(points[i+1,1]-points[i,1])
        return i,float(u)
    a=points[:-1];delta=points[1:]-a
    t=np.clip(np.sum((point-a)*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
    closest=a+t[:,None]*delta
    i=int(np.argmin(np.sum((closest-point)**2,axis=1)))
    return i,float(t[i])


def weights(name,points):
    p=np.asarray(points)
    if name in FEATURES:
        bone=name+'_lid' if name.startswith('eye_') else name
        return [[(bone,1.)] for _ in p]
    if name in CURVES:
        out=[]
        for point in p:
            i,t=curve_coordinate(name,point);u=float(smooth(t))
            out.append(normalized({f'{name}_{i}':1-u,f'{name}_{i+1}':u}))
        return out
    return body_weights(p)


@lru_cache(maxsize=None)
def binding(name):
    p=BPOS[name];samples=[p,p+(-12,0),p+(12,0)]
    return [[(b,np.r_[s(q)-s(BPOS[b]),1],w) for b,w in row]
            for q,row in zip(samples,body_weights(samples))]


def follow_surface(name,pose,world,sk,rotate=True):
    pos,left,right=[sum(w*(world[b]@local)[:2] for b,local,w in row) for row in binding(name)]
    host=world[sk.parent[name]]
    local=(np.linalg.inv(host)@np.r_[pos,1])[:2]-sk.local[name]
    r,x,y,sx,sy=pose.get(name,(0,0,0,1,1))
    angle=0
    if rotate:
        angle=math.degrees(math.atan2(*(right-left)[::-1])-math.atan2(host[1,0],host[0,0]))
        angle=(angle+180)%360-180
    pose[name]=(angle+r,float(local[0])+x,float(local[1])+y,sx,sy)


def post(pose,world,frame,sk):
    for name in FEATURES:follow_surface(name,pose,world,sk)
    for name,points in CURVES.items():
        socket=name+'_socket'
        follow_surface(socket,pose,world,sk,name.startswith('antenna'))
        params=frame.extra.get('curves',{}).get(name,{})
        rest=np.asarray([s(p) for p in points]);curve=rest.copy()
        reach=min(1.,np.linalg.norm(np.diff(rest,axis=0),axis=1).sum()/440.) if name.startswith('tentacle') else 1.
        for i in range(len(points)):
            u=i/(len(points)-1)
            # Keep the covered root straight. Bending starts below the skirt,
            # so a broad sweep cannot rotate a square texture edge into view.
            flex=float(np.clip((u-.125)/.875,0,1));g=float(smooth(flex))
            phase=params.get('phase',0)
            reference=params.get('reference_phase',0)
            wave=params.get('wave',0)*(math.sin(phase-u*4.2)-math.sin(reference-u*4.2))
            arch=math.sin(math.pi*flex)*float(smooth(flex/.35))
            curve[i]+=reach*np.array([params.get('swing',0)*g+params.get('bend',0)*arch+wave*g,
                                params.get('pull',0)*g+params.get('curl',0)*g**3
                                +params.get('lift',0)*arch])
        for i in range(len(points)):
            a=max(0,i-1);b=min(len(points)-1,i+1)
            v0=rest[b]-rest[a];v1=curve[b]-curve[a]
            angle=math.degrees(math.atan2(v1[1],v1[0])-math.atan2(v0[1],v0[0]))
            angle=(angle+180)%360-180
            angle*=float(smooth((i/(len(points)-1))/.3))
            delta=curve[i]-rest[0]-sk.local[f'{name}_{i}']
            volume=1+params.get('bulk',0)*.025
            pose[f'{name}_{i}']=(angle,float(delta[0]),float(delta[1]),volume,1)
