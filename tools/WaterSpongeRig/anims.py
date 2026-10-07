"""Soft mass, contact holds and delayed appendage recovery."""
import math
from rigutil import Frame, TAU, key, hold, bump, ease, seg
ANIMS = {'idle_loop': (4., True), 'attack': (1.15, False), 'cast': (1.5, False),
         'soak': (1.35, False), 'hurt': (.58, False), 'die': (1.5, False),
         'revive': (1.4, False), 'summon': (1.2, False), 'power_up': (1.2, False)}
EVENTS = {'attack': [('slap_contact', .48)], 'cast': [('spray_release', .64)],
          'soak': [('water_absorbed', .56)], 'die': [('collapse', 1.2)]}

def breath(t, phase=0, period=4):
    return math.sin(TAU*t/period-phase)-math.sin(-phase)

def body(f, x=0, sx=0, sy=0):
    # Squash around the sole plane, not the middle of the torso.
    f.P.add('body', x=x, y=350*sy, sx=sx, sy=sy)

def crowns(f, t, start, peak, end, amount):
    for i, name in enumerate(['crown_l', 'crown_mid', 'crown_r']):
        lag = i*.045; h = bump(t, start+lag, peak+lag, end+lag)
        f.P.add(name, r=(1 if i%2 == 0 else -1)*amount*h, sy=.018*h)

def idle(t):
    f=Frame();w=breath(t);body(f,sx=.014*w,sy=-.014*w)
    f.P.add('belly',sx=.027*breath(t,.35),sy=.018*breath(t,.55))
    f.P.add('head',r=.8*breath(t,.45),y=2*breath(t,.7))
    for i,n in enumerate(['crown_l','crown_mid','crown_r']):f.P.add(n,r=(1.2+i*.18)*breath(t,.35+i*.5))
    f.P.add('arm_far',r=1.5*breath(t,.7));f.P.add('arm_near',r=-1.8*breath(t,.95))
    f.P.add('nozzle',sx=.025*breath(t,.35,2),sy=-.014*breath(t,.35,2))
    f.P.add('eye_far',sy=-.52*(bump(t,1.76,1.84,2.00)+.6*bump(t,2.11,2.17,2.30)))
    f.P.add('eye_near',sy=-.55*(bump(t,1.78,1.86,2.02)+.6*bump(t,2.13,2.19,2.32)))
    return f

def attack(t):
    f=Frame();wind=hold(t,0,.25,.31,.46)
    hit=key(t,(0,0),(.31,0),(.48,1),(.54,.96),(.73,-.17),(.92,.07),(1.15,0))
    settle=bump(t,.54,.68,1.12)
    body(f,x=28*wind-102*hit,sx=.055*wind+.042*hit,sy=-.068*wind-.022*hit)
    f.P.add('head',x=7*wind-19*hit,r=-2*wind+3.3*hit)
    f.P.add('belly',sx=.03*wind+.065*settle,sy=-.025*wind-.035*settle)
    arm=key(t,(0,0),(.27,-.3),(.48,1),(.55,1),(.76,-.12),(1.08,0),(1.15,0))
    f.P.add('arm_far',r=-17*arm,x=-30*arm,y=14*arm)
    f.P.add('arm_near',r=-13*arm,x=-24*arm,y=8*arm)
    f.P.add('foot_l',x=-16*hit);f.P.add('foot_r',x=-25*hit,y=11*bump(t,.30,.45,.68))
    f.P.add('nozzle',sx=-.035*wind+.035*hit);f.P.add('eye_near',sy=-.18*wind)
    crowns(f,t,.37,.61,1.04,3.0);return f

def cast(t):
    f=Frame();inhale=hold(t,0,.38,.49,.70)
    squeeze=key(t,(0,0),(.49,0),(.64,1),(.81,.82),(1.04,-.16),(1.27,.06),(1.5,0))
    recoil=bump(t,.60,.74,1.12)
    body(f,x=8*inhale+24*recoil,sx=.025*inhale+.034*squeeze,sy=.038*inhale-.062*squeeze)
    f.P.add('belly',sx=.065*inhale-.070*squeeze,sy=.046*inhale-.050*squeeze)
    f.P.add('head',x=-24*squeeze,y=8*inhale,r=1.8*squeeze)
    f.P.add('nozzle',x=-9*squeeze,sx=-.07*inhale+.24*squeeze,sy=-.06*inhale+.105*squeeze)
    f.P.add('eye_far',sy=-.23*inhale-.14*recoil);f.P.add('eye_near',sy=-.28*inhale-.12*recoil)
    f.P.add('arm_far',r=8*inhale-3*squeeze,x=4*inhale);f.P.add('arm_near',r=-8*inhale+3*squeeze,x=3*inhale)
    crowns(f,t,.50,.80,1.40,3.1);return f

