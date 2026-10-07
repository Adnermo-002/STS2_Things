"""Split the Origin Eye (本源利齿眼) illustration into rig parts.

Source: flower.png (monochrome grey + alpha, vanilla EyeWithTeeth texture convention) and
tentacle_src.png (one straight tentacle). Outputs parts/*.png + parts/meta.json and
tentacles.json (bone joints along each curved tentacle, source px).
"""
import json, math, os
import numpy as np, cv2
from PIL import Image

os.makedirs('parts', exist_ok=True)
src = np.array(Image.open('flower.png').convert('RGBA')).astype(np.float32)
H, W = src.shape[:2]
yy, xx = np.mgrid[0:H, 0:W]

EYE_C, EYE_R = (522.0, 425.0), 150.0
IRIS_C, IRIS_R = (587.0, 420.0), (47.0, 80.0)


def poly(pts):
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 1); return m > 0


circle = (xx - EYE_C[0]) ** 2 + (yy - EYE_C[1]) ** 2 <= (EYE_R + 6) ** 2
circle_in = (xx - EYE_C[0]) ** 2 + (yy - EYE_C[1]) ** 2 <= (EYE_R - 2) ** 2
iris = ((xx - IRIS_C[0]) / IRIS_R[0]) ** 2 + ((yy - IRIS_C[1]) / IRIS_R[1]) ** 2 <= 1.0

TOP_TIPS = [(366, 466), (415, 440), (445, 421), (472, 402), (488, 391), (503, 372), (518, 350),
            (528, 327), (545, 296), (555, 262), (562, 238)]
def inward(pts, d):
    out = []
    for x, y in pts:
        v = np.array([EYE_C[0] - x, EYE_C[1] - y]); v /= np.linalg.norm(v) + 1e-9
        out.append((x + v[0] * d, y + v[1] * d))
    return out
TOP_TIPS = inward(TOP_TIPS, 18)
lid_top = circle & poly(TOP_TIPS + [(562, 150), (330, 150), (330, 466)])
LOW_TIPS = [(366, 468), (437, 474), (482, 507), (510, 522), (540, 499), (560, 494), (590, 517),
            (612, 527), (637, 490), (662, 471), (690, 468)]
LOW_TIPS = inward(LOW_TIPS, 22)
lid_low = circle & poly(LOW_TIPS + [(690, 650), (366, 650)])
jaw = poly([(548, 262), (552, 234), (590, 220), (650, 210), (720, 200), (780, 194), (832, 190), (852, 204),
            (852, 262), (828, 296), (802, 332), (772, 367), (736, 392), (690, 405), (652, 403), (630, 380),
            (600, 330), (570, 290)]) & ~circle
jaw_over = circle & poly([(548, 246), (705, 246), (705, 318), (650, 300), (610, 290), (572, 280), (552, 268)]) & ~lid_top
jaw = jaw | jaw_over
stalk = poly([(486, 584), (566, 584), (552, 690), (542, 808), (490, 808), (480, 690)]) & ~circle & ~lid_low
eyeball_vis = circle & ~lid_top & ~lid_low & ~iris & ~jaw_over
alpha = src[..., 3] > 3
petals = alpha & ~circle & ~jaw & ~stalk

meta = {}
LAYERS = {}


def save(name, rgba, mask=None):
    a = rgba.copy()
    if mask is not None: a[..., 3] *= mask.astype(np.float32)
    LAYERS[name] = a


def write(name, a):
    ys, xs = np.where(a[..., 3] > 1)
    x0, y0, x1, y1 = xs.min() - 2, ys.min() - 2, xs.max() + 3, ys.max() + 3
    x0, y0 = max(x0, 0), max(y0, 0)
    crop = a[y0:y1, x0:x1]
    Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).save(f'parts/{name}.png')
    meta[name] = dict(x=int(x0), y=int(y0), w=int(crop.shape[1]), h=int(crop.shape[0]))


def fill_under(rgba, known, region, grey=167.0):
    """Paint hidden `region` by inpainting alpha from `known` pixels (colour stays the flat grey)."""
    a = np.where(known, rgba[..., 3], 0).astype(np.uint8)
    hole = (region & ~known).astype(np.uint8)
    filled = cv2.inpaint(a, hole, 9, cv2.INPAINT_TELEA).astype(np.float32)
    out = rgba.copy()
    out[..., 3] = np.where(hole > 0, filled, np.where(known, rgba[..., 3], 0))
    out[..., :3] = np.where((hole > 0)[..., None], grey, rgba[..., :3])
    return out


