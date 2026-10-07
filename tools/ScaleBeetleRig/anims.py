"""Authored action curves: rigid armored mass, planted feet, articulated feelers.

Each combat move has a full-body windup, contact and complete recovery. The whip
is one continuous three-hit animation; event times are shared with packaging.
"""
import math
from rigutil import Frame, TAU, ease, ease_out, ease_in, seg, bump, hold, kick, key
from rigdef import LEGS, GLOW_OF

ANIMS = {
    'idle_loop': (4.8, True), 'attack': (1.95, False), 'whip': (2.75, False),
    'cast': (2.3, False), 'molt': (2.65, False), 'power_up': (2.2, False),
    'hurt': (0.85, False), 'die': (2.8, False), 'revive': (2.2, False), 'summon': (2.2, False),
}
EVENTS = {
    'attack': [('bite_contact', .68)],
    'whip': [('whip_contact', .60), ('whip_ready_second', .88),
             ('whip_contact', 1.12), ('whip_ready_third', 1.40), ('whip_contact', 1.68)],
    'cast': [('reconstruct_release', .76)],
    'molt': [('molt_release', .80)],
    'summon': [('landing', .88)], 'die': [('death_ground', 1.45)],
}
COLD_START = ('revive', 'summon')


class F(Frame):
    def __init__(self, t=0, duration=None):
        super().__init__()
        self.extra['feet'] = {name: [0.0, 0.0, 0.0] for name in LEGS}
        self.glow = {name: 0.0 for name in GLOW_OF}
        if duration:
            self.extra['spring_mix'] = 1-ease(seg(t, duration-0.25, duration))

    def step(self, name, t, start, duration, dx=0, lift=12, tilt=6):
        u = seg(t, start, start+duration)
        arc = math.sin(math.pi*u)**2 if 0 < u < 1 else 0
        foot = self.extra['feet'][name]
        foot[0] += dx*ease(u)
        foot[1] += lift*arc
        foot[2] += tilt*arc

    def plate_glow(self, level):
        for name in ('shell_far_glow', 'shell_near_glow', 'collar_glow'):
            self.glow[name] += level

    def feeler_glow(self, level):
        for name in ('eye_glow', 'antenna_far_glow', 'antenna_near_glow'):
            self.glow[name] += level


def periodic(t, phase=0, harmonics=1):
    phase_t = TAU*t/4.8*harmonics
    return math.sin(phase_t+phase)-math.sin(phase)


def idle_loop(t):
    f = F(); p = f.P
    phase = TAU*t/4.8
    breath = 0.5-0.5*math.cos(phase)
    p.add('body', y=-7.0*breath, r=0.8*math.sin(phase))
    p.add('thorax', r=0.9*periodic(t, 0.3), y=0.5*periodic(t, 0.5))
    p.add('abdomen', r=-0.3*periodic(t, 0.8))
    p.add('neck', r=0.7*periodic(t, 0.4))
    p.add('head', r=2.4*periodic(t, 0.8)+0.6*periodic(t, 0.2, 2), x=-3*breath)
    p.add('neck_shield', r=0.35*periodic(t, 1.1))
    p.add('collar', r=-0.3*periodic(t, 1.5))
    p.add('shell_near', r=0.16*periodic(t, 0.6), y=0.5*breath)
    p.add('shell_far', r=-0.22*periodic(t, 1.1), y=0.7*breath)
    chatter = bump(t, 1.55, 1.75, 2.25)*max(0, math.sin(TAU*7*t))
    p.add('jaw_near', r=1.4*breath+2.3*chatter)
    p.add('jaw_far', r=-1.0*breath-1.7*chatter)
    for side, lag in (('near', 0), ('far', 0.7)):
        scan = bump(t, 0.45+lag, 1.0+lag, 2.5+lag)
        for i in range(7):
            p.add(f'antenna_{side}_{i}', r=(0.6+0.10*i)*periodic(t, 0.2*i+lag))
            f.bias[f'antenna_{side}_{i}'] = (4.0 if i == 0 else 0.3)*scan
    f.step('far_rear', t, 1.25, 0.62, lift=6, tilt=-3)
    f.step('front', t, 2.85, 0.64, lift=9, tilt=3)
    p.add('body', x=1.4*bump(t, 2.7, 3.15, 3.65))
    f.feeler_glow(0.025+0.08*breath)
    return f


