"""Bell-driven swimming, travelling ribbon bends and two-beat replay gestures."""
import math
from functools import partial
from rigutil import Frame,TAU,key,hold,bump,seg,ease,kick

ANIMS={'idle_loop':(6.,True),'attack':(1.2,False),'cast':(1.35,False),'hurt':(.62,False),
       'die':(2.,False),'power_up':(1.35,False),'revive':(1.8,False),'summon':(1.65,False)}
EVENTS={'attack':[('echo_hit',.48)],'cast':[('echo_shield',.5)],'die':[('bell_settles',1.45)]}
for a in range(4):
    for b in range(4):
        name=f'playback_{a}_{b}'
        ANIMS[name]=(2.3,False)
        EVENTS[name]=[('first_beat',.50),('second_beat',1.00),('final_pulse',1.55),('amplify',1.82)]


def wave(t,period=6,phase=0):
    return math.sin(TAU*t/period-phase)-math.sin(-phase)


def blink(f,t,start,amount=1):
    for i in range(2):
        lag=i*.025
        v=key(t,(0,0),(start+lag,0),(start+.055+lag,1),(start+.11+lag,.96),(start+.25+lag,0))
        f.P.add(f'eye_{i}_lid',sy=-.95*v*amount)


def curves(f,t,swing=0,pull=0,energy=0,wave_amount=0,phase=0,bend=0,lift=0):
    out=f.extra.setdefault('curves',{})
    for i in range(6):
        side=(i-2.5)/2.5
        out[f'tentacle_{i}']=dict(swing=swing*(.83+.12*math.cos(i))-.15*pull*side,
            pull=pull*(.83+.16*math.sin(i*.8)),curl=8*energy*math.sin(i*.9),
            bend=bend*(.6+.4*side),lift=lift,wave=wave_amount,
            phase=phase-i*.5,reference_phase=-i*.5,bulk=.3*energy)
    out['antenna_left']=dict(swing=-14*energy+7*math.sin(t*6)*energy,pull=5*energy,
                            bend=6*energy,wave=wave_amount*.28,phase=phase*.7)
    out['antenna_right']=dict(swing=17*energy-6*math.sin(t*6-.4)*energy,pull=-4*energy,
                             bend=-7*energy,wave=wave_amount*.24,phase=phase*.7-.5,
                             reference_phase=-.5)


def bell(f,inflate=0,compress=0,lean=0):
    f.P.add('mantle',sx=.034*inflate+.023*compress,sy=.047*inflate-.067*compress,r=lean)
    f.P.add('dome',y=14*inflate-10*compress)
    f.P.add('flank_left',x=-7*inflate-3*compress)
    f.P.add('flank_right',x=7*inflate+3*compress)
    f.P.add('skirt_middle',y=-5*inflate+8*compress)
    f.P.add('mouth',sy=.15*inflate-.12*compress)
    for i in range(6):f.P.add(f'skirt_{i}',y=(3+math.sin(i))*inflate-4*compress)


def swim(t):
    # A slow intake, quick contraction and long glide, twice per idle loop.
    return key(t%3,(0,0),(.32,-.18),(.62,-.34),(.98,.95),(1.21,.72),
               (1.90,.10),(2.50,-.12),(3.,0))


def snap(t,contact):
    return key(t,(0,0),(contact-.17,0),(contact,1),(contact+.075,.82),
               (contact+.25,-.19),(contact+.44,0))


def idle(t):
    f=Frame();stroke=swim(t)
    f.P.add('root',y=18*wave(t,6)+22*stroke,x=8*wave(t,6,1.1),r=.65*wave(t,6,.7))
    bell(f,inflate=.22*wave(t,3)-.15*stroke,compress=.70*stroke,lean=1.1*wave(t,6,.4))
    out=f.extra.setdefault('curves',{})
    for i in range(6):
        lag=.09+i*.028;trail=swim(t-lag)-swim(-lag);side=(i-2.5)/2.5
        f.P.add(f'skirt_{i}',y=4*wave(t,3,.5+i*.35)-5*trail)
        out[f'tentacle_{i}']=dict(swing=22*wave(t,6,.3+i*.55)+14*side*trail,
            pull=-30*trail+6*wave(t,3,.5+i*.38),bend=12*wave(t,3,.8+i*.48),
            lift=5*wave(t,3,i*.38),wave=7,phase=TAU*t/3-i*.55,reference_phase=-i*.55)
    out['antenna_left']=dict(swing=10*wave(t,3,.5)-8*stroke,pull=3*wave(t,3,.8),
                            bend=7*wave(t,3,1.1))
    out['antenna_right']=dict(swing=-12*wave(t,3,.8)+10*stroke,pull=3*wave(t,3,1),
                             bend=-6*wave(t,3,1.3))
    glance=bump(t,1.5,1.9,2.55)-.7*bump(t,3.45,3.8,4.45)
    for i in range(2):f.P.add(f'eye_{i}',x=-3*glance,y=1.6*glance)
    blink(f,t,2.2);blink(f,t,4.7,.65)
    return f


