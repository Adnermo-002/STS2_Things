"""Heavy planted breathing, closed lids, full wake-up, brood contractions and recovery."""
import math
from rigutil import Frame,TAU,key,hold,bump,ease,seg
ANIMS={'sleep_loop':(4.8,True),'wake_up':(1.5,False),'idle_loop':(4.,True),
       'attack':(1.4,False),'crush':(1.6,False),'summon':(1.8,False),'cast':(1.65,False),
       'curl':(1.4,False),'power_up':(1.5,False),'hurt':(.65,False),'die':(1.75,False),
       'retreat':(1.35,False)}
EVENTS={'wake_up':[('eyes_open',.56)],'attack':[('bite_contact',.52)],
        'crush':[('crush_contact',.66)],'summon':[('brood_release',.76)],
        'cast':[('parasite_release',.76)],'curl':[('settle',.48)],'die':[('collapse',1.2)]}
def frame(lids=0):
    f=Frame();f.glow.update(lid_far=lids,lid_near=lids);return f
def wave(t,phase=0,period=4):return math.sin(TAU*t/period-phase)-math.sin(-phase)
def body(f,x=0,sx=0,sy=0):
    f.P.add('body',x=x,y=210*sy,sx=sx,sy=sy)
    f.P.add('sucker',x=-(x+202*sx)/(1+sx),y=-20*sy/(1+sy),sx=1/(1+sx)-1,sy=1/(1+sy)-1)
def sleeping(f,h=1):
    body(f,sx=.025*h,sy=-.025*h)
    f.P.add('neck_0',y=-35*h,x=16*h,r=-1.4*h)
    f.P.add('neck_1',y=-25*h,x=10*h,r=1.3*h)
    f.P.add('head',y=-30*h,x=16*h,r=-2.5*h)
    f.P.add('mouth',sy=-.16*h,sx=-.05*h)
    f.P.add('tail_2',r=3*h);f.P.add('tail_3',r=2*h)
def sleep(t):
    f=frame(1);sleeping(f)
    w=wave(t,0,4.8);f.P.add('belly',sx=.025*w,sy=.035*w)
    f.P.add('head',y=4*w);f.P.add('mouth',sy=.023*w)
    f.P.add('pouch_front',sy=.015*wave(t,.5,4.8));f.P.add('pouch_mid',sy=.02*wave(t,.9,4.8))
    return f
def wake(t):
    h=1-ease(seg(t,0,1.3));f=frame(1-ease(seg(t,.28,.96)));sleeping(f,h)
    stretch=bump(t,.35,.85,1.5);f.P.add('neck_0',y=18*stretch,r=2*stretch)
    f.P.add('head',y=23*stretch,r=-2*stretch);f.P.add('mouth',sx=.035*stretch,sy=.07*stretch)
    f.P.add('belly',sx=.023*stretch,sy=.04*stretch)
    return f
def idle(t):
    f=frame();w=wave(t);body(f,sx=.008*w,sy=.009*w)
    f.P.add('belly',sx=.022*wave(t,.55),sy=.028*wave(t,.55))
    for i in range(2):f.P.add(f'neck_{i}',r=.45*wave(t,.7+i*.8),sy=.008*wave(t,.7+i*.8))
    for i in range(5):f.P.add(f'tail_{i}',r=.4*wave(t,.8+i*.45))
    f.P.add('mouth',sx=.012*wave(t,.2),sy=.02*wave(t,.5))
    for b in ['pouch_front','pouch_mid']:f.P.add(b,sy=.016*wave(t,1))
    f.glow['lid_near']=.85*bump(t,2.19,2.3,2.48);f.glow['lid_far']=.85*bump(t,2.16,2.27,2.45)
    return f
def attack(t):
    f=frame();wind=hold(t,0,.25,.31,.54)
    hit=key(t,(0,0),(.31,0),(.52,1),(.64,1),(.85,-.06),(1.05,.025),(1.4,0))
    body(f,x=26*wind-43*hit,sx=-.024*wind+.014*hit,sy=.018*wind)
    f.P.add('neck_0',x=16*wind-38*hit,r=1.4*wind-.8*hit)
    f.P.add('neck_1',x=12*wind-30*hit,r=1.1*wind-.7*hit)
    f.P.add('head',x=-24*hit,y=-5*hit,r=-1.2*hit)
    opened=hold(t,.2,.45,.57,.82);f.P.add('mouth',sx=.06*opened,sy=.055*opened)
    f.P.add('lip_upper',y=3*opened);f.P.add('lip_lower',y=-5*opened)
    f.P.add('belly',sx=-.019*hit,sy=.025*wind)
    for i in range(5):f.P.add(f'tail_{i}',r=1.4*bump(t,.25+i*.025,.58+i*.025,1.2+i*.025))
    return f