def attack(t):
    f = F(t, 1.95); p = f.P
    load = key(t, (0,0), (.29,1), (.54,0), (1.95,0))
    thrust = key(t, (0,0), (.34,0), (.68,1), (.86,1.04), (1.07,1), (1.32,.82), (1.60,.40), (1.90,0), (1.95,0))
    p.add('body', x=26*load-110*thrust,
          y=key(t,(0,0),(.30,-32),(.68,-31),(1.18,-30),(1.80,0),(1.95,0)),
          r=-5*load+6*thrust)
    p.add('thorax', r=-3*load+2*thrust)
    p.add('abdomen', r=2.5*load-2.5*thrust)
    p.add('neck', r=-5*load+1*thrust, x=-12*thrust)
    p.add('head', r=-12*load+2*thrust, x=-16*thrust)
    p.add('neck_shield', r=-3*load+2*thrust)
    p.add('collar', r=-2*load+3*thrust)
    gape=key(t,(0,0),(.30,1),(.52,1),(.68,-.14),(.78,-.08),(1.18,.10),(1.75,0),(1.95,0))
    p.add('jaw_near', r=46*gape); p.add('jaw_far', r=-34*gape)
    for side, delay in (('near',0),('far',.045)):
        for i in range(7):
            tail=key(t-delay-.012*i,(0,0),(.37,-1),(.72,.8),(.96,-.4),(1.38,.15),(1.70,0),(1.95,0))
            p.add(f'antenna_{side}_{i}',r=(-10*load+5*thrust if i==0 else 0)+(2+.35*i)*tail)
    # The short far legs step after the body passes over them. Three other
    # contacts keep carrying the carapace during the fast forward transfer.
    f.step('front',t,0,.28,10,16,3)
    f.step('far_front',t,0,.28,40,20,3)
    for name, a, b, dx, lift in (
        ('front',.30,.34,-130,45),('far_front',.31,.31,-138,29),
        ('middle',.36,.35,-108,34),('rear',.70,.34,-98,25),
        ('far_rear',.72,.32,-103,23),('far_middle',.74,.32,-105,24)):
        f.step(name,t,a,b,dx,lift,5 if 'front' in name else -4)
    for name,a,b,dx in (('far_middle',1.06,.26,105),('far_rear',1.32,.28,103),
                        ('front',1.06,.26,120),('far_front',1.32,.28,98),
                        ('middle',1.60,.30,108),('rear',1.60,.30,98)):
        f.step(name,t,a,b,dx,25,-4)
    f.glow['eye_glow']=.58*bump(t,.16,.64,1.18)
    f.extra['spring_mix'] *= .55
    return f


