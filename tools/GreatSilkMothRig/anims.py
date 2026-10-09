"""Wing-driven motion with distinct anticipation, contact and recovery poses."""
import math
from rigutil import Frame, TAU, key, bump, hold, seg, ease, kick

ANIMS = {
    'idle_loop': (6.0, True), 'attack': (1.35, False), 'cast': (1.55, False),
    'flutter': (1.5, False), 'hurt': (.68, False), 'die': (1.75, False),
    'revive': (1.6, False), 'summon': (1.5, False), 'power_up': (1.35, False),
}
EVENTS = {
    'attack': [('swoop_contact', .48)],
    'cast': [('silk_release', .62), ('second_silk_release', .78)],
    'flutter': [('wing_hit', .42), ('wing_hit', .67)],
    'die': [('land', 1.32)],
}
COLD_START = tuple(name for name in ANIMS if name != 'idle_loop')


def wave(t, period, phase=0):
    return math.sin(TAU*t/period-phase) - math.sin(-phase)


def frame(t, clip):
    f = Frame()
    duration = ANIMS[clip][0]
    f.extra['spring_mix'] = hold(t, 0, .12, duration-.20, duration)
    return f


def wings(f, stroke, follow=0, far=None, hind=None, cup=0):
    """Three independently timed planes, with a firm root and flexible tips."""
    far = stroke if far is None else far
    hind = stroke if hind is None else hind
    f.P.add('wing_far', r=-12.5*far, sx=-.13*far, sy=.020*far)
    f.P.add('wing_far_mid', r=-2.8*follow, sy=-.035*cup)
    f.P.add('wing_far_tip', r=-4.5*follow, sy=-.045*cup)
    f.P.add('wing_near', r=11.5*stroke, sx=-.16*stroke, sy=.035*stroke)
    f.P.add('wing_near_mid', r=3.7*follow, sy=-.035*cup)
    f.P.add('wing_near_tip', r=5.3*follow, sy=-.045*cup)
    f.P.add('wing_hind', r=7.0*hind, sx=-.095*hind)
    f.P.add('wing_hind_mid', r=2.8*follow)
    f.P.add('wing_hind_tip', r=4.0*follow)


def feelers(f, drive, lag=0, far_bias=0):
    f.P.add('antenna_near', r=-3.1*drive)
    f.P.add('antenna_near_mid', r=-1.5*lag)
    f.P.add('antenna_near_tip', r=2.4*lag)
    f.P.add('antenna_far', r=-2.3*drive+far_bias)
    f.P.add('antenna_far_mid', r=-1.2*lag)
    f.P.add('antenna_far_tip', r=1.9*lag)


def abdomen(f, drive, lag=0, breathing=0):
    f.P.add('abdomen', r=-4.5*drive, sx=.018*breathing, sy=-.014*breathing)
    f.P.add('abdomen_mid', r=-2.5*lag)
    f.P.add('abdomen_tip', r=-1.7*lag)


def pendants(f, drive, lag=0, near=0):
    f.P.add('silk_a', r=-6.5*drive)
    f.P.add('silk_a_mid', r=-2.2*lag)
    f.P.add('silk_a_tip', r=-3.0*lag)
    f.P.add('silk_b', r=-5.5*(drive+near))
    f.P.add('silk_b_mid', r=-2.6*lag)
    f.P.add('silk_b_tip', r=-3.8*lag)
    f.P.add('tail', r=-4.4*drive)
    f.P.add('tail_mid', r=-3.1*lag)
    f.P.add('tail_tip', r=-4.0*lag)


def flap(t, delay=0):
    # Long recovery stroke, quick downstroke, then a brief glide.
    def cycle(value):
        q = (value % 1.2) / 1.2
        return key(q, (0,0), (.18,-.62), (.38,-.78), (.57,1),
                   (.69,.88), (.86,.12), (1,0))
    return cycle(t-delay)-cycle(-delay)


def idle(t):
    f = frame(t, 'idle_loop')
    spread = 1+.055*math.sin(TAU*t/6)
    wings(f, flap(t)*spread, flap(t,.055), far=flap(t,.035),
          hind=flap(t,.095), cup=.25*flap(t,.055))
    f.P.add('thorax', y=5.5*wave(t,1.2,1.3)+6*wave(t,3,.4),
            x=2.1*wave(t,6,.8), r=.85*wave(t,3,.65))
    breath = wave(t,3,.7)
    f.P.add('neck', sx=.007*breath, sy=.012*breath)
    abdomen(f, .18*wave(t,3,.8), .23*wave(t,3,1.1), breath)
    f.P.add('head', r=.7*wave(t,6,.4))
    feelers(f, .44*wave(t,3,.2), .46*wave(t,3,.65), .6*wave(t,6,.8))
    inspect = bump(t,2.08,2.40,2.91)
    f.P.add('leg_near', r=-2.2*inspect)
    f.P.add('leg_near_tip', r=3.2*inspect)
    pendants(f, .26*wave(t,3,.5), .42*wave(t,3,1.0), .06*wave(t,6,.3))
    blink = bump(t,3.19,3.28,3.43)
    f.P.add('eye_near', sy=-.34*blink)
    f.P.add('eye_far', sy=-.30*blink)
    return f


