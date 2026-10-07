"""Stage B: layers with occlusion completion + glow layers.

Every opaque source pixel belongs to exactly one visible layer.  Each layer is
then extended underneath the layers drawn in front of it (blob continuation,
clipped to the original silhouette) and the hidden texels are colour-filled
with a push-pull pyramid so that motion never reveals holes.
"""
import numpy as np, cv2, json, os
from PIL import Image
from scipy import ndimage as ndi

im = np.array(Image.open('src.png').convert('RGBA')).astype(np.float32)
H, W = im.shape[:2]; rgb = im[..., :3]; a = im[..., 3]
m = a > 0
labels = np.load('labels.npy'); PARTS = json.load(open('parts_list.json'))
pid = {p: i + 1 for i, p in enumerate(PARTS)}
hsv = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV)
h = hsv[..., 0].astype(int) * 2; s = hsv[..., 1].astype(int); v = hsv[..., 2].astype(int)
teal = (h >= 160) & (h < 210) & (s > 60) & m

LEGS = [f'leg{i}_{k}' for i in (5, 4, 3, 2, 1) for k in ('upper', 'shin', 'claw')]
ORDER = ['membrane_rear', 'egg_sac', 'rear_shell', 'dome3', 'membrane_front', 'leaf_plate', 'dome2',
         'shell_mid', 'crest_1', 'crest_2', 'crest_3', 'crest_4', 'crest_5', 'mandible_upper',
         'mandible_lower', 'head', 'eye', 'pupil', 'shell_front'] + LEGS
assert sorted(ORDER) == sorted(PARTS), set(ORDER) ^ set(PARTS)
rank = {p: i for i, p in enumerate(ORDER)}
# body silhouette without the free-hanging leg segments: body layers may only extend inside it
legmask = np.isin(labels, [pid[n] for n in LEGS])
bodyonly = m & ~legmask
bodysil = cv2.morphologyEx(bodyonly.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))) > 0
bodysil = ndi.binary_fill_holes(bodysil) & m
shinclaw = np.isin(labels, [pid[n] for n in LEGS if not n.endswith('upper')])
# how far (px) a layer may continue underneath the layers in front of it
EXT = {'membrane_rear': 90, 'egg_sac': 45, 'rear_shell': 30, 'membrane_front': 80, 'leaf_plate': 40,
       'dome2': 30, 'dome3': 30, 'shell_mid': 36, 'head': 30, 'eye': 0, 'pupil': 0, 'shell_front': 0,
       'mandible_upper': 26, 'mandible_lower': 30}
for i in range(1, 6): EXT[f'crest_{i}'] = 26
EXT['leaf_plate'] = 18
for n in LEGS: EXT[n] = 16
EXT_INTO = {'head': ['shell_front', 'eye', 'pupil']}
CLOSE = {'membrane_rear': 121, 'membrane_front': 101, 'egg_sac': 61, 'head': 61}

def ell(r): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))

# the pupil takes its antialiased dark rim with it, so the iris underneath is clean
pup = cv2.dilate((labels == pid['pupil']).astype(np.uint8), ell(7)) > 0
pup &= (labels == pid['eye']) | (labels == pid['pupil'])
labels = labels.copy(); labels[pup] = pid['pupil']
layers = {}
for p in ORDER:
    vis = labels == pid[p]
    infront = np.zeros((H, W), bool)
    for q in ORDER[rank[p] + 1:]:
        if p in EXT_INTO and q not in EXT_INTO[p]: continue
        infront |= labels == pid[q]
    full = vis.copy()
    e = EXT[p]
    if e > 0:
        grow = cv2.dilate(vis.astype(np.uint8), ell(e)) > 0
        if p in CLOSE:
            big = cv2.morphologyEx(vis.astype(np.uint8), cv2.MORPH_CLOSE, ell(CLOSE[p] // 2)) > 0
            big = ndi.binary_fill_holes(big)
        else:
            big = np.zeros((H, W), bool)
        ext = (grow | (big & (cv2.dilate(vis.astype(np.uint8), ell(e * 2)) > 0))) & infront & (a > 200)
        if p not in LEGS: ext &= bodysil & ~shinclaw
        full = vis | ext
        full = cv2.morphologyEx(full.astype(np.uint8), cv2.MORPH_OPEN, ell(3)) > 0
        full |= vis
        # keep components connected to the visible part
        n, lab = cv2.connectedComponents(full.astype(np.uint8), connectivity=8)
        keep = np.unique(lab[vis]); keep = keep[keep > 0]
        full = np.isin(lab, keep)
    layers[p] = dict(vis=vis, full=full)
# the eye must fill in under the pupil
layers['eye']['full'] = ndi.binary_fill_holes(layers['eye']['vis'] | layers['pupil']['vis'])
# the egg sac continues under the whole rear shell rim so it can bulge
sac = np.load('sac_mask.npy')
layers['egg_sac']['full'] |= sac & (a > 200) & np.isin(labels, [pid['rear_shell'], pid['membrane_rear'], pid['dome3']])

def pushpull(col, wt):
    levels = [(col * wt[..., None], wt)]
    c, w = levels[0]
    while min(w.shape) > 2:
        c = cv2.pyrDown(c); w = cv2.pyrDown(w); levels.append((c, w))
    cc, ww = levels[-1]
    est = cc / np.maximum(ww, 1e-6)[..., None]
    for c, w in reversed(levels[:-1]):
        up = cv2.resize(est, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR)
        here = c / np.maximum(w, 1e-6)[..., None]
        k = np.clip(w * 4, 0, 1)[..., None]
        est = here * k + up * (1 - k)
    return est

os.makedirs('parts', exist_ok=True)
for f in os.listdir('parts'): os.remove(os.path.join('parts', f))
meta = {}
def save(name, col, alpha, box_mask, pad=2):
    ys, xs = np.nonzero(box_mask)
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + 1 + pad, W)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + 1 + pad, H)
    out = np.dstack([col, alpha])[y0:y1, x0:x1]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(f'parts/{name}.png')
    meta[name] = dict(x=int(x0), y=int(y0), w=int(x1 - x0), h=int(y1 - y0))

