"""Overlapping joints, individual digits and baked supporting hands."""
import math
from rigutil import Frame,TAU,key,bump,hold,kick,ease,seg

ANIMS={'idle_loop':(6,True),'attack':(1.25,False),'sweep':(1.4,False),
       'grasp':(1.5,False),'pulse':(1.55,False),'scatter':(1.65,False),
       'hurt':(.6,False),'cast':(1.4,False),'power_up':(1.2,False),
       'revive':(1.5,False),'summon':(1.5,False),'die':(1.9,False)}
ARMS=['upper_left','upper_right','lower_left','lower_right']
SIGNS={n:(1 if 'left' in n else -1) for n in ARMS}
CORE=['core_top','core','core_mid','core_low']
DIGITS={name:(4 if name=='upper_left' else 3) for name in ARMS}

def fingers(f,name,curl=0,spread=0,t=0,ripple=0):
    for digit in range(DIGITS[name]):
        for joint,gain in enumerate([1.,.64,.40]):
            wave=ripple*math.sin(t*TAU/3-digit*.55-joint*.48)
            factor=.6 if digit==3 else .86+.12*digit
            angle=curl*gain*factor+(digit-1)*spread/(joint+1)+wave
            f.P.add(f'{name}_finger_{digit}_{joint}',r=angle)

def arm(f,name,scapula=0,shoulder=0,elbow=0,wrist=0,curl=0,spread=0,t=0):
    f.P.add(name+'_socket',r=scapula)
    for i,v in enumerate([shoulder,.12*shoulder,.45*elbow,.55*elbow,wrist]):
        f.P.add(name+'_'+str(i),r=v)
    fingers(f,name,curl,spread,t)

def living(f,t,strength=1):
    w=TAU*t/6;breath=math.sin(w)
    f.P.add('chest',sx=.012*breath*strength,sy=-.006*breath*strength,r=.45*math.sin(w+.2)*strength)
    f.P.add('torso',r=.55*math.sin(w-.45)*strength)
    f.P.add('waist',r=-.8*math.sin(w-.75)*strength)
    for i,name in enumerate(ARMS):
        phase=w+i*1.67
        arm(f,name,.65*math.sin(phase)*strength,
            1.1*math.sin(phase-.2)*strength,2.1*math.sin(phase-.55)*strength,
            2.6*math.sin(phase-.95)*strength,1.4*math.sin(phase-1.35)*strength,
            .8*math.sin(phase-1.7)*strength,t)
        for digit in range(DIGITS[name]):
            for joint in range(3):
                f.P.add(f'{name}_finger_{digit}_{joint}',
                    r=.65*strength*math.sin(w*2+i*.6-digit*.9-joint*.42))
    for rib,phase in [('rib_upper_left',0),('rib_upper_right',.45),
                       ('rib_lower_left',.7),('rib_lower_right',1.05)]:
        side=1 if 'left' in rib else -1
        f.P.add(rib,r=side*.65*math.sin(w-phase)*strength,x=side*1.6*breath*strength)
    for side in ['left','right']:
        for i in range(4):
            f.P.add('trail_'+side+('' if i==0 else '_'+str(i)),
                r=(1.2+.22*i)*math.sin(w-i*.48+(0 if side=='left' else 1.6))*strength)
    for i,name in enumerate(CORE):f.P.add(name,s=.015*math.sin(w-i*.22)*strength)

def idle_loop(t):
    f=Frame();living(f,t)
    f.extra['support']={'lower_left':.85,'lower_right':.85}
    return f

def motion(t,contact,duration,delay=0):
    t-=delay
    anticipation=hold(t,0,.20,contact-.16,contact-.04)
    stroke=key(t,(0,0),(contact-.15,0),(contact,1),(contact+.055,.98),
               (contact+.25,.23),(duration-.16,-.045),(duration,0))
    return anticipation,stroke

def drive(f,name,t,contact,duration,scapula,shoulder,elbow,wrist,curl,spread=0,delay=0):
    a,h=motion(t,contact,duration,delay)
    _,e=motion(t,contact+.025,duration,.015+delay)
    _,w=motion(t,contact+.025,duration,.040+delay)
    f.P.add(name+'_socket',r=scapula[0]*a+scapula[1]*h)
    for i,v in enumerate([shoulder[0]*a+shoulder[1]*h,
            (shoulder[0]*a+shoulder[1]*h)*.1,
            (elbow[0]*a+elbow[1]*e)*.44,
            (elbow[0]*a+elbow[1]*e)*.56,wrist[0]*a+wrist[1]*w]):
        f.P.add(name+'_'+str(i),r=v)
    for digit in range(DIGITS[name]):
        for joint,gain in enumerate([1.,.64,.40]):
            da,dh=motion(t,contact,duration,delay+digit*.013+joint*.012-.022)
            factor=.6 if digit==3 else .82+.13*digit
            angle=(curl[0]*da+curl[1]*dh)*gain*factor
            angle+=(digit-1)*spread*a/(joint+1)
            angle+=1.1*kick(t,contact+.085+digit*.018+joint*.01,3.2,8)*(1-joint*.2)
            f.P.add(f'{name}_finger_{digit}_{joint}',r=angle)
    settle=kick(t,contact+.10+delay,2.8,7)
    f.P.add(name+'_3',r=1.3*settle);f.P.add(name+'_4',r=2.1*settle)