def attack(t):
    f = frame(t, 'attack')
    wind = hold(t,0,.23,.27,.46)
    thrust = key(t,(0,0),(.27,0),(.48,1),(.57,.91),(.77,.38),(1.13,0),(1.35,0))
    follow = bump(t,.32,.61,1.15)
    settle = kick(t,.72,2.8,6)*(1-ease(seg(t,1.04,1.27)))
    f.P.add('thorax', x=44*wind-208*thrust+10*settle,
            y=24*wind-34*thrust, r=-5.3*wind+7.8*thrust)
    f.P.add('neck', sy=.023*wind-.034*thrust)
    f.P.add('head', r=-1.7*wind+3.0*thrust, x=-7*thrust)
    wings(f,-.85*wind+1.03*thrust,.87*follow,
          far=-.73*wind+.91*thrust, hind=-.65*wind+1.10*follow, cup=.8*thrust)
    abdomen(f,thrust-.20*wind,follow,.45*wind)
    feelers(f,thrust-.38*wind,follow,.7*wind)
    f.P.add('leg_far', r=-3.3*wind+5*thrust)
    f.P.add('leg_far_mid', r=2.2*wind-3.1*thrust)
    f.P.add('leg_far_tip', r=3*wind-4*thrust)
    f.P.add('leg_near', r=-4.1*wind+6*thrust)
    f.P.add('leg_near_mid', r=2.8*wind-3.8*thrust)
    f.P.add('leg_near_tip', r=3.5*wind-4.8*thrust)
    pendants(f,thrust-.3*wind,follow,.1*settle)
    f.P.add('eye_near', sy=-.16*bump(t,.26,.36,.48))
    return f


def cast(t):
    f = frame(t, 'cast')
    gather = hold(t,0,.32,.44,.78)
    release_far = bump(t,.46,.62,.93)
    release_near = bump(t,.61,.78,1.08)
    follow = bump(t,.59,.93,1.42)
    f.P.add('thorax', x=15*gather-10*release_far-6*release_near,
            y=23*gather+5*follow, r=-2.4*gather+1.4*release_far+1.1*release_near)
    f.P.add('neck', sx=.016*gather, sy=.024*gather)
    f.P.add('head', r=-1.2*gather+1.8*release_far+.9*release_near)
    wings(f,-.62*gather+.48*release_far+.34*release_near,.42*follow,
          far=-.53*gather+.43*release_near, hind=-.42*gather+.55*follow)
    abdomen(f,.32*follow,.30*follow,gather)
    feelers(f,-.65*gather+.6*follow,.64*follow,-.7*gather)
    # Draw both cocoons in, then extend each wrist at its own release frame.
    for name, release in [('leg_far',release_far), ('leg_near',release_near)]:
        f.P.add(name,r=-5.5*gather+10.5*release)
        f.P.add(name+'_mid',r=3.7*gather-6.2*release)
        f.P.add(name+'_tip',r=7*gather-11*release)
    for name, release in [('silk_a',release_far), ('silk_b',release_near)]:
        f.P.add(name,r=4*gather-8.2*release,sy=-.042*gather)
        f.P.add(name+'_mid',r=-3.2*release)
        f.P.add(name+'_tip',r=-4.5*release)
    f.P.add('tail',r=-2.8*follow)
    f.P.add('tail_mid',r=-2*follow)
    f.P.add('tail_tip',r=-3*follow)
    f.P.add('eye_near',sy=-.17*bump(t,.1,.25,.43))
    return f


def flutter(t):
    f = frame(t, 'flutter')
    wind = hold(t,0,.20,.26,.40)
    hit_a = bump(t,.28,.42,.57)
    hit_b = bump(t,.55,.67,.94)
    follow_a = bump(t,.35,.51,.75)
    follow_b = bump(t,.63,.83,1.30)
    drive = hit_a+.82*hit_b
    follow = .6*follow_a+.68*follow_b
    f.P.add('thorax',x=33*wind-73*hit_a-61*hit_b,
            y=14*wind-8*hit_a+8*hit_b,r=-2.8*wind+3.8*hit_a-1.6*hit_b)
    f.P.add('neck',sy=.018*wind-.025*drive)
    f.P.add('head',r=1.9*hit_a-1.4*hit_b)
    wings(f,-.79*wind+1.05*hit_a+.87*hit_b,follow,
          far=-.67*wind+.89*hit_a+1.01*hit_b,
          hind=-.56*wind+.86*follow_a+.95*follow_b,cup=.6*drive)
    abdomen(f,.65*drive,follow)
    feelers(f,.62*drive,.70*follow)
    f.P.add('leg_far',r=3.7*hit_a+2.1*hit_b)
    f.P.add('leg_near',r=2.3*hit_a+4.2*hit_b)
    pendants(f,.75*drive,follow,.08*hit_b)
    f.P.add('eye_near',sy=-.13*bump(t,.47,.54,.63))
    return f