outline_dark = v < 70
for p in ORDER:
    vis, full = layers[p]['vis'], layers[p]['full']
    # colour sources: solid visible texels away from foreign parts (avoid picking up neighbour ink)
    foreign = cv2.dilate((~vis & m).astype(np.uint8), ell(3)) > 0
    src = vis & ~foreign & (a > 250)
    if p != 'pupil': src &= ~outline_dark | ~cv2.erode(vis.astype(np.uint8), ell(4)).astype(bool)
    if src.sum() < 50: src = vis & (a > 250)
    fill = cv2.GaussianBlur(pushpull(rgb, src.astype(np.float32)), (0, 0), 1.5)
    col = np.where(vis[..., None], rgb, fill)
    alpha = np.where(vis, a, 0).astype(np.float32)
    hidden = full & ~vis
    soft = cv2.GaussianBlur(full.astype(np.float32), (0, 0), 0.8) * 255
    alpha = np.where(hidden, np.minimum(a, soft), alpha)
    # visible edge against a part drawn *behind* stays as painted; edge against a part in front is
    # continued (hidden) so there is no seam.
    save(p, col, alpha, full & (alpha > 0))
    layers[p]['alpha'] = alpha

# ---- glow layers (additive): derived from each gem's own shading + a soft halo
def glow_layer(mask, halo_col, inner_gain=0.75, halo_sig=8.0, halo_gain=1.1, pw=1.6):
    mk = mask.astype(np.float32)
    lum = (v.astype(np.float32) / 255.0) ** pw
    inner = cv2.GaussianBlur(mk * lum, (0, 0), 0.8) * inner_gain
    halo = np.clip(cv2.GaussianBlur(mk, (0, 0), halo_sig) * halo_gain, 0, 1) * (1 - 0.6 * mk)
    alpha = np.clip(inner + halo * 0.55, 0, 1) * 255
    src_col = np.clip(rgb * 1.15 + 30, 0, 255)
    hc = np.zeros_like(rgb); hc[...] = halo_col
    w = np.clip(cv2.GaussianBlur(mk, (0, 0), 1.5), 0, 1)[..., None]
    col = src_col * w + hc * (1 - w)
    return col, alpha
n, lab, st, cen = cv2.connectedComponentsWithStats((teal & ~layers['eye']['full']).astype(np.uint8), 8)
GLOW = {}
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] < 400: continue
    owner = PARTS[np.bincount(labels[lab == i]).argmax() - 1]
    GLOW.setdefault(owner, np.zeros((H, W), bool))
    GLOW[owner] |= lab == i
gem_parts = {}
for owner, mk in GLOW.items():
    col, g = glow_layer(mk, (90, 255, 225))
    save(owner + '_glow', col, g, g > 4)
    gem_parts[owner + '_glow'] = owner
eggvis = layers['egg_sac']['vis']
col, g = glow_layer(eggvis, (255, 170, 60), inner_gain=0.9, halo_sig=10.0, halo_gain=0.5, pw=2.2)
g = np.where(eggvis, g, g * 0.5)
save('egg_sac_glow', col, g, g > 4); gem_parts['egg_sac_glow'] = 'egg_sac'
eyem = layers['eye']['full']
# build from the pupil-free iris texture so a moving pupil leaves no ghost
e = meta['eye']; eimg = np.array(Image.open('parts/eye.png')).astype(np.float32)
v_save, rgb_save = v, rgb
v = v.copy(); rgb = rgb.copy()
sl = (slice(e['y'], e['y'] + e['h']), slice(e['x'], e['x'] + e['w']))
rgb[sl] = np.where(eyem[sl][..., None], eimg[..., :3], rgb[sl])
v[sl] = np.where(eyem[sl], eimg[..., :3].max(-1), v[sl])
col, g = glow_layer(eyem, (130, 255, 240), inner_gain=0.7, halo_sig=6.0, halo_gain=0.9)
v, rgb = v_save, rgb_save
save('eye_glow', col, g, g > 4); gem_parts['eye_glow'] = 'eye'

json.dump(meta, open('parts/meta.json', 'w'), indent=1)
json.dump({'order': ORDER, 'glow_of': gem_parts}, open('order.json', 'w'), indent=1)
print(len(meta), 'texels', sum(v['w'] * v['h'] for v in meta.values()), 'glows', gem_parts)
