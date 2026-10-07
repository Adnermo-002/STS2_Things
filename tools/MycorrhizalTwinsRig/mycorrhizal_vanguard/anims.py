"""Rooted feet, staged whip contact, soft cap recoil, and independent form poses."""
from pathlib import Path
import math
from rigutil import Frame,TAU,key,bump,hold,seg,ease
TALL=Path.cwd().name.endswith('vanguard')
ANIMS={'idle_loop':(3.6,True),'attack':(1.28,False),'double_attack':(1.52,False),'cast':(1.5,False),
 'guard':(1.5,False),'exchange':(1.55,False),'enrage':(1.6,False),'hurt':(.62,False),
 'die':(1.9,False),'revive':(1.7,False),'summon':(1.4,False),'power_up':(1.35,False),
 'robust':(1.,True),'withered':(1.,True)}
EVENTS={'attack':[('root_contact',.48)],'double_attack':[('root_contact',.48),('root_contact',.73)],
 'cast':[('spore_release',.60)],'guard':[('cap_set',.56)],'exchange':[('sap_transfer',.62)],
 'enrage':[('root_snap',.35),('fury_bloom',.7)],'die':[('cap_land',1.25)]}
def wave(t,p=3.6,phase=0):return math.sin(TAU*t/p-phase)-math.sin(-phase)
def cap(f,h,lag=0):
 f.P.add('cap',r=-2*h,y=3*h,sy=.02*h)
 f.P.add('cap_l',r=-3.5*lag,sy=.025*lag);f.P.add('cap_r',r=4.2*lag,sy=-.022*lag)
 f.P.add('cap_l_tip',r=-2.1*lag);f.P.add('cap_r_tip',r=2.6*lag)
def arms(f,a,b=None):
 b=a if b is None else b
 f.P.add('arm_far',r=-a*22);f.P.add('elbow_far',r=-a*12);f.P.add('hand_far',r=-a*8)
 f.P.add('arm_near',r=-b*30);f.P.add('elbow_near',r=-b*16);f.P.add('hand_near',r=-b*9)
 for side,h in [('far',a),('near',b)]:
  f.P.add('finger_'+side+'_a',r=5*h);f.P.add('finger_'+side+'_b',r=-4*h)
def idle(t):
 f=Frame();period=3.6 if TALL else 1.8;w=wave(t,period)
 f.P.add('body',y=(4 if TALL else 2.5)*w,sx=.012*w,r=.35*wave(t,3.6,.3))
 f.P.add('neck',r=.85*wave(t,period,.6))
 cap(f,.40*w,.55*wave(t,period,.9));arms(f,.055*wave(t,3.6,.4),.07*wave(t,3.6,1.2))
 f.P.add('cap_l_tip',r=.8*wave(t,period,1.1));f.P.add('cap_r_tip',r=-.7*wave(t,period,1.35))
 f.P.add('tail',r=2.8*wave(t,3.6,.9))
 blink=2.33 if TALL else 1.28
 for i in range(2):f.P.add(f'eye_{i}',sy=-.72*bump(t,blink+i*.04,blink+.08+i*.04,blink+.28+i*.03))
 return f
def attack(t):
 f=Frame();wind=hold(t,0,.24,.30,.46)
 h=key(t,(0,0),(.30,0),(.48,1),(.56,1),(.79,-.12),(1.28,0))
 f.P.add('body',x=25*wind-(54 if TALL else 67)*h,r=-3*wind+(5 if TALL else 7)*h,y=(6 if TALL else -10)*wind)
 f.P.add('neck',r=-3*wind+4.5*h)
 if TALL:arms(f,-.4*wind+.96*h,-.65*wind+1.30*h)
 else:
  arms(f,-.2*wind+.18*h,.2*wind-.28*h)
  f.P.add('cap',r=3.5*h,sx=.025*wind)
 cap(f,-wind+1.1*h,bump(t,.40,.68,1.2));f.P.add('tail',r=-8*h)
 f.P.add('hand_near',r=4*bump(t,.53,.72,1.22))
 f.P.add('toe_near',r=-3*h);f.P.add('eye_1',sy=-.22*bump(t,.34,.48,.70));return f
def double_attack(t):
 f=Frame();wind=hold(t,0,.23,.29,.44)
 a=bump(t,.30,.48,.64);b=key(t,(0,0),(.58,0),(.73,1),(.81,1),(1.04,-.12),(1.52,0))
 h=.8*a+b
 f.P.add('body',x=23*wind-48*h,r=-3*wind+4.5*h);f.P.add('neck',r=3*h)
 arms(f,-.40*wind+1.05*a+.18*b,-.6*wind+.25*a+1.32*b)
 f.P.add('hand_far',r=4*bump(t,.51,.64,.88));f.P.add('hand_near',r=5*bump(t,.76,.91,1.45))
 cap(f,h-wind,bump(t,.4,.84,1.4));f.P.add('tail',r=-8*b)
 f.P.add('cap_l_tip',r=-1.2*a);f.P.add('cap_r_tip',r=1.8*b);return f
