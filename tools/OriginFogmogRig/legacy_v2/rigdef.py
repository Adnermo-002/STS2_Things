"""Rig definition v2 — Origin Fogmog (本源雾菇). Source pixels of origin_fogmog.png (886x954).
Faces LEFT (towards the player): forward = -x in spine space.
Structure follows vanilla fogmog: separate cap, trunk, eyes, mouth, arms with individual claws, legs (IK feet),
plus additive glow on the cap spots / face drips and 8 spore FX sprites (the 'origin' spores)."""
import json, math
from rigutil import chain_skin

NAME = 'origin_fogmog'
ORIGIN = (430.0, 945.0)
VIEW = dict(scale=0.40, W=560, H=480, ox=280, oy=440)

_meta = json.load(open('parts/meta.json'))
_sp = _meta['spore1']; SPORE_AT = (_sp['x'] + _sp['w'] / 2, _sp['y'] + _sp['h'] / 2)

CLAW_L = {'claw_l1': (104, 702), 'claw_l2': (140, 712), 'claw_l3': (214, 716)}
CLAW_R = {'claw_r1': (716, 713), 'claw_r2': (795, 704), 'claw_r3': (832, 698), 'claw_r4': (853, 703)}

BONES = [
    ('root', None, ORIGIN),
    ('hip', 'root', (430, 720)),
    ('spine1', 'hip', (430, 560)),
    ('spine2', 'spine1', (430, 400)),
    ('eye_l', 'spine2', (340, 352)), ('eye_r', 'spine2', (456, 362)),
    ('mouth', 'spine2', (408, 395)),
    ('cap', 'spine2', (430, 225)),
    ('cap_l', 'cap', (235, 245)), ('cap_l2', 'cap_l', (70, 315)),
    ('cap_r', 'cap', (630, 190)), ('cap_r2', 'cap_r', (830, 225)),
    ('shoulder_l', 'spine1', (338, 515)), ('elbow_l', 'shoulder_l', (228, 590)), ('wrist_l', 'elbow_l', (160, 672)),
    ('shoulder_r', 'spine1', (612, 448)), ('elbow_r', 'shoulder_r', (722, 522)), ('wrist_r', 'elbow_r', (790, 632)),
    ('thigh_l', 'hip', (345, 760)), ('knee_l', 'thigh_l', (330, 840)), ('ankle_l', 'knee_l', (312, 895)),
    ('thigh_r', 'hip', (560, 760)), ('knee_r', 'thigh_r', (580, 840)), ('ankle_r', 'knee_r', (615, 895)),
]
BONES += [(n, 'wrist_l', p) for n, p in CLAW_L.items()]
BONES += [(n, 'wrist_r', p) for n, p in CLAW_R.items()]
BONES += [(f'spore{i}', 'root', SPORE_AT) for i in range(1, 9)]
POS = {n: p for n, _, p in BONES}

ORDER = (['leg_l', 'leg_r', 'arm_l'] + list(CLAW_L) + ['body', 'eye_l', 'eye_r', 'mouth', 'arm_r'] + list(CLAW_R) + ['cap'])
SPORES = [f'spore{i}' for i in range(1, 9)]
GLOW_OF = {'face_glow': 'mouth', 'cap_glow': 'cap', **{s: None for s in SPORES}}
GLOW_SKIN = {'face_glow': 'face_glow', 'cap_glow': 'cap', **{s: s for s in SPORES}}
NOSCALE = tuple(SPORES)
GLOW_ALPHA = 1.0

