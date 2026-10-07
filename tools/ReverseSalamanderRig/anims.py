"""Authored weight, traveling tail arcs and overlapping recovery, baked at 60 Hz.

Contact times match ReverseSalamander.cs. Feet use world-space targets, so body
compression does not slide the toes. Torso controls preserve painted volume;
tail crests and gill tips follow the main action with a delay.
"""
import math
from rigutil import Frame, TAU, key, bump, hold, seg, ease, kick

ANIMS = {
    'idle_loop': (6.0, True), 'attack': (1.4, False), 'tide': (1.55, False),
    'roll': (1.65, False), 'gather': (1.55, False), 'recall': (1.4, False),
    'cast': (1.4, False), 'power_up': (1.5, False), 'hurt': (.65, False),
    'die': (2.0, False), 'revive': (1.8, False), 'summon': (1.6, False),
}
EVENTS = {
    'attack': [('tail_hit', .50)], 'tide': [('water_hit', .56)],
    'roll': [('water_hit', .46), ('water_hit', .74), ('water_hit', 1.02)],
    'gather': [('water_hit', .56), ('water_shield', 1.20)],
    'recall': [('card_returns', .54)], 'cast': [('card_returns', .54)],
    'power_up': [('current_grows', .48)], 'die': [('body_settles', 1.35)],
}


def wave(t, period=6, phase=0):
    return math.sin(TAU*t/period-phase)-math.sin(-phase)


def finish(t, duration, length=.18):
    return 1-ease(seg(t, duration-length, duration))


def body(f, compression=0, extension=0):
    """Local volume shifts, not a scale of the complete animal."""
    f.P.add('chest', y=-3.8*compression+2.6*extension, sx=.012*compression, sy=-.016*compression)
    f.P.add('back', y=-4.5*compression+3.2*extension, r=-.45*compression)
    f.P.add('belly', sx=.018*compression-.01*extension, sy=-.014*compression+.018*extension)
    f.P.add('haunch', sx=.012*compression, sy=-.01*compression, y=-2*compression)


def tail_wave(f, t, drive, duration, gain=1, delay=.027):
    """Root leads, the neck of the curl follows, then each crest rolls over."""
    envelope = finish(t, duration)
    for i in range(7):
        follow=drive(max(0,t-i*delay))*gain*envelope
        f.P.add(f'tail_{i}', r=(1.45+i*.24)*follow)
    for i,n in enumerate(('fin_a','fin_b','fin_c')):
        u=max(0,t-.16-i*.019)
        f.P.add(n, r=(-1 if i==0 else 1)*3.8*drive(u)*gain*envelope)
        f.P.add(n+'_tip', r=(1 if i==0 else -1)*3.0*drive(max(0,u-.055))*gain*envelope)


def gills(f, t, drive, duration, gain=1):
    for i in range(3):
        f.P.add(f'gill_{i}', r=(2.3+i*.35)*drive(max(0,t-i*.021))*gain*finish(t,duration))
        f.P.add(f'gill_{i}_tip', r=(3.0+i*.4)*drive(max(0,t-.064-i*.026))*gain*finish(t,duration))


def foot(f, name, x=0, lift=0, pitch=0, curl=0):
    f.extra.setdefault('feet',{})[name]=(x,lift,pitch)
    f.P.add(name+'_toe', r=curl)


def step(f, t, name, distance, start, contact, return_start, end, lift=14):
    # Travel only while airborne. The target is still throughout contact.
    x=distance*hold(t,start,contact,return_start,end)
    outbound=bump(t,start,(start+contact)/2,contact)
    inbound=bump(t,return_start,(return_start+end)/2,end)
    foot(f,name,x,lift*(outbound+.7*inbound),-4*outbound+3*inbound,5*outbound-3*inbound)


def blink(f, t, start, strength=1):
    # Asymmetric closing and reopening; preserve a little socket thickness.
    near=key(t,(0,0),(start,0),(start+.055,1),(start+.105,.96),(start+.22,0))
    far=key(t,(0,0),(start+.015,0),(start+.070,1),(start+.12,.96),(start+.24,0))
    f.P.add('eye_near',sy=-.69*near*strength,y=-2.5*near*strength)
    f.P.add('eye_far',sy=-.65*far*strength,y=-2*far*strength)