def whip(t):
    f = F(t, 2.75); p = f.P
    # Load once, alternate feelers, then commit both to the final heavy sweep.
    body=key(t,(0,0),(.31,-5),(.60,7),(.88,-5),(1.12,8),(1.40,-6),(1.68,10),(1.90,4),(2.32,-1),(2.75,0))
    p.add('body',x=key(t,(0,0),(.31,15),(.60,-24),(.88,8),(1.12,-32),(1.40,10),(1.68,-43),(2.35,-5),(2.75,0)),
          y=key(t,(0,0),(.28,-27),(.60,-23),(1.40,-28),(1.68,-27),(2.30,-8),(2.75,0)),r=body)
    p.add('abdomen',r=-.35*body)
    p.add('thorax',r=.20*body)
    p.add('neck',r=.15*body)
    p.add('head',r=-.65*body)
    p.add('collar',r=-.3*body)
    p.add('neck_shield',r=.3*body)
    p.add('jaw_near',r=key(t,(0,0),(.32,18),(.60,4),(1.12,7),(1.48,23),(1.68,3),(2.75,0)))
    p.add('jaw_far',r=key(t,(0,0),(.32,-13),(.60,-3),(1.12,-5),(1.48,-17),(1.68,-2),(2.75,0)))
    shapes={
        'near':((0,0),(.31,-35),(.60,79),(.79,28),(1.04,-25),(1.30,5),(1.43,-36),(1.68,79),(1.91,35),(2.25,-10),(2.75,0)),
        'far':((0,0),(.36,-20),(.62,17),(.86,-36),(1.12,86),(1.30,27),(1.46,-25),(1.72,79),(1.97,29),(2.32,-8),(2.75,0)),
    }
    for side, points in shapes.items():
        for i in range(7):
            sweep=key(max(0,t-.011*i),*points)
            curl=key(t,(0,0),(.34,-1),(.64,1),(.88,-1),(1.17,1),(1.46,-1),(1.73,1),(2.13,-.35),(2.55,0),(2.75,0))
            p.add(f'antenna_{side}_{i}',r=sweep if i==0 else (3.5 if i<4 else -2)*curl)
    for name,dx in (('front',10),('far_front',26),('rear',22),('far_rear',12)):
        early=name in ('front','far_front')
        f.step(name,t,.02 if early else .23,.21,dx,18,4)
        f.step(name,t,2.03 if early else 2.31,.28,-dx,17,-3)
    f.feeler_glow(sum(.75*bump(t,c-.26,c,c+.26) for c in (.60,1.12,1.68)))
    f.extra['spring_mix'] *= .40
    return f


def cast(t):
    f = F(t, 2.3); p = f.P
    load=key(t,(0,0),(.36,1),(.70,0),(2.3,0))
    rise=key(t,(0,0),(.36,0),(.76,1),(1.12,1),(1.50,.65),(2.12,0),(2.3,0))
    p.add('body',y=-26*load-12*rise,r=3*load-7*rise)
    p.add('abdomen',r=2.8*rise)
    p.add('thorax',r=-5.5*rise)
    p.add('neck',r=-5*rise)
    p.add('head',r=7*load-12*rise,x=-8*rise)
    p.add('jaw_near',r=24*rise);p.add('jaw_far',r=-18*rise)
    p.add('neck_shield',r=4.5*rise)
    p.add('collar',r=3*rise,y=3*rise)
    for side, target in (('near',30),('far',-25)):
        for i in range(7):
            p.add(f'antenna_{side}_{i}',r=(-10*load+target*rise if i==0 else (-1.2 if side=='near' else -2.2)*rise))
    lift=key(t,(0,0),(.40,0),(.72,1),(1.12,1),(1.88,0),(2.3,0))
    for name,dist,height in (('front',-30,88),('far_front',30,64)):
        f.extra['feet'][name]=[dist*lift,height*lift,10*lift]
    f.feeler_glow(.95*bump(t,.16,.76,1.95));f.plate_glow(.35*bump(t,.61,.95,1.85))
    return f


