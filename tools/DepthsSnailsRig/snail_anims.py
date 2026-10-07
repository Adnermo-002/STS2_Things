"""Staggered effort, contact and follow-through; native contact times preserved."""
import math
from functools import partial
from rigutil import Frame,TAU,key,bump,hold,kick,ease,seg
from snail_rig import NAME,C,CURVES,FOOT,RIBS

ROCK=NAME=='rock_snail';SLIME=NAME=='slime_snail';CRYSTAL=not ROCK and not SLIME
ANIMS={'idle_loop':(5.6,True),'attack':(1.5,False),'cast':(1.5,False),
       'hurt':(.7,False),'die':(1.8,False),'power_up':(1.5,False),
       'revive':(1.7,False),'summon':(1.7,False),'retreat':(1.5,False),
       'crawl':(1.6,False),'shell_break':(1.0,False)}
EVENTS={'attack':[('impact',.62 if ROCK else .48)],'cast':[('spit',.58)],
        'crawl':[('step',.62)],'retreat':[('tuck',.55)],'shell_break':[('crack',.12)]}

def wave(t,period=5.6,phase=0):return math.sin(TAU*t/period-phase)-math.sin(-phase)

def stroke(t,start,peak,release,end):
    return key(t,(0,0),(start,0),(peak,1),(release,.9),(end,0))

def tip(f,name,**values):
    row=f.extra.setdefault('curves',{}).setdefault(name,{})
    for k,v in values.items():row[k]=row.get(k,0)+v

def feelers(f,t,drive=0,tuck=0,spit=0,impact=None):
    for i in range(2):
        lag=.045+i*.055
        recoil=kick(t,impact+lag,2.65+i*.37,5.1) if impact is not None else 0
        tip(f,f'stalk_{i}',sway=(14 if ROCK else 23)*drive+6*tuck-24*spit+(18+i*7)*recoil,
            bend=(-1 if i else 1)*(6*drive+3*tuck)+7*recoil,
            pull=-5*tuck+10*spit-4*drive,curl=(-5 if i else 4)*recoil,shorten=.13*max(0,tuck))
    for i in range(3 if SLIME else 0):
        recoil=kick(t,impact+.065+i*.042,2.5-i*.2,4.8) if impact is not None else 0
        tip(f,f'drool_{i}',sway=15*drive-(24+i*5)*spit+(22-i*3)*recoil,
            pull=(17+i*3)*spit-12*drive-5*recoil,bend=7*recoil,curl=6*recoil)

def pedal(f,t,amount=1,period=1.6):
    # The release wave travels tail to head while the rest of the sole stays planted.
    for i in range(len(FOOT)):
        phase=(t/period+i*.085)%1
        lift=math.sin(math.pi*seg(phase,.13,.64))**2 if .13<phase<.64 else 0
        taper=.45+.55*math.sin(math.pi*i/(len(FOOT)-1))
        push=math.sin(TAU*seg(phase,.13,.64))*lift if lift else 0
        f.P.add(f'foot_{i}',x=7.5*amount*push*taper,y=16*amount*lift*taper,sx=.014*amount*push)

def belly(f,t,amount=1,period=1.6):
    for i in range(len(RIBS)):
        v=math.sin(TAU*t/period+i*.82)
        f.P.add(f'rib_{i}',y=7.5*amount*v,x=5*amount*math.cos(TAU*t/period+i*.82),sy=.025*amount*v)

def blink(f,t,start,amount=1):
    if SLIME:return
    for i in range(2):
        b=key(t,(0,0),(start+i*.035,0),(start+.05+i*.035,1),(start+.12+i*.035,.97),(start+.27+i*.035,0))
        f.P.add(f'stalk_{i}_lid',sy=-.90*b*amount,sx=.025*b)

