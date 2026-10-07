"""Continuous floor contour, surface-follow details and a nine-control tongue cage.

All constraints are baked into ordinary Spine transforms. The shipped rig does
not depend on this authoring code or a custom runtime solver.
"""
import json
import math
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image

NAME='cave_maw'
ORIGIN=(900,755)
VIEW=dict(scale=.40,W=820,H=410,ox=412,oy=376)
ORDER=['cavity','tongue','tooth_back_0','tooth_back_1','tooth_back_2',
       'tooth_front_0','tooth_front_1','rim','eye_far','eye_near']
SPACING={n:14 for n in ORDER}
SPACING.update(rim=14,cavity=23,tongue=11,eye_far=6,eye_near=6,
               tooth_back_0=8,tooth_back_1=8,tooth_back_2=8,tooth_front_0=8,tooth_front_1=8)
CHAINS={}
BACK=[(356,448),(547,362),(758,324),(1001,330),(1223,405),(1431,494)]
FRONT=[(287,603),(477,636),(700,683),(900,695),(1170,671),(1376,610)]
BONES=[('root',None,ORIGIN),('throat','root',(880,520)),
       ('throat_up','throat',(891,409)),('throat_low','throat',(877,603)),
       ('back_base','root',(906,415)),('front_base','root',(878,704))]
for prefix,points in [('back',BACK),('front',FRONT)]:
    BONES += [(f'{prefix}_{i}',prefix+'_base',point) for i,point in enumerate(points)]
BONES += [('cheek_left','root',(239,537)),('cheek_left_fold','cheek_left',(300,499)),
          ('cheek_right','root',(1431,583)),('cheek_right_fold','cheek_right',(1474,488))]
# Siblings on a baked curve, rather than cumulative chain rotations. Reach is
# distributed along the full tongue instead of translating one short segment.
TONGUE=[(1208,596),(1112,588),(1010,585),(910,585),(811,572),
        (715,530),(632,484),(550,463),(474,479)]
BONES.append(('tongue_socket','root',TONGUE[0]))
for i,point in enumerate(TONGUE):
    BONES.append((f'tongue_{i}','tongue_socket',point))
EDGES={'tongue_edge_a':(804,602),'tongue_edge_b':(644,509)}
BONES += [(name,'tongue_socket',point) for name,point in EDGES.items()]
PLATES={'plate_back':((653,293),'back_1'),'plate_left':((307,425),'cheek_left'),
        'plate_right':((1495,554),'cheek_right'),'plate_front':((996,691),'front_3')}
for name,(point,parent) in PLATES.items():BONES.append((name,parent,point))
BROWS={'brow_far':(1042,274),'brow_near':(1220,316)}
BONES += [(name,'back_base',point) for name,point in BROWS.items()]
EYES={'eye_far':((1042,286),'brow_far'),'eye_near':((1220,329),'brow_near')}
for name,(point,parent) in EYES.items():
    BONES += [(name,parent,point),(name+'_lid',name,(point[0],point[1]+17))]
TEETH={'tooth_back_0':((800,361),'back_base'),'tooth_back_1':((900,371),'back_base'),
       'tooth_back_2':((1013,395),'back_base'),'tooth_front_0':((369,581),'front_base'),
       'tooth_front_1':((530,624),'front_base')}
for name,(point,parent) in TEETH.items():BONES.append((name,parent,point))
BONES += [('mouth_vfx','throat',(869,524)),('tongue_tip_vfx','tongue_8',(461,472))]
SKIN={name:[('root',(0,0),(0,0))] for name in ORDER}
BPOS={name:np.asarray(point,float) for name,_,point in BONES}

parts=Path(__file__).resolve().parent/'parts'
meta=json.loads((parts/'meta.json').read_text('utf-8'))
alpha=np.asarray(Image.open(parts/'rim.png'))[...,3]
occupied=alpha>24
columns=np.where(occupied.any(axis=0))[0]
bottom=np.max(np.where(occupied,np.arange(alpha.shape[0])[:,None],-1),axis=0)
floor_x=np.arange(alpha.shape[1])+meta['rim']['x']
floor_y=np.interp(np.arange(alpha.shape[1]),columns,bottom[columns])+meta['rim']['y']


def smooth(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)


def s(point):
    return np.asarray([point[0]-ORIGIN[0],ORIGIN[1]-point[1]],float)


def field(points,names,anchors,radius):
    p=np.asarray(points);a=np.asarray(anchors)
    d2=np.sum((p[:,None,:]-a[None,:,:])**2,axis=2)
    w=np.exp(-(d2-d2.min(axis=1,keepdims=True))/(2*radius*radius))
    w/=w.sum(axis=1,keepdims=True)
    return [{n:float(v) for n,v in zip(names,row) if v>.0001} for row in w]


def normalized(row):
    row={n:v for n,v in row.items() if v>.0001}
    total=sum(row.values())
    return [(n,v/total) for n,v in row.items()]


def blend(row,name,weight):
    for n in list(row):row[n]*=1-weight
    row[name]=row.get(name,0)+weight


def ring(points,with_brows=True):
    names=[f'back_{i}' for i in range(6)]+[f'front_{i}' for i in range(6)]+['cheek_left','cheek_right']
    anchors=BACK+FRONT+[(239,537),(1431,583)]
    out=field(points,names,anchors,100)
    for point,row in zip(points,out):
        floor=float(np.interp(point[0],floor_x,floor_y))
        # Follow the entire curved lower contour, including the side corners.
        pin=float(smooth((point[1]-(floor-49))/42))
        blend(row,'root',pin)
        for name,(anchor,_) in PLATES.items():
            weight=.24*math.exp(-np.sum(((np.asarray(point)-anchor)/(110,65))**2))*(1-pin)
            blend(row,name,weight)
        for side,anchor in [('left',(300,499)),('right',(1474,488))]:
            weight=.18*math.exp(-np.sum(((np.asarray(point)-anchor)/(75,85))**2))*(1-pin)
            blend(row,f'cheek_{side}_fold',weight)
        if with_brows:
            for name,anchor in BROWS.items():
                weight=.66*math.exp(-np.sum(((np.asarray(point)-anchor)/(67,39))**2)*1.7)
                blend(row,name,weight)
    return out


