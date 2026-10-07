"""Rig definition for the Bowlbug Progenitor (盛碗虫祖母). Positions are source-image pixels."""
import json, os
ORIGIN = (760.0, 776.0)          # ground point under the body -> spine (0,0)
def S(p): return (round(p[0] - ORIGIN[0], 2), round(ORIGIN[1] - p[1], 2))

_here = os.path.dirname(os.path.abspath(__file__))
J = {int(k): v for k, v in json.load(open(os.path.join(_here, 'leg_joints.json'))).items()}
J[1]['hip'] = [585, 588]         # socket centre (segmentation contact edge is long)
LEG_HOST = {1: 'front', 2: 'dome2', 3: 'dome3', 4: 'rear', 5: 'rear'}

CREST = {  # base (hidden under head/shield), tip
    1: ((298, 245), (280, 77)), 2: ((336, 262), (322, 132)), 3: ((360, 272), (387, 132)),
    4: ((416, 290), (460, 155)), 5: ((476, 325), (510, 240)),
}

BONES = [
    ('root', None, ORIGIN),
    ('body', 'root', (760, 560)),
    ('rear', 'body', (1150, 470)),
    ('egg', 'rear', (1140, 380)),
    ('egg_f', 'egg', (990, 400)),
    ('egg_m', 'egg', (1130, 290)),
    ('egg_r', 'egg', (1285, 360)),
    ('egg_lo', 'egg', (1150, 500)),
    ('mid', 'body', (790, 470)),
    ('mem_rear', 'body', (880, 480)),
    ('dome2', 'body', (700, 575)),
    ('dome3', 'body', (925, 600)),
    ('front', 'body', (600, 520)),
    ('leaf', 'front', (615, 455)),
    ('mem_front', 'front', (500, 540)),
    ('shield', 'front', (470, 480)),
    ('neck', 'front', (360, 540)),
    ('head', 'neck', (300, 515)),
    ('mand_u', 'head', (92, 574)),
    ('mand_l', 'head', (214, 628)),
    ('eye', 'head', (148, 566)),
    ('pupil', 'eye', (122, 560)),
]
for i, (b, t) in CREST.items():
    mid = ((b[0] + t[0]) / 2, (b[1] + t[1]) / 2)
    BONES += [(f'crest{i}_0', 'front', b), (f'crest{i}_1', f'crest{i}_0', mid)]
for i in range(1, 6):
    BONES += [(f'leg{i}_hip', LEG_HOST[i], tuple(J[i]['hip'])),
              (f'leg{i}_knee', f'leg{i}_hip', tuple(J[i]['knee'])),
              (f'leg{i}_ankle', f'leg{i}_knee', tuple(J[i]['ankle']))]

# part -> skin segments (bone, a, b); single entry = rigid
SKIN = {
    'membrane_rear': [('mem_rear', (860, 430), (940, 520)), ('mid', (780, 380), (780, 380)),
                      ('rear', (1060, 560), (1250, 620)), ('dome2', (720, 600), (720, 600))],
    'membrane_front': [('mem_front', (470, 480), (560, 600)), ('shield', (380, 420), (380, 420)),
                       ('body', (640, 480), (640, 560))],
    'egg_sac': [('egg_f', (980, 330), (990, 470)), ('egg_m', (1080, 200), (1200, 300)),
                ('egg_r', (1270, 280), (1300, 460)), ('egg_lo', (1080, 500), (1220, 520))],
    'rear_shell': [('rear', (0, 0), (0, 0))],
    'shell_mid': [('mid', (0, 0), (0, 0))],
    'dome2': [('dome2', (0, 0), (0, 0))], 'dome3': [('dome3', (0, 0), (0, 0))],
    'leaf_plate': [('leaf', (0, 0), (0, 0))],
    'shell_front': [('shield', (0, 0), (0, 0))],
    'head': [('head', (0, 0), (0, 0))],
    'mandible_upper': [('mand_u', (0, 0), (0, 0))], 'mandible_lower': [('mand_l', (0, 0), (0, 0))],
    'eye': [('eye', (0, 0), (0, 0))], 'pupil': [('pupil', (0, 0), (0, 0))],
}
for i, (b, t) in CREST.items():
    mid = ((b[0] + t[0]) / 2, (b[1] + t[1]) / 2)
    SKIN[f'crest_{i}'] = [(f'crest{i}_0', b, mid), (f'crest{i}_1', mid, t)]
for i in range(1, 6):
    SKIN[f'leg{i}_upper'] = [(f'leg{i}_hip', (0, 0), (0, 0))]
    SKIN[f'leg{i}_shin'] = [(f'leg{i}_knee', (0, 0), (0, 0))]
    SKIN[f'leg{i}_claw'] = [(f'leg{i}_ankle', (0, 0), (0, 0))]
SIGMA = {'membrane_rear': 70.0, 'membrane_front': 60.0, 'egg_sac': 80.0}
CREST_CHAIN = True