def idle(t):
    f=Frame()
    breath=wave(t,3)
    f.P.add('pelvis',y=1.8*breath,x=.8*wave(t,6,.8))
    f.P.add('body',r=.30*wave(t,6),y=1.1*wave(t,3,.3))
    f.P.add('chest',sy=.008*wave(t,3,.22),y=1.5*wave(t,3,.22))
    f.P.add('belly',sx=.008*breath,sy=.014*breath)
    f.P.add('back',y=1.2*wave(t,3,.65))
    look=bump(t,3.35,4.18,5.6)
    f.P.add('neck',r=-.35*look)
    f.P.add('head',r=.34*wave(t,6,.8)-.5*look)
    f.P.add('jaw',y=-.8*wave(t,3,.65))
    f.P.add('eye_near',x=-1.2*look)
    f.P.add('eye_far',x=-.6*look)
    for i in range(7):
        f.P.add(f'tail_{i}',r=(.48+i*.105)*wave(t,6,.46+i*.46))
    for i,n in enumerate(('fin_a','fin_b','fin_c')):
        f.P.add(n,r=(1.05+i*.2)*wave(t,3,1.2+i*.4))
        f.P.add(n+'_tip',r=(1.4+i*.2)*wave(t,3,1.9+i*.4))
    for i in range(3):
        f.P.add(f'gill_{i}',r=(1.1+i*.15)*wave(t,3,.5+i*.24))
        f.P.add(f'gill_{i}_tip',r=(1.6+i*.2)*wave(t,3,1.0+i*.24))
    blink(f,t,2.25)
    blink(f,t,4.93,.65)
    return f


def attack(t):
    f=Frame()
    wind=hold(t,0,.24,.31,.47)
    hit=key(t,(0,0),(.31,0),(.50,1),(.56,.96),(.81,-.13),(1.13,.035),(1.40,0))
    f.P.add('pelvis',x=20*wind-48*hit,y=-11*wind-5*hit)
    f.P.add('body',r=-1.6*wind+2.6*hit)
    body(f,wind+.4*hit,hit)
    f.P.add('neck',r=1.6*hit)
    f.P.add('head',r=-1.6*wind+1.2*key(t,(0,0),(.39,0),(.57,1),(.82,-.2),(1.25,0)))
    f.P.add('muzzle',x=-4.5*hit)
    f.P.add('jaw',r=-1.4*bump(t,.36,.52,.84))
    drive=lambda u: -.9*hold(u,0,.22,.28,.43)+1.5*key(u,(0,0),(.28,0),(.45,1),(.51,.95),(.77,-.24),(1.04,.045),(1.23,0))
    tail_wave(f,t,drive,1.4)
    gills(f,t,lambda u: -.4*hold(u,0,.24,.3,.46)+.75*bump(u,.44,.63,1.10),1.4)
    step(f,t,'front_near',-28,.22,.48,.83,1.21,17)
    step(f,t,'front_far',-15,.29,.51,.92,1.30,11)
    foot(f,'hind_near',pitch=3*wind,curl=-2*wind)
    foot(f,'hind_far',pitch=1.8*wind,curl=-1.5*wind)
    blink(f,t,.43,.20)
    return f


def tide(t):
    f=Frame()
    wind=hold(t,0,.27,.40,.55)
    release=key(t,(0,0),(.38,0),(.56,1),(.66,.85),(.99,-.12),(1.37,0))
    f.P.add('pelvis',y=-16*wind+9*release,x=9*wind-22*release)
    f.P.add('body',r=-1.1*wind+1.7*release)
    body(f,wind,release)
    f.P.add('neck',r=1.8*release,y=3*release)
    f.P.add('head',r=-1.5*wind+1.2*release)
    f.P.add('jaw',r=-2.3*release)
    drive=lambda u: -1.0*hold(u,0,.26,.35,.50)+1.3*key(u,(0,0),(.35,0),(.49,1),(.61,.8),(.89,-.20),(1.27,0))
    tail_wave(f,t,drive,1.55,1.08,.035)
    gills(f,t,lambda u: .65*bump(u,.4,.64,1.3),1.55)
    for name in ('front_near','front_far'):
        foot(f,name,pitch=-1.5*release,curl=2*wind)
    blink(f,t,.48,.27)
    return f


