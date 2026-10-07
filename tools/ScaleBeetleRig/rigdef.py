"""Rigid chitin, continuous articulated limbs, and two seven-link antennae."""
from pathlib import Path
import json
import math
import numpy as np

NAME = 'scale_beetle'
ORIGIN = (563.5, 883.0)
VIEW = dict(scale=0.45, W=850, H=590, ox=485, oy=540)
HERE = Path(__file__).resolve().parent
ORDER_DATA = json.loads((HERE / 'parts/order.json').read_text())
ORDER = ORDER_DATA['order']
GLOW_OF = ORDER_DATA['glow_of']
GLOW_SCALE = 0.5
GLOW_ALPHA = 0.60

LEGS = {
    'front': ((424, 662), (365, 758), (194, 840), (48, 866), 'thorax'),
    'middle': ((590, 687), (631, 697), (681, 850), (741, 883), 'body'),
    'rear': ((778, 738), (886, 627), (926, 825), (997, 854), 'abdomen'),
    'far_front': ((291, 673), (223, 718), (75, 750), (10, 765), 'thorax'),
    'far_middle': ((610, 726), (606, 769), (557, 802), (508, 816), 'body'),
    'far_rear': ((835, 734), (831, 777), (782, 810), (733, 824), 'abdomen'),
}
ANTENNAE = {
    'far': [(99, 563), (82, 497), (70, 400), (102, 292), (154, 201), (230, 121), (319, 53), (426, 18)],
    'near': [(125, 578), (124, 510), (145, 405), (187, 308), (255, 230), (350, 171), (453, 128), (554, 129)],
}
BONES = [
    ('root', None, ORIGIN),
    ('ground_shadow', 'root', (578, 864)),
    ('body', 'root', (650, 657)),
    ('abdomen', 'body', (800, 620)),
    ('thorax', 'body', (458, 604)),
    ('neck', 'thorax', (365, 593)),
    ('head', 'neck', (285, 604)),
    ('neck_shield', 'thorax', (366, 568)),
    ('collar', 'thorax', (465, 536)),
    ('shell_far', 'abdomen', (765, 430)),
    ('shell_near', 'abdomen', (775, 579)),
    ('jaw_far', 'head', (60, 642)),
    ('jaw_near', 'head', (164, 676)),
    ('eye', 'head', (202, 617)),
]
for side, points in ANTENNAE.items():
    for i, point in enumerate(points):
        BONES.append((f'antenna_{side}_{i}', 'head' if i == 0 else f'antenna_{side}_{i-1}', point))
for name, (hip, knee, ankle, toe, parent) in LEGS.items():
    BONES += [(f'{name}_hip', parent, hip), (f'{name}_knee', f'{name}_hip', knee),
              (f'{name}_ankle', f'{name}_knee', ankle), (f'{name}_toe', f'{name}_ankle', toe)]

SKIN = {name: [(name, (0, 0), (0, 0))]
        for name in ['ground_shadow', 'body', 'head', 'neck_shield', 'collar', 'shell_far', 'shell_near', 'eye', 'jaw_far', 'jaw_near']}
for side, points in ANTENNAE.items():
    SKIN[f'antenna_{side}'] = [(f'antenna_{side}_{i}', points[i], points[i+1]) for i in range(7)]
for name, (hip, knee, ankle, toe, _) in LEGS.items():
    SKIN[f'leg_{name}'] = [(f'{name}_hip', hip, knee), (f'{name}_knee', knee, ankle),
                          (f'{name}_ankle', ankle, toe)]

SPACING = {name: (7 if name.startswith('antenna') else 9 if name.startswith('leg') else 24) for name in SKIN}
SPACING.update({'eye': 14, 'jaw_far': 10, 'jaw_near': 10})
CHAINS = {f'feelers_{side}': dict(bones=[f'antenna_{side}_{i}' for i in range(7)],
          freq=3.8 if side == 'near' else 3.4, zeta=0.55, clamp=9.0, gain=0.003,
          rgain=0.003, taper=0.045) for side in ANTENNAE}


def weights(name, points):
    """Nearest arc coordinate, with blending confined to the actual joint collars.

    A single indexed mesh spans each whole appendage, so adjacent triangles share
    vertices. Long rigid cores keep the shell plates and antenna beads intact.
    """
    segments = SKIN[name]
    if len(segments) == 1:
        return [[(segments[0][0], 1.0)] for _ in points]
    distances, params = [], []
    lengths = []
    for _, a, b in segments:
        a, b = np.array(a), np.array(b)
        vector = b - a
        length = np.linalg.norm(vector)
        t = np.clip((points-a) @ vector / (length*length), 0, 1)
        distances.append(np.linalg.norm(points - a - t[:, None]*vector, axis=1))
        params.append(t)
        lengths.append(length)
    nearest = np.array(distances).argmin(axis=0)
    out = []
    for point, index in enumerate(nearest):
        t = params[index][point]
        width = (9.0 if name.startswith('antenna') else 14.0) / lengths[index]
        bone = segments[index][0]
        if index > 0 and t < width:
            u = np.clip(0.5 + 0.5*t/width, 0, 1)
            mix = u*u*(3-2*u)
            out.append([(segments[index-1][0], 1-mix), (bone, mix)])
        elif index < len(segments)-1 and t > 1-width:
            u = np.clip(0.5*(t-(1-width))/width, 0, 1)
            mix = u*u*(3-2*u)
            out.append([(bone, 1-mix), (segments[index+1][0], mix)])
        else:
            out.append([(bone, 1.0)])
    return [[(bone, float(weight)) for bone, weight in row if weight > 1e-8] for row in out]


