"""Procedural animation curves v2 — Origin Fogmog (本源雾菇).
Spine space: x right, y up, rotation CCW-positive.  Faces LEFT: forward = -x.
Upright torso bone: POSITIVE rotation leans FORWARD (top towards -x).
Left arm (front side, -x) raises with negative r, right arm with positive r.
Claws: curl = fingers close (left claws +r, right claws -r point tips inward/back).
Game timing kept from v1: attack hit 0.50 s, power_up heal 0.55 s, summon spawn 0.75 s.
Flavour follows vanilla fogmog: heavy lumbering sway, cap wobble, blinking glowing eyes, spore puffs.
"""
import math, random
from rigutil import Frame, clamp, ease, ease_out, ease_in, seg, bump, kick, hold, TAU
import rigdef as R

SPORES = R.SPORES
MOUTH = R.POS['mouth']; SP0 = R.SPORE_AT
CAPTOP = (430, 90)
CLAWS_L = list(R.CLAW_L); CLAWS_R = list(R.CLAW_R)


def rel(p):   # source px point -> spine translate offset of a spore bone
    return (p[0] - SP0[0], -(p[1] - SP0[1]))


def curl(f, amt_l, amt_r, t=0.0, wig=0.0):
    for i, c in enumerate(CLAWS_L):
        f.P.add(c, r=amt_l * (1 + 0.15 * i) + wig * math.sin(TAU * 1.3 * t + i))
    for i, c in enumerate(CLAWS_R):
        f.P.add(c, r=-amt_r * (1 + 0.15 * i) - wig * math.sin(TAU * 1.3 * t + i + 0.5))


def blink(f, t, times, dur=0.16):
    b = 0.0
    for t0 in times:
        b = max(b, bump(t, t0, t0 + dur * 0.4, t0 + dur))
    for e in ('eye_l', 'eye_r'):
        f.P.add(e, sy=-0.88 * b, sx=0.06 * b)
    f.glow['face_glow'] = f.glow.get('face_glow', 0.0) * (1 - 0.7 * b)


def eyes(f, sq=0.0, wide=0.0):
    for e in ('eye_l', 'eye_r'):
        f.P.add(e, sy=-0.45 * sq + 0.25 * wide, sx=0.12 * wide)


def glow(f, cap, face):
    f.glow['cap_glow'] = clamp(cap); f.glow['face_glow'] = clamp(face)


def puff(f, t, t0, src, spread=1.0, n=8, dur=1.0, up=1.0, fwd=0.0, seed=1, size=1.0):
    """spore burst: each sprite leaves `src` at t0 + small stagger, drifts up/out, fades."""
    rnd = random.Random(seed)
    for i, s in enumerate(SPORES[:n]):
        st = t0 + rnd.uniform(0, 0.12)
        ang = math.radians(rnd.uniform(-70, 70) * spread + 90)
        spd = rnd.uniform(260, 460)
        u = seg(t, st, st + dur * rnd.uniform(0.8, 1.2))
        if u <= 0 or u >= 1: continue
        e = ease_out(u)
        ox, oy = rel(src)
        x = ox + math.cos(ang) * spd * e - fwd * 120 * e + 18 * math.sin(TAU * (1.4 * u + i * 0.3))
        y = oy + math.sin(ang) * spd * e * up + 40 * u * u
        sc = size * (0.35 + 0.45 * rnd.random()) * (1 + 0.5 * e)
        f.P.add(s, x=x, y=y, r=200 * u * (1 if i % 2 else -1), sx=sc - 1, sy=sc - 1)
        a = min(1.0, u / 0.12) * (1 - ease_in(u))
        f.glow[s] = max(f.glow.get(s, 0.0), a)


