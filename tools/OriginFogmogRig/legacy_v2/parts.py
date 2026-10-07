"""Origin Fogmog v2 — split origin_fogmog.png (886x954) into many rig parts with occlusion fill.
Back -> front: leg_l, leg_r, arm_l, claw_l1..4, body, eye_l, eye_r, mouth, arm_r, claw_r1..4, cap
Plus additive glow overlays (cap_glow, face_glow) and spore FX sprites.
Output: parts/<name>.png + parts/meta.json {name: {x,y,w,h}} in source px."""
import json, os
import numpy as np, cv2
from PIL import Image

SRC = np.array(Image.open('src.png').convert('RGBA'))
H, W = SRC.shape[:2]
# remove the signature mark bottom-right
SRC[835:905, 790:860] = 0
A = SRC[..., 3] > 8
RGB = SRC[..., :3].copy()
r, g, b = [RGB[..., i].astype(int) for i in range(3)]
HSV = cv2.cvtColor(RGB, cv2.COLOR_RGB2HSV)
yy, xx = np.mgrid[0:H, 0:W]


def poly(pts):
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 1); return m.astype(bool)


def ell(cx, cy, ax, ay):
    m = np.zeros((H, W), np.uint8); cv2.ellipse(m, (cx, cy), (ax, ay), 0, 0, 360, 1, -1); return m.astype(bool)


def dil(m, px):
    return cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))).astype(bool)


def fill_holes(m):
    p = np.pad(m.astype(np.uint8), 1); msk = np.zeros((p.shape[0] + 2, p.shape[1] + 2), np.uint8)
    cv2.floodFill(p, msk, (0, 0), 2); return m | (p[1:-1, 1:-1] == 0)


def largest(m):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if n <= 1: return m
    return lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))


def comps(m, min_area):
    n, lab, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    return [(lab == k, cen[k]) for k in range(1, n) if st[k, cv2.CC_STAT_AREA] >= min_area]