def cast(t):
 f=Frame();g=hold(t,0,.30,.43,.60);h=key(t,(0,0),(.43,0),(.6,1),(.75,.7),(1.03,-.12),(1.5,0))
 f.P.add('body',y=-10*g+18*h,sx=.035*g-.02*h,sy=-.025*g+.035*h)
 f.P.add('neck',y=10*h,r=-4*h);arms(f,.45*g-.42*h,.65*g-.52*h)
 cap(f,1.35*h-g,1.45*bump(t,.45,.74,1.4));f.P.add('eye_1',sy=.25*h)
 f.P.add('cap_l_tip',r=-2*bump(t,.62,.83,1.45));f.P.add('cap_r_tip',r=2.4*bump(t,.64,.86,1.47));return f
def guard(t):
 f=Frame();h=key(t,(0,0),(.28,.3),(.56,1),(.82,1),(1.15,-.05),(1.5,0))
 f.P.add('body',sy=-.055*h,sx=.065*h,y=-14*h)
 f.P.add('neck',y=-18*h,r=-3*h);f.P.add('cap',sx=(.09 if TALL else .14)*h,sy=-.045*h,y=-10*h)
 f.P.add('cap_l',r=-4*h);f.P.add('cap_r',r=5*h)
 f.P.add('cap_l_tip',r=-2*h);f.P.add('cap_r_tip',r=2*h)
 arms(f,.52*h,.74*h);f.P.add('tail',r=7*h)
 f.P.add('eye_0',sy=-.15*h);f.P.add('eye_1',sy=-.22*h);return f
def exchange(t):
 f=Frame();draw=bump(t,0,.30,.65);surge=key(t,(0,0),(.32,0),(.62,1),(.82,.88),(1.13,-.08),(1.55,0))
 f.P.add('body',y=-7*draw+10*surge,sx=.022*surge);f.P.add('neck',r=2*draw-2.5*surge)
 cap(f,-draw+surge,bump(t,.52,.88,1.5));arms(f,-.19*surge,-.25*surge)
 f.P.add('tail',r=14*surge);return f
def enrage(t):
 f=Frame();fold=hold(t,0,.22,.31,.62);burst=key(t,(0,0),(.34,0),(.7,1),(.9,.7),(1.25,-.12),(1.6,0))
 f.P.add('body',y=-16*fold+23*burst,sx=.055*burst,sy=-.04*fold+.06*burst)
 f.P.add('neck',r=5*fold-7*burst);cap(f,1.65*burst-fold,bump(t,.6,.89,1.57))
 arms(f,.52*fold-.65*burst,.5*fold-.8*burst);f.P.add('tail',r=-15*burst)
 f.P.add('eye_0',sy=.22*burst);f.P.add('eye_1',sy=.22*burst)
 return f
def hurt(t):
 f=Frame();h=key(t,(0,0),(.08,1),(.16,.65),(.34,-.18),(.49,.06),(.62,0))
 f.P.add('body',x=25*h,r=-2.5*h);f.P.add('neck',r=-5*h);cap(f,h,h)
 f.P.add('cap_l_tip',r=-1.3*h);f.P.add('cap_r_tip',r=1.3*h)
 arms(f,-.2*h,-.25*h)
 for i in range(2):f.P.add(f'eye_{i}',sy=-.55*bump(t,0,.1,.38))
 return f
def fallen(f,h):
 f.P.add('body',sy=-.42*h,sx=.13*h,y=-48*h,r=-4*h)
 f.P.add('neck',r=-9*h,y=-20*h);f.P.add('cap',r=12*h,sy=-.18*h)
 f.P.add('cap_l',r=-7*h);f.P.add('cap_r',r=9*h);arms(f,-.24*h,-.42*h)
 f.P.add('eye_0',sy=-.7*h);f.P.add('eye_1',sy=-.7*h)
def die(t):
 f=Frame();fallen(f,ease(seg(t,.18,1.25)));f.P.add('cap',y=-8*bump(t,1.1,1.29,1.85));return f
def revive(t):
 f=Frame();fallen(f,1-ease(seg(t,.2,1.5)));f.P.add('cap',y=7*bump(t,1.0,1.37,1.7));return f
def summon(t):
 f=Frame();h=1-ease(seg(t,0,1.15));f.P.add('body',sy=-.25*h,y=-23*h);cap(f,-.6*h,bump(t,.65,.91,1.4));return f
def power_up(t):return exchange(t*1.55/1.35)
def robust(t):
 f=Frame();f.P.add('cap_posture',sx=.06,sy=.02,r=1.5);return f
def withered(t):
 f=Frame();f.P.add('cap_posture',sx=-.055,sy=-.055,r=-4.5,y=-8);return f
FUNCS={n:globals()['idle' if n=='idle_loop' else n] for n in ANIMS}