def crush(t):
    f=frame();rise=hold(t,0,.32,.44,.70);impact=bump(t,.48,.66,1.28)
    body(f,x=18*rise-32*impact,sy=.045*rise-.015*impact,sx=-.014*rise+.035*impact)
    f.P.add('neck_0',y=44*rise-37*impact,x=-29*impact,r=2*rise)
    f.P.add('neck_1',y=27*rise-27*impact,r=2*rise)
    f.P.add('head',y=27*rise-40*impact,x=-24*impact,r=-3*impact)
    f.P.add('belly',sx=.075*impact,sy=-.03*impact)
    for b in ['pouch_front','pouch_mid']:f.P.add(b,sy=-.045*impact,sx=.035*impact)
    return f
def summon(t):
    f=frame();gather=hold(t,0,.32,.48,.9);release=bump(t,.48,.76,1.8)
    body(f,x=12*gather,sx=-.022*gather,sy=.022*gather)
    f.P.add('belly',sx=.06*gather-.032*release,sy=.06*gather-.036*release)
    f.P.add('neck_0',sy=.018*gather,x=-16*release);f.P.add('head',y=13*gather-9*release,x=-17*release)
    f.P.add('mouth',sx=.18*release,sy=.18*release)
    f.P.add('lip_upper',y=8*release);f.P.add('lip_lower',y=-15*release)
    for i,b in enumerate(['pouch_mid','pouch_front']):
        h=bump(t,.1+i*.16,.46+i*.12,1.30+i*.12);f.P.add(b,sx=.05*h,sy=.06*h)
    for i in range(5):f.P.add(f'tail_{i}',r=-1.6*bump(t,.2+i*.05,.55+i*.05,1.4+i*.05))
    return f
def cast(t):return summon(t*1.8/1.65)
def curl(t):
    f=frame();h=hold(t,0,.48,.77,1.4);body(f,x=10*h,sx=-.035*h,sy=.018*h)
    f.P.add('neck_0',x=9*h,y=-15*h);f.P.add('head',x=10*h,y=-17*h,r=-1*h)
    f.P.add('mouth',sx=-.035*h,sy=-.065*h)
    f.P.add('tail_2',r=1.7*h);f.P.add('tail_3',r=1.4*h)
    f.glow.update(lid_far=.75*h,lid_near=.8*h)
    return f
def power_up(t):
    f=frame();h=bump(t,.05,.53,1.5);body(f,sx=.025*h,sy=.035*h)
    f.P.add('belly',sx=.045*h,sy=.058*h);f.P.add('head',y=14*h)
    return f
def hurt(t):
    f=frame();h=key(t,(0,0),(.08,1),(.18,.62),(.33,-.12),(.49,.035),(.65,0))
    body(f,x=21*h,sx=-.02*h,sy=.013*h);f.P.add('head',x=11*h,r=1.5*h)
    f.P.add('belly',sx=-.018*h,sy=.025*h);return f
def die(t):
    f=frame();h=ease(seg(t,.07,1.40));f.P.add('body',y=-91*h,x=15*h,sy=-.39*h,sx=.045*h)
    f.P.add('neck_0',y=-32*h,r=-2*h);f.P.add('head',y=-38*h,r=-3*h)
    f.P.add('mouth',sy=-.22*h);f.glow.update(lid_far=h,lid_near=h)
    f.tint=(1-.17*h,1-.17*h,1-.12*h,1);return f
def retreat(t):
    f=frame(1);sleeping(f);h=ease(seg(t,0,1.35));f.P.add('root',x=180*h,y=-42*h,sx=-.13*h,sy=-.14*h)
    f.tint=(1,1,1,1-h);return f
FUNCS={'sleep_loop':sleep,'wake_up':wake,'idle_loop':idle,'attack':attack,'crush':crush,'summon':summon,
       'cast':cast,'curl':curl,'power_up':power_up,'hurt':hurt,'die':die,'retreat':retreat}