def s(point):
    return np.array([point[0]-ORIGIN[0], ORIGIN[1]-point[1]], float)


def angle(vector):
    return math.atan2(vector[1], vector[0])


def rotate_matrix(degrees):
    a = math.radians(degrees)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def local_matrix(position, degrees):
    matrix = np.eye(3)
    matrix[:2, :2] = rotate_matrix(degrees)
    matrix[:2, 2] = position
    return matrix


def wrap(degrees):
    return (degrees+180) % 360-180


def post(pose, world, frame, skeleton):
    # The mass travels horizontally, while its contact shadow stays on the floor.
    body = pose.get('body', (0, 0, 0, 1, 1))
    pose['ground_shadow'] = (0, body[1], 0, 1, 1)
    for name, (hip, knee, ankle, toe, parent) in LEGS.items():
        hip_bone, knee_bone, ankle_bone = f'{name}_hip', f'{name}_knee', f'{name}_ankle'
        matrix = world[parent]
        h = (matrix @ np.r_[skeleton.local[hip_bone], 1])[:2]
        rest_a, rest_h, rest_k = s(ankle), s(hip), s(knee)
        offset = frame.extra.get('feet', {}).get(name, (0, 0, 0))
        target = rest_a + np.array(offset[:2])
        len1, len2 = np.linalg.norm(rest_k-rest_h), np.linalg.norm(rest_a-rest_k)
        delta = target-h
        distance = np.linalg.norm(delta)
        reach = np.clip(distance, abs(len1-len2)+0.02, len1+len2-0.02)
        if abs(reach-distance) > 1e-5:
            # Keep the contact plane when extending/recovering from a crouch.
            dy = np.clip(delta[1], -reach+0.001, reach-0.001)
            side = 1 if ankle[0] >= hip[0] else -1
            target = h + [side*math.sqrt(max(0, reach*reach-dy*dy)), dy]
        local_target = (np.linalg.inv(matrix) @ np.r_[target, 1])[:2] - skeleton.local[hip_bone]
        distance = np.linalg.norm(local_target)
        va, vb = rest_k-rest_h, rest_a-rest_h
        cross = va[0]*vb[1]-va[1]*vb[0]
        sign = 1 if cross >= 0 else -1
        alpha = math.acos(np.clip((len1*len1+distance*distance-len2*len2)/(2*len1*distance), -1, 1))
        upper_angle = angle(local_target)-sign*alpha
        r1 = wrap(math.degrees(upper_angle-angle(skeleton.local[knee_bone])))
        upper = matrix @ local_matrix(skeleton.local[hip_bone], r1)
        k = (upper @ np.r_[skeleton.local[knee_bone], 1])[:2]
        r2 = wrap(math.degrees(angle(target-k)-angle(upper[:2, :2] @ skeleton.local[ankle_bone])))
        lower = upper @ local_matrix(skeleton.local[knee_bone], r2)
        foot_vector = s(toe)-s(ankle)
        r3 = wrap(math.degrees(angle(foot_vector)-angle(lower[:2, :2] @ foot_vector))+offset[2])
        pose[hip_bone] = (r1, 0, 0, 1, 1)
        pose[knee_bone] = (r2, 0, 0, 1, 1)
        pose[ankle_bone] = (r3, 0, 0, 1, 1)
    if frame.extra.get('antenna_floor'):
        for side in ANTENNAE:
            floor = 30.0 if side == 'near' else 43.0
            for i in range(7):
                current = skeleton.world(pose)
                bone, child = f'antenna_{side}_{i}', f'antenna_{side}_{i+1}'
                base = current[bone][:2, 2]
                tip = current[child][:2, 2]
                if tip[1] >= floor:
                    continue
                parent = current[skeleton.parent[bone]]
                length = np.linalg.norm(skeleton.local[child])
                dy = np.clip(floor-base[1], -length+0.01, length-0.01)
                dx = -math.sqrt(max(0, length*length-dy*dy))
                rotation = wrap(math.degrees(angle((dx, dy))-angle(parent[:2, :2] @ skeleton.local[child])))
                old = pose.get(bone, (0, 0, 0, 1, 1))
                pose[bone] = (rotation,) + tuple(old[1:])
