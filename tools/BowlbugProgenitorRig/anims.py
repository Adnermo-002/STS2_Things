"""Procedural animation curves for the Bowlbug Progenitor.

Every function returns an AnimFrame: non-leg bone pose, glow levels, foot
offsets (in root space, before IK), crest fan targets, tint and collapse.
Legs are solved by export.py (planted-foot IK with sliding) and the crest
spikes by a spring simulation driven by the head's motion.
"""
import math
FPS = 30
TAU = 2 * math.pi
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_in(x): x = clamp(x); return x ** 3
def seg(t, t0, t1): return clamp((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t0)
def bump(t, t0, t1, t2):
    """0 -> 1 (ease t0..t1) -> 0 (ease t1..t2)"""
    return ease(seg(t, t0, t1)) * (1 - ease(seg(t, t1, t2)))
def kick(t, t0, freq=3.0, damp=4.0):
    if t < t0: return 0.0
    x = t - t0; return math.exp(-damp * x) * math.sin(TAU * freq * x)
def dspring(t, t0, freq=3.0, damp=4.0):
    if t < t0: return 0.0
    x = t - t0; return math.exp(-damp * x) * math.cos(TAU * freq * x)
_pn = None
def pulse(x, rise=0.035, dec=0.16):
    global _pn
    if x <= 0: return 0.0
    f = lambda z: (1 - math.exp(-z / rise)) * math.exp(-z / dec)
    if _pn is None: _pn = max(f(z / 1000) for z in range(1, 1000))
    return f(x) / _pn

class Pose(dict):
    def add(self, b, r=0, x=0, y=0, sx=0, sy=0, s=0):
        R, X, Y, SX, SY = self.get(b, (0, 0, 0, 1, 1))
        self[b] = (R + r, X + x, Y + y, SX * (1 + sx + s), SY * (1 + sy + s))

GLOWS = ['rear_shell_glow', 'shell_mid_glow', 'head_glow', 'shell_front_glow', 'egg_sac_glow', 'eye_glow']
GEMS = ['head_glow', 'shell_front_glow', 'shell_mid_glow', 'rear_shell_glow']   # front -> rear

class F:
    def __init__(self):
        self.P = Pose(); self.glow = {g: 0.0 for g in GLOWS}
        self.feet = {i: [0.0, 0.0, 0.0] for i in range(1, 6)}    # dx, dy (spine units, y up), claw tilt
        self.fan = {i: 0.0 for i in range(1, 6)}                 # extra crest target angle
        self.tint = (1.0, 1.0, 1.0); self.c = 0.0
    def step(self, i, t, t0, dur, dx=0.0, lift=10.0, tilt=14.0):
        """foot i: lift and re-plant, shifted by dx"""
        u = seg(t, t0, t0 + dur)
        if u <= 0: return
        e = ease(u); arc = math.sin(math.pi * u) if u < 1 else 0.0
        self.feet[i][0] += dx * e; self.feet[i][1] += lift * arc; self.feet[i][2] += tilt * arc
    def stomp(self, i, t, t0, dur=0.26, lift=18.0):
        """quick raise and slam (no displacement)"""
        u = seg(t, t0, t0 + dur)
        if 0 < u < 1:
            up = math.sin(math.pi * min(1.0, u / 0.7)) if u < 0.7 else max(0.0, 1 - (u - 0.7) / 0.12)
            self.feet[i][1] += lift * up; self.feet[i][2] += 18 * up
    def gems(self, level):
        for g in GEMS: self.glow[g] += level

# ------------------------------------------------------------------ idle
def idle(t, f=None, amp=1.0, T=3.0):
    f = f or F(); P = f.P
    ph = TAU * t / T
    br = 0.5 - 0.5 * math.cos(ph)                       # 0..1 breath
    P.add('body', y=-3.2 * br * amp, r=0.35 * math.sin(ph) * amp)
    P.add('mid', r=0.9 * math.sin(ph + 0.5) * amp, y=1.8 * math.sin(ph + 0.5) * amp, s=0.006 * br * amp)
    P.add('rear', r=-0.55 * math.sin(ph + 1.0) * amp, sx=0.006 * math.sin(ph + 1.0) * amp)
    for b, lag in (('egg_f', 0.0), ('egg_m', 1.1), ('egg_r', 2.2)):
        P.add(b, s=0.028 * math.sin(2 * ph - lag) * amp)
    P.add('egg_lo', sy=0.022 * math.sin(2 * ph - 1.7) * amp, y=1.2 * math.sin(2 * ph - 1.7) * amp)
    P.add('mem_rear', s=0.02 * math.sin(ph + 1.5) * amp)
    P.add('mem_front', s=0.016 * math.sin(ph + 2.0) * amp)
    P.add('front', r=0.7 * math.sin(ph + 0.3) * amp)
    P.add('shield', r=0.6 * math.sin(ph + 0.8) * amp)
    P.add('leaf', r=1.4 * math.sin(ph + 1.2) * amp)
    P.add('dome2', r=0.8 * math.sin(ph + 0.4) * amp); P.add('dome3', r=-0.7 * math.sin(ph + 0.9) * amp)
    P.add('neck', r=1.6 * math.sin(ph + 0.6) * amp)
    P.add('head', r=(2.2 * math.sin(ph + 1.1) + 0.8 * math.sin(2 * ph + 0.4)) * amp)
    # mandibles: slow breathing gape + a quick chatter burst
    ch = bump(t, 1.85, 1.95, 2.45) * math.sin(TAU * 8.0 * (t - 1.85))
    P.add('mand_u', r=(-2.5 * br - 5 * max(0, ch)) * amp)
    P.add('mand_l', r=(3.0 * br + 6 * max(0, ch)) * amp)
    # pupil: look around, hold, come back
    lx = -5.5 * bump(t, 0.55, 0.68, 1.55) + 4.5 * bump(t, 1.6, 1.72, 2.55)
    ly = 1.5 * bump(t, 0.55, 0.68, 1.55) - 2.0 * bump(t, 1.6, 1.72, 2.55)
    P.add('pupil', x=lx * amp, y=ly * amp, s=0.05 * math.sin(ph * 2) * amp)
    P.add('eye', s=0.01 * math.sin(ph + 2.0) * amp)
    for i in range(1, 6): f.fan[i] += 1.5 * math.sin(ph + 0.6 * i) * amp
    # feet fidget (lift and replant in place)
    f.step(3, t, 0.95, 0.42, 0, 9 * amp, 10 * amp)
    f.step(1, t, 2.05, 0.40, 0, 8 * amp, 10 * amp)
    wave = 0.5 - 0.5 * math.cos(ph)
    for k, g in enumerate(GEMS):
        f.glow[g] += (0.14 + 0.16 * (0.5 - 0.5 * math.cos(ph - 0.7 * k))) * amp
    f.glow['egg_sac_glow'] += (0.10 + 0.10 * (0.5 - 0.5 * math.cos(2 * ph - 1.1))) * amp
    f.glow['eye_glow'] += 0.08 * wave * amp
    return f

# ------------------------------------------------------------------ attack (mandible lunge)
def attack(t):
    f = idle(t, amp=1 - bump(t, 0.0, 0.2, 1.2) * 0.8); P = f.P
    ant = ease(seg(t, 0.0, 0.34)) * (1 - ease_out(seg(t, 0.34, 0.44)))
    hit = ease_out(seg(t, 0.36, 0.46)) * (1 - ease(seg(t, 0.62, 1.15)))
    P.add('body', x=10 * ant - 22 * hit + 4 * kick(t, 0.46, 2.2, 5), y=-6 * ant - 4 * hit, r=-0.8 * ant + 0.6 * hit)
    P.add('front', r=-3.5 * ant + 3 * hit + 1.5 * kick(t, 0.46, 2.6, 5))
    P.add('neck', r=-3.5 * ant + 3.5 * hit + 2 * kick(t, 0.46, 3.0, 5))
    P.add('head', r=-4.5 * ant + 4.5 * hit + 3 * kick(t, 0.47, 3.4, 5))
    gape = ease(seg(t, 0.05, 0.34)) * (1 - ease_out(seg(t, 0.40, 0.45)))
    snap = kick(t, 0.45, 5.0, 7)
    P.add('mand_u', r=-22 * gape + 7 * snap); P.add('mand_l', r=25 * gape - 8 * snap)
    P.add('shield', r=-2 * ant + 2 * hit); P.add('leaf', r=-5 * ant + 6 * kick(t, 0.46, 2.5, 4))
    P.add('mid', r=-1.5 * ant + 1.2 * hit); P.add('rear', r=-2.0 * ant + 1.5 * hit, x=4 * ant)
    P.add('pupil', x=-5 * ease(seg(t, 0.1, 0.3)) * (1 - ease(seg(t, 0.8, 1.1))), s=-0.2 * ant)
    for i in range(1, 6): f.fan[i] += -8 * ant + 10 * hit
    f.step(1, t, 0.30, 0.22, -22, 16, 14); f.step(1, t, 0.78, 0.30, 22, 8, 8)
    f.step(2, t, 0.40, 0.20, -8, 6, 6); f.step(2, t, 0.86, 0.26, 8, 5, 5)
    f.step(3, t, 0.36, 0.20, -14, 10, 10); f.step(3, t, 0.84, 0.28, 14, 8, 8)
    f.step(4, t, 0.40, 0.20, -18, 12, 10); f.step(4, t, 0.90, 0.28, 18, 8, 8)
    f.step(5, t, 0.33, 0.22, -20, 12, 10); f.step(5, t, 0.95, 0.26, 20, 8, 8)
    f.glow['eye_glow'] += 0.8 * bump(t, 0.2, 0.42, 0.9)
    f.gems(0.25 * bump(t, 0.3, 0.45, 1.0))
    return f

# ------------------------------------------------------------------ cast (rear up, screech)
def cast(t):
    f = idle(t, amp=1 - bump(t, 0.0, 0.2, 1.3) * 0.85); P = f.P
    crouch = bump(t, 0.0, 0.25, 0.42)
    up = ease_out(seg(t, 0.25, 0.5)) * (1 - ease(seg(t, 0.95, 1.35)))
    scream = bump(t, 0.45, 0.55, 1.05)
    shake = math.sin(TAU * 13 * t) * scream
    P.add('body', y=-8 * crouch + 3 * up, r=1.5 * crouch - 2.5 * up, x=6 * up)
    P.add('front', r=1.5 * crouch - 5 * up + 0.6 * shake)
    P.add('neck', r=2 * crouch - 5 * up + 1.0 * shake)
    P.add('head', r=2 * crouch - 6 * up + 1.8 * shake + 2 * kick(t, 1.0, 2.5, 4))
    P.add('mand_u', r=-20 * up * (0.8 + 0.2 * math.sin(TAU * 11 * t)))
    P.add('mand_l', r=24 * up * (0.8 + 0.2 * math.sin(TAU * 11 * t + 1)))
    P.add('leaf', r=-3 * crouch + 9 * up + 4 * kick(t, 1.0, 2.2, 4))
    P.add('shield', r=-4 * up); P.add('mid', r=2.5 * up, y=5 * up, s=0.01 * up)
    P.add('rear', r=-1.5 * up, sx=0.01 * up)
    P.add('egg_m', s=0.04 * scream * math.sin(TAU * 6 * t)); P.add('egg_f', s=0.03 * scream * math.sin(TAU * 6 * t + 1))
    P.add('mem_front', s=0.03 * up); P.add('mem_rear', s=0.025 * up)
    P.add('pupil', s=-0.3 * scream)
    P.add('eye', s=0.06 * scream)
    for i in range(1, 6): f.fan[i] += (-6 - 2.5 * (i - 3)) * up + 3 * shake
    f.stomp(1, t, 0.28, 0.24, 14); f.stomp(2, t, 0.34, 0.24, 10)
    for k, g in enumerate(GEMS): f.glow[g] += 0.9 * bump(t, 0.38 + 0.05 * k, 0.6 + 0.05 * k, 1.3)
    f.glow['eye_glow'] += 0.9 * scream
    f.glow['egg_sac_glow'] += 0.35 * bump(t, 0.5, 0.7, 1.2)
    return f

# ------------------------------------------------------------------ hurt
def hurt(t):
    f = idle(t, amp=1 - bump(t, 0.0, 0.05, 0.65) * 0.8); P = f.P
    k1 = kick(t, 0.0, 2.4, 6.0); k2 = kick(t, 0.02, 3.2, 6.5); k3 = kick(t, 0.03, 4.0, 7.0)
    P.add('body', x=16 * k1, y=-5 * abs(k1), r=-2.5 * k1)
    P.add('front', r=-4 * k2); P.add('neck', r=-5 * k2); P.add('head', r=-8 * k3)
    P.add('mand_u', r=-16 * abs(k3)); P.add('mand_l', r=18 * abs(k3))
    P.add('leaf', r=-8 * k2); P.add('shield', r=-3 * k2)
    P.add('mid', r=-2 * k1, x=4 * k1); P.add('rear', r=2 * k1)
    P.add('egg', sy=-0.04 * abs(k1), sx=0.03 * abs(k1))
    P.add('egg_m', s=0.04 * k2); P.add('egg_r', s=-0.035 * k2)
    P.add('pupil', s=-0.4 * bump(t, 0.0, 0.04, 0.5), x=3 * k2)
    P.add('eye', s=-0.05 * abs(k3))
    for i in range(1, 6): f.fan[i] += 6 * k2
    f.glow['eye_glow'] += 0.5 * bump(t, 0.0, 0.03, 0.35)
    return f

# ------------------------------------------------------------------ collapse pose (die end / revive start)
FEET_SPLAY = {1: (-34, 0), 2: (-16, 0), 3: (14, 0), 4: (26, 0), 5: (38, 0)}
def collapse(f, c, t=0.0):
    P = f.P
    P.add('body', y=-74 * c, r=-1.0 * c)
    P.add('front', r=2 * c, y=-4 * c); P.add('neck', r=5 * c); P.add('head', r=7 * c)
    P.add('mand_u', r=-12 * c); P.add('mand_l', r=15 * c)
    P.add('mid', r=-3 * c, y=-6 * c); P.add('rear', r=3 * c, y=-4 * c)
    P.add('egg', sy=-0.07 * c, sx=0.02 * c, y=-6 * c)
    P.add('leaf', r=9 * c); P.add('shield', r=3 * c)
    P.add('mem_front', sy=-0.05 * c); P.add('mem_rear', sy=-0.06 * c)
    P.add('dome2', r=-5 * c); P.add('dome3', r=5 * c)
    P.add('pupil', s=0.25 * c, x=2 * c, y=-3 * c)
    for i in range(1, 6):
        f.fan[i] += (10 + 2 * i) * c
        dx, dy = FEET_SPLAY[i]; f.feet[i][0] += dx * c; f.feet[i][2] += -10 * c if i <= 2 else 10 * c
    g = 1 - 0.42 * c
    f.tint = (g, g * 0.97, g * 1.02); f.c = c

def die(t):
    f = idle(t, amp=max(0.0, 1 - seg(t, 0.0, 0.4))); P = f.P
    k1 = kick(t, 0.0, 2.2, 5.0)
    P.add('body', x=14 * k1); P.add('head', r=-8 * bump(t, 0.0, 0.12, 0.55)); P.add('neck', r=-4 * bump(t, 0.0, 0.12, 0.55))
    P.add('mand_u', r=-18 * bump(t, 0.02, 0.15, 0.7)); P.add('mand_l', r=20 * bump(t, 0.02, 0.15, 0.7))
    P.add('pupil', s=-0.4 * bump(t, 0.0, 0.05, 0.6))
    # legs give out in two stages, then the carcass settles with a bounce
    c = 0.35 * ease(seg(t, 0.35, 0.7)) + 0.65 * ease_in(seg(t, 0.75, 1.3))
    bounce = kick(t, 1.3, 2.4, 5.0)
    collapse(f, c)
    P.add('body', y=6 * bounce); P.add('head', r=-5 * bounce); P.add('rear', r=-2 * bounce)
    P.add('egg', sy=0.03 * kick(t, 1.3, 3.0, 5), sx=-0.02 * kick(t, 1.3, 3.0, 5))
    # last twitch of the front leg
    f.stomp(1, t, 1.9, 0.25, 8)
    f.glow['eye_glow'] += 0.6 * bump(t, 0.0, 0.05, 0.4)
    alive = 1 - ease(seg(t, 0.4, 1.4))
    for g in GLOWS: f.glow[g] *= alive
    f.gems(0.5 * bump(t, 0.2, 0.35, 1.1))
    return f

def revive(t):
    c = 1 - ease(seg(t, 0.25, 1.25)) * 1.0
    f = idle(t, amp=ease(seg(t, 1.0, 1.8))); P = f.P
    shiver = math.sin(TAU * 12 * t) * bump(t, 0.0, 0.2, 0.55)
    collapse(f, c)
    P.add('body', x=1.5 * shiver, y=6 * kick(t, 1.25, 2.4, 5))
    P.add('head', r=2 * shiver - 6 * bump(t, 1.0, 1.25, 1.7))
    P.add('neck', r=-3 * bump(t, 1.0, 1.25, 1.7))
    P.add('mand_u', r=-18 * bump(t, 1.1, 1.3, 1.65)); P.add('mand_l', r=20 * bump(t, 1.1, 1.3, 1.65))
    P.add('leaf', r=8 * kick(t, 1.2, 2.2, 4))
    for i in range(1, 6): f.fan[i] += -10 * bump(t, 1.05, 1.3, 1.75)
    f.stomp(2, t, 1.2, 0.25, 12); f.stomp(4, t, 1.3, 0.25, 12)
    for k, g in enumerate(GEMS): f.glow[g] += 1.0 * bump(t, 0.2 + 0.1 * k, 1.05 + 0.05 * k, 1.8)
    f.glow['egg_sac_glow'] += 0.6 * bump(t, 0.4, 1.1, 1.8)
    f.glow['eye_glow'] += 1.0 * bump(t, 0.9, 1.1, 1.7)
    return f

# ------------------------------------------------------------------ summon (lay an egg)
def summon(t):
    f = idle(t, amp=1 - bump(t, 0.0, 0.15, 1.2) * 0.85); P = f.P
    lift = bump(t, 0.0, 0.28, 0.95)
    P.add('rear', r=4.5 * lift, y=4 * lift); P.add('body', r=1.2 * lift, y=-4 * lift)
    P.add('front', r=1 * lift); P.add('neck', r=-2.5 * lift); P.add('head', r=-3.5 * lift)
    # peristaltic squeeze front -> rear, rebound after the pop
    for b, t0, a in (('egg_f', 0.28, 0.07), ('egg_m', 0.40, 0.08), ('egg_r', 0.52, 0.09)):
        P.add(b, s=-a * bump(t, t0, t0 + 0.14, t0 + 0.3) + 0.5 * a * kick(t, t0 + 0.3, 2.5, 4.5))
    P.add('egg_lo', sy=-0.06 * bump(t, 0.48, 0.63, 0.74), y=-6 * bump(t, 0.48, 0.63, 0.74))
    pop = kick(t, 0.70, 2.6, 5.0)
    P.add('egg', s=0.05 * pop); P.add('rear', x=7 * pop, r=2 * pop); P.add('body', y=4 * pop)
    P.add('mid', r=1.5 * pop, y=3 * lift); P.add('mem_rear', s=0.04 * bump(t, 0.36, 0.62, 0.86))
    P.add('mand_u', r=-14 * bump(t, 0.68, 0.8, 0.92) - 12 * bump(t, 0.94, 1.04, 1.16))
    P.add('mand_l', r=16 * bump(t, 0.68, 0.8, 0.92) + 14 * bump(t, 0.94, 1.04, 1.16))
    P.add('pupil', x=6 * bump(t, 0.1, 0.25, 0.9), y=2 * bump(t, 0.1, 0.25, 0.9))
    P.add('leaf', r=5 * pop)
    for i in range(1, 6): f.fan[i] += -5 * bump(t, 0.62, 0.78, 1.15)
    f.stomp(4, t, 0.60, 0.24, 14); f.stomp(5, t, 0.66, 0.24, 14)
    f.glow['egg_sac_glow'] += 1.0 * bump(t, 0.25, 0.70, 1.15)
    f.gems(0.35 * bump(t, 0.58, 0.72, 1.2))
    f.glow['rear_shell_glow'] += 0.4 * bump(t, 0.58, 0.72, 1.15)
    return f

# ------------------------------------------------------------------ power up (swell, gems flare, stomp)
def power_up(t):
    f = idle(t, amp=1 - bump(t, 0.0, 0.2, 1.4) * 0.85); P = f.P
    crouch = bump(t, 0.0, 0.28, 0.45)
    swell = ease_out(seg(t, 0.3, 0.6)) * (1 - ease(seg(t, 1.0, 1.5)))
    P.add('body', y=-7 * crouch + 2 * swell, sy=0.02 * swell, sx=0.01 * swell)
    P.add('mid', y=7 * swell - 3 * crouch, r=2.5 * swell, s=0.012 * swell)
    P.add('rear', r=-2 * swell, s=0.01 * swell); P.add('egg', s=0.03 * swell)
    P.add('leaf', r=12 * swell - 4 * crouch + 3 * kick(t, 1.0, 2, 4)); P.add('shield', r=-5 * swell + 2 * crouch)
    P.add('front', r=-3 * swell + 1.5 * crouch); P.add('neck', r=-3 * swell + 1.5 * crouch); P.add('head', r=-4 * swell + 2 * crouch)
    P.add('mem_front', s=0.04 * swell); P.add('mem_rear', s=0.035 * swell)
    clack = bump(t, 0.62, 0.7, 0.78) + bump(t, 0.8, 0.88, 0.96)
    P.add('mand_u', r=-18 * clack); P.add('mand_l', r=20 * clack)
    P.add('pupil', s=-0.25 * swell); P.add('eye', s=0.05 * swell)
    for i in range(1, 6): f.fan[i] += (-9 - 2.5 * (i - 3)) * swell
    f.stomp(1, t, 0.52, 0.26, 20); f.stomp(2, t, 0.62, 0.26, 16); f.stomp(3, t, 0.72, 0.26, 14)
    P.add('body', y=-3 * (kick(t, 0.72, 4, 8) + kick(t, 0.82, 4, 8)))
    for k, g in enumerate(GEMS): f.glow[g] += 1.0 * bump(t, 0.3 + 0.06 * k, 0.62 + 0.06 * k, 1.45)
    f.glow['egg_sac_glow'] += 0.5 * bump(t, 0.45, 0.8, 1.4)
    f.glow['eye_glow'] += 0.8 * bump(t, 0.4, 0.62, 1.2)
    return f

ANIMS = {'idle_loop': (3.0, True), 'attack': (1.25, False), 'cast': (1.4, False), 'hurt': (0.65, False),
         'die': (2.6, False), 'summon': (1.3, False), 'power_up': (1.5, False), 'revive': (1.8, False)}
FUNCS = {'idle_loop': idle, 'attack': attack, 'cast': cast, 'hurt': hurt, 'die': die,
         'summon': summon, 'power_up': power_up, 'revive': revive}