def hurt(t):
    f = frame(t, 'hurt')
    recoil = key(t,(0,0),(.075,1),(.16,.73),(.31,-.15),(.48,.045),(.62,0),(.68,0))
    follow = bump(t,.05,.19,.60)
    f.P.add('thorax',x=47*recoil,y=-7*recoil,r=-3.5*recoil)
    f.P.add('neck',sy=-.015*follow)
    f.P.add('head',r=-2.7*recoil)
    wings(f,.52*recoil,.45*follow,far=.31*recoil,hind=.65*follow)
    abdomen(f,-.42*recoil,-.44*follow)
    feelers(f,-.65*recoil,-.45*follow)
    f.P.add('leg_far',r=-2.3*follow)
    f.P.add('leg_near',r=-3.1*follow)
    pendants(f,-.63*recoil,-.54*follow)
    blink = bump(t,.01,.095,.36)
    f.P.add('eye_near',sy=-.36*blink)
    f.P.add('eye_far',sy=-.30*blink)
    return f


def fallen(f, weight):
    f.P.add('thorax',y=-175*weight,r=14*weight)
    f.P.add('neck',sy=-.025*weight)
    f.P.add('head',r=-2.5*weight)
    f.P.add('leg_far',r=-2.8*weight)
    f.P.add('leg_near',r=-3.7*weight)
    f.P.add('abdomen',r=5*weight)
    f.P.add('abdomen_mid',r=2.1*weight)
    f.P.add('abdomen_tip',r=1.0*weight)
    f.P.add('wing_far',r=18*weight,sy=-.27*weight)
    f.P.add('wing_near',r=-16*weight,sy=-.27*weight)
    f.P.add('wing_hind',r=-13*weight,sy=-.20*weight)
    for name in ('silk_a','silk_b','tail'):
        f.P.add(name,sy=-.22*weight,r=-5*weight)
        f.P.add(name+'_tip',r=-4*weight)
    f.P.add('eye_near',sy=-.22*weight)
    f.P.add('eye_far',sy=-.19*weight)


def die(t):
    f = frame(t, 'die')
    flinch = bump(t,0,.10,.36)
    loss = ease(seg(t,.20,1.32))
    settle = bump(t,1.21,1.35,1.65)
    fallen(f,loss)
    f.P.add('thorax',x=13*flinch,y=12*flinch-9*settle)
    wings(f,.35*flinch,.2*flinch)
    feelers(f,-.38*flinch,-.28*flinch)
    f.P.add('tail_mid',r=1.8*settle)
    return f


def revive(t):
    f = frame(t, 'revive')
    fallen(f,1-ease(seg(t,.20,1.38)))
    gather = bump(t,.22,.63,1.07)
    lift = bump(t,.72,1.03,1.47)
    wings(f,-.54*gather+.64*lift,.35*lift)
    feelers(f,-.3*gather,.24*lift)
    f.P.add('thorax',y=14*lift)
    pendants(f,.22*lift,.24*lift)
    return f


def summon(t):
    f = frame(t, 'summon')
    arrive = 1-ease(seg(t,0,1.19))
    brake = bump(t,.30,.70,1.25)
    f.P.add('thorax',x=92*arrive,y=78*arrive+10*brake,r=-4.0*arrive+2.0*brake)
    wings(f,.72*brake,.40*bump(t,.43,.88,1.36),far=.60*brake,hind=.78*brake)
    abdomen(f,.20*brake,.32*brake)
    feelers(f,.23*brake,.3*brake)
    pendants(f,.4*brake,.5*bump(t,.47,.90,1.36))
    return f


def power_up(t):
    f = frame(t, 'power_up')
    gather = bump(t,0,.36,.68)
    show = bump(t,.30,.67,1.18)
    settle = bump(t,.66,.91,1.30)
    f.P.add('thorax',y=19*gather+13*show,r=-1.1*gather+.7*show)
    f.P.add('neck',sy=.020*show)
    abdomen(f,-.21*show,.22*settle,.7*gather)
    wings(f,-.72*gather+.49*show,.4*settle,far=-.59*gather+.5*show,hind=-.48*gather+.42*show)
    feelers(f,-.41*show,.4*settle)
    f.P.add('leg_far',r=-3.4*gather+3*show)
    f.P.add('leg_near',r=-3*gather+4*show)
    pendants(f,-.30*gather+.3*show,.45*settle)
    return f


FUNCS = {name:globals()[name] for name in ANIMS if name != 'idle_loop'}
FUNCS['idle_loop'] = idle
