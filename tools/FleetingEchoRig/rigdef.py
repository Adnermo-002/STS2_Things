"""Articulated scapulae, three-joint digits, torso cage and baked hand support."""
import numpy as np
import math
NAME='fleeting_echo'
ORIGIN=(768,964)
VIEW=dict(scale=.36,W=720,H=470,ox=357,oy=426)
ORDER=['upper_left','upper_right','lower_right','body','lower_left','core_top','core','core_mid','core_low']
GLOW_OF={}
CHAINS={}
SPACING={n:12 for n in ORDER}
SPACING.update(body=11,core=6,core_top=6,core_mid=6,core_low=6)
SIGMA={n:39 for n in ORDER};SIGMA['body']=75
BONES=[('root',None,ORIGIN),('torso','root',(770,502)),('chest','torso',(748,372)),
       ('waist','torso',(773,651)),('trail_left','waist',(746,710)),
       ('trail_left_1','trail_left',(755,797)),('trail_left_2','trail_left_1',(820,910)),
       ('trail_right','waist',(837,710)),('trail_right_1','trail_right',(875,790)),
       ('trail_right_2','trail_right_1',(907,893)),
       ('trail_left_3','trail_left_2',(833,947)),('trail_right_3','trail_right_2',(915,928)),
       ('rib_upper_left','chest',(672,435)),('rib_upper_right','chest',(834,435)),
       ('rib_lower_left','torso',(717,560)),('rib_lower_right','torso',(819,559)),
       ('core','chest',(720,419)),('core_top','chest',(727,337)),
       ('core_mid','torso',(732,534)),('core_low','waist',(743,601))]
ARMS={
 'upper_left':[(636,357),(452,374),(269,343),(233,263),(222,169)],
 'upper_right':[(844,383),(1042,433),(1280,447),(1336,373),(1286,280)],
 'lower_left':[(644,472),(533,559),(346,653),(268,755),(320,841)],
 'lower_right':[(864,487),(1007,581),(1176,692),(1263,756),(1259,842)],
}
FINGERS={
 'upper_left':[[(218,172),(176,110),(208,56)],[(230,153),(245,57),(288,36)],[(239,161),(291,112),(331,132)],[(270,215),(298,190),(291,157)]],
 'upper_right':[[(1291,279),(1340,176),(1294,109)],[(1284,274),(1287,169),(1225,139)],[(1276,282),(1202,247),(1197,207)]],
 'lower_left':[[(305,850),(223,880),(197,938)],[(302,859),(270,915),(299,964)],[(332,851),(352,882),(374,938)]],
 'lower_right':[[(1240,840),(1175,864),(1194,919)],[(1260,866),(1273,940),(1217,985)],[(1276,876),(1327,905),(1353,983)]],
}
SKIN={}
ordered=[]
for name in ORDER:
    ordered.append(name)
    if name in ARMS:ordered.extend(name+'_digit'+str(i) for i in range(len(FINGERS[name])))
ORDER=ordered
SPACING.update({n:6 for n in ORDER if '_digit' in n})
for name,points in ARMS.items():
    names=[name+'_'+str(i) for i in range(len(points))]
    host='chest' if name.startswith('upper') else 'torso'
    BONES.append((name+'_socket',host,points[0]))
    for i,(bone,point) in enumerate(zip(names,points)):
        BONES.append((bone,name+'_socket' if i==0 else names[i-1],point))
    entries=[(bone,points[i],points[i+1] if i+1<len(points) else FINGERS[name][0][0]) for i,bone in enumerate(names)]
    for finger,knots in enumerate(FINGERS[name]):
        tip=tuple((np.array(knots[1])*.45+np.array(knots[2])*.55).tolist())
        controls=[knots[0],knots[1],tip,knots[2]]
        digit_skin=[]
        for j in range(3):
            bone=f'{name}_finger_{finger}_{j}'
            BONES.append((bone,names[-1] if j==0 else f'{name}_finger_{finger}_{j-1}',controls[j]))
            digit_skin.append((bone,controls[j],controls[j+1]))
        SKIN[name+'_digit'+str(finger)]=digit_skin
    SKIN[name]=entries
BONES.append(('lower_right_elbow_spur','lower_right_2',(1265,750)))
for name in ['core_top','core','core_mid','core_low']:
    point=next(p for n,_,p in BONES if n==name)
    SKIN[name]=[(name,point,point)]
SKIN['body']=[('chest',(743,294),(751,480)),('torso',(752,459),(774,608)),
              ('waist',(774,609),(789,720)),('trail_left',(746,710),(755,797)),
              ('trail_left_1',(755,797),(820,910)),('trail_left_2',(820,910),(833,947)),
              ('trail_left_3',(833,947),(844,961)),
              ('trail_right',(837,710),(875,790)),('trail_right_1',(875,790),(907,893)),
              ('trail_right_2',(907,893),(915,928)),('trail_right_3',(915,928),(924,952))]