def body_action(f,t,contact,duration,reach=1,twist=1):
    a,h=motion(t,contact,duration)
    _,lag=motion(t,contact,duration,.045)
    f.P.add('torso',x=(10*a-40*h)*reach,r=(-1.4*a+2.4*h)*twist)
    f.P.add('waist',x=6*a+5*h,r=(.8*a-1.3*lag)*twist)
    f.P.add('chest',r=(-.8*a+1.1*lag)*twist,sx=-.018*a+.010*h,sy=.010*a-.006*h)
    for rib,side in [('rib_upper_left',1),('rib_upper_right',-1)]:
        f.P.add(rib,r=side*(-1.2*a+1.7*lag),x=side*(-2*a+1.5*h))
    for rib,side in [('rib_lower_left',1),('rib_lower_right',-1)]:
        f.P.add(rib,r=side*(-.6*a+.95*lag))
    for side,phase in [('left',0),('right',.035)]:
        for i in range(4):
            f.P.add('trail_'+side+('' if i==0 else '_'+str(i)),
                r=(1+.25*i)*kick(t,contact+.07+i*.025+phase,2.3,6))
    return a,h

def attack(t):
    f=Frame();living(f,t,.3);a,h=body_action(f,t,.52,1.25)
    drive(f,'lower_left',t,.52,1.25,(-1.8,2.6),(-5,10),(-10,14),(-7,-9),(-5,12),3)
    drive(f,'upper_left',t,.52,1.25,(-.8,1),(-2,3),(-3,4),(2,-3),(-2,3),1,.035)
    arm(f,'upper_right',scapula=-.7*a,shoulder=2*a-3*h,elbow=3*a,wrist=-3*h,curl=2*a)
    f.extra['support']={'lower_right':.92,'lower_left':.84*(1-max(a,h))}
    return f

def sweep(t):
    f=Frame();living(f,t,.3);a,h=body_action(f,t,.58,1.4,1.05,1.25)
    drive(f,'upper_left',t,.58,1.4,(-2,3),(-7,10),(-10,14),(-4,-10),(-6,10),4)
    drive(f,'lower_left',t,.58,1.4,(1.4,-2),(5,-10),(8,-13),(4,9),(4,-9),2,.045)
    arm(f,'upper_right',scapula=-1*a,shoulder=4*a-4*h,elbow=-3*h,wrist=4*h,curl=3*a)
    f.extra['support']={'lower_right':.7,'lower_left':.75*(1-max(a,h))}
    return f

def grasp(t):
    f=Frame();living(f,t,.25);a,h=body_action(f,t,.62,1.5,.85,.8)
    drive(f,'upper_left',t,.62,1.5,(-1.6,2.6),(-5,11),(-9,15),(-2,-8),(-8,16),4)
    drive(f,'upper_right',t,.62,1.5,(1.8,-2.7),(5,-11),(8,-16),(3,9),(7,-14),-4,.028)
    f.extra['support']={'lower_left':.94,'lower_right':.94}
    f.P.add('core',sx=-.055*a+.025*h,sy=.025*a-.02*h)
    return f

def pulse(t):
    f=Frame();living(f,t,.25);a,h=body_action(f,t,.64,1.55,.5,.4)
    for i,name in enumerate(ARMS[:2]):
        s=SIGNS[name]
        drive(f,name,t,.64,1.55,(s*2,-s*2.3),(s*7,-s*9),(s*9,-s*13),(-s*4,-s*10),(-s*6,s*10),s*4,i*.025)
    for i,name in enumerate(ARMS[2:]):
        s=SIGNS[name]
        arm(f,name,scapula=-s*1.3*a,shoulder=-s*3*a,elbow=s*4*h,wrist=-s*5*h,curl=s*2*a)
    f.extra['support']={'lower_left':.97,'lower_right':.97}
    for i,name in enumerate(CORE):
        _,ch=motion(t,.64,1.55,i*.028);f.P.add(name,s=-.06*a+.08*ch)
    return f

