"""Anchored suction, travelling muscle waves and asynchronous soft-body recovery."""
import math
from rigutil import Frame, TAU, key, hold, bump, ease, seg
ANIMS={'idle_loop':(4.,True),'attack':(1.12,False),'cast':(1.45,False),'curl':(1.1,False),
       'feed':(.85,False),'hurt':(.6,False),'die':(1.5,False),'revive':(1.4,False),
       'summon':(1.2,False),'power_up':(1.3,False)}
EVENTS={'attack':[('bite_contact',.46)],'cast':[('parasite_release',.62)],
        'curl':[('curl_contact',.38)],'feed':[('blood_return',.30)],'die':[('collapse',1.2)]}

def wave(t,phase=0,period=4):return math.sin(TAU*t/period-phase)-math.sin(-phase)

def body(f,x=0,sx=0,sy=0):
    # Keep the rear suction pad planted under the moving front mass.
    f.P.add('body',x=x,y=171*sy,sx=sx,sy=sy)
    f.P.add('sucker',x=-(x+157*sx)/(1+sx),y=-38*sy/(1+sy),sx=1/(1+sx)-1,sy=1/(1+sy)-1)

def tail_wave(f,t,start,peak,end,strength):
    for i in range(4):
        lag=i*.035;f.P.add(f'tail_{i}',r=strength*(.42+i*.2)*bump(t,start+lag,peak+lag,end+lag))

def idle(t):
    f=Frame();w=wave(t);body(f,sx=.014*w,sy=-.012*w)
    f.P.add('belly',sx=.026*wave(t,.55),sy=.039*wave(t,.55))
    for i in range(3):
        h=wave(t,.3+i*.7);f.P.add(f'neck_{i}',r=.8*h,sx=.007*h,sy=.013*h)
    for i in range(4):f.P.add(f'tail_{i}',r=(.85+i*.20)*wave(t,.8+i*.55))
    f.P.add('head',r=-.9*wave(t,1.05),y=2*wave(t,1.3))
    f.P.add('mouth',sx=.025*wave(t,.45,2),sy=.018*wave(t,.45,2));f.P.add('lip_lower',y=-1.8*wave(t,.7,2))
    f.P.add('eye_far',sy=-.49*bump(t,2.12,2.21,2.42));f.P.add('eye_near',sy=-.52*bump(t,2.16,2.25,2.46))
    return f

def attack(t):
    f=Frame();wind=hold(t,0,.22,.27,.43)
    reach=key(t,(0,0),(.27,0),(.46,1),(.57,1),(.76,-.12),(.95,.04),(1.12,0))
    body(f,x=20*wind-44*reach,sx=-.048*wind+.026*reach,sy=.032*wind-.023*reach)
    for i,n in enumerate(['neck_0','neck_1','neck_2']):f.P.add(n,x=7*wind-(16+i*3)*reach,r=-(1.6-i*.3)*wind+(2.7-i*.55)*reach)
    f.P.add('head',x=-25*reach,y=-6*reach,r=-4.3*reach+2*wind)
    opened=hold(t,.14,.34,.42,.55);seal=bump(t,.43,.51,.77)
    f.P.add('mouth',sx=.14*opened-.062*seal,sy=.09*opened-.075*seal)
    f.P.add('lip_upper',y=6*opened-3*seal);f.P.add('lip_lower',y=-7*opened+3*seal)
    f.P.add('belly',sx=-.028*reach,sy=.018*wind)
    tail_wave(f,t,.27,.54,1.0,4.0);return f

def cast(t):
    f=Frame();crouch=hold(t,0,.28,.37,.67)
    cough=key(t,(0,0),(.48,0),(.62,1),(.69,.84),(.86,-.16),(1.13,.045),(1.45,0))
    body(f,x=15*crouch+12*cough,sx=-.036*crouch,sy=.038*crouch-.025*cough)
    f.P.add('belly',sx=.058*bump(t,.05,.26,.58),sy=.075*bump(t,.05,.26,.58))
    for i in range(3):
        h=bump(t,.13+i*.075,.34+i*.075,.69+i*.075)
        f.P.add(f'neck_{i}',sx=.022*h,sy=.041*h,r=(-1 if i%2==0 else 1)*2*h,x=-8*cough)
    f.P.add('head',y=13*crouch-5*cough,x=-18*cough,r=1.5*crouch)
    f.P.add('mouth',sx=.14*cough,sy=.105*cough);f.P.add('lip_upper',y=4*cough);f.P.add('lip_lower',y=-8*cough)
    f.P.add('eye_near',sy=-.20*crouch);tail_wave(f,t,.34,.69,1.30,-4.0);return f

