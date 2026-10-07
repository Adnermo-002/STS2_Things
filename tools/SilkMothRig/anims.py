"""Cloth wing beats, a drifting body, and delayed silk pendulums."""
import math
from rigutil import Frame, TAU, key, bump, hold, seg, ease
ANIMS={'idle_loop':(4.,True),'attack':(1.20,False),'cast':(1.55,False),
       'flutter':(1.30,False),'hurt':(.58,False),'die':(1.55,False),
       'revive':(1.4,False),'summon':(1.4,False),'power_up':(1.2,False)}
EVENTS={'attack':[('swoop_contact',.48)],'cast':[('silk_release',.62)],
        'flutter':[('wing_hit',.42),('wing_hit',.67)],'die':[('land',1.15)]}

def wave(t,period=4,phase=0):
    return math.sin(TAU*t/period-phase)-math.sin(-phase)

def wings(f,beat,lag=0):
    f.P.add('wing_far',r=-6.0*beat,sx=-.08*beat,sy=.02*beat)
    f.P.add('wing_near',r=4.6*beat,sx=-.115*beat,sy=.035*beat)
    f.P.add('wing_far_mid',r=-1.6*lag);f.P.add('wing_far_tip',r=-2.4*lag)
    f.P.add('wing_near_mid',r=1.8*lag);f.P.add('wing_near_tip',r=2.8*lag)

def tails(f,t,amount=1,period=4):
    for i,n in enumerate(['silk_a','silk_b','silk_c']):
        f.P.add(n,r=1.6*amount*wave(t,period,.4+i*.4))
        f.P.add(n+'_tip',r=2.2*amount*wave(t,period,.9+i*.35))

def idle(t):
    f=Frame();wings(f,wave(t,1),wave(t,1,.5))
    f.P.add('thorax',y=11*wave(t,2,.3),r=.7*wave(t))
    f.P.add('abdomen',r=1.3*wave(t,2,.9),sy=.015*wave(t,2))
    f.P.add('head',r=.8*wave(t,4,.5))
    f.P.add('antenna_far',r=2.6*wave(t,2,.5));f.P.add('antenna_near',r=-2.4*wave(t,2,.8))
    f.P.add('eye_far',sy=-.40*bump(t,2.48,2.57,2.76));f.P.add('eye_near',sy=-.44*bump(t,2.50,2.60,2.79))
    tails(f,t);return f

def attack(t):
    f=Frame();wind=hold(t,0,.25,.30,.45)
    hit=key(t,(0,0),(.28,0),(.48,1),(.55,.97),(.77,-.10),(1.2,0))
    f.P.add('thorax',x=32*wind-143*hit,y=20*wind-28*hit,r=-4*wind+7*hit)
    f.P.add('head',r=3*hit,x=-9*hit);f.P.add('abdomen',r=-5*hit)
    wings(f,-1.2*wind+1.1*hit,bump(t,.30,.59,1.12))
    for i,n in enumerate(['silk_a','silk_b','silk_c']):
        h=bump(t,.29+i*.035,.57+i*.035,1.19)
        f.P.add(n,r=-6*h);f.P.add(n+'_tip',r=-4*h)
    f.P.add('antenna_near',r=-8*bump(t,.30,.57,1.1));return f

def cast(t):
    f=Frame();gather=hold(t,0,.32,.46,.65)
    release=key(t,(0,0),(.45,0),(.62,1),(.75,.95),(1.03,-.16),(1.55,0))
    f.P.add('thorax',y=22*gather,x=18*gather+20*bump(t,.59,.74,1.2),r=-2*gather+2*release)
    f.P.add('abdomen',sx=.07*gather-.035*release,sy=-.035*gather+.03*release)
    f.P.add('head',r=3*release);wings(f,-.6*gather+.65*release,bump(t,.45,.79,1.48))
    f.P.add('leg_far',r=-4*gather+6*release);f.P.add('leg_near',r=-5*gather+7*release)
    for i,n in enumerate(['silk_a','silk_b','silk_c']):
        f.P.add(n,r=(2+i)*gather-7*release,sy=-.035*gather)
        f.P.add(n+'_tip',r=-6*release+3*bump(t,.75,.99,1.5))
    f.P.add('antenna_near',r=4*gather-6*release);return f

def flutter(t):
    f=Frame();wind=hold(t,0,.22,.29,.39)
    a=bump(t,.28,.42,.57);b=bump(t,.54,.67,.86);h=a+.8*b
    f.P.add('thorax',x=20*wind-52*h,y=15*wind+8*h,r=3*h)
    wings(f,-1.0*wind+1.45*a+1.35*b,bump(t,.4,.75,1.26))
    f.P.add('abdomen',r=-4*h);f.P.add('head',r=2*h)
    for n in ['silk_a','silk_b','silk_c']:
        f.P.add(n,r=-6*h);f.P.add(n+'_tip',r=-5*bump(t,.43,.79,1.28))
    return f

def hurt(t):
    f=Frame();h=key(t,(0,0),(.075,1),(.15,.7),(.30,-.22),(.45,.07),(.58,0))
    f.P.add('thorax',x=42*h,r=-4*h);f.P.add('head',r=-5*h)
    wings(f,.6*h,h);f.P.add('eye_near',sy=-.35*bump(t,.02,.10,.31))
    for n in ['silk_a','silk_b','silk_c']:f.P.add(n,r=5*h)
    return f

def fallen(f,h):
    f.P.add('thorax',y=-160*h,r=16*h)
    f.P.add('abdomen',r=6*h);f.P.add('head',r=-8*h)
    f.P.add('wing_near',r=-17*h,sy=-.30*h);f.P.add('wing_far',r=19*h,sy=-.35*h)
    f.P.add('wing_near_tip',r=-8*h);f.P.add('wing_far_tip',r=6*h)
    for n in ['silk_a','silk_b','silk_c']:f.P.add(n,sy=-.28*h,r=-4*h)
    f.P.add('eye_near',sy=-.28*h);f.P.add('eye_far',sy=-.28*h)

def die(t):
    f=Frame();fallen(f,ease(seg(t,.15,1.15)))
    f.P.add('thorax',y=20*bump(t,0,.15,.40)-12*bump(t,1.04,1.19,1.5));return f

def revive(t):
    f=Frame();fallen(f,1-ease(seg(t,.15,1.25)))
    f.P.add('thorax',y=16*bump(t,.7,1.02,1.4));return f

def summon(t):
    f=Frame();v=1-ease(seg(t,0,1.2));f.P.add('thorax',x=80*v,y=90*v,r=-6*v)
    wings(f,.8*bump(t,.22,.56,1.34),bump(t,.30,.72,1.4))
    tails(f,t,1-ease(seg(t,.8,1.4)),2.8);return f

def power_up(t):
    f=Frame();h=bump(t,0,.47,1.2);f.P.add('thorax',y=30*h)
    wings(f,-.85*h,-.8*h);f.P.add('abdomen',sx=.04*h)
    for n in ['silk_a','silk_b','silk_c']:f.P.add(n,sy=.06*h)
    return f

FUNCS={'idle_loop':idle,'attack':attack,'cast':cast,'flutter':flutter,'hurt':hurt,
       'die':die,'revive':revive,'summon':summon,'power_up':power_up}
