import math, numpy as np
from fk import Skel
FPS=30
def clamp(x,a=0,b=1): return max(a,min(b,x))
def ease(x): x=clamp(x); return x*x*(3-2*x)
def ease_out(x): x=clamp(x); return 1-(1-x)**3
def ease_in(x): x=clamp(x); return x**3
def seg(t,t0,t1): return clamp((t-t0)/(t1-t0)) if t1>t0 else float(t>=t0)
_pn=None
def pulse(x,rise=0.035,dec=0.16):
    global _pn
    if x<=0: return 0.0
    f=lambda z:(1-math.exp(-z/rise))*math.exp(-z/dec)
    if _pn is None: _pn=max(f(z/1000) for z in range(1,1000))
    return f(x)/_pn
def dspring(t,t0,freq=3.0,damp=4.0):
    """damped oscillation starting at t0 with value 1"""
    if t<t0: return 0.0
    x=t-t0; return math.exp(-damp*x)*math.cos(2*math.pi*freq*x)
def kick(t,t0,freq=3.0,damp=4.0):
    """damped sine (starts at 0, first lobe +)"""
    if t<t0: return 0.0
    x=t-t0; return math.exp(-damp*x)*math.sin(2*math.pi*freq*x)
TAU=2*math.pi

class Pose(dict):
    def add(self,b,r=0,x=0,y=0,sx=0,sy=0,s=0):
        R,X,Y,SX,SY=self.get(b,(0,0,0,1,1))
        self[b]=(R+r,X+x,Y+y,SX*(1+sx+s),SY*(1+sy+s))

TUBES_LEFT=['tube_a','tube_b','mid_tip','bottom_tip']
def beats(t,period,offset,n=4,**kw):
    return sum(pulse(t-offset-k*period,**kw) for k in range(-2,n))

# ---------------------------------------------------------------- idle base
def idle_base(t, P=None, amp=1.0, T=3.0):
    """heart rhythm + breathing; periodic with period T (=3s, two beats)"""
    P=P if P is not None else Pose()
    ph=TAU*t/T
    Pa=beats(t,1.5,0.0)*amp; Pv=beats(t,1.5,0.17)*amp; Pr=beats(t,1.5,0.30,dec=0.25)*amp
    br=math.sin(ph)
    P.add('body',y=2.5*br,sy=0.006*br,sx=-0.003*br)
    P.add('heart',s=0.012*Pv,sy=-0.004*Pa)
    P.add('atrium',s=0.03*Pa-0.012*Pv, r=0.6*Pa)
    P.add('tube_a',r=-3.0*Pr+1.2*math.sin(ph+0.4),s=0.02*Pa)
    P.add('tube_b',r=2.4*Pr+1.0*math.sin(ph+1.3),s=0.02*Pa)
    P.add('bulb_base',s=0.02*Pv)
    P.add('bulb',s=0.055*Pv-0.01*Pa,r=-1.0*Pv)
    P.add('mid_lobe',s=0.018*beats(t,1.5,0.22),x=-1.5*Pv)
    P.add('mid_tip',r=1.6*Pr+0.8*math.sin(ph+2.0))
    P.add('bottom_lobe',s=0.015*beats(t,1.5,0.26),y=1.0*Pv)
    P.add('bottom_tip',r=-1.4*Pr+0.7*math.sin(ph+2.6))
    P.add('right_lobe',s=0.022*beats(t,1.5,0.24))
    P.add('purple_mass',s=0.012*beats(t,1.5,0.28),r=0.4*math.sin(ph+0.9))
    P.add('purple_top',r=1.2*math.sin(ph+1.7)-1.5*Pr)
    P.add('ptube_l',r=2.2*math.sin(ph+2.2)+2.5*Pr)
    P.add('ptube_r',r=-1.8*math.sin(ph+2.9)-2.0*Pr)
    P.add('purple_lr',s=0.01*Pr)
    P.add('plr_a',r=-1.6*math.sin(ph+0.3)-1.8*Pr)
    P.add('plr_b',r=1.4*math.sin(ph+1.1)+1.5*Pr)
    P.add('blue_main',s=0.012*beats(t,1.5,0.25),r=0.5*math.sin(ph+0.5))
    P.add('blue_up',r=-1.8*math.sin(ph+1.4)-2.2*Pr)
    P.add('blue_down',r=1.6*math.sin(ph+2.4)+2.0*Pr,s=0.015*Pr)
    P.add('blue_bottom',r=-1.2*math.sin(ph+0.2)+1.5*Pr)
    glow={'atrium_glow':clamp(0.10+0.55*Pa), 'bulb_glow':clamp(0.10+0.75*Pv)}
    return P,glow