def roll(t):
    f=Frame()
    wind=hold(t,0,.23,.28,.42)
    # Three progressively heavier contacts; the body stays braced.
    a=bump(t,.29,.46,.60)
    b=bump(t,.58,.74,.89)
    c=key(t,(0,0),(.86,0),(1.02,1),(1.08,.95),(1.30,-.12),(1.65,0))
    h=.55*a+.78*b+c
    brace=hold(t,0,.26,1.08,1.52)
    f.P.add('pelvis',x=12*wind-26*h,y=-8*brace-4*h)
    f.P.add('body',r=1.7*h)
    body(f,.5*brace+.3*h,.3*h)
    f.P.add('neck',r=-1.05*h)
    f.P.add('head',r=-.65*h+.25*kick(t,1.02,3,9)*finish(t,1.65))
    f.P.add('jaw',r=-1.4*h)
    drive=lambda u: (-.7*hold(u,0,.21,.26,.39)+1.15*bump(u,.27,.405,.57)
                     -1.22*bump(u,.55,.685,.84)+1.62*bump(u,.82,.965,1.29))
    tail_wave(f,t,drive,1.65,1,.024)
    gills(f,t,lambda u: .4*bump(u,.3,.50,.65)+.55*bump(u,.61,.79,.94)+.75*bump(u,.9,1.12,1.48),1.65)
    step(f,t,'front_near',-15,.10,.30,1.15,1.52,11)
    foot(f,'hind_near',pitch=1.5*brace,curl=-2*brace)
    blink(f,t,.96,.2)
    return f


def gather(t):
    f=Frame()
    wind=hold(t,0,.27,.4,.55)
    hit=bump(t,.37,.56,.87)
    brace=hold(t,.67,.96,1.21,1.55)
    f.P.add('pelvis',x=8*wind-20*hit+4*brace,y=-11*wind-18*brace)
    f.P.add('body',r=1.2*hit-.7*brace)
    body(f,wind+brace,hit)
    f.P.add('neck',y=-3*brace,r=1.2*brace)
    f.P.add('head',r=-1.0*hit+1.2*brace)
    f.P.add('belly',sx=.024*brace)
    drive=lambda u: -.6*hold(u,0,.27,.38,.51)+.8*bump(u,.4,.52,.79)-.9*hold(u,.70,.95,1.14,1.36)
    tail_wave(f,t,drive,1.55)
    gills(f,t,lambda u: -.6*hold(u,.68,.98,1.20,1.40)+.25*bump(u,.40,.61,.83),1.55)
    for name in ('front_near','hind_near','front_far','hind_far'):
        foot(f,name,pitch=(-1.6 if name.startswith('front') else 1.6)*brace,curl=2*brace)
    blink(f,t,1.13,.35)
    return f


def recall(t):
    f=Frame()
    rise=key(t,(0,0),(.17,-.18),(.54,1),(.68,.83),(1.03,-.1),(1.4,0))
    f.P.add('pelvis',y=7*rise,x=3*rise)
    f.P.add('body',r=-.7*rise)
    body(f,0,.6*rise)
    f.P.add('neck',r=-1.0*rise)
    f.P.add('head',r=-1.5*rise,y=1.5*rise)
    f.P.add('eye_near',sy=.09*bump(t,.27,.54,.92))
    f.P.add('eye_far',sy=.065*bump(t,.30,.58,.96))
    drive=lambda u: key(u,(0,0),(.14,-.25),(.36,.85),(.5,1),(.83,-.18),(1.18,0))
    tail_wave(f,t,drive,1.4,1.18,.040)
    gills(f,t,lambda u: .7*bump(u,.26,.6,1.22),1.4)
    return f


def cast(t):
    return recall(t)