def weights(name,points):
    p=np.asarray(points)
    if name in TEETH:return [[(name,1.)] for _ in p]
    if name in EYES:return [[(name+'_lid',1.)] for _ in p]
    if name=='tongue':
        # A continuous longitudinal coordinate never mixes opposite sides of
        # the painted curl. Each cross-section follows adjacent controls only.
        knots=-np.asarray(TONGUE,float)[:,0]
        out=[]
        for point in p:
            coordinate=float(np.clip(-point[0],knots[0],knots[-1]))
            i=min(len(knots)-2,max(0,np.searchsorted(knots,coordinate,side='right')-1))
            u=float(smooth((coordinate-knots[i])/(knots[i+1]-knots[i])))
            row={f'tongue_{i}':1-u,f'tongue_{i+1}':u}
            for edge,anchor in EDGES.items():
                w=.10*math.exp(-np.sum(((point-anchor)/(93,46))**2))
                blend(row,edge,w)
            out.append(normalized(row))
        return out
    out=ring(p)
    if name=='cavity':
        for point,row in zip(p,out):
            interior=.48*math.exp(-np.sum(((point-(880,520))/(370,130))**2))
            for n in list(row):row[n]*=1-interior
            row['throat']=interior*.65
            row['throat_up' if point[1]<520 else 'throat_low']=interior*.35
    return [normalized(row) for row in out]


@lru_cache(maxsize=None)
def surface_bind(name,with_brows):
    anchor=BPOS[name]
    points=[anchor,anchor+(-15,0),anchor+(15,0)]
    return [[(b,np.r_[s(point)-s(BPOS[b]),1.],w) for b,w in normalized(row)]
            for point,row in zip(points,ring(points,with_brows))]


def surface_follow(name,pose,world,sk,with_brows=True):
    samples=[sum(w*(world[b]@local)[:2] for b,local,w in row)
             for row in surface_bind(name,with_brows)]
    target,left,right=samples
    host=world[sk.parent[name]]
    local=(np.linalg.inv(host)@np.r_[target,1.])[:2]-sk.local[name]
    tangent=right-left
    angle=math.atan2(tangent[1],tangent[0])-math.atan2(host[1,0],host[0,0])
    angle=(math.degrees(angle)+180)%360-180
    # A long tongue follows the root's position, not the cheek's skin shear.
    # Inheriting the gum tangent would swing the tip through the upper lip.
    if name=='tongue_socket':angle=0
    r,x,y,sx,sy=pose.get(name,(0,0,0,1,1))
    pose[name]=(angle+r,float(local[0])+x,float(local[1])+y,sx,sy)


def tongue_point(point,params):
    u=float(np.clip((TONGUE[0][0]-point[0])/(TONGUE[0][0]-TONGUE[-1][0]),0,1))
    ease=float(smooth(u))
    reach=params.get('reach',0)
    lift=params.get('lift',0)
    curl=params.get('curl',0)
    phase=params.get('phase',0)
    ripple=params.get('ripple',0)*(math.sin(phase-u*math.tau)-math.sin(-u*math.tau))
    ripple*=math.sin(math.pi*u)**1.5
    return s(point)+(-reach*ease,lift*ease+curl*ease**3+ripple)


def post(pose,world,frame,sk):
    # Rigid details inherit the actual skinned surface rather than the closest
    # lip control. This keeps tooth roots and eye sockets attached under shear.
    for name in BROWS:surface_follow(name,pose,world,sk,False)
    world=sk.world(pose)
    for name in (*TEETH,*EYES,'tongue_socket'):
        surface_follow(name,pose,world,sk)
    params=frame.extra.get('tongue',{})
    rest=np.asarray([s(p) for p in TONGUE])
    curve=np.asarray([tongue_point(p,params) for p in TONGUE])
    socket=s(TONGUE[0])
    rotations=[]
    for i in range(len(TONGUE)):
        a=max(0,i-1);b=min(len(TONGUE)-1,i+1)
        v0=rest[b]-rest[a];v1=curve[b]-curve[a]
        angle=math.degrees(math.atan2(v1[1],v1[0])-math.atan2(v0[1],v0[0]))
        angle=(angle+180)%360-180
        rotations.append(angle)
        delta=curve[i]-socket-np.asarray(sk.local[f'tongue_{i}'])
        u=i/(len(TONGUE)-1)
        volume=1+.025*params.get('bulk',0)-.12*params.get('reach',0)/734*u
        volume*=1-.55*params.get('fold',0)
        pose[f'tongue_{i}']=(angle,float(delta[0]),float(delta[1]),1,volume)
    for name,point in EDGES.items():
        u=float(np.clip((TONGUE[0][0]-point[0])/734,0,1))
        position=tongue_point(point,params)-socket
        position[1]-=params.get('bulk',0)*2.5*math.sin(math.pi*u)
        delta=position-np.asarray(sk.local[name])
        angle=float(np.interp(u,np.linspace(0,1,len(TONGUE)),rotations))
        pose[name]=(angle,float(delta[0]),float(delta[1]),1,1-.55*params.get('fold',0))