def weed_target_idle(name,i,t,base_x,T=3.0):
    """underwater current: travelling wave left->right"""
    ph=TAU*t/T - (base_x/1358.0)*TAU*0.5
    return (2.2+1.2*i)*math.sin(ph-0.5*i)+0.8*math.sin(2*ph+1.1+0.4*i)

# ---------------------------------------------------------------- one-shots
def attack(t):
    P,g=idle_base(t,amp=0.6)
    a=seg(t,0.0,0.30); s=seg(t,0.30,0.42); r=seg(t,0.42,1.25)
    # body: anticipation (lean back right, squash) -> lunge left (stretch) -> settle w/ overshoot
    back=ease(a)*(1-ease_out(s))
    lunge=ease_out(s)*(1-ease(r))
    osc=kick(t,0.42,1.6,4.0)
    P.add('body',x=22*back-58*lunge+10*osc, y=-6*back+10*lunge, r=-3.5*back+5.5*lunge-1.5*osc,
          sx=0.035*back+0.05*lunge, sy=-0.05*back-0.02*lunge+0.02*osc)
    charge=ease(a)*(1-s)
    P.add('heart',s=-0.05*charge+0.12*math.exp(-8*max(0,t-0.32))*float(t>0.30)-0.03*osc)
    P.add('bulb',s=-0.04*charge+0.18*pulse(t-0.30,0.03,0.18),r=6*lunge)
    P.add('atrium',s=-0.03*charge+0.10*pulse(t-0.28,0.03,0.2),r=-4*back+6*lunge,x=-10*lunge)
    for b,sg in (('tube_a',1),('tube_b',-1)):
        P.add(b,r=sg*(-8*back+10*lunge)+sg*6*kick(t,0.42,2.4,5),x=-14*lunge,s=0.12*pulse(t-0.32,0.03,0.2))
    P.add('mid_lobe',x=-8*lunge,s=0.06*pulse(t-0.33))
    P.add('mid_tip',r=6*back-9*lunge+5*kick(t,0.45,2.2,5))
    P.add('bottom_lobe',x=-6*lunge,s=0.05*pulse(t-0.35))
    P.add('bottom_tip',r=-5*back+7*lunge-4*kick(t,0.47,2.2,5))
    P.add('right_lobe',s=0.05*pulse(t-0.36))
    P.add('back',x=10*back-18*lunge,r=-2*back+2*lunge)
    P.add('ptube_l',r=6*back-8*lunge+6*kick(t,0.5,2.0,4)); P.add('ptube_r',r=-5*back+7*lunge-5*kick(t,0.52,2.0,4))
    P.add('purple_top',r=-3*back+5*lunge)
    P.add('blue',x=8*back-12*lunge); P.add('blue_up',r=-6*back+8*lunge-4*kick(t,0.5,2.2,4))
    P.add('blue_down',r=5*back-7*lunge); P.add('plr_a',r=-4*back+6*lunge); P.add('plr_b',r=4*back-5*lunge)
    flash=pulse(t-0.30,0.03,0.25)
    g['atrium_glow']=clamp(g['atrium_glow']+0.5*charge+0.9*flash); g['bulb_glow']=clamp(g['bulb_glow']+0.6*charge+1.0*flash)
    return P,g