def base_idle(f, t, amp=1.0, period=2.8):
    w = TAU / period
    br = math.sin(w * t)
    f.P.add('hip', y=-6 * amp * (0.5 + 0.5 * br), x=2.5 * amp * math.sin(w * t * 0.5 * 2))
    f.P.add('spine1', sy=0.014 * amp * br, r=1.0 * amp * math.sin(w * t - 0.4))
    f.P.add('spine2', r=1.8 * amp * math.sin(w * t - 0.9), sy=0.012 * amp * br)
    f.P.add('cap', r=2.4 * amp * math.sin(w * t - 1.5), y=3.5 * amp * math.sin(w * t - 1.2))
    f.P.add('mouth', sy=0.06 * amp * br, sx=-0.02 * amp * br)
    f.P.add('shoulder_l', r=3.5 * amp * math.sin(w * t - 1.0)); f.P.add('elbow_l', r=4.0 * amp * math.sin(w * t - 1.6))
    f.P.add('wrist_l', r=5.0 * amp * math.sin(w * t - 2.1))
    f.P.add('shoulder_r', r=-3.5 * amp * math.sin(w * t - 1.2)); f.P.add('elbow_r', r=-4.0 * amp * math.sin(w * t - 1.8))
    f.P.add('wrist_r', r=-5.0 * amp * math.sin(w * t - 2.3))
    curl(f, 4 * amp * math.sin(w * t - 2.6), 4 * amp * math.sin(w * t - 2.8))
    for b in ('cap_l', 'cap_l2'): f.bias[b] = 2.0 * amp * math.sin(w * t - 2.0)
    for b in ('cap_r', 'cap_r2'): f.bias[b] = -2.0 * amp * math.sin(w * t - 2.0)
    glow(f, 0.28 + 0.22 * amp * (0.5 + 0.5 * math.sin(w * t - 0.5)), 0.35 + 0.2 * (0.5 + 0.5 * math.sin(w * t)))


def torso(f, lean=0.0, dx=0.0, dy=0.0, squash=0.0):
    f.P.add('hip', x=dx, y=dy)
    f.P.add('spine1', r=lean * 0.45, sy=squash, sx=-squash * 0.5)
    f.P.add('spine2', r=lean * 0.55)


def idle(t):
    f = Frame(); base_idle(f, t)
    blink(f, t, [0.9, 2.35])
    # one lazy spore drifting off the cap top per loop
    puff(f, t, 0.3, (520, 60), spread=0.4, n=2, dur=1.9, up=0.5, seed=7, size=0.8)
    return f


def attack(t):
    """Big overhead double rake like vanilla fogmog's swipe; contact at 0.50 s."""
    f = Frame(); base_idle(f, t, amp=0.3)
    wind = bump(t, 0.0, 0.32, 0.5)
    strike = hold(t, 0.4, 0.5, 0.62, 1.05)
    torso(f, lean=-12 * wind + 20 * strike, dx=16 * wind - 44 * strike, dy=-12 * strike + 6 * wind,
          squash=0.035 * wind - 0.05 * strike)
    f.P.add('shoulder_l', r=-55 * wind + 30 * strike); f.P.add('elbow_l', r=-20 * wind + 14 * strike)
    f.P.add('wrist_l', r=-18 * wind + 22 * strike)
    f.P.add('shoulder_r', r=40 * wind - 16 * strike); f.P.add('elbow_r', r=26 * wind - 10 * strike)
    f.P.add('wrist_r', r=16 * wind - 12 * strike)
    curl(f, -22 * wind + 38 * strike, -18 * wind + 30 * strike)       # claws splay in wind-up, snap shut on hit
    f.P.add('cap', r=-6 * wind + 8 * strike + 4 * kick(t, 0.5, 2.4, 5.0), y=4 * wind)
    f.P.add('mouth', sy=0.25 * wind - 0.08 * strike, sx=0.05 * wind)
    eyes(f, sq=strike, wide=wind * 0.6)
    glow(f, 0.3 + 0.5 * strike, 0.4 + 0.6 * wind)
    f.extra['foot_l'] = (-30 * ease(seg(t, 0.36, 0.48)) * (1 - ease(seg(t, 0.7, 1.05))), 12 * bump(t, 0.36, 0.42, 0.5))
    f.extra['toe_l'] = 8 * bump(t, 0.36, 0.44, 0.6)
    return f