def soak(t):
    f=Frame();crouch=hold(t,0,.25,.43,.65);gulp=bump(t,.32,.56,.91)
    swell=key(t,(0,0),(.36,0),(.64,1),(.80,.86),(1.02,-.13),(1.35,0))
    body(f,sx=.052*crouch+.022*swell,sy=-.07*crouch+.042*swell)
    f.P.add('belly',sx=.07*swell,sy=.055*swell);f.P.add('head',y=-9*crouch+7*swell,r=-1.6*crouch)
    f.P.add('nozzle',sx=-.10*gulp,sy=-.07*gulp)
    f.P.add('eye_far',sy=-.30*gulp);f.P.add('eye_near',sy=-.33*gulp)
    f.P.add('arm_far',r=7*crouch-3*swell);f.P.add('arm_near',r=-7*crouch+3*swell)
    crowns(f,t,.46,.78,1.25,2.8);return f

def hurt(t):
    f=Frame();h=key(t,(0,0),(.075,1),(.16,.65),(.30,-.20),(.43,.07),(.58,0))
    body(f,x=36*h,sx=-.048*h,sy=.027*h)
    f.P.add('head',x=9*h,r=-3.7*h);f.P.add('belly',sx=-.035*h,sy=.035*h);f.P.add('nozzle',sy=.085*h)
    f.P.add('eye_far',sy=-.20*bump(t,.02,.10,.30));f.P.add('eye_near',sy=-.24*bump(t,.02,.10,.32))
    crowns(f,t,.04,.18,.44,3.0);return f

def death(u):
    f=Frame();h=ease(u);body(f,sx=.15*h,sy=-.62*h)
    # Feet share the final affine squash so the ankle blend does not fold.
    f.P.add('foot_l',x=-38.4*h,y=-21.08*h,sx=.15*h,sy=-.62*h)
    f.P.add('foot_r',x=37.8*h,y=-17.36*h,sx=.15*h,sy=-.62*h)
    f.P.add('belly',sx=.05*h,sy=-.06*h);f.P.add('head',r=-5*h)
    f.P.add('eye_far',sy=-.35*h);f.P.add('eye_near',sy=-.38*h)
    f.P.add('arm_far',r=5*h);f.P.add('arm_near',r=-5*h)
    f.tint=(1-.20*h,1-.19*h,1-.16*h,1);return f

def die(t):
    f=death(seg(t,.12,1.2));h=bump(t,0,.12,.36)
    f.P.add('head',r=-3*h);f.P.add('nozzle',sy=.04*h);return f

def revive(t):return death(1-ease(seg(t,0,1.4)))

def summon(t):
    f=Frame();h=key(t,(0,1),(.27,1.08),(.55,-.26),(.82,.10),(1.2,0))
    body(f,sx=.07*h,sy=-.12*h);f.P.add('belly',sx=.045*h,sy=-.035*h)
    crowns(f,t,.29,.58,1.10,3.0);return f

def power_up(t):
    f=Frame();charge=bump(t,0,.32,.62);rise=bump(t,.27,.57,1.2)
    body(f,sx=.03*charge-.018*rise,sy=-.04*charge+.045*rise)
    f.P.add('belly',sx=.065*rise,sy=.04*rise);f.P.add('head',y=5*rise);f.P.add('nozzle',sx=.065*rise)
    f.P.add('arm_far',r=-5*rise);f.P.add('arm_near',r=5*rise)
    crowns(f,t,.32,.69,1.10,2.2);return f

FUNCS={'idle_loop':idle,'attack':attack,'cast':cast,'soak':soak,'hurt':hurt,
       'die':die,'revive':revive,'summon':summon,'power_up':power_up}
