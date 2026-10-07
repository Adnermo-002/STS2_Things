"""Authored anticipation, contact holds, two-stage swallowing and soft recovery."""
import math
from rigutil import Frame,TAU,key,hold,bump,seg,ease,kick

ANIMS={'idle_loop':(6.,True),'attack':(1.35,False),'cast':(1.6,False),'devour':(2.1,False),
       'press':(1.5,False),'empty':(1.15,False),'power_up':(1.4,False),'hurt':(.6,False),
       'die':(1.9,False),'revive':(1.7,False),'summon':(1.6,False)}
EVENTS={'attack':[('bite_hit',.48)],'cast':[('offer_debris',.54),('offer_debris',.74)],
        'devour':[('inhale',.50),('meal_settles',1.4)],
        'press':[('press_hit',.44),('press_hit',.80)],'die':[('mouth_closes',1.30)]}


def wave(t,period=6,phase=0):
    return math.sin(TAU*t/period-phase)-math.sin(-phase)


def tongue(f,**params):
    f.extra['tongue']=params


def jaw(f,opening=0,closing=0,lean=0):
    f.P.add('back_base',y=34*opening-58*closing,r=.65*lean)
    f.P.add('front_base',y=-6*opening+26*closing)
    f.P.add('throat',sy=.065*opening-.15*closing,y=-8*closing)
    f.P.add('throat_up',y=-5*closing)
    f.P.add('throat_low',sy=-.06*closing,y=5*closing)
    f.P.add('cheek_left',x=-4.5*opening+3*closing)
    f.P.add('cheek_right',x=4.5*opening-3*closing)
    f.P.add('cheek_left_fold',r=-1.3*opening+1.6*closing)
    f.P.add('cheek_right_fold',r=1.1*opening-1.3*closing)
    for i in range(6):
        arch=1-abs(i-2.5)/3
        f.P.add(f'back_{i}',y=3.5*arch*opening,r=(i-2.5)*.12*opening)
        f.P.add(f'front_{i}',r=-(i-2.5)*.12*closing)


def lip_wave(f,t,start,peak,end,amount=1,reverse=False):
    for i in range(6):
        lag=(5-i if reverse else i)*.021
        v=bump(t,start+lag,peak+lag,end+lag)*amount
        f.P.add(f'back_{i}',y=-2.5*v)
        f.P.add(f'front_{i}',y=3.8*v)


def settle(f,t,start,end,gain=1):
    v=kick(t,start,3.2,9)*(1-ease(seg(t,end-.15,end)))*gain
    f.P.add('cheek_left_fold',r=1.2*v)
    f.P.add('cheek_right_fold',r=-1.0*v)
    f.P.add('plate_front',r=-1.1*v)
    f.P.add('plate_right',r=.9*v)


def blink(f,t,start,amount=1,delay=.025):
    for name,lag in [('eye_far',0),('eye_near',delay)]:
        close=key(t,(0,0),(start+lag,0),(start+.055+lag,1),
                  (start+.115+lag,.98),(start+.265+lag,0))
        f.P.add(name+'_lid',sy=-.95*close*amount)


def idle(t):
    f=Frame()
    breath=wave(t,3)
    f.P.add('back_base',y=2.1*breath)
    f.P.add('front_base',y=.8*wave(t,3,.65))
    f.P.add('throat',sy=.012*wave(t,3,.9))
    for i in range(6):
        f.P.add(f'back_{i}',y=.8*wave(t,6,i*.43))
        f.P.add(f'front_{i}',y=.9*wave(t,6,.7+i*.4))
    glance=bump(t,3.05,3.90,5.55)
    f.P.add('brow_near',r=-1.1*glance,y=1.3*glance)
    f.P.add('brow_far',r=.5*glance,y=.6*glance)
    tongue(f,reach=1.8*wave(t,6,.4),lift=1.6*wave(t,3,.8),
           curl=2.4*wave(t,6,1.2),ripple=.7,phase=TAU*t/3)
    blink(f,t,1.65)
    blink(f,t,4.45,.8,delay=.045)
    return f


def attack(t):
    f=Frame()
    wind=hold(t,0,.23,.31,.47)
    hit=key(t,(0,0),(.345,0),(.48,1),(.525,.99),(.76,-.12),(1.10,.025),(1.35,0))
    jaw(f,opening=.63*wind,closing=.91*hit,lean=-.55*wind+.7*hit)
    f.P.add('back_0',x=-8*hit)
    f.P.add('front_0',x=-5*hit)
    f.P.add('cheek_left_fold',r=1.3*hit)
    f.P.add('brow_near',r=-1.4*wind,y=1.4*wind)
    tongue(f,reach=-16*wind-18*hit,lift=-32*hit,curl=-14*hit,
           ripple=1.3*bump(t,.40,.61,1.02),phase=(t-.4)*14,bulk=.7*hit)
    lip_wave(f,t,.36,.48,.73,.55)
    settle(f,t,.55,1.35,.65)
    blink(f,t,.425,.38)
    return f


def cast(t):
    f=Frame()
    wind=hold(t,0,.24,.32,.51)
    first=bump(t,.35,.54,.70)
    second=key(t,(0,0),(.62,0),(.74,1),(.82,.7),(1.08,-.10),(1.6,0))
    offer=first+.75*second
    jaw(f,opening=.65*offer,closing=.32*wind,lean=-.6*offer)
    tongue(f,reach=-14*wind+31*first+22*second,
           lift=11*first+8*second,curl=12*first+7*second,
           ripple=.8*bump(t,.4,.80,1.3),phase=t*12)
    f.P.add('brow_near',y=3*offer,r=-.9*offer)
    f.P.add('brow_far',y=2*offer,r=.6*offer)
    f.P.add('eye_near',sy=.035*offer)
    f.P.add('eye_far',sy=.025*offer)
    lip_wave(f,t,.45,.60,.93,.45,reverse=True)
    settle(f,t,.85,1.6,.45)
    return f