# eyeball: full sphere painted in under lids + iris
eye_known = eyeball_vis & (src[..., :3].mean(-1) > 60)
eyeball = fill_under(src, eye_known, circle_in | eyeball_vis)
save('eyeball', eyeball, circle_in | eyeball_vis)
save('iris', src, iris)
save('lid_top', src, lid_top)
save('lid_low', src, lid_low)
# jaw sits behind the eyeball: extend it a little under the sphere rim
jaw_known = jaw & alpha
jaw_ext = cv2.dilate(jaw.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
jaw_ext &= circle & poly([(548, 230), (860, 180), (860, 420), (620, 420), (560, 300)])
j = src.copy(); jr = jaw | jaw_ext
hole = (jaw_ext & ~jaw).astype(np.uint8)
for c in range(4):
    j[..., c] = np.where(hole > 0, cv2.inpaint(np.where(jaw_known, src[..., c], 0).astype(np.uint8), hole, 9,
                                               cv2.INPAINT_TELEA).astype(np.float32), j[..., c])
save('jaw', j, jr)
save('stalk', src, stalk)
# petals: fill a ring under the eye assembly so small relative motion never opens a gap
ring = (cv2.dilate((~petals & ~alpha | circle | jaw | stalk).astype(np.uint8) * 0 + (circle | jaw | stalk).astype(np.uint8),
                   np.ones((1, 1), np.uint8)) > 0)
inner = (xx - EYE_C[0]) ** 2 + (yy - EYE_C[1]) ** 2 <= (EYE_R - 22) ** 2
ring_zone = (circle | jaw | stalk) & ~inner
pet = fill_under(src, petals, ring_zone)
save('petals', pet, petals | ring_zone)

# ---------------------------------------------------------------- translucency compensation
# Parts are translucent (vanilla convention), so painted-in fills under a part would show
# through it.  Composite back->front; every part solves its own alpha/colour on the pixels it
# owns so that the rest pose reproduces the approved art exactly.  Fills are capped to the
# source alpha so a solution always exists.
OWN = {'petals': petals, 'stalk': stalk, 'jaw': jaw & alpha, 'eyeball': eyeball_vis,
       'iris': iris, 'lid_low': lid_low, 'lid_top': lid_top}
ORDER_FLOWER = ['petals', 'stalk', 'jaw', 'eyeball', 'iris', 'lid_low', 'lid_top']
sa = src[..., 3] / 255.0; sc = src[..., :3]
acc_a = np.zeros((H, W)); acc_c = np.zeros((H, W, 3))       # premultiplied colour
for n in ORDER_FLOWER:
    L = LAYERS[n]; own = OWN[n]; la = L[..., 3] / 255.0; lc = L[..., :3].copy()
    fill = (la > 0) & ~own
    ab = acc_a; cb = acc_c / np.maximum(ab, 1e-6)[..., None]
    cap = np.clip((0.85 * sa - ab) / np.maximum(1 - ab, 1e-6), 0, 1)
    # smooth the cap (erode then blur) so the fill never inherits the source's structure
    cap_s = cv2.GaussianBlur(cv2.erode(cap.astype(np.float32), np.ones((17, 17), np.uint8)), (0, 0), 6)
    la = np.where(fill, np.minimum(la, np.minimum(cap_s, np.where(sa > 0, 1.0, 0.0))), la)
    at = np.clip((sa - ab) / np.maximum(1 - ab, 1e-6), 0, 1)
    ct = (sc * sa[..., None] - cb * (ab * (1 - at))[..., None]) / np.maximum(at, 1e-6)[..., None]
    la = np.where(own, at, la); lc = np.where(own[..., None], np.clip(ct, 0, 255), lc)
    acc_c = lc * la[..., None] + acc_c * (1 - la[..., None]); acc_a = la + acc_a * (1 - la)
    LAYERS[n] = np.dstack([lc, la * 255.0])
for n, a in LAYERS.items(): write(n, a)

# ---------------------------------------------------------------- tentacles
tent = np.array(Image.open('tentacle_src.png').convert('RGBA')).astype(np.float32)
FLOWER_H = 755.0
L = FLOWER_H * 1.1
s = L / tent.shape[0]
tent = cv2.resize(tent, (max(8, int(tent.shape[1] * s * 0.72)), int(L)), interpolation=cv2.INTER_AREA)
th, tw = tent.shape[:2]


def bez(p0, p1, p2, p3, n=200):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def warp_strip(T, curve, rows=60):
    """Map vertical strip T (top = root) along curve (N x 2, root first) with per-quad affine warps."""
    h, w = T.shape[:2]
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))]
    tq = np.linspace(0, d[-1], rows + 1)
    P = np.c_[np.interp(tq, d, curve[:, 0]), np.interp(tq, d, curve[:, 1])]
    tg = np.gradient(P, axis=0); tg /= np.linalg.norm(tg, axis=1, keepdims=True)
    nrm = np.c_[-tg[:, 1], tg[:, 0]]
    Lp = P - nrm * (w / 2); Rp = P + nrm * (w / 2)
    allp = np.r_[Lp, Rp]; x0, y0 = np.floor(allp.min(0)).astype(int) - 3; x1, y1 = np.ceil(allp.max(0)).astype(int) + 3
    out = np.zeros((y1 - y0, x1 - x0, 4), np.float32)
    for i in range(rows):
        sy0, sy1 = h * i / rows, h * (i + 1) / rows
        srcq = [(0, sy0), (w, sy0), (w, sy1), (0, sy1)]
        dstq = [Lp[i], Rp[i], Rp[i + 1], Lp[i + 1]]
        for tri in ((0, 1, 2), (0, 2, 3)):
            s3 = np.float32([srcq[k] for k in tri]); d3 = np.float32([dstq[k] - (x0, y0) for k in tri])
            M = cv2.getAffineTransform(s3, d3)
            patch = cv2.warpAffine(T, M, (out.shape[1], out.shape[0]), flags=cv2.INTER_LINEAR)
            m = np.zeros(out.shape[:2], np.float32)
            cv2.fillConvexPoly(m, np.round(d3 * 4).astype(np.int32), 1.0, lineType=cv2.LINE_AA, shift=2)
            m = cv2.dilate(m, np.ones((2, 2), np.uint8))
            out = np.where(m[..., None] > 0.5, patch, out)
    return out, (int(x0), int(y0))