# ---------------------------------------------------------------- colour classes
red = A & (r > g + 75) & (r > b + 70) & (yy < 440)
red = fill_holes(largest(cv2.morphologyEx(red.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(bool)))
glow = A & (g > r + 60) & (g > b + 60)
olive = A & (HSV[..., 0] >= 20) & (HSV[..., 0] <= 40) & (HSV[..., 1] > 90) & (g > 80) & ~(g > r + 40)

# ---------------------------------------------------------------- cap = red dome + gills + top spikes
TRUNK_TOP = poly([(298, 170), (602, 160), (610, 300), (598, 400), (300, 420), (290, 300)])
gill = A & ~red & (yy < 445) & (((xx < 296) & (yy < 440)) | ((xx > 604) & (yy < 355)))
gill &= ~poly([(200, 520), (330, 420), (330, 560)])          # keep the trunk-side spike near the left shoulder
cap = red | gill | (A & (yy < 70))
cap = fill_holes(largest(cap | (A & dil(red, 3) & ~TRUNK_TOP & (yy < 300))))
# gill parts that reach into the trunk column stay with the cap only where they are not trunk
cap &= ~(TRUNK_TOP & ~red & (yy > 200))

# ---------------------------------------------------------------- limbs
ARM_L = [(345, 480), (338, 530), (322, 580), (297, 613), (258, 658), (247, 700), (250, 835), (40, 835), (45, 690),
         (150, 615), (212, 558), (232, 528), (300, 508)]
ARM_R = [(585, 400), (650, 405), (720, 480), (800, 560), (870, 650), (886, 835), (680, 835), (680, 700),
         (674, 612), (640, 552), (618, 530), (600, 480)]
LEG_L = [(262, 650), (278, 692), (312, 735), (360, 760), (437, 773), (445, 850), (445, 954), (170, 954),
         (175, 850), (245, 812), (262, 760)]
LEG_R = [(468, 773), (540, 763), (600, 732), (640, 690), (662, 760), (706, 828), (760, 954), (468, 954)]

arm_l_all = A & poly(ARM_L) & ~cap
arm_r_all = A & poly(ARM_R) & ~cap
arm_l_all = largest(dil(arm_l_all, 1) & arm_l_all | (olive & poly(ARM_L))) | (olive & poly(ARM_L))
arm_r_all = largest(arm_r_all) | (olive & poly(ARM_R))

# claws: olive blobs of the hands (+ 3 px outline), each its own part
def claws_of(region, side):
    cm = olive & region & (yy > 680)
    cm = cv2.morphologyEx(cm.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    out = []
    for m, c in comps(cm, 150):
        m = dil(m, 3) & A & region
        m = m & (yy > 695)
        out.append((m, c))
    out.sort(key=lambda mc: mc[1][0])   # left -> right
    return out

claws_l = claws_of(poly(ARM_L), 'l')
claws_r = claws_of(poly(ARM_R), 'r')
print('claws', len(claws_l), len(claws_r), [tuple(int(v) for v in c) for _, c in claws_l + claws_r])
claw_l_any = np.any([m for m, _ in claws_l], 0); claw_r_any = np.any([m for m, _ in claws_r], 0)
arm_l = arm_l_all & ~claw_l_any
arm_r = arm_r_all & ~claw_r_any
leg_l = A & poly(LEG_L) & ~cap & ~arm_l_all & ~arm_r_all
leg_r = A & poly(LEG_R) & ~cap & ~arm_l_all & ~arm_r_all
body = A & ~cap & ~arm_l_all & ~arm_r_all & ~leg_l & ~leg_r
isl = body & ~largest(body)
leg_l |= isl & (xx < 455) & (yy > 700); leg_r |= isl & (xx >= 455) & (yy > 700)
body &= ~(isl & (yy > 700))
low = body & (yy >= 800)
leg_l |= low & (xx < 455); leg_r |= low & (xx >= 455); body &= ~low

# ---------------------------------------------------------------- face overlays
dark = A & (RGB.max(-1) < 70)
mouth_core = largest(dark & poly([(360, 300), (455, 300), (455, 500), (360, 500)]))
mouth = dil(fill_holes(mouth_core), 5) & body
eye_l = ell(340, 352, 22, 44) & body
eye_r = ell(456, 362, 22, 36) & body

# ---------------------------------------------------------------- inpaint helper
def inpaint(known, radius=7):
    img = RGB.copy(); img[~known] = 0
    return cv2.inpaint(img, (~known).astype(np.uint8), radius, cv2.INPAINT_TELEA)


def smooth_fill(known):
    """push-pull fill: normalized blurs from coarse to fine (no Telea streaks)."""
    k = known.astype(np.float32); c = RGB.astype(np.float32) * k[..., None]
    out = np.zeros_like(c); have = np.zeros(k.shape, np.float32)
    for sig in (64, 32, 16, 8, 4, 2):
        num = cv2.GaussianBlur(c, (0, 0), sig); den = cv2.GaussianBlur(k, (0, 0), sig)
        est = num / np.maximum(den[..., None], 1e-5)
        w = np.clip(den * 4, 0, 1)
        out = out * (1 - w[..., None]) + est * w[..., None]
    return out


def wood_fill(known, region, seed=3):
    col = smooth_fill(known)
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), sigmaX=1.2, sigmaY=10)
    n /= (n.std() + 1e-6)
    hole = region & ~known
    col[hole] *= (1 + 0.045 * n[hole, None])
    return np.clip(col, 0, 255).astype(np.uint8)


def make(vis, extra, fill='telea', dark_fill=0.0, fade=None):
    region = vis | extra
    if extra.any():
        col = wood_fill(vis, region) if fill == 'wood' else inpaint(vis)
    else:
        col = RGB.copy()
    col = np.where(vis[..., None], RGB, col)
    alpha = np.zeros((H, W), np.float32); alpha[region] = 255
    alpha[vis] = SRC[..., 3][vis]
    if fade is not None:
        fm, px = fade
        d = cv2.distanceTransform((~vis).astype(np.uint8), cv2.DIST_L2, 5)
        sel = fm & ~vis
        alpha[sel] *= np.clip(1 - d[sel] / px, 0, 1)
    if dark_fill:
        f = region & ~vis; col[f] = (col[f] * (1 - dark_fill)).astype(np.uint8)
    return np.dstack([col, alpha.clip(0, 255).astype(np.uint8)]), region


