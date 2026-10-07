"""A soft continuous sponge mesh; face, three crown openings, feet and belly articulate independently."""
import numpy as np

NAME = 'water_sponge'
ORIGIN = (640, 1172)
VIEW = dict(scale=.43, W=760, H=650, ox=370, oy=600)
ORDER = ['skin']
SPACING = {'skin': 18}
CHAINS = {}
BONES = [
 ('root', None, ORIGIN), ('body', 'root', (666, 822)),
 ('belly', 'body', (620, 918)), ('head', 'body', (405, 552)),
 ('nozzle', 'head', (281, 644)), ('eye_far', 'head', (312, 523)),
 ('eye_near', 'head', (425, 537)), ('crown_l', 'body', (452, 264)),
 ('crown_mid', 'body', (720, 167)), ('crown_r', 'body', (972, 415)),
 ('arm_far', 'body', (207, 850)), ('arm_near', 'body', (958, 855)),
 ('foot_l', 'root', (410, 1138)), ('foot_r', 'root', (918, 1144)),
]
SKIN = {'skin': [('body', (0, 0), (0, 0))]}

FIELDS = [
 ('belly', (630, 920), (238, 160), .90),
 ('head', (408, 548), (170, 150), .90),
 ('crown_l', (455, 254), (115, 112), .92),
 ('crown_mid', (718, 170), (142, 138), .95),
 ('crown_r', (970, 405), (112, 145), .94),
 ('arm_far', (210, 845), (62, 100), .96),
 ('arm_near', (959, 854), (88, 145), .96),
 ('nozzle', (285, 643), (78, 65), .96),
 ('eye_far', (312, 525), (44, 58), .91),
 ('eye_near', (426, 537), (58, 65), .91),
 ('foot_l', (410, 1138), (96, 51), .999),
 ('foot_r', (918, 1144), (95, 47), .999),
]


def weights(name, points):
    points = np.asarray(points)
    fields = []
    for bone, center, radius, strength in FIELDS:
        distance = ((points - np.asarray(center)) / np.asarray(radius)) ** 2
        fields.append((bone, strength * np.exp(-distance.sum(axis=1) * 1.45)))
    result = []
    for index in range(len(points)):
        acc = {'body': 1.}
        for bone, values in fields:
            weight = float(values[index])
            acc = {key: value * (1-weight) for key, value in acc.items()}
            acc[bone] = acc.get(bone, 0) + weight
        acc = {key: value for key, value in acc.items() if value > .002}
        total = sum(acc.values())
        result.append([(key, value/total) for key, value in acc.items()])
    return result