SKIN = {
    'cap': [('cap', (330, 120), (560, 120))] + chain_skin(['cap_l', 'cap_l2'], POS, (0, 360))
           + chain_skin(['cap_r', 'cap_r2'], POS, (886, 240)),
    'body': [('hip', (430, 820), (430, 660)), ('spine1', (430, 660), (430, 470)), ('spine2', (430, 470), (430, 200))],
    'eye_l': [('eye_l', (0, 0), (1, 0))], 'eye_r': [('eye_r', (0, 0), (1, 0))], 'mouth': [('mouth', (0, 0), (1, 0))],
    'arm_l': [('spine1', (380, 470), (420, 560))] + chain_skin(['shoulder_l', 'elbow_l', 'wrist_l'], POS, (120, 760)),
    'arm_r': [('spine1', (560, 420), (540, 520))] + chain_skin(['shoulder_r', 'elbow_r', 'wrist_r'], POS, (830, 760)),
    'leg_l': [('hip', (380, 700), (430, 700))] + chain_skin(['thigh_l', 'knee_l', 'ankle_l'], POS, (250, 945)),
    'leg_r': [('hip', (480, 700), (530, 700))] + chain_skin(['thigh_r', 'knee_r', 'ankle_r'], POS, (690, 945)),
}
for n in list(CLAW_L) + list(CLAW_R): SKIN[n] = [(n, (0, 0), (1, 0))]
for s in SPORES: SKIN[s] = [(s, (0, 0), (1, 0))]
SIGMA = {'cap': 70.0, 'body': 45.0, 'arm_l': 20.0, 'arm_r': 20.0, 'leg_l': 24.0, 'leg_r': 24.0}
SPACING = {'cap': 22, 'body': 22, 'arm_l': 14, 'arm_r': 14, 'leg_l': 16, 'leg_r': 16}

CHAINS = {
    'cap_l': dict(bones=['cap_l', 'cap_l2'], freq=2.0, zeta=0.25, clamp=10, gain=0.014, rgain=0.4, taper=0.1),
    'cap_r': dict(bones=['cap_r', 'cap_r2'], freq=2.0, zeta=0.25, clamp=10, gain=0.014, rgain=0.4, taper=0.1),
}

_rest = {}


def post(P, W, f, sk):
    """Plant the feet with two-bone IK (anims may slide a foot via f.extra['foot_l'/'foot_r'] = (dx, dy))."""
    import rigkit
    if not _rest:
        W0 = sk.world({})
        for s in ('l', 'r'):
            _rest[s] = W0[f'ankle_{s}'][:2, 2].copy()
            _rest['a' + s] = math.degrees(math.atan2(W0[f'ankle_{s}'][1, 0], W0[f'ankle_{s}'][0, 0]))
    for s, bend in (('l', -1.0), ('r', 1.0)):
        dx, dy = f.extra.get(f'foot_{s}', (0.0, 0.0))
        tgt = (_rest[s][0] + dx, _rest[s][1] + dy)
        rigkit.ik2(sk, sk.world(P), P, f'thigh_{s}', f'knee_{s}', f'ankle_{s}', tgt, bend=bend)
        Wn = sk.world(P)[f'ankle_{s}']
        cur = math.degrees(math.atan2(Wn[1, 0], Wn[0, 0]))
        r0 = P.get(f'ankle_{s}', (0, 0, 0, 1, 1))
        P[f'ankle_{s}'] = (r0[0] - rigkit.wrap(cur - _rest['a' + s]) + f.extra.get(f'toe_{s}', 0.0),) + tuple(r0[1:])


# Detail parts inherit the weight field of the surface they sit on (fixes eyes/mouth/claws sliding
# off the trunk and hands whenever the blended meshes bend).
INHERIT = {
    'eye_l': ('body', {'spine2': 'eye_l'}),
    'eye_r': ('body', {'spine2': 'eye_r'}),
    'mouth': ('body', {'spine2': 'mouth'}),
    'face_glow': ('body', {'spine2': 'mouth'}),
    **{c: ('arm_l', {'wrist_l': c}) for c in CLAW_L},
    **{c: ('arm_r', {'wrist_r': c}) for c in CLAW_R},
}
SKIN['face_glow'] = [('mouth', (0, 0), (1, 0))]