def gesture(t,beats,end,final_contact=None):
    """The body leads; alternating ribbons carry the stroke down to their tips."""
    f=Frame()
    h=sum(snap(t,c) for mask,c in beats if mask&1)
    guard=sum(hold(t,c-.23,c-.035,c+.07,c+.37) for mask,c in beats if mask&2)
    wind=sum(bump(t,c-.30,c-.17,c-.015) for mask,c in beats if mask&1)
    finale=snap(t,final_contact) if final_contact is not None else 0
    charge=bump(t,final_contact-.30,final_contact-.12,final_contact) if final_contact else 0
    settle=1-ease(seg(t,end-.30,end))
    bell(f,inflate=1.05*guard+.48*wind+.5*charge,compress=.85*h+1.1*finale,
         lean=2.6*h-1.1*guard+1.4*finale)
    f.P.add('root',x=-28*h+10*wind-12*finale,y=14*guard-11*h+12*finale-7*charge)
    curves(f,t,energy=.75*h+.8*guard+finale,wave_amount=8*(abs(h)+guard+abs(finale)),phase=t*10)
    for i in range(6):
        side=(i-2.5)/2.5;reach=(.85,.8,1.,.65,.83,1.)[i]
        whip=0;coil=0;flutter=0
        for beat,(mask,c) in enumerate(beats):
            lag=.014*(i//2)+(.052 if i%2!=beat%2 else 0)
            if mask&1:
                whip+=snap(t-lag,c)
                flutter+=kick(t,c+.04+lag,3.4,9)*settle
            if mask&2:coil+=hold(t-lag,c-.23,c-.035,c+.07,c+.37)
        ring=snap(t-.016*i,final_contact) if final_contact else 0
        params=f.extra['curves'][f'tentacle_{i}']
        params.update(swing=reach*(-144*whip+26*wind-62*ring)+side*23*coil,
                      pull=reach*(66*coil+26*wind-19*whip+25*charge-15*ring),
                      bend=reach*(-24*whip+side*28*coil+14*flutter),
                      lift=12*coil,curl=12*flutter,wave=8*(abs(whip)+coil+abs(ring)))
        f.P.add(f'skirt_{i}',y=5*coil-5*whip+3*flutter)
    for index,(mask,c) in enumerate(beats):
        if mask:
            flash=bump(t,c-.13,c,c+.24)
            f.P.add(f'channel_{index%2}',s=.025*flash)
    for name,side,lag in [('antenna_left',-1,.045),('antenna_right',1,.085)]:
        spring=sum(kick(t,c+lag,3.1,6.8) for mask,c in beats if mask)
        if final_contact:spring+=kick(t,final_contact+lag,3.1,6.8)
        f.extra['curves'][name]['swing']+=side*22*spring*settle
        f.extra['curves'][name]['bend']+=side*9*spring*settle
    return f


def playback(t,first,second):
    f=gesture(t,((first,.50),(second,1.00)),2.3,1.55)
    if second:blink(f,t,1.76,.65)
    else:blink(f,t,1.42,.3)
    return f


def attack(t):
    f=gesture(t,((1,.48),),1.2)
    blink(f,t,.42,.3)
    return f


def cast(t):
    f=gesture(t,((2,.50),),1.35)
    h=bump(t,.16,.50,1.05)
    f.P.add('eye_0',sy=.04*h);f.P.add('eye_1',sy=.04*h)
    return f


def power_up(t):
    f=cast(t)
    f.P.add('channel_0',s=.02*bump(t,.2,.48,.92))
    f.P.add('channel_1',s=.02*bump(t,.24,.52,.96))
    return f


def hurt(t):
    f=Frame();h=key(t,(0,0),(.07,1),(.15,.72),(.32,-.16),(.48,.03),(.62,0))
    bell(f,compress=1.1*h,lean=-4.3*h)
    f.P.add('root',x=28*h,y=5*h)
    curves(f,t,swing=62*h,pull=-18*h,energy=-h,wave_amount=7*abs(h),phase=t*13,bend=-16*h)
    for i in range(6):
        recoil=key(t,(0,0),(.09+i*.009,1),(.2+i*.009,.4),(.40+i*.009,-.12),(.62,0))
        f.extra['curves'][f'tentacle_{i}']['swing']=62*recoil
    blink(f,t,.014,.95)
    return f


def collapsed(f,h):
    bell(f,compress=4.2*h,lean=7*h)
    f.P.add('root',y=-85*h,x=17*h)
    f.P.add('dome',y=-32*h)
    curves(f,0,swing=28*h,pull=84*h,energy=-h,bend=-12*h,lift=-8*h)
    f.extra['curves']['antenna_left'].update(swing=26*h,pull=-48*h,bend=15*h)
    f.extra['curves']['antenna_right'].update(swing=30*h,pull=-58*h,bend=-16*h)
    for i in range(2):f.P.add(f'eye_{i}_lid',sy=-.95*h)


def die(t):
    f=Frame();h=ease(seg(t,.12,1.45));collapsed(f,h)
    tremor=kick(t,.16,3.1,4.4)*(1-ease(seg(t,1.45,1.9)))
    f.P.add('mantle',r=1.3*tremor)
    f.P.add('skirt_middle',y=-9*bump(t,1.22,1.47,1.91))
    return f


def revive(t):
    f=Frame();collapsed(f,1-ease(seg(t,.17,1.55)))
    lift=bump(t,.73,1.3,1.8)
    f.P.add('root',y=24*lift)
    bell(f,inflate=.35*lift)
    return f


def summon(t):
    f=Frame();h=1-ease(seg(t,0,1.4))
    settle=kick(t,.48,2.1,4)*(1-ease(seg(t,1.35,1.65)))
    bell(f,compress=1.2*h,inflate=.4*settle)
    f.P.add('root',y=60*h+13*settle)
    curves(f,t,pull=82*h,swing=18*settle,energy=.35*settle,
           wave_amount=6*bump(t,.5,.9,1.4),phase=t*8)
    return f


FUNCS={n:globals()['idle' if n=='idle_loop' else n] for n in list(ANIMS)[:8]}
for a in range(4):
    for b in range(4):FUNCS[f'playback_{a}_{b}']=partial(playback,first=a,second=b)