def scatter(t):
    f=Frame();living(f,t,.2);a,h=body_action(f,t,.70,1.65,1.1,1.1)
    for i,name in enumerate(ARMS):
        s=SIGNS[name];upper=i<2
        drive(f,name,t,.70,1.65,(-s*2.2,s*3),(-s*9,s*(12 if upper else 9)),
              (-s*14,s*17),(-s*8,s*9),(s*9,-s*12),s*4,(i%2)*.026+(0 if upper else .035))
    # All four arms release together in this last strike. Replanting a hand
    # during its follow-through would force the elbow back against the sweep.
    for i,name in enumerate(CORE):
        _,ch=motion(t,.70,1.65,i*.018);f.P.add(name,s=-.08*a+.10*ch)
    return f

def hurt(t):
    f=Frame();v=key(t,(0,0),(.075,1),(.16,.6),(.29,-.12),(.43,.035),(.6,0))
    f.P.add('chest',x=11*v,r=-1.1*v,sx=-.05*v,sy=.018*v)
    f.P.add('torso',x=4*v,r=-.8*v);f.P.add('waist',r=.55*v)
    f.P.add('rib_upper_left',x=6*v,sx=-.035*v)
    f.P.add('rib_lower_left',r=1.3*v)
    for i,name in enumerate(ARMS):
        lag=kick(t,.10+i*.025,3.4,9)
        arm(f,name,scapula=SIGNS[name]*.7*v,shoulder=SIGNS[name]*1.8*v,
            elbow=2.1*lag,wrist=3.0*lag,curl=1.5*v,spread=.7*v,t=t)
    for name in CORE:f.P.add(name,sx=-.04*v,sy=.015*v)
    f.extra['support']={'lower_left':.8,'lower_right':.8}
    return f

def power_up(t):
    f=Frame();living(f,t,.4);v=bump(t,0,.43,1.2)
    f.P.add('chest',sx=.013*v,sy=.018*v)
    for name in ARMS:arm(f,name,scapula=-SIGNS[name]*.7*v,
        shoulder=-SIGNS[name]*3*v,elbow=SIGNS[name]*4*v,wrist=-SIGNS[name]*4*v,
        curl=-SIGNS[name]*3*v,spread=SIGNS[name]*2*v)
    for i,name in enumerate(CORE):f.P.add(name,s=.045*bump(t,i*.035,.43+i*.035,1.2))
    f.extra['support']={'lower_left':.9,'lower_right':.9}
    return f
def cast(t):return power_up(t*1.2/1.4)

def summon(t):
    f=Frame();appear=ease(seg(t,0,.9));release=1-ease(seg(t,.05,1.35))
    living(f,t,ease(seg(t,.4,1.5)))
    f.P.add('torso',sx=-.14*release,sy=-.18*release)
    for i,name in enumerate(ARMS):
        a=1-ease(seg(t,.10+i*.045,1.20+i*.04));s=SIGNS[name]
        arm(f,name,scapula=-s*1.5*a,shoulder=-s*10*a,elbow=s*13*a,wrist=s*11*a,curl=s*12*a)
    f.tint=(1,1,1,appear)
    f.extra['support']={'lower_left':.75*(1-release),'lower_right':.75*(1-release)}
    return f
def revive(t):return summon(t)

def die(t):
    f=Frame()
    for i,name in enumerate(ARMS):
        s=SIGNS[name];delay=[0,.045,.09,.13][i]
        digit=ease(seg(t,.10+delay,.72+delay))
        wrist=ease(seg(t,.20+delay,.91+delay))
        elbow=ease(seg(t,.32+delay,1.10+delay))
        shoulder=ease(seg(t,.46+delay,1.27+delay))
        arm(f,name,scapula=-s*2*shoulder,shoulder=-s*17*shoulder,
            elbow=s*23*elbow,wrist=s*19*wrist,curl=s*19*digit)
        thin=ease(seg(t,.88+delay,1.64+delay))
        for j in range(1,5):f.P.add(name+'_'+str(j),sx=-.25*thin,sy=-.25*thin)
        for digit in range(DIGITS[name]):
            for joint in range(3):
                shrink=ease(seg(t,.66+delay+joint*.035,1.5+delay+joint*.035))
                f.P.add(f'{name}_finger_{digit}_{joint}',sx=-.28*shrink,sy=-.28*shrink)
    collapse=ease(seg(t,.74,1.75))
    f.P.add('torso',sx=-.60*collapse,sy=-.66*collapse,y=32*collapse)
    f.P.add('waist',r=-2.5*collapse)
    for side in ['left','right']:
        for i in range(4):
            fold=ease(seg(t,.42+i*.08,1.45+i*.06))
            f.P.add('trail_'+side+('' if i==0 else '_'+str(i)),r=(6 if side=='left' else -6)*fold,sx=-.2*fold,sy=-.2*fold)
    for i,name in enumerate(['core_low','core_mid','core_top','core']):
        close=ease(seg(t,1.22+i*.055,1.80+i*.03));f.P.add(name,sx=-.55*close,sy=-.30*close)
    f.tint=(1,1,1,1-ease(seg(t,.70,1.88)))
    return f

FUNCS={name:globals()[name] for name in ANIMS}