def hurt(t):
    P,g=idle_base(t,amp=0.5)
    j=pulse(t,0.025,0.14); o=kick(t,0.05,2.6,6.0)
    P.add('body',x=26*j-6*o,r=-4.5*j+1.5*o,sx=-0.05*j,sy=0.05*j-0.02*o,y=4*j)
    P.add('heart',s=-0.035*j+0.02*o)
    P.add('bulb',s=-0.04*j+0.04*kick(t,0.06,3.2,6),r=-2*j)
    P.add('atrium',s=-0.03*j+0.03*kick(t,0.04,3.6,6),r=2*j)
    P.add('tube_a',r=-10*j+6*kick(t,0.06,3.0,5)); P.add('tube_b',r=9*j-6*kick(t,0.07,3.0,5))
    P.add('mid_lobe',x=6*j,s=0.04*kick(t,0.05,3.4,6)); P.add('mid_tip',r=8*j-5*kick(t,0.07,2.8,5))
    P.add('bottom_lobe',x=5*j,s=0.04*kick(t,0.06,3.0,6)); P.add('bottom_tip',r=-7*j+4*kick(t,0.08,2.8,5))
    P.add('right_lobe',s=-0.02*j+0.03*kick(t,0.07,3.3,6))
    P.add('back',x=12*j,r=-2*j); P.add('blue',x=10*j)
    P.add('ptube_l',r=-6*j+5*kick(t,0.1,2.4,5)); P.add('ptube_r',r=5*j-4*kick(t,0.1,2.4,5))
    P.add('blue_up',r=-6*j+4*kick(t,0.1,2.6,5)); P.add('blue_down',r=5*j); P.add('plr_a',r=-5*j); P.add('plr_b',r=4*j)
    g['atrium_glow']=clamp(g['atrium_glow']+0.7*j); g['bulb_glow']=clamp(g['bulb_glow']+0.8*j)
    return P,g
def cast(t,big=1.0):
    P,g=idle_base(t,amp=0.4)
    gat=ease(seg(t,0.0,0.40)); rel=seg(t,0.40,0.55); st=ease(seg(t,0.55,1.40))
    hold=gat*(1-st)
    # three accelerating heartbeats while gathering
    qb=sum(pulse(t-tb,0.025,0.09) for tb in (0.05,0.20,0.31))
    boom=pulse(t-0.40,0.03,0.22)
    P.add('body',y=14*hold*big+6*boom,sy=0.04*hold*big-0.03*boom,sx=-0.015*hold+0.04*boom,r=0.8*math.sin(TAU*t*5)*hold)
    P.add('heart',s=0.05*qb+0.14*boom*big)
    P.add('bulb',s=0.08*qb+0.2*boom*big)
    P.add('atrium',s=0.06*qb+0.12*boom*big)
    P.add('tube_a',r=-10*hold*big+8*kick(t,0.45,2.2,4)); P.add('tube_b',r=9*hold*big-7*kick(t,0.46,2.2,4))
    P.add('ptube_l',r=8*hold*big-6*kick(t,0.48,2,4)); P.add('ptube_r',r=-8*hold*big+6*kick(t,0.49,2,4))
    P.add('purple_top',r=-3*hold)
    P.add('blue_up',r=-8*hold*big+6*kick(t,0.47,2.1,4)); P.add('blue_down',r=7*hold*big)
    P.add('plr_a',r=-7*hold); P.add('plr_b',r=6*hold)
    P.add('mid_tip',r=6*hold); P.add('bottom_tip',r=-6*hold)
    P.add('mid_lobe',s=0.06*boom); P.add('bottom_lobe',s=0.05*boom); P.add('right_lobe',s=0.07*boom)
    P.add('purple_mass',s=0.05*boom); P.add('blue_main',s=0.05*boom)
    g['atrium_glow']=clamp(0.15+0.8*hold+0.4*qb+boom); g['bulb_glow']=clamp(0.15+0.85*hold+0.5*qb+boom)
    return P,g
def power_up(t):
    P,g=cast(t*1.0,big=1.35)
    sw=ease(seg(t,0.4,0.8))*(1-ease(seg(t,1.0,1.5)))
    P.add('heart',s=0.04*sw*math.sin(TAU*t*6)**2)
    return P,g
def summon(t):
    P,g=idle_base(t,amp=0.5)
    heave=ease(seg(t,0,0.3))*(1-ease(seg(t,0.8,1.3)))
    P.add('body',y=10*heave,sy=0.03*heave)
    # peristaltic wave through every tube, one after another
    seq=[('tube_a',-1),('tube_b',1),('ptube_l',1),('ptube_r',-1),('blue_up',-1),('blue_down',1),('plr_a',-1),('plr_b',1)]
    for k,(b,sg) in enumerate(seq):
        t0=0.25+0.07*k; p=pulse(t-t0,0.04,0.15)
        P.add(b,r=sg*12*p,s=0.15*p)
    P.add('heart',s=0.08*pulse(t-0.2,0.04,0.2)); P.add('bulb',s=0.12*pulse(t-0.22,0.04,0.2))
    g['atrium_glow']=clamp(g['atrium_glow']+0.8*heave); g['bulb_glow']=clamp(g['bulb_glow']+0.9*heave)
    return P,g
