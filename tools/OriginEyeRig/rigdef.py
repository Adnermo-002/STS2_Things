"""Rig definition — Origin Eye (本源利齿眼), the Origin Fogmog's illusion minion.
Positions are source pixels of flower.png (tentacles extend below/right of it)."""
import json, math, os
from rigutil import chain_skin

NAME = 'origin_eye_with_teeth'
ORIGIN = (520.0, 1010.0)          # ground point under the floating flower -> spine (0,0)
VIEW = dict(scale=0.42, W=700, H=520, ox=300, oy=500)
_here = os.path.dirname(os.path.abspath(__file__))
TJ = json.load(open(os.path.join(_here, 'tentacles.json')))

C = (520.0, 430.0)                # flower centre
NP = 12                           # radial petal bones
def petal_dir(k):
    a = math.radians(k * 360.0 / NP)
    return math.cos(a), math.sin(a)

BONES = [('root', None, ORIGIN), ('body', 'root', C)]
for k in range(NP):
    dx, dy = petal_dir(k)
    BONES.append((f'pet{k}', 'body', (C[0] + dx * 110, C[1] + dy * 110)))
BONES += [
    ('eye', 'body', (522, 425)),
    ('iris', 'eye', (587, 420)),
    ('lid_top', 'eye', (556, 250)),     # hinge top-right of the upper-left lid
    ('lid_low', 'eye', (522, 548)),
    ('jaw', 'eye', (552, 244)),         # hinge of the big side maw
    ('stalk', 'body', (525, 590)),
    ('stalk2', 'stalk', (518, 700)),
]
TENT_BONES = {}
for t, pts in TJ.items():
    names = [f'{t}{i}' for i in range(len(pts) - 1)]
    TENT_BONES[t] = names
    for i, n in enumerate(names):
        BONES.append((n, 'body' if i == 0 else names[i - 1], tuple(pts[i])))
POS = {n: p for n, _, p in BONES}

ORDER = ['tent_c', 'tent_b', 'tent_a', 'petals', 'stalk', 'jaw', 'eyeball', 'iris', 'lid_low', 'lid_top']

SKIN = {
    'petals': [(f'pet{k}', (C[0] + petal_dir(k)[0] * 90, C[1] + petal_dir(k)[1] * 90),
                (C[0] + petal_dir(k)[0] * 480, C[1] + petal_dir(k)[1] * 480)) for k in range(NP)],
    'eyeball': [('eye', None, None)],
    'iris': [('iris', None, None)],
    'lid_top': [('lid_top', None, None)],
    'lid_low': [('lid_low', None, None)],
    'jaw': [('jaw', None, None)],
    'stalk': [('stalk', (525, 585), (522, 680)), ('stalk2', (522, 680), (515, 810))],
}
for t, names in TENT_BONES.items():
    SKIN[t] = chain_skin(names, POS, tuple(TJ[t][-1]))
SIGMA = {'petals': 80.0, 'stalk': 40.0, 'tent_a': 30.0, 'tent_b': 30.0, 'tent_c': 30.0}
SPACING = {'petals': 26, 'eyeball': 30, 'iris': 30, 'lid_top': 24, 'lid_low': 24, 'jaw': 24, 'stalk': 18,
           'tent_a': 14, 'tent_b': 14, 'tent_c': 14}

CHAINS = {t: dict(bones=names, freq=2.2, zeta=0.38, clamp=9, gain=0.012, rgain=0.25, taper=0.08)
          for t, names in TENT_BONES.items()}