def idle(t):
    f=Frame();breath=wave(t,2.8)
    f.P.add('mantle',y=(2.3 if ROCK else 5)*breath)
    f.P.add('throat',sx=(.015 if ROCK else .025)*breath,sy=.017*breath)
    if CRYSTAL:
        sniff=hold(t,.7,1.2,1.5,2.15);hide=bump(t,2.3,2.7,3.5)
        f.P.add('head',x=-16*sniff+14*hide,y=9*sniff-7*hide,r=-1.1*sniff)
        f.P.add('neck',x=-6*sniff+5*hide,y=2*breath)
        f.P.add('shell',r=.65*wave(t,5.6,.65),y=1.8*wave(t,2.8,.5))
        f.P.add('tail',r=1.3*wave(t,5.6,1.8),y=2*wave(t,5.6,1))
        for i in range(2):tip(f,f'stalk_{i}',sway=(13+3*i)*wave(t,5.6,.65+i*.8)-12*sniff,
            bend=(6 if i else -8)*sniff,pull=(5+i*2)*sniff)
        blink(f,t,2.22);blink(f,t,4.7,.65)
    elif SLIME:
        gulp=bump(t,.55,1.15,2.);search=hold(t,2.25,2.95,3.45,4.75)
        f.P.add('head',r=-2.1*search,x=-14*search,y=7*gulp+7*wave(t,5.6,.5))
        f.P.add('neck',r=1.3*wave(t,5.6,.8),sx=.03*gulp,y=5*breath)
        f.P.add('throat',sx=.09*gulp,sy=.045*gulp)
        f.P.add('tail',r=4.1*wave(t,5.6,1.15),y=6*wave(t,2.8,.7))
        belly(f,t,.22,2.8)
        for i in range(2):tip(f,f'stalk_{i}',sway=(17 if i else -13)*wave(t,5.6,.8+i*.6)-12*search,
            bend=7*wave(t,2.8,.5+i),pull=7*wave(t,5.6,.4+i*.6))
        for i in range(3):tip(f,f'drool_{i}',sway=(7+i)*wave(t,2.8,i*.65),
            pull=9*wave(t,5.6,.7+i*.7)+8*gulp,bend=3*wave(t,2.8,1+i*.5))
    else:
        effort=bump(t,1.1,1.9,3.);settle=bump(t,3.1,3.7,4.8)
        f.P.add('head',x=-9*effort+5*settle,y=-5*effort,r=-.7*effort)
        f.P.add('neck',sy=-.02*effort)
        f.P.add('shell',r=.5*wave(t,5.6,1),y=-4*effort+2*settle)
        f.P.add('tail',r=.7*wave(t,5.6,1.4))
        for i in range(2):tip(f,f'stalk_{i}',sway=(7+i*3)*wave(t,5.6,1.1+i*.9)-8*effort,
            pull=-4*effort,bend=(3 if i else -3)*wave(t,5.6,.6))
        blink(f,t,2.65)
    pedal(f,t,.11 if ROCK else .15,2.8)
    return f

def attack(t):
    f=Frame();contact=.62 if ROCK else .48
    wind=hold(t,0,contact-.19,contact-.11,contact+.02)
    hit=stroke(t,contact-.145,contact,contact+.055,1.23)
    shell_hit=stroke(t,contact-.075,contact+.07,contact+.14,1.42)
    spring=kick(t,contact+.075,3.1,5)*(1-ease(seg(t,1.1,1.5)))
    if ROCK:
        f.P.add('root',x=22*wind-112*hit)
        f.P.add('body',sy=-.07*wind+.025*hit)
        f.P.add('head',x=22*wind-48*hit,y=16*wind-17*hit,r=2*wind-3.5*hit)
        f.P.add('neck',x=12*wind-24*hit,sy=-.045*wind)
        f.P.add('shell',x=22*(hit-shell_hit),r=-2*wind+4.4*shell_hit+.7*spring,y=-8*wind-7*shell_hit)
        f.P.add('tail',x=-9*shell_hit,r=-3*hit)
    elif CRYSTAL:
        f.P.add('root',x=12*wind-61*hit)
        f.P.add('head',x=27*wind-50*hit,y=-7*wind+11*hit,r=1.4*wind-2.5*hit)
        f.P.add('neck',x=10*wind-24*hit,sy=-.035*wind+.02*hit)
        f.P.add('throat',sy=-.04*hit)
        f.P.add('shell',x=19*(hit-shell_hit),r=-2.8*wind+3.6*shell_hit+1.4*spring,y=3*wind-4*shell_hit)
        f.P.add('tail',r=-4*shell_hit+2*spring)
    else:
        f.P.add('root',x=8*wind-28*hit)
        f.P.add('head',x=29*wind-66*hit,y=22*wind-20*hit,r=-3*hit)
        f.P.add('neck',x=13*wind-22*hit,sx=.045*wind,sy=-.045*hit)
        f.P.add('throat',sx=.12*wind-.045*hit)
        f.P.add('tail',r=-6*wind+8*shell_hit,y=6*spring)
    pedal(f,t,.36*(wind+hit),1.5);belly(f,t,.25*hit)
    feelers(f,t,drive=shell_hit,tuck=.35*wind,spit=.4*hit,impact=contact)
    blink(f,t,contact-.015,.65)
    return f

