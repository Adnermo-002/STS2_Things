"""Continuous body meshes, independently bending stalks, planted belly waves.

All input geometry is painted raster art. Binding rules vary with each anatomy.
The shell is rigid and attaches to the same mantle bone at runtime.
"""
from pathlib import Path
import json,math
from functools import lru_cache
import numpy as np
from PIL import Image

NAME=Path.cwd().name
SPEC={
 'crystal_snail':dict(origin=(765,906),head=(350,718),neck=(483,804),mantle=(807,753),tail=(1265,873),
    shell=(880,520),foot=(420,1370,886),
    stalks=[[(283,673),(255,630),(211,586),(155,563)],
            [(394,672),(374,612),(355,552),(316,524)]]),
 'slime_snail':dict(origin=(792,888),head=(325,425),neck=(434,605),mantle=(825,754),tail=(1360,755),
    shell=(800,605),foot=(369,1320,863),
    stalks=[[(307,362),(293,300),(273,233),(218,159)],
            [(392,367),(431,318),(480,296),(535,324),(574,392)]],
    drool=[[(211,449),(204,489),(188,538)],[(229,462),(229,506),(227,551)],[(245,488),(252,548),(257,610)]]),
 'rock_snail':dict(origin=(800,853),head=(346,626),neck=(494,706),mantle=(858,703),tail=(1355,801),
    shell=(934,519),foot=(297,1400,826),
    stalks=[[(253,568),(221,527),(181,485),(139,468)],
            [(390,602),(375,549),(347,497),(312,477)]])}
C=SPEC[NAME];ORIGIN=C['origin'];CHAINS={}
META=json.loads(Path('parts/meta.json').read_text('utf-8'))
ORDER=([f'drool_{i}' for i in range(3)] if NAME=='slime_snail' else [])+['body']
ORDER+=([f'eye_{i}' for i in range(2)] if NAME!='slime_snail' else [])
ORDER+=(['shell'] if 'shell' in META else [])
SPACING={'body':13,'shell':48,'eye_0':8,'eye_1':8,'drool_0':10,'drool_1':10,'drool_2':10}
SKIN={n:[('root',(0,0),(0,0))] for n in ORDER}
SKIN['shell']=[('shell',(0,0),(0,0))]
VIEW=dict(scale=.35,W=620,H=410,ox=320,oy=375)

def smooth(v):
    v=np.clip(v,0,1);return v*v*(3-2*v)

def s(p):return np.array([p[0]-ORIGIN[0],ORIGIN[1]-p[1]],float)

BONES=[('root',None,ORIGIN),('body','root',C['mantle']),
       ('mantle','body',C['mantle']),('neck','body',C['neck']),
       ('head','body',C['head']),('tail','body',C['tail']),
       ('throat','body',tuple(np.asarray(C['head'])*.38+np.asarray(C['neck'])*.62)),
       ('shell_mount','root',C['shell']),('shell','shell_mount',C['shell'])]
FOOT=np.linspace(C['foot'][0],C['foot'][1],11)
BONES += [(f'foot_{i}','root',(float(x),C['foot'][2])) for i,x in enumerate(FOOT)]
RIBS=np.linspace(C['neck'][0]+100,C['tail'][0]-70,5)
BONES += [(f'rib_{i}','body',(float(x),C['foot'][2]-100)) for i,x in enumerate(RIBS)]

def subdivide(path,count):
    p=np.asarray(path,float);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    samples=np.linspace(0,distance[-1],count)
    return np.c_[np.interp(samples,distance,p[:,0]),np.interp(samples,distance,p[:,1])]

CURVES={f'stalk_{i}':subdivide(p,7 if NAME=='slime_snail' and i==1 else 6) for i,p in enumerate(C['stalks'])}
CURVES.update({f'drool_{i}':subdivide(p,5) for i,p in enumerate(C.get('drool',[]))})
for name,points in CURVES.items():
    BONES.append((name+'_socket','root',tuple(points[0])))
    BONES += [(f'{name}_{i}',name+'_socket',tuple(p)) for i,p in enumerate(points)]
    if name.startswith('stalk'):
        eye=f'eye_{name[-1]}'
        m=META.get(eye)
        center=(m['x']+m['w']/2,m['y']+m['h']/2) if m else tuple(points[-1])
        BONES.append((name+'_lid',f'{name}_{len(points)-1}',center))
