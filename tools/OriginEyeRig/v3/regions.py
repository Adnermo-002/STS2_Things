"""Load the vanilla eye_with_teeth atlas regions (unrotated, whitespace offsets applied).
Vanilla inputs are not shipped: set EYE_REF to a folder holding eye_with_teeth.{png,atlas,skel}
(e.g. <STS2 unpack>/animations/monsters/eye_with_teeth), default ../ref."""
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get('EYE_REF', os.path.join(HERE, '..', 'ref'))
VPNG = os.path.join(REF, 'eye_with_teeth.png')
VATL = os.path.join(REF, 'eye_with_teeth.atlas')


def parse_atlas(path):
    regions = {}; cur = None; lines = open(path).read().splitlines()
    for line in lines[1:]:
        if not line.strip(): continue
        if ':' not in line: cur = line.strip(); regions[cur] = {}
        elif cur: k, v = line.split(':', 1); regions[cur][k.strip()] = v.strip()
    return regions


def vanilla_regions():
    page = np.array(Image.open(VPNG).convert('RGBA'))
    out = {}
    for n, d in parse_atlas(VATL).items():
        x, y, w, h = map(int, d['bounds'].split(','))
        rot = d.get('rotate') == '90'
        sub = page[y:y + (w if rot else h), x:x + (h if rot else w)]
        if rot: sub = np.rot90(sub, -1)
        if 'offsets' in d:
            ox, oy, Wf, Hf = map(int, d['offsets'].split(','))
            full = np.zeros((Hf, Wf, 4), np.uint8); full[Hf - oy - sub.shape[0]:Hf - oy, ox:ox + sub.shape[1]] = sub; sub = full
        out[n] = sub
    return out