def cast(t):
    f=Frame();inhale=hold(t,0,.29,.42,.60)
    jet=stroke(t,.45,.58,.63,.98)
    settle=kick(t,.69,2.7,4.7)*(1-ease(seg(t,1.16,1.5)))
    f.P.add('head',x=23*inhale-61*jet+7*settle,y=25*inhale-16*jet,r=-2.8*inhale+3.5*jet)
    f.P.add('neck',x=9*inhale-27*jet,y=6*inhale,sy=.045*inhale-.06*jet)
    f.P.add('throat',sx=.19*inhale-.08*jet,sy=.08*inhale-.07*jet)
    f.P.add('mantle',y=-5*inhale+5*jet)
    f.P.add('tail',r=-6*inhale+8*jet+3*settle,y=4*inhale)
    f.P.add('shell',r=1.7*inhale-2*jet+.8*settle)
    belly(f,t,.25*(inhale+jet),1.5)
    feelers(f,t,drive=.45*settle,tuck=.3*inhale,spit=jet,impact=.59)
    for i in range(3 if SLIME else 0):
        hanging=stroke(t,.40+i*.02,.65+i*.045,.72+i*.04,1.24+i*.04)
        tip(f,f'drool_{i}',sway=-14*hanging,pull=-8*hanging,curl=7*settle)
    return f

def retreat(t):
    f=Frame();eyes=hold(t,0,.18,.75,1.32)
    head=hold(t,.055,.39,.64,1.36);torso=hold(t,.16,.51,.69,1.44)
    peek=bump(t,.80,1.03,1.37)
    wobble=kick(t,.45,2.8,5)*(1-ease(seg(t,1.1,1.5)))
    f.P.add('head',x=(91 if ROCK else 152)*head-16*peek,y=-28*head+10*peek,r=-3*head,sx=-.06*head,sy=-.09*head)
    f.P.add('neck',x=(44 if ROCK else 68)*torso,y=-12*torso,sy=-.07*torso)
    f.P.add('throat',sx=.045*torso,sy=-.10*head)
    f.P.add('mantle',x=-4*torso,y=-7*torso)
    f.P.add('shell',x=-6*torso,r=-1.7*torso+1.9*wobble,y=-8*torso)
    f.P.add('tail',x=-17*torso,r=3.1*torso)
    feelers(f,t,drive=.25*wobble,tuck=eyes,impact=.43)
    for i in range(2):
        tip(f,f'stalk_{i}',sway=(7+i*4)*eyes,pull=-8*eyes,bend=(4 if i else -3)*eyes)
        f.P.add(f'stalk_{i}_lid',sy=-.70*eyes)
    return f

def crawl(t):
    f=Frame();reach=hold(t,0,.31,.51,1.2)
    pull=stroke(t,.32,.81,.96,1.6);shell=stroke(t,.51,1.00,1.16,1.6)
    f.P.add('head',x=-30*reach+8*pull,y=7*reach,r=-1.2*reach)
    f.P.add('neck',x=-21*reach+11*pull,y=3*reach)
    f.P.add('mantle',x=10*reach-9*shell,y=-4*pull)
    f.P.add('shell',x=10*reach-14*shell,r=-1.5*reach+1.9*shell,y=3*reach-5*shell)
    f.P.add('tail',x=-14*shell,y=3*shell,r=1.6*shell)
    envelope=hold(t,0,.23,1.2,1.6)
    pedal(f,t,1.12*envelope,1.6);belly(f,t,.55*envelope,1.6)
    feelers(f,t,drive=.45*pull,impact=.94)
    for i in range(2):tip(f,f'stalk_{i}',sway=-11*reach,pull=7*reach)
    return f