def curl(t):
    f=Frame();h=hold(t,0,.38,.64,1.1);body(f,x=17*h,sx=-.070*h,sy=.042*h)
    f.P.add('neck_0',r=5*h,x=10*h);f.P.add('neck_1',r=4.2*h);f.P.add('neck_2',r=-2*h)
    f.P.add('head',r=-7*h,y=-21*h,x=12*h)
    f.P.add('tail_0',r=-2.5*h);f.P.add('tail_1',r=3.5*h);f.P.add('tail_2',r=7*h);f.P.add('tail_3',r=6*h)
    f.P.add('mouth',sx=-.08*h,sy=-.07*h);f.P.add('eye_far',sy=-.24*h);f.P.add('eye_near',sy=-.27*h);return f

def feed(t):
    f=Frame();swallowed=bump(t,.12,.30,.85);body(f,sx=.017*swallowed,sy=.027*swallowed)
    f.P.add('mouth',sx=-.065*bump(t,0,.12,.34),sy=-.07*bump(t,0,.12,.34))
    for i in range(3):
        delay=(2-i)*.065;h=bump(t,.02+delay,.15+delay,.50+delay)
        f.P.add(f'neck_{i}',sx=.015*h,sy=.045*h)
    f.P.add('belly',sx=.075*swallowed,sy=.115*swallowed)
    f.P.add('eye_far',sy=-.21*swallowed);f.P.add('eye_near',sy=-.28*swallowed)
    tail_wave(f,t,.12,.37,.72,2.2);return f

def hurt(t):
    f=Frame();h=key(t,(0,0),(.08,1),(.17,.65),(.31,-.17),(.46,.055),(.6,0))
    body(f,x=33*h,sx=-.042*h,sy=.035*h)
    f.P.add('neck_0',r=-2*h);f.P.add('neck_1',r=-1.4*h);f.P.add('head',r=-2.5*h,x=7*h)
    f.P.add('mouth',sy=.09*h);f.P.add('eye_near',sy=-.25*bump(t,0,.10,.35))
    tail_wave(f,t,.02,.16,.48,4.0);return f

def death(u):
    f=Frame();h=ease(u)
    # Death releases the rear pad; the entire body shares the final collapse.
    f.P.add('body',y=-121*h,x=20*h,sx=.10*h,sy=-.65*h)
    f.P.add('neck_0',r=-4*h);f.P.add('head',r=-9*h)
    f.P.add('eye_far',sy=-.38*h);f.P.add('eye_near',sy=-.42*h)
    f.P.add('mouth',sy=-.1*h);f.P.add('tail_2',r=5*h)
    f.tint=(1-.25*h,1-.25*h,1-.2*h,1);return f

def die(t):
    f=death(seg(t,.10,1.2));f.P.add('mouth',sy=.06*bump(t,0,.12,.33));return f

def revive(t):return death(1-ease(seg(t,0,1.4)))

def summon(t):
    f=Frame();arrive=1-ease(seg(t,0,.78));settle=bump(t,.53,.76,1.2)
    f.P.add('body',x=82*arrive,y=-12*arrive,sx=-.13*arrive+.03*settle,sy=-.07*arrive)
    f.P.add('neck_0',r=4*arrive-1.5*settle);tail_wave(f,t,.30,.67,1.08,-3.2);return f

def power_up(t):
    f=Frame();gather=bump(t,0,.28,.6);swell=bump(t,.20,.54,1.3)
    body(f,sx=-.024*gather+.028*swell,sy=.05*swell)
    f.P.add('belly',sx=.075*swell,sy=.09*swell);f.P.add('neck_0',r=-1.8*swell);f.P.add('head',y=10*swell)
    f.P.add('mouth',sx=-.035*gather+.04*swell);tail_wave(f,t,.30,.65,1.18,3.0);return f

FUNCS={'idle_loop':idle,'attack':attack,'cast':cast,'curl':curl,'feed':feed,'hurt':hurt,
       'die':die,'revive':revive,'summon':summon,'power_up':power_up}