BONES += [('mouth','head',(214,446) if NAME=='slime_snail' else (260,C['head'][1]+20))]
BPOS={n:np.asarray(p,float) for n,_,p in BONES}
SHELL_POINTS=None
if 'shell' in META:
    m=META['shell'];alpha=np.asarray(Image.open('parts/shell.png'))[...,3]
    boundary=[]
    for y in range(0,alpha.shape[0],7):
        xs=np.where(alpha[y]>128)[0]
        if len(xs):boundary.extend([(xs[0]+m['x'],y+m['y']),(xs[-1]+m['x'],y+m['y'])])
    for x in range(0,alpha.shape[1],7):
        ys=np.where(alpha[:,x]>128)[0]
        if len(ys):boundary.extend([(x+m['x'],ys[0]+m['y']),(x+m['x'],ys[-1]+m['y'])])
    SHELL_POINTS=np.array([np.r_[s(p)-s(C['shell']),1] for p in boundary])

def normal(row):
    row={n:float(v) for n,v in row.items() if v>.0005};total=sum(row.values())
    return [(n,v/total) for n,v in row.items()]

def body_weights(points):
    out=[]
    names=['head','neck','mantle','tail','throat',*[f'rib_{i}' for i in range(5)]]
    centers=np.array([BPOS[n] for n in names]);radii=np.array([110,140,195,158,83,*([95]*5)])
    priorities=np.array([3.2,1.05,.95,1.6,1.1,*([.7]*5)])
    for p in np.asarray(points):
        energy=np.sum((centers-p)**2,axis=1)/(2*radii**2)
        row=np.exp(-(energy-energy.min()))*priorities;row/=row.sum()
        sole=float(smooth((p[1]-(C['foot'][2]-114))/114))*.985
        weights={n:v*(1-sole) for n,v in zip(names,row)}
        i=int(np.clip(np.searchsorted(FOOT,p[0])-1,0,len(FOOT)-2))
        u=float(smooth((p[0]-FOOT[i])/(FOOT[i+1]-FOOT[i])))
        weights[f'foot_{i}']=sole*(1-u);weights[f'foot_{i+1}']=sole*u
        out.append(normal(weights))
    return out

def project(points,p):
    a=points[:-1];d=points[1:]-a
    t=np.clip(np.sum((p-a)*d,axis=1)/np.sum(d*d,axis=1),0,1)
    v=np.sum((a+t[:,None]*d-p)**2,axis=1);i=int(np.argmin(v))
    return i,float(t[i]),float(v[i])

def weights(name,points):
    if name=='shell':return [[('shell',1.)] for _ in points]
    if name.startswith('eye_'):return [[(f'stalk_{name[-1]}_lid',1.)] for _ in points]
    if name.startswith('drool_'):
        out=[]
        for p in points:
            i,t,_=project(CURVES[name],p);u=float(smooth(t))
            out.append(normal({f'{name}_{i}':1-u,f'{name}_{i+1}':u}))
        return out
    out=[]
    for p,base in zip(points,body_weights(points)):
        candidates=[]
        for curve,path in CURVES.items():
            i,t,d2=project(path,p)
            if curve.startswith('stalk'):
                if NAME=='slime_snail':
                    influence=(smooth((385-p[1])/70) if curve=='stalk_0' else
                        smooth((p[0]-385)/75)*smooth((500-p[1])/55)*(1-smooth((math.sqrt(d2)-65)/60)))
                else:influence=smooth((path[0,1]-p[1])/50)
            else:continue
            candidates.append((d2,curve,i,t,float(influence)))
        if not candidates:out.append(base);continue
        _,curve,i,t,mix=min(candidates)
        if mix<=.001:out.append(base);continue
        path=CURVES[curve];u=float(smooth(t))
        row={n:v*(1-mix) for n,v in base}
        for j,v in ((i,1-u),(i+1,u)):
            n=f'{curve}_{j}'
            row[n]=row.get(n,0)+mix*v
        if NAME!='slime_snail':
            # The painted eyeball cap and its separate lid must follow exactly
            # the same rigid tip. Blending through the sclera tears at blinks.
            cap_i=min(range(2),key=lambda j:np.linalg.norm(p-CURVES[f'stalk_{j}'][-1]))
            cap_curve=CURVES[f'stalk_{cap_i}']
            cap=float(1-smooth((np.linalg.norm(p-cap_curve[-1])-49)/32))
            if cap>0:
                row={n:w*(1-cap) for n,w in row.items()}
                n=f'stalk_{cap_i}_{len(cap_curve)-1}';row[n]=row.get(n,0)+cap
        out.append(normal(row))
    return out