def cast(t):
    """Spore incantation: rise, arms spread palms-up, cap shivers, spots flare, spores rise from the cap."""
    f = Frame(); base_idle(f, t, amp=0.4)
    up = hold(t, 0.0, 0.35, 0.7, 1.0)
    shiver = math.sin(TAU * 9 * t) * bump(t, 0.25, 0.45, 0.75)
    torso(f, lean=-7 * up, dy=10 * up, squash=0.035 * up)
    f.P.add('shoulder_l', r=-34 * up); f.P.add('elbow_l', r=-20 * up); f.P.add('wrist_l', r=-16 * up)
    f.P.add('shoulder_r', r=34 * up); f.P.add('elbow_r', r=20 * up); f.P.add('wrist_r', r=16 * up)
    curl(f, -24 * up, -24 * up, t, wig=5 * up)
    f.P.add('cap', r=3 * shiver, y=12 * up)
    f.P.add('mouth', sx=0.1 * up, sy=0.2 * up)
    eyes(f, wide=up)
    glow(f, 0.3 + 0.7 * up, 0.35 + 0.65 * up)
    puff(f, t, 0.3, CAPTOP, spread=1.0, n=8, dur=0.7, up=1.0, seed=3)
    return f


def hurt(t):
    f = Frame(); base_idle(f, t, amp=0.3)
    rec = bump(t, 0.0, 0.07, 0.55); jig = kick(t, 0.02, 3.2, 6.0)
    torso(f, lean=-14 * rec - 4 * jig, dx=24 * rec, dy=-8 * rec, squash=-0.03 * rec)
    f.P.add('cap', r=-6 * rec + 5 * kick(t, 0.05, 2.4, 5.0))
    f.P.add('shoulder_l', r=-16 * rec); f.P.add('shoulder_r', r=16 * rec)
    f.P.add('elbow_l', r=-12 * rec); f.P.add('elbow_r', r=12 * rec)
    curl(f, -20 * rec, -20 * rec)
    f.P.add('mouth', sx=-0.2 * rec, sy=0.2 * rec)
    eyes(f, sq=0.9 * bump(t, 0.0, 0.05, 0.4))
    glow(f, 0.3 - 0.2 * rec, 0.4 - 0.3 * rec)
    puff(f, t, 0.02, (430, 250), spread=1.2, n=3, dur=0.5, up=0.6, fwd=-0.6, seed=11, size=0.7)
    return f


def power_up(t):
    """Heal: crouch, then swell upward with a roar, spots blaze; heal lands at 0.55 s."""
    f = Frame(); base_idle(f, t, amp=0.3)
    crouch = bump(t, 0.0, 0.28, 0.46)
    swell = hold(t, 0.36, 0.55, 0.85, 1.3)
    torso(f, lean=6 * crouch - 9 * swell, dy=-30 * crouch + 16 * swell, squash=-0.045 * crouch + 0.06 * swell)
    f.P.add('spine2', s=0.05 * swell)
    f.P.add('cap', y=18 * swell - 7 * crouch, s=0.05 * swell, r=2.5 * kick(t, 0.55, 2.2, 4.0))
    f.P.add('shoulder_l', r=-12 * crouch - 46 * swell); f.P.add('elbow_l', r=-22 * swell); f.P.add('wrist_l', r=-20 * swell)
    f.P.add('shoulder_r', r=12 * crouch + 46 * swell); f.P.add('elbow_r', r=22 * swell); f.P.add('wrist_r', r=20 * swell)
    curl(f, 25 * crouch - 28 * swell, 25 * crouch - 28 * swell)
    f.P.add('mouth', sx=0.15 * swell, sy=0.32 * swell)
    eyes(f, sq=crouch, wide=swell)
    glow(f, 0.3 + 0.7 * swell, 0.4 + 0.6 * swell)
    puff(f, t, 0.52, (430, 200), spread=1.6, n=8, dur=0.75, up=1.0, seed=5)
    return f