def power_up(t):
    f=Frame()
    swell=key(t,(0,0),(.18,-.13),(.48,1),(.68,.94),(1.11,-.07),(1.5,0))
    f.P.add('pelvis',y=10*swell)
    f.P.add('body',r=-.8*swell)
    body(f,0,swell)
    f.P.add('belly',sx=.023*swell,sy=.024*swell)
    f.P.add('neck',r=-1.4*swell)
    f.P.add('head',r=-1.3*swell)
    tail_wave(f,t,lambda u: .9*bump(u,.14,.40,1.18),1.5,1,.033)
    gills(f,t,lambda u: 1.15*bump(u,.16,.49,1.29),1.5)
    blink(f,t,.57,.3)
    return f


def hurt(t):
    f=Frame()
    recoil=key(t,(0,0),(.075,1),(.15,.75),(.32,-.16),(.49,.035),(.65,0))
    f.P.add('pelvis',x=23*recoil,y=-5*recoil)
    f.P.add('body',r=-1.5*recoil)
    body(f,.65*recoil)
    f.P.add('neck',r=-2.5*recoil)
    f.P.add('head',r=-1.1*key(t,(0,0),(.10,1),(.19,.55),(.37,-.15),(.65,0)))
    tail_wave(f,t,lambda u: -.65*key(u,(0,0),(.08,1),(.16,.6),(.32,-.22),(.48,0)),.65,.8,.013)
    gills(f,t,lambda u: -.9*bump(u,0,.085,.43),.65)
    blink(f,t,.015,.72)
    return f


def fallen(f, h):
    f.P.add('pelvis',y=-34*h,x=5*h)
    f.P.add('body',r=1.2*h)
    body(f,1.8*h)
    f.P.add('belly',sy=-.065*h,sx=.025*h)
    f.P.add('neck',r=2.5*h,y=-8*h)
    f.P.add('head',r=2*h,y=-2*h)
    f.P.add('eye_near',sy=-.72*h)
    f.P.add('eye_far',sy=-.68*h)
    for i in range(3):
        f.P.add(f'gill_{i}',r=-(4.5+i*.5)*h)
        f.P.add(f'gill_{i}_tip',r=-3*h)
    for i in range(7):
        f.P.add(f'tail_{i}',r=(2.4+i*.34)*h)
    for n in ('fin_a','fin_b','fin_c'):
        f.P.add(n,r=4*h)
        f.P.add(n+'_tip',r=5*h)


def die(t):
    f=Frame()
    h=ease(seg(t,.13,1.35))
    fallen(f,h)
    # The body lands, then the heavy crest finishes settling.
    f.P.add('head',y=-4*bump(t,.88,1.18,1.72))
    f.P.add('jaw',r=-1.4*bump(t,.6,1.25,1.85))
    for i in range(7):
        lag=ease(seg(t,.26+i*.05,1.22+i*.06))
        f.P.add(f'tail_{i}',r=(2.4+i*.34)*(lag-h))
    return f


def revive(t):
    f=Frame()
    h=1-ease(seg(t,.18,1.62))
    fallen(f,h)
    f.P.add('head',y=6*bump(t,.74,1.13,1.74),r=-1.3*bump(t,.50,.94,1.65))
    f.P.add('chest',y=3*bump(t,.37,.76,1.4))
    gills(f,t,lambda u: .6*bump(u,.75,1.18,1.66),1.8)
    return f


def summon(t):
    f=Frame()
    h=1-ease(seg(t,0,1.30))
    f.P.add('pelvis',y=-24*h)
    f.P.add('body',r=-1.8*h)
    body(f,h,.35*bump(t,.68,1.01,1.52))
    f.P.add('head',r=1.8*h-1.2*bump(t,.54,.91,1.50))
    for i in range(7):
        f.P.add(f'tail_{i}',r=-(1.4+i*.22)*(1-ease(seg(t,.05*i,1.05+.065*i))))
    gills(f,t,lambda u: .7*bump(u,.52,.92,1.43),1.6)
    blink(f,t,1.04,.4)
    return f


FUNCS={n: globals()['idle' if n=='idle_loop' else n] for n in ANIMS}