def devour(t):
    f=Frame()
    inhale=hold(t,0,.30,.93,1.31)
    pull=hold(t,.22,.65,1.23,1.98)
    first=bump(t,1.06,1.21,1.40)
    second=bump(t,1.22,1.40,1.84)
    gulp=.26*first+.83*second
    jaw(f,opening=1.06*inhale,closing=gulp)
    tongue(f,reach=-52*pull,lift=-15*pull-18*gulp,curl=-9*gulp,
           ripple=2.4*bump(t,.61,1.18,1.78),phase=(t-.5)*11,bulk=1.4*gulp)
    lip_wave(f,t,.90,1.19,1.48,.55,reverse=True)
    lip_wave(f,t,1.21,1.40,1.77,.9)
    f.P.add('throat_low',y=6*first-4*second)
    f.P.add('brow_near',y=2*inhale-2*gulp,r=.5*gulp)
    f.P.add('brow_far',y=1.3*inhale-1.5*gulp)
    f.P.add('plate_front',r=.9*bump(t,1.38,1.54,1.98))
    settle(f,t,1.50,2.1,.6)
    blink(f,t,1.32,.8)
    return f


def press(t):
    f=Frame()
    wind=hold(t,0,.23,.29,.43)
    brace=hold(t,.13,.30,.94,1.35)
    a=bump(t,.30,.44,.60)
    b=key(t,(0,0),(.65,0),(.80,1),(.855,.95),(1.11,-.1),(1.5,0))
    jaw(f,opening=.38*wind+.14*bump(t,.55,.63,.76),
        closing=.08*brace+.80*a+1.02*b,lean=.60*a-.75*b)
    f.P.add('cheek_left_fold',r=2.0*a)
    f.P.add('cheek_right_fold',r=-2.3*b)
    f.P.add('brow_near',r=1.2*a-1.2*b)
    tongue(f,reach=-8*brace-20*b,lift=-26*a-36*b,curl=-12*(a+b),
           ripple=1.0*bump(t,.34,.80,1.21),phase=t*16,bulk=.8*(a+b))
    lip_wave(f,t,.32,.44,.63,.65)
    lip_wave(f,t,.69,.80,1.06,.9,reverse=True)
    settle(f,t,.88,1.5,.65)
    blink(f,t,.735,.45)
    return f


def empty(t):
    f=Frame()
    search=bump(t,0,.30,.83)
    jaw(f,opening=.26*search,lean=.42*search)
    tongue(f,reach=15*search,lift=3*search,curl=8*search)
    f.P.add('brow_near',y=4*bump(t,.23,.51,.95),r=-2*bump(t,.23,.51,.95))
    f.P.add('brow_far',y=-1.1*search,r=1.2*search)
    blink(f,t,.54,.90,delay=.065)
    return f


def power_up(t):
    f=Frame()
    h=key(t,(0,0),(.18,-.1),(.48,1),(.66,.91),(1.04,-.07),(1.4,0))
    jaw(f,opening=.34*h,closing=-.08*h)
    tongue(f,reach=-10*h,lift=5*h,curl=5*h,bulk=1.3*h)
    lip_wave(f,t,.27,.49,.98,.65)
    f.P.add('brow_near',y=2.5*h,r=-1.0*h)
    f.P.add('brow_far',y=1.2*h)
    settle(f,t,.72,1.4,.45)
    blink(f,t,.65,.40)
    return f


def hurt(t):
    f=Frame()
    h=key(t,(0,0),(.065,1),(.135,.7),(.29,-.13),(.44,.025),(.6,0))
    jaw(f,closing=.29*h,lean=-.45*h)
    f.P.add('back_0',x=5*h,y=-2.5*h)
    f.P.add('front_1',y=2.5*h)
    f.P.add('cheek_left_fold',r=2.4*h)
    f.P.add('brow_near',r=1.6*h,y=-1.5*h)
    tongue(f,reach=-15*h,lift=-7*h,curl=-4*h)
    settle(f,t,.13,.6,.65)
    blink(f,t,.012,.8)
    return f


def collapse(f,h):
    jaw(f,closing=1.6*h)
    tongue(f,reach=-135*h,lift=-80*h,curl=-20*h,fold=.7*h)
    f.P.add('throat',sy=-.17*h)
    f.P.add('brow_far',y=-4*h,r=1.7*h)
    f.P.add('brow_near',y=-5*h,r=-1.6*h)
    for n in ('eye_far','eye_near'):f.P.add(n+'_lid',sy=-.97*h)
    for i in range(6):f.P.add(f'back_{i}',y=-4*h)


def die(t):
    f=Frame()
    collapse(f,key(t,(0,0),(.12,.025),(.65,.46),(1.30,1),(1.9,1)))
    f.P.add('front_2',y=2*bump(t,1.07,1.34,1.76))
    f.P.add('plate_right',r=1.2*bump(t,.79,1.29,1.85))
    return f


def revive(t):
    f=Frame()
    collapse(f,1-ease(seg(t,.17,1.41)))
    if t>.55:
        h=bump(t,.55,1.06,1.70)
        f.P.add('brow_near',y=2*h,r=-1.2*h)
    return f


def summon(t):
    f=Frame()
    collapse(f,.72*(1-ease(seg(t,0,1.24))))
    f.P.add('brow_near',y=2*bump(t,.60,1.02,1.50))
    blink(f,t,1.13,.45)
    return f


FUNCS={n:globals()['idle' if n=='idle_loop' else n] for n in ANIMS}