@lru_cache(None)
def binding(name):
    p=BPOS[name];samples=[p,p+(-8,0),p+(8,0)]
    return [[(b,np.r_[s(q)-s(BPOS[b]),1],w) for b,w in row]
        for q,row in zip(samples,body_weights(samples))]

def post(pose,world,frame,sk):
    # A hard shell rides on soft tissue without inheriting its squash/stretch.
    p=C['mantle'];samples=[p,(p[0]-12,p[1]),(p[0]+12,p[1])]
    rows=body_weights(samples);positions=[]
    for q,row in zip(samples,rows):
        positions.append(sum(w*(world[b]@np.r_[s(q)-s(BPOS[b]),1])[:2] for b,w in row))
    pos,left,right=positions;angle=math.atan2(*(right-left)[::-1])
    c,si=math.cos(angle),math.sin(angle)
    pos+=np.array([[c,-si],[si,c]])@(s(C['shell'])-s(p))
    host=world['root'];local=(np.linalg.inv(host)@np.r_[pos,1])[:2]-sk.local['shell_mount']
    local_angle=math.degrees(angle-math.atan2(host[1,0],host[0,0]))
    pose['shell_mount']=((local_angle+180)%360-180,float(local[0]),float(local[1]),1,1)
    if SHELL_POINTS is not None:
        minimum=float((SHELL_POINTS@sk.world(pose)['shell'].T)[:,1].min())
        if minimum<2:
            r,x,y,sx,sy=pose['shell_mount'];pose['shell_mount']=(r,x,y+2-minimum,sx,sy)
    for name,path in CURVES.items():
        socket=name+'_socket'
        pos,left,right=[sum(w*(world[b]@q)[:2] for b,q,w in row) for row in binding(socket)]
        host=world[sk.parent[socket]]
        local=(np.linalg.inv(host)@np.r_[pos,1])[:2]-sk.local[socket]
        angle=math.degrees(math.atan2(*(right-left)[::-1])-math.atan2(host[1,0],host[0,0]))
        pose[socket]=((angle+180)%360-180,float(local[0]),float(local[1]),1,1)
        params=frame.extra.get('curves',{}).get(name,{})
        shorten=1-float(np.clip(params.get('shorten',0),0,.26))
        pose[socket]=((angle+180)%360-180,float(local[0]),float(local[1]),shorten,shorten)
        rest=np.array([s(p) for p in path]);curve=rest.copy()
        for i in range(len(path)):
            u=i/(len(path)-1);g=float(smooth(u));phase=params.get('phase',0)
            wave=params.get('wave',0)*math.sin(phase-u*3.2)*g
            curve[i]+=np.array([params.get('sway',0)*g+params.get('bend',0)*math.sin(math.pi*u)+wave,
                               params.get('pull',0)*g+params.get('curl',0)*u*u])
        # Keep a swaying tip from collapsing or stretching like rubber.
        for i in range(1,len(path)):
            rest_length=np.linalg.norm(rest[i]-rest[i-1]);delta=curve[i]-curve[i-1]
            length=np.linalg.norm(delta)
            if length>1e-6:curve[i]=curve[i-1]+delta/length*np.clip(length,.90*rest_length,1.10*rest_length)
        for i in range(len(path)):
            a=max(0,i-1);b=min(len(path)-1,i+1);v0=rest[b]-rest[a];v1=curve[b]-curve[a]
            r=math.degrees(math.atan2(v1[1],v1[0])-math.atan2(v0[1],v0[0]))
            r=((r+180)%360-180)*float(smooth(i/(len(path)-1)/.4))
            d=curve[i]-rest[0]-sk.local[f'{name}_{i}']
            pose[f'{name}_{i}']=(r,float(d[0]),float(d[1]),1,1)