def molt(t):
    f = F(t, 2.65); p = f.P
    brace=key(t,(0,0),(.36,1),(.64,1),(.86,0),(2.65,0))
    spread=key(t,(0,0),(.45,0),(.80,1),(1.20,1),(1.75,.60),(2.45,0),(2.65,0))
    release=key(t,(0,0),(.72,0),(.84,1),(1.02,-.38),(1.23,.18),(1.47,0),(2.65,0))
    p.add('body',y=-35*brace+3*spread-5*release,r=-4.5*spread)
    p.add('abdomen',r=2*spread)
    p.add('thorax',r=-3*spread)
    p.add('neck',r=-3*spread)
    p.add('head',r=-10*spread+2*release)
    p.add('shell_far',r=-13*spread+1.8*release,x=16*spread,y=30*spread+3*release)
    p.add('shell_near',r=7.5*spread-1.4*release,x=12*spread,y=17*spread-2*release)
    p.add('collar',r=-8*spread+1.4*release,y=7*spread)
    p.add('neck_shield',r=6*spread,x=-4*spread)
    p.add('jaw_near',r=18*spread);p.add('jaw_far',r=-13*spread)
    for side, target in (('near',18),('far',-13)):
        for i in range(7):
            p.add(f'antenna_{side}_{i}',r=(-16*brace+target*spread if i==0 else -1.3*brace+1.2*release))
    for name,dx in (('front',22),('middle',10),('rear',26),('far_front',30),('far_middle',5),('far_rear',12)):
        early=name in ('front','rear','far_middle')
        f.step(name,t,.02 if early else .24,.22,dx,16,3)
        f.step(name,t,1.82 if early else 2.12,.30,-dx,13,-3)
    f.plate_glow(.9*bump(t,.35,.80,1.95));f.feeler_glow(.45*bump(t,.52,.85,1.65))
    return f


def power_up(t):
    f = F(t, 2.2); p = f.P
    load=key(t,(0,0),(.38,1),(.75,0),(2.2,0))
    flare=key(t,(0,0),(.35,0),(.75,1),(1.0,1),(1.60,.25),(2.2,0))
    p.add('body',y=-25*load-8*flare,r=3*load-6*flare)
    p.add('abdomen',r=2*flare)
    p.add('thorax',r=-4*flare);p.add('neck',r=-4*flare)
    p.add('head',r=-12*flare+5*load)
    p.add('neck_shield',r=5*flare);p.add('collar',r=-4*flare)
    p.add('shell_far',r=-4*flare,y=8*flare);p.add('shell_near',r=2.5*flare,y=5*flare)
    p.add('jaw_near',r=29*flare);p.add('jaw_far',r=-22*flare)
    for side,target in (('near',32),('far',-20)):
        for i in range(7):p.add(f'antenna_{side}_{i}',r=(target if i==0 else -2.5)*flare)
    for i,name in enumerate(('eye_glow','collar_glow','shell_near_glow','shell_far_glow')):
        f.glow[name]=.90*bump(t,.20+.08*i,.73+.04*i,1.85)
    for name,dx in (('far_front',25),('front',12)):
        f.step(name,t,.06,.32,dx,15,3);f.step(name,t,1.66,.40,-dx,12,-2)
    f.feeler_glow(.65*bump(t,.3,.75,1.7))
    return f


def hurt(t):
    f = F(t, .85);p=f.P
    hit=key(t,(0,0),(.11,1),(.19,.85),(.36,-.15),(.55,.06),(.85,0))
    p.add('body',x=28*hit,y=-14*max(0,hit),r=-3.5*hit)
    p.add('thorax',r=-3*hit);p.add('neck',r=-2.5*hit)
    p.add('head',r=-8*hit);p.add('jaw_near',r=17*hit);p.add('jaw_far',r=-12*hit)
    p.add('shell_far',r=-1.4*hit);p.add('shell_near',r=1.3*hit)
    for side,strength in (('near',1),('far',.8)):
        for i in range(7):p.add(f'antenna_{side}_{i}',r=-9*hit*strength/(1+.4*i))
    for name,dx in (('front',18),('far_front',30)):
        f.step(name,t,0,.14,dx,12,3);f.step(name,t,.30,.35,-dx,10,-3)
    f.feeler_glow(.32*bump(t,0,.08,.3));f.tint=(1,1-.10*max(0,hit),1-.13*max(0,hit),1)
    return f