def dist_to_segment(points,a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);v=b-a
    u=np.clip(((points-a)@v)/max(float(v@v),1e-6),0,1)
    return np.sum((points-a-u[:,None]*v)**2,axis=1)

def weights(name,points):
    points=np.asarray(points,float)
    if name.startswith('core'):
        return [[(name,1.)] for _ in points]
    entries=SKIN[name]
    d=np.stack([dist_to_segment(points,a,b) for _,a,b in entries],axis=1)
    sigma=np.full(len(points),65. if name=='body' else (11. if '_digit' in name else 29.))
    if name in ARMS:
        wrist=np.asarray(ARMS[name][-1])
        near=np.linalg.norm(points-wrist,axis=1)
        sigma=np.where(near<140,15.,29.)
    w=np.exp(-(d-d.min(axis=1,keepdims=True))/(sigma[:,None]**2))
    w/=np.maximum(w.sum(axis=1,keepdims=True),1e-300)
    # Keep influence local: adjacent finger branches should not pull one another.
    keep=w
    out=[]
    for point,row in zip(points,keep):
        values={entries[i][0]:float(v) for i,v in enumerate(row) if v>.002}
        if name=='body':
            # Painted shoulder overlaps follow the same scapular controls as
            # their arms, rather than peeling away under a torso twist.
            for arm,knots in ARMS.items():
                r=np.asarray(knots[0]);delta=(point-r)/np.array([60.,58.])
                amount=.64*np.exp(-float(delta@delta)*1.7)
                values={k:v*(1-amount) for k,v in values.items()}
                values[arm+'_socket']=values.get(arm+'_socket',0)+amount*sum(row)
            for rib,anchor in [('rib_upper_left',(672,435)),('rib_upper_right',(834,435)),
                               ('rib_lower_left',(717,560)),('rib_lower_right',(819,559))]:
                delta=(point-np.array(anchor))/np.array([68.,48.])
                amount=.26*np.exp(-float(delta@delta)*1.7)
                total=sum(values.values())
                values={k:v*(1-amount) for k,v in values.items()}
                values[rib]=values.get(rib,0)+amount*total
        if name=='lower_right':
            def smooth(v):
                v=float(np.clip(v,0,1));return v*v*(3-2*v)
            amount=smooth((point[0]-1190)/80)*smooth((point[1]-660)/30)*(1-smooth((point[1]-803)/35))
            total=sum(values.values())
            values={k:v*(1-amount) for k,v in values.items()}
            values['lower_right_elbow_spur']=values.get('lower_right_elbow_spur',0)+amount*total
        total=sum(values.values())
        values={k:v for k,v in values.items() if v/total>.0005}
        total=sum(values.values())
        out.append([(k,v/total) for k,v in values.items()])
    return out

def post(pose,world,frame,sk):
    # Bake a four-segment FABRIK solve into native rotations. Keep the shoulder
    # attached to its torso: translating the whole arm to pin a hand would
    # stretch the shoulder paint and defeat the point of articulated elbows.
    for name,strength in frame.extra.get('support',{}).items():
        if strength<=0:continue
        world=sk.world(pose)
        chain=[name+'_'+str(i) for i in range(5)]
        wrist=chain[-1]
        target=np.asarray(sk.setup[wrist],float)
        target+=np.asarray(frame.extra.get('support_offsets',{}).get(name,(0,0)),float)
        points=np.array([world[b][:2,2] for b in chain])
        target=points[-1]*(1-strength)+target*strength
        origin=points[0].copy();lengths=np.linalg.norm(np.diff(points,axis=0),axis=1)
        def unit(v):return v/max(float(np.linalg.norm(v)),1e-8)
        if np.linalg.norm(target-origin)>=sum(lengths):
            direction=unit(target-origin)
            for i,length in enumerate(lengths):points[i+1]=points[i]+direction*length
        else:
            for _ in range(6):
                points[-1]=target
                for i in range(3,-1,-1):points[i]=points[i+1]+unit(points[i]-points[i+1])*lengths[i]
                points[0]=origin
                for i in range(4):points[i+1]=points[i]+unit(points[i+1]-points[i])*lengths[i]
        for i in range(4):
            b=chain[i];child=chain[i+1];parent=sk.parent[b]
            world=sk.world(pose)
            direction=np.linalg.solve(world[parent][:2,:2],points[i+1]-points[i])
            r,x,y,sx,sy=pose.get(b,(0,0,0,1,1))
            offset=np.array(sk.local[child])*np.array([sx,sy])
            angle=math.degrees(math.atan2(direction[1],direction[0])-math.atan2(offset[1],offset[0]))
            pose[b]=((angle+180)%360-180,x,y,sx,sy)