def hurt(t,broken=False):
    f=Frame();duration=1. if broken else .7
    shock=key(t,(0,0),(.075,1),(.17,.72),(duration*.58,-.12),(duration,0))
    trail=stroke(t,.035,.14,.19,duration)
    wobble=kick(t,.12,3.5,6)*(1-ease(seg(t,duration*.65,duration)))
    f.P.add('root',x=(20 if ROCK else 28)*shock)
    f.P.add('head',x=(46 if broken else 31)*shock,y=-13*shock,r=-2*shock)
    f.P.add('neck',sy=-.045*shock,x=8*shock)
    f.P.add('throat',sx=.05*shock,sy=-.06*shock)
    f.P.add('mantle',y=-6*trail)
    f.P.add('shell',r=-3*trail+1.2*wobble,x=-8*shock,y=4*shock)
    f.P.add('tail',r=4*trail)
    feelers(f,t,drive=trail,tuck=.6*shock,impact=.075)
    if broken:
        look=bump(t,.42,.70,1.)
        f.P.add('head',x=-20*look,y=18*look)
        for i in range(2):tip(f,f'stalk_{i}',pull=14*look,sway=(-10 if i else 12)*look)
    for i in range(2):f.P.add(f'stalk_{i}_lid',sy=-.83*max(0,shock))
    return f

def die(t):
    f=Frame();head=ease(seg(t,.07,.69));body=ease(seg(t,.25,1.18));shell=ease(seg(t,.40,1.29))
    flop=kick(t,.70,2.3,5)*(1-ease(seg(t,1.25,1.7)))
    f.P.add('body',sy=-.15*body,y=-8*body)
    f.P.add('head',x=30*head,y=-54*head,r=-5*head)
    f.P.add('neck',x=12*body,y=-18*body,sy=-.04*body)
    f.P.add('throat',sy=-.075*body,sx=.035*body)
    f.P.add('mantle',y=-10*body)
    f.P.add('shell',r=(-5 if ROCK else -9)*shell+1.5*flop,y=-27*shell,x=-9*shell)
    f.P.add('tail',r=-4*body,y=-4*body)
    for i in range(len(RIBS)):
        collapse=ease(seg(t,.29+i*.065,.82+i*.085))
        f.P.add(f'rib_{i}',y=-4*collapse)
    feelers(f,t,tuck=1.7*head,drive=.2*flop,impact=.67)
    for i in range(2):f.P.add(f'stalk_{i}_lid',sy=-.95*head)
    f.tint=(1-.15*body,1-.13*body,1-.11*body,1-ease(seg(t,1.35,1.8)))
    return f

def power_up(t):
    f=retreat(t);charge=hold(t,.13,.50,.74,1.32)
    f.P.add('mantle',y=9*charge)
    f.P.add('shell',y=8*charge,r=.7*kick(t,.68,2.8,6))
    f.P.add('throat',sx=.055*charge)
    return f

def arrive(t):
    f=Frame();unfurl=1-ease(seg(t,.13,1.12));settle=kick(t,.84,2.7,5)*(1-ease(seg(t,1.3,1.7)))
    f.P.add('root',x=38*(1-ease(seg(t,0,1.25))))
    f.P.add('head',x=95*unfurl,y=-26*unfurl+7*settle,sy=-.07*unfurl)
    f.P.add('neck',x=32*unfurl,y=-10*unfurl)
    f.P.add('shell',r=-2*unfurl+1.4*settle,y=-7*unfurl)
    f.P.add('tail',r=4*unfurl)
    feelers(f,t,tuck=unfurl,drive=settle,impact=.92)
    for i in range(2):f.P.add(f'stalk_{i}_lid',sy=-.65*unfurl)
    f.tint=(1,1,1,ease(seg(t,0,.38)))
    return f

FUNCS={'idle_loop':idle,'attack':attack,'cast':cast,'hurt':hurt,'die':die,
       'power_up':power_up,'revive':arrive,'summon':arrive,'retreat':retreat,
       'crawl':crawl,'shell_break':partial(hurt,broken=True)}