def collapse(f, c):
    p = f.P
    p.add('body', y=-74*c, r=-1.0*c)
    p.add('abdomen', r=1.0*c)
    p.add('thorax', r=1.4*c)
    p.add('neck', r=2.0*c)
    p.add('head', r=11*c, x=-4*c)
    p.add('jaw_near', r=15*c)
    p.add('jaw_far', r=-9*c)
    p.add('shell_near', r=0.7*c, y=-2*c)
    p.add('shell_far', r=-1.4*c, y=-3*c)
    p.add('collar', r=2.3*c)
    p.add('neck_shield', r=1.8*c)
    for name, amount in [('front', -55), ('middle', 87), ('rear', 64),
                          ('far_front', -24), ('far_middle', 37), ('far_rear', 40)]:
        f.extra['feet'][name][0] += amount*c
    for side, strength in (('near', 1), ('far', 0.85)):
        for i in range(7):
            angle = 115 if i == 0 else (12 if i < 5 else 8)
            p.add(f'antenna_{side}_{i}', r=angle*c*strength)
    f.extra['antenna_floor'] = True
    f.tint = (1-0.35*c, 1-0.36*c, 1-0.31*c, 1)


def die(t):
    f = F(t, 2.8); p = f.P
    c = 0.30*ease(seg(t, 0.30, 0.68))+0.70*ease_in(seg(t, 0.88, 1.45))
    collapse(f, c)
    recoil = bump(t, 0, 0.09, 0.48)
    p.add('body', x=17*recoil, r=-1.7*recoil)
    p.add('head', r=-5*recoil)
    bounce = kick(t, 1.45, 3.1, 7)*(1-ease(seg(t, 2.10, 2.40)))
    p.add('body', y=5*bounce)
    p.add('shell_near', r=0.8*bounce)
    p.add('shell_far', r=-1.2*bounce)
    p.add('head', r=-2*bounce)
    # A final small tarsus twitch dies out completely before the held end pose.
    f.step('front', t, 1.97, 0.30, 0, 5, 6)
    f.feeler_glow(0.32*bump(t, 0, 0.06, 0.42))
    f.extra['spring_mix'] = 1-ease(seg(t, 1.8, 2.55))
    return f


def revive(t):
    f = F(t, 2.2); p = f.P
    c = 1-ease(seg(t, 0.32, 1.55))
    collapse(f, c)
    tremor = math.sin(TAU*9*t)*bump(t, 0.06, 0.22, 0.52)
    p.add('body', x=0.9*tremor, y=3*kick(t, 1.55, 2.5, 8)*(1-ease(seg(t, 1.85, 2.2))))
    p.add('head', r=-3*bump(t, 1.35, 1.58, 2.08))
    f.extra['spring_mix'] = ease(seg(t, 0.3, 0.8))*(1-ease(seg(t, 1.8, 2.2)))
    f.feeler_glow(0.55*bump(t, 0.04, 0.43, 1.9))
    f.plate_glow(0.36*bump(t, 0.28, 0.84, 1.85))
    return f


def summon(t):
    f = F(t, 2.2);p=f.P
    load=key(t,(0,0),(.30,1),(.62,0),(2.2,0))
    rear=key(t,(0,0),(.22,0),(.57,1),(.80,.7),(.94,0),(1.2,.12),(1.6,0),(2.2,0))
    land=key(t,(0,0),(.86,0),(1.0,1),(1.35,.18),(1.85,0),(2.2,0))
    p.add('body',y=-30*load-23*land-8*rear,r=-6*rear+2*land)
    p.add('thorax',r=-5*rear);p.add('neck',r=-4*rear)
    p.add('head',r=-11*rear+4*land)
    p.add('collar',r=-3*rear+2*land);p.add('shell_far',r=-2*rear+1.5*land)
    for side in ('near','far'):
        for i in range(7):p.add(f'antenna_{side}_{i}',r=(-18 if i==0 else -1)*rear+(5 if i==0 else 1.4)*land)
    lift=key(t,(0,0),(.23,0),(.58,1),(.66,1),(.88,0),(2.2,0))
    for name,dx,height in (('front',-20,94),('far_front',25,66)):
        f.extra['feet'][name]=[dx*lift,height*lift,8*lift]
    f.feeler_glow(.6*bump(t,.2,.65,1.75))
    return f


FUNCS = {name: globals()[name] for name in ANIMS}