def summon(t):
    """Rear back and scream a spore cloud from the mouth, then thrust both claws forward (spawn 0.75 s)."""
    f = Frame(); base_idle(f, t, amp=0.3)
    rear = bump(t, 0.0, 0.45, 0.75)
    push = hold(t, 0.6, 0.75, 0.95, 1.4)
    shake = math.sin(TAU * 11 * t) * bump(t, 0.2, 0.5, 0.8)
    torso(f, lean=-14 * rear + 14 * push, dx=12 * rear - 22 * push, dy=7 * rear - 7 * push)
    f.P.add('cap', r=3.5 * shake - 6 * rear + 7 * push, y=7 * rear)
    f.P.add('mouth', sx=0.18 * rear, sy=0.36 * rear + 0.12 * push)
    f.P.add('shoulder_l', r=-28 * rear + 34 * push); f.P.add('elbow_l', r=-14 * rear - 24 * push)
    f.P.add('wrist_l', r=-8 * rear - 20 * push)
    f.P.add('shoulder_r', r=28 * rear + 34 * push); f.P.add('elbow_r', r=14 * rear - 12 * push)
    f.P.add('wrist_r', r=8 * rear - 14 * push)
    curl(f, 18 * rear - 30 * push, 18 * rear - 30 * push)
    eyes(f, wide=rear)
    glow(f, 0.3 + 0.7 * max(rear, push), 0.4 + 0.6 * rear)
    puff(f, t, 0.55, MOUTH, spread=0.7, n=8, dur=0.8, up=0.3, fwd=1.0, seed=9, size=1.1)
    return f


def collapse(f, c, lean_sign=1.0):
    e = ease(c)
    torso(f, lean=20 * e * lean_sign, dx=-18 * e, dy=-70 * e, squash=-0.05 * e)
    f.P.add('cap', r=10 * e, y=-8 * e)
    f.P.add('shoulder_l', r=28 * e); f.P.add('elbow_l', r=20 * e); f.P.add('wrist_l', r=12 * e)
    f.P.add('shoulder_r', r=-24 * e); f.P.add('elbow_r', r=-22 * e); f.P.add('wrist_r', r=-12 * e)
    curl(f, 30 * e, 30 * e)
    f.P.add('mouth', sy=0.22 * e)
    f.extra['foot_l'] = (-8 * e, 0); f.extra['foot_r'] = (10 * e, 0)
    eyes(f, sq=e)


def die(t):
    f = Frame(); base_idle(f, t, amp=max(0.0, 1 - t / 0.4))
    stag = bump(t, 0.0, 0.18, 0.55)
    torso(f, lean=-14 * stag, dx=18 * stag)
    f.P.add('mouth', sx=0.14 * stag, sy=0.28 * stag)
    collapse(f, seg(t, 0.35, 1.45))
    f.P.add('cap', r=5 * kick(t, 1.3, 2.0, 4.0))
    for b in ('cap_l', 'cap_l2'): f.bias[b] = -7 * ease(seg(t, 0.8, 1.6))
    for b in ('cap_r', 'cap_r2'): f.bias[b] = 7 * ease(seg(t, 0.8, 1.6))
    fade = 1 - ease(seg(t, 0.4, 1.6))
    glow(f, 0.5 * fade + 0.4 * bump(t, 1.35, 1.45, 1.8), 0.4 * fade)
    puff(f, t, 1.38, (430, 330), spread=1.8, n=8, dur=1.0, up=0.7, seed=13)
    return f


def revive(t):
    f = Frame(); base_idle(f, t, amp=ease(seg(t, 1.2, 1.8)))
    c = 1 - ease_out(seg(t, 0.2, 1.25))
    collapse(f, c)
    pop = kick(t, 1.1, 2.0, 4.5)
    f.P.add('cap', y=9 * pop); f.P.add('mouth', sy=0.2 * bump(t, 0.9, 1.2, 1.6))
    wake = ease(seg(t, 0.0, 1.0))
    glow(f, 0.1 + 0.9 * bump(t, 0.0, 0.5, 1.6) + 0.3 * wake, 0.1 + 0.4 * wake)
    puff(f, t, 0.05, (430, 330), spread=1.4, n=6, dur=1.0, up=1.0, seed=17, size=0.8)
    return f


ANIMS = {'idle_loop': (2.8, True), 'attack': (1.2, False), 'cast': (1.0, False), 'hurt': (0.6, False),
         'die': (1.9, False), 'summon': (1.4, False), 'power_up': (1.3, False), 'revive': (1.8, False)}
FUNCS = {'idle_loop': idle, 'attack': attack, 'cast': cast, 'hurt': hurt, 'die': die,
         'summon': summon, 'power_up': power_up, 'revive': revive}
COLD_START = ('revive',)