DIE_END=2.6
def collapse_pose(P,c):
    P.add('body',y=-26*c,sy=-0.16*c,sx=0.06*c,r=-2*c)
    P.add('heart',sy=-0.06*c)
    P.add('bulb',s=-0.1*c,y=-10*c)
    P.add('atrium',s=-0.06*c,y=-8*c,r=4*c)
    P.add('tube_a',r=14*c,y=-6*c); P.add('tube_b',r=12*c,y=-4*c)
    P.add('mid_lobe',y=-6*c,sx=0.04*c); P.add('mid_tip',r=8*c)
    P.add('bottom_lobe',sx=0.05*c,sy=-0.08*c); P.add('bottom_tip',r=4*c)
    P.add('right_lobe',y=-6*c,s=-0.05*c)
    P.add('back',y=-18*c,r=-3*c); P.add('purple_top',r=-10*c); P.add('ptube_l',r=16*c); P.add('ptube_r',r=-18*c)
    P.add('plr_a',r=-12*c); P.add('plr_b',r=-6*c)
    P.add('blue',y=-12*c); P.add('blue_up',r=-22*c); P.add('blue_down',r=-10*c); P.add('blue_bottom',r=6*c)
def tint_of(dark): return (1-0.45*dark, 1-0.42*dark, 1-0.35*dark)
def die(t):
    P=Pose()
    irr=[(0.0,1.0),(0.28,0.7),(0.45,0.5),(0.9,0.55),(1.35,0.25)]
    Pv=sum(w*pulse(t-t0,0.03,0.12) for t0,w in irr)
    fl=0.5+0.5*math.sin(TAU*t*11)*math.sin(TAU*t*3.3)
    c=ease_in(seg(t,0.9,2.2))*0.35+ease(seg(t,0.9,2.2))*0.65
    P.add('body',x=4*math.sin(TAU*t*7)*math.exp(-3*t))
    P.add('heart',s=0.06*Pv); P.add('bulb',s=0.09*Pv); P.add('atrium',s=0.05*Pv)
    collapse_pose(P,c)
    g={'atrium_glow':clamp((0.2+0.6*Pv)*(1-c)*fl), 'bulb_glow':clamp((0.2+0.8*Pv)*(1-c)*(1-fl*0.5))}
    dark=ease(seg(t,0.9,2.4))
    return P,g,tint_of(dark),c
def revive(t):
    P=Pose()
    u=ease_out(seg(t,0.3,1.15))
    c=1-u
    collapse_pose(P,c)
    ov=kick(t,1.0,1.8,3.5)*(1-ease(seg(t,1.4,1.8)))
    P.add('body',sy=0.06*ov,y=8*ov)
    b1=pulse(t-0.12,0.04,0.2); b2=pulse(t-0.95,0.03,0.18); b3=pulse(t-1.13,0.03,0.18)
    P.add('heart',s=0.05*b1+0.1*b2+0.06*b3); P.add('bulb',s=0.08*b1+0.16*b2+0.1*b3); P.add('atrium',s=0.05*b1+0.08*b2)
    e=ease(seg(t,1.35,1.8))
    I,gi=idle_base(t-1.8)
    for b,v in I.items():
        r,x,y,sx,sy=v; P.add(b,r=r*e,x=x*e,y=y*e,sx=(sx-1)*e,sy=(sy-1)*e)
    g={'atrium_glow':clamp(0.1*e+0.6*b1+0.9*b2+0.5*b3), 'bulb_glow':clamp(0.1*e+0.7*b1+1.0*b2+0.6*b3)}
    dark=1-ease(seg(t,0.2,1.2))
    return P,g,tint_of(dark),c
ANIMS={ # name: (duration, loop)
 'idle_loop':(3.0,True),'attack':(1.25,False),'cast':(1.4,False),'hurt':(0.65,False),
 'die':(DIE_END,False),'summon':(1.3,False),'power_up':(1.5,False),'revive':(1.8,False)}