def extend(m, other, dx, dy, steps):
    out = np.zeros_like(m)
    for k in range(1, steps + 1):
        out |= np.roll(np.roll(m, int(round(dy * k)), 0), int(round(dx * k)), 1)
    return out & other & ~m


parts = {}
# BODY: the full trunk is painted in underneath cap (top), both arms near the shoulders, face features and leg tops.
face = eye_l | eye_r | mouth
body_vis = body & ~face
trunk_hull = fill_holes(dil(body | face, 2))
under_cap = cap & poly([(292, 170), (608, 160), (640, 300), (640, 440), (270, 440), (262, 300)])
under_arm_r = arm_r_all & poly([(585, 395), (660, 405), (700, 470), (700, 640), (600, 700), (560, 600)])
under_arm_l = arm_l_all & poly([(350, 470), (240, 520), (220, 640), (300, 700), (380, 640)])
under_legs = (leg_l | leg_r) & (yy < 800) & poly([(250, 640), (660, 640), (660, 800), (250, 800)])
body_extra = (under_cap | under_arm_r | face) & ~body_vis
parts['body'] = make(body_vis, body_extra, fill='wood',
                     fade=((under_cap & (yy < 215)) | (under_arm_r & (xx > 675)), 26))
parts['eye_l'] = make(eye_l, np.zeros_like(A))
parts['eye_r'] = make(eye_r, np.zeros_like(A))
parts['mouth'] = make(mouth, np.zeros_like(A))
parts['leg_l'] = make(leg_l, extend(leg_l, body | arm_l_all, 0, -1, 30), dark_fill=0.10)
parts['leg_r'] = make(leg_r, extend(leg_r, body | arm_r_all, 0, -1, 30), dark_fill=0.10)
# arms continue into the shoulder (under the trunk) so rotation never opens a gap
parts['arm_l'] = make(arm_l, extend(arm_l, body, 0.8, -0.6, 45) | (dil(claw_l_any, 4) & ~claw_l_any & ~arm_l & dil(arm_l, 8)),
                      dark_fill=0.08)
arm_r_extra = (dil(claw_r_any, 4) & ~claw_r_any & ~arm_r & dil(arm_r, 8))
parts['arm_r'] = make(arm_r, arm_r_extra, dark_fill=0.08)
for i, (m, _) in enumerate(claws_l): parts[f'claw_l{i + 1}'] = make(m, np.zeros_like(A))
for i, (m, _) in enumerate(claws_r): parts[f'claw_r{i + 1}'] = make(m, np.zeros_like(A))
parts['cap'] = make(cap, np.zeros_like(A))

# ---------------------------------------------------------------- glow overlays (additive): green spots / eyes / drips
def glow_part(mask, grow=6, blur=5):
    m = dil(mask, grow)
    a = cv2.GaussianBlur((mask.astype(np.float32) * 255), (0, 0), blur)
    a = np.maximum(a, mask * 200.0) * m
    col = np.zeros((H, W, 3), np.uint8); col[...] = (70, 200, 60)
    return np.dstack([col, a.clip(0, 255).astype(np.uint8)]), m

parts['cap_glow'] = glow_part(glow & cap)
parts['face_glow'] = glow_part(glow & ~cap & (yy < 520), grow=5, blur=4)

# spore FX sprite: one bright spot cut from the cap, soft halo
spot = largest(glow & cap & poly([(280, 80), (360, 80), (360, 140), (280, 140)]))
ys, xs = np.nonzero(spot); cy, cx = int(ys.mean()), int(xs.mean())
# procedural round spore (a cut cap spot had hard rectangular edges once it drifted off the cap)
_yy, _xx = np.mgrid[0:45, 0:53].astype(np.float32)
_r = np.hypot((_xx - 26) / 1.0, (_yy - 22) / 1.0)
_core = np.clip(1 - _r / 12.0, 0, 1) ** 1.1
_halo = np.exp(-(_r / 14.0) ** 2) * np.clip((22 - _r) / 5.0, 0, 1)
_a = np.clip(0.7 * _halo + _core, 0, 1)
_rgb = np.stack([70 + 150 * _core, 205 + 50 * _core, 70 + 90 * _core], -1)
sp = np.dstack([_rgb, _a * 255]).round().clip(0, 255).astype(np.uint8)
sp[sp[..., 3] == 0, :3] = 0
parts_extra = {'spore': sp}

