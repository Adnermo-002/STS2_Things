"""Procedural animation curves — Origin Eye (本源利齿眼).
Spine space: x right, y up, rotation CCW-positive. Skeleton faces RIGHT (+x); the scene mirrors it (scale.x < 0) so in game it faces the player on the left.
Game timing: HEAL_BOSS "Attack" 0.45 s, DISTRACT "Attack" 0.70 s; StunTrigger -> die (held),
WakeUpTrigger -> revive, Hit -> hurt, Dead -> die.
"""
import math
from rigutil import Frame, clamp, ease, ease_out, ease_in, seg, bump, kick, hold, TAU
import rigdef as RD

NP = RD.NP
TENTS = RD.TENT_BONES


def pdir(k):  # petal direction in spine space
    dx, dy = RD.petal_dir(k); return dx, -dy


def base_idle(f, t, amp=1.0, period=2.4):
    w = TAU / period
    f.P.add('body', y=7 * amp * math.sin(w * t), r=1.6 * amp * math.sin(w * t + 0.8),
            x=3 * amp * math.sin(w * t * 0.5 + 0.3))
    for k in range(NP):
        dx, dy = pdir(k); ph = k * 0.52
        br = 4.0 * amp * math.sin(w * t - ph)
        f.P.add(f'pet{k}', x=dx * br, y=dy * br, r=2.2 * amp * math.sin(w * t * 2 - ph * 1.3))
    f.P.add('iris', x=5 * amp * math.sin(w * t * 0.5), y=3 * amp * math.sin(w * t + 1.1))
    f.P.add('jaw', r=2.2 * amp * max(0.0, math.sin(w * t * 2 + 0.4)))
    f.P.add('lid_top', r=-1.2 * amp * math.sin(w * t + 0.3))
    f.P.add('lid_low', y=-2.0 * amp * math.sin(w * t + 0.3))
    f.P.add('stalk', r=2.5 * amp * math.sin(w * t - 0.9)); f.P.add('stalk2', r=4 * amp * math.sin(w * t - 1.6))
    for ti, (tn, names) in enumerate(TENTS.items()):
        for i, b in enumerate(names):
            f.bias[b] = 2.2 * amp * math.sin(w * t - i * 0.75 - ti * 1.9)


def petals_flare(f, amt, rot=0.0):
    for k in range(NP):
        dx, dy = pdir(k)
        f.P.add(f'pet{k}', x=dx * amt, y=dy * amt, r=rot * dx)


def idle(t):
    f = Frame(); base_idle(f, t); return f


def attack(t):
    f = Frame(); base_idle(f, t, amp=0.4)
    wind = bump(t, 0.0, 0.28, 0.40)                 # pull back
    lunge = bump(t, 0.30, 0.42, 0.85)               # strike towards the player (left)
    openm = bump(t, 0.08, 0.30, 0.44)               # mouths wide before the bite
    bite = hold(t, 0.40, 0.46, 0.62, 0.95)          # jaws clamp shut (contact 0.45)
    f.P.add('body', x=-22 * wind + 58 * lunge - 6 * kick(t, 0.46, 3.0, 6.0), y=6 * wind - 8 * lunge,
            r=7 * wind - 9 * lunge)
    petals_flare(f, 16 * openm - 10 * bite + 8 * wind, rot=5 * wind - 6 * lunge)
    f.P.add('lid_top', r=-5 * openm + 6 * bite)
    f.P.add('lid_low', y=-6 * openm + 4 * bite, r=-1 * openm)
    f.P.add('jaw', r=18 * openm - 5 * bite)
    f.P.add('iris', x=10 * (wind + lunge), s=0.12 * openm - 0.1 * bite)
    for names in TENTS.values():
        for i, b in enumerate(names):
            f.bias[b] = f.bias.get(b, 0) + 2.5 * wind - 2 * lunge
    return f


def hurt(t):
    f = Frame(); base_idle(f, t, amp=0.3)
    hit = kick(t, 0.02, 2.6, 5.5); rec = bump(t, 0.0, 0.08, 0.45)
    f.P.add('body', x=-26 * rec - 4 * hit, r=9 * rec + 3 * hit, y=-4 * rec)
    f.P.add('lid_top', r=9 * rec); f.P.add('lid_low', y=8 * rec)
    f.P.add('iris', sx=-0.25 * rec, sy=-0.12 * rec, x=-6 * hit)
    for k in range(NP):
        f.P.add(f'pet{k}', r=5 * kick(t, 0.02 + 0.01 * k, 5.0, 7.0))
    f.P.add('jaw', r=-4 * rec)
    return f


def collapse(f, c):
    """c: 0 = alive rest pose, 1 = downed illusion"""
    e = ease(c)
    f.P.add('body', y=-45 * e, r=-14 * e, x=-10 * e)
    for k in range(NP):
        dx, dy = pdir(k)
        f.P.add(f'pet{k}', x=-dx * 26 * e, y=-dy * 26 * e - 14 * e, r=10 * dx * e)
    f.P.add('lid_top', r=11 * e); f.P.add('lid_low', y=12 * e)
    f.P.add('iris', s=-0.4 * e); f.P.add('jaw', r=-6 * e)
    f.P.add('stalk', r=10 * e); f.P.add('stalk2', r=16 * e)
    for names in TENTS.values():
        for i, b in enumerate(names):
            f.bias[b] = f.bias.get(b, 0) - 2.5 * e
    a = 1 - 0.55 * ease(seg(c, 0.3, 1.0))
    f.tint = (1.0, 1.0, 1.0, a)


def die(t):
    f = Frame(); base_idle(f, t, amp=max(0.0, 1 - t / 0.5))
    shock = kick(t, 0.0, 3.0, 6.0)
    f.P.add('body', x=-10 * shock, r=6 * shock)
    collapse(f, seg(t, 0.12, 1.05))
    return f


def revive(t):
    f = Frame(); base_idle(f, t, amp=ease(seg(t, 0.5, 0.9)))
    c = 1 - ease_out(seg(t, 0.0, 0.62))
    collapse(f, c)
    pop = kick(t, 0.45, 2.6, 5.0)
    petals_flare(f, 10 * pop); f.P.add('body', y=8 * pop)
    return f


ANIMS = {'idle_loop': (2.4, True), 'attack': (1.0, False), 'hurt': (0.5, False),
         'die': (1.2, False), 'revive': (0.9, False)}
FUNCS = {'idle_loop': idle, 'attack': attack, 'hurt': hurt, 'die': die, 'revive': revive}
COLD_START = ('revive',)