# rest curves (root hidden behind the petals / stalk), trailing back-down (the creature faces left)
TENTS = {
    'tent_a': [(505, 615), (450, 800), (560, 930), (700, 975)],
    'tent_b': [(530, 615), (600, 780), (760, 880), (930, 930)],
    'tent_c': [(552, 600), (700, 690), (880, 760), (1060, 800)],
}
NJ = 7
tjoints = {}
for name, ctrl in TENTS.items():
    curve = bez(*ctrl)
    img, (ox, oy) = warp_strip(tent, curve)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(f'parts/{name}.png')
    meta[name] = dict(x=ox, y=oy, w=img.shape[1], h=img.shape[0])
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))]
    tq = np.linspace(0, d[-1], NJ + 1)
    pts = np.c_[np.interp(tq, d, curve[:, 0]), np.interp(tq, d, curve[:, 1])]
    tjoints[name] = [[round(float(x), 1), round(float(y), 1)] for x, y in pts]

json.dump(meta, open('parts/meta.json', 'w'), indent=1)
json.dump(tjoints, open('tentacles.json', 'w'), indent=1)

# recomposite check (tentacles excluded; they are new)
order = ['petals', 'stalk', 'jaw', 'eyeball', 'iris', 'lid_low', 'lid_top']
c = Image.new('RGBA', (W, H), (0, 0, 0, 0))
for n in order:
    c.alpha_composite(Image.open(f'parts/{n}.png'), (meta[n]['x'], meta[n]['y']))
diff = np.abs(np.array(c).astype(np.float32) - src)
print('recomp mean abs diff (alpha)', round(float(diff[..., 3].mean()), 3), 'max', float(diff[..., 3].max()))
print({k: (v['w'], v['h']) for k, v in meta.items()})