# drop tiny orphan specks (claw line-art crumbs) from limb layers
for _n in ('arm_l', 'arm_r', 'leg_l', 'leg_r'):
    _rgba = parts[_n][0]
    _cnt, _lab, _st, _ = cv2.connectedComponentsWithStats((_rgba[..., 3] > 0).astype(np.uint8), connectivity=8)
    for _k in range(1, _cnt):
        if _st[_k, cv2.CC_STAT_AREA] < 100: _rgba[_lab == _k] = 0
os.makedirs('parts', exist_ok=True)
for f in os.listdir('parts'): os.remove(os.path.join('parts', f))
ORDER = (['leg_l', 'leg_r', 'arm_l'] + [f'claw_l{i + 1}' for i in range(len(claws_l))] +
         ['body', 'face_glow', 'eye_l', 'eye_r', 'mouth', 'arm_r'] + [f'claw_r{i + 1}' for i in range(len(claws_r))] +
         ['cap', 'cap_glow'])
meta = {}
for n in ORDER:
    rgba, _ = parts[n]
    if not (rgba[..., 3] > 0).any(): print("EMPTY", n); continue
    ys, xs = np.nonzero(rgba[..., 3] > 0)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    x0, y0 = max(0, x0 - 2), max(0, y0 - 2); x1, y1 = min(W, x1 + 2), min(H, y1 + 2)
    crop = rgba[y0:y1, x0:x1].copy(); crop[crop[..., 3] == 0, :3] = 0
    Image.fromarray(crop).save(f'parts/{n}.png')
    meta[n] = dict(x=int(x0), y=int(y0), w=int(x1 - x0), h=int(y1 - y0))
Image.fromarray(parts_extra['spore']).save('parts/spore.png')
meta['spore'] = dict(x=int(cx - 26), y=int(cy - 22), w=53, h=45)
json.dump(dict(meta=meta, order=ORDER, claws_l=[[float(v) for v in c] for _, c in claws_l],
               claws_r=[[float(v) for v in c] for _, c in claws_r]), open('parts/meta_full.json', 'w'), indent=1)
json.dump(meta, open('parts/meta.json', 'w'), indent=1)

# self check: static recomposite vs source (glows excluded)
comp = np.zeros((H, W, 4), np.float32)
for n in ORDER:
    if 'glow' in n: continue
    mm = meta[n]; p = np.array(Image.open(f'parts/{n}.png')).astype(np.float32) / 255
    dst = comp[mm['y']:mm['y'] + mm['h'], mm['x']:mm['x'] + mm['w']]
    a = p[..., 3:4]
    dst[..., :3] = p[..., :3] * a + dst[..., :3] * (1 - a); dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)
src = SRC.astype(np.float32) / 255
da = np.abs(comp[..., 3] - src[..., 3]) * 255
dc = (np.abs(comp[..., :3] - src[..., :3]).max(-1) * 255)[src[..., 3] > 0.5]
print('recomp alpha mean %.3f | colour mean %.3f p99.9 %.1f' % (da.mean(), dc.mean(), np.percentile(dc, 99.9)))
print({n: (meta[n]['w'], meta[n]['h']) for n in ORDER})

# spore FX slots (8 copies of the same sprite, each its own attachment)
import shutil
for i in range(1, 9):
    shutil.copy('parts/spore.png', f'parts/spore{i}.png'); meta[f'spore{i}'] = dict(meta['spore'])
json.dump(meta, open('parts/meta.json', 'w'), indent=1)


# additive slots: fully transparent texels must be black (no square halos under PMA blending)
for _n in ['cap_glow', 'face_glow', 'spore'] + [f'spore{i}' for i in range(1, 9)]:
    _p = f'parts/{_n}.png'
    if os.path.exists(_p):
        _a = np.array(Image.open(_p).convert('RGBA')).astype(np.float32)
        _a[_a[..., 3] == 0, :3] = 0
        Image.fromarray(_a.round().astype(np.uint8)).save(_p)
