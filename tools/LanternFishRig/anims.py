"""Weightless, mildly goofy fish motion; danger comes from the light, not a snarl."""
import math
from rigutil import Frame,TAU,key,bump,hold,ease,seg
ANIMS={'idle_loop':(4.,True),'attack':(1.25,False),'tail_swipe':(.95,False),
       'cast':(1.8,False),'guard':(1.25,False),'hurt':(.65,False),
       'die':(1.8,False),'revive':(1.6,False),'summon':(1.3,False),'power_up':(1.6,False)}
EVENTS={'attack':[('bite_contact',.48)],'tail_swipe':[('tail_contact',.36)],
        'cast':[('flash_release',.72)],'guard':[('guard_release',.42)],'die':[('collapse',1.35)]}
def base():
    f=Frame();f.glow={'lantern_glow':.1};return f
def ripple(f,t,a=1):
    for i in range(8):f.P.add(f'lure_{i}',r=a*math.sin(TAU*t/4-i*.4)*.8)
    for i in range(3):f.P.add(f'tail_{i}',r=a*math.sin(TAU*t/2+i*.55)*3.0)
    f.P.add('fin_0',r=math.sin(TAU*t/1.0)*7*a,sy=.08*math.sin(TAU*t/1.0)*a)
    f.P.add('fin_1',r=math.sin(TAU*t/1.0-.4)*4*a)
    f.P.add('dorsal_0',r=math.sin(TAU*t/4+.6)*2*a)
def idle(t):
    f=base();u=math.sin(TAU*t/4);f.P.add('body',y=16*u,r=.8*u)
    f.P.add('head',r=-.6*u);f.P.add('jaw',r=1.2*math.sin(TAU*t/2))
    ripple(f,t);f.glow['lantern_glow']=.12+.04*u;return f
def attack(t):
    f=base();k=key(t,(0,0),(.26,-.35),(.48,1),(.62,.85),(1.25,0))
    f.P.add('body',x=-104*k,y=8*k,r=3*k)
    f.P.add('head',r=4*k);f.P.add('jaw',r=key(t,(0,0),(.32,11),(.48,-3),(.7,1),(1.25,0)))
    f.P.add('tail_0',r=10*k);f.P.add('tail_1',r=6*k)
    ripple(f,t,1.2*math.sin(math.pi*t/1.25));return f
def tail_swipe(t):
    f=base();k=key(t,(0,0),(.20,-.55),(.36,1),(.51,.65),(.95,0))
    f.P.add('body',x=-30*k,r=5*k,y=10*k)
    f.P.add('tail_0',r=-22*k);f.P.add('tail_1',r=-8*k);f.P.add('tail_2',r=-3*k)
    f.P.add('head',r=-3*k);f.P.add('fin_0',r=12*k);f.P.add('dorsal_0',r=-7*k)
    f.P.add('lure_0',r=3*k);return f
def cast(t):
    f=base();h=hold(t,.06,.55,1.02,1.8);f.P.add('body',y=30*h,x=12*h,r=-2*h)
    f.P.add('head',r=-3*h);f.P.add('jaw',r=4*h);f.P.add('fin_0',r=-14*h)
    f.P.add('lure_0',r=4*h);f.P.add('lure_2',r=-5*h);f.P.add('lamp',r=-3*h)
    f.glow['lantern_glow']=.12+.85*hold(t,.46,.72,.92,1.35);return f
def guard(t):
    f=base();h=hold(t,0,.42,.74,1.25);f.P.add('body',y=-16*h,sx=-.045*h,sy=.025*h)
    f.P.add('fin_0',r=22*h,sy=-.24*h);f.P.add('dorsal_0',r=10*h);f.P.add('tail_0',r=12*h)
    f.P.add('lure_0',r=-5*h);f.glow['lantern_glow']=.12*(1-h);return f
def hurt(t):
    f=base();h=bump(t,0,.13,.65);f.P.add('body',x=39*h,y=-12*h,r=-6*h)
    f.P.add('jaw',r=4*h);f.P.add('lure_0',r=-4*h);f.P.add('tail_0',r=7*h);return f
def death(u):
    f=base();h=ease(u);f.P.add('body',y=-215*h,r=15*h,x=15*h)
    f.P.add('head',r=6*h);f.P.add('jaw',r=7*h);f.P.add('fin_0',r=24*h,sy=-.25*h)
    for i in range(7):f.P.add(f'lure_{i}',r=-4*h)
    f.P.add('tail_0',r=-14*h);f.glow['lantern_glow']=.1*(1-h)
    f.tint=(1-.22*h,1-.22*h,1-.18*h,1);return f
def die(t):return death(seg(t,0,1.35))
def revive(t):return death(1-ease(seg(t,0,1.6)))
def summon(t):
    f=base();h=1-ease(seg(t,0,1.0));f.P.add('body',y=-100*h,x=55*h,r=-5*h)
    ripple(f,t,h);return f
def power_up(t):return cast(t*1.8/1.6)
FUNCS={'idle_loop':idle,'attack':attack,'tail_swipe':tail_swipe,'cast':cast,'guard':guard,
       'hurt':hurt,'die':die,'revive':revive,'summon':summon,'power_up':power_up}
