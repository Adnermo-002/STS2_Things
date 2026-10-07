"""Re-texture vanilla eye_with_teeth: unpack atlas regions (unrotate, unstrip), upscale x2, add Origin traits
(fogmog-cap spots on petals/leaves, darker cap-rim tips), repack unrotated -> origin_eye_with_teeth.{png,atlas}."""
import re, json, numpy as np, cv2
from PIL import Image
UP = 2
page = np.array(Image.open('../ref/eye_with_teeth.png').convert('RGBA'))
txt = open('../ref/eye_with_teeth.atlas').read().splitlines()
regions = {}; cur = None
for line in txt[1:]:
    if ':' not in line:
        cur = line.strip(); regions[cur] = {}
    elif cur:
        k, v = line.split(':', 1); regions[cur][k.strip()] = v.strip()
imgs = {}
for n, d in regions.items():
    x, y, w, h = map(int, d['bounds'].split(','))
    rot = d.get('rotate') == '90'
    sub = page[y:y + (w if rot else h), x:x + (h if rot else w)]
    if rot: sub = np.rot90(sub, -1)
    if 'offsets' in d:
        ox, oy, W, H = map(int, d['offsets'].split(','))
        full = np.zeros((H, W, 4), np.uint8); full[H - oy - sub.shape[0]:H - oy, ox:ox + sub.shape[1]] = sub; sub = full
    imgs[n] = sub
json.dump({n: list(v.shape[:2]) for n, v in imgs.items()}, open('orig_sizes.json', 'w'))

def up(a): return cv2.resize(a, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)

rng = np.random.default_rng(42)
def spots(im, n, rmin, rmax, avoid_bright=True, seed=0):
    rng = np.random.default_rng(seed)
    a = im[..., 3].astype(np.float32) / 255
    inside = cv2.distanceTransform((a > 0.3).astype(np.uint8), cv2.DIST_L2, 5)
    lum = im[..., :3].mean(-1)
    out = im.astype(np.float32)
    H, W = a.shape; placed = []
    tries = 0
    while len(placed) < n and tries < 4000:
        tries += 1
        r = rng.uniform(rmin, rmax); x = rng.uniform(0, W); y = rng.uniform(0, H)
        xi, yi = int(x), int(y)
        if inside[yi, xi] < r + 4: continue
        if avoid_bright:
            y0, y1, x0, x1 = max(0, yi - int(r) - 4), yi + int(r) + 4, max(0, xi - int(r) - 4), xi + int(r) + 4
            if lum[y0:y1, x0:x1].max() > 215 or lum[y0:y1, x0:x1].min() < 25: continue   # teeth / mouth / outline
        if any(np.hypot(x - px, y - py) < r + pr + 5 for px, py, pr in placed): continue
        placed.append((x, y, r))
    yy, xx = np.mgrid[0:H, 0:W]
    glow = np.zeros((H, W), np.float32)
    for x, y, r in placed:
        ry = r * rng.uniform(0.75, 0.95)
        d = np.sqrt(((xx - x) / r) ** 2 + ((yy - y) / ry) ** 2)
        rim = (d <= 1.18) & (d > 1.0); body = d <= 1.0
        hl = np.sqrt(((xx - (x - r * 0.3)) / (r * 0.35)) ** 2 + ((yy - (y - ry * 0.35)) / (ry * 0.28)) ** 2) <= 1
        base = out[..., :3].mean(-1, keepdims=True)
        out[..., :3] = np.where(rim[..., None], base * 0.55, out[..., :3])
        out[..., :3] = np.where(body[..., None], np.clip(base * 0.3 + 170, 0, 255), out[..., :3])
        out[..., :3] = np.where((hl & body)[..., None], np.clip(base * 0.3 + 190, 0, 255), out[..., :3])
        glow = np.maximum(glow, np.clip((1.12 - d) / 0.25, 0, 1) * 0.9 + (hl & body) * 0.1)
    SPOTMASK[0] = glow * a
    return np.clip(out, 0, 255).astype(np.uint8), len(placed)
SPOTMASK = [None]

def dark_tips(im, frac=0.22):
    """darken the outer rim band of a petal a little (fogmog cap edge)."""
    a = (im[..., 3] > 128).astype(np.uint8)
    d = cv2.distanceTransform(a, cv2.DIST_L2, 5)
    m = np.clip(1 - d / (d.max() * frac + 1e-6), 0, 1) * (im[..., 3] / 255)
    out = im.astype(np.float32); out[..., :3] *= (1 - 0.25 * m[..., None])
    return out.astype(np.uint8)

new = {}
for n, im in imgs.items():
    u = up(im)
    if n == 'back petals':
        u = dark_tips(u); u, k = spots(u, 14, 10, 19, seed=1); print('petal spots', k)
    elif n in ('leaf 2', 'leaf 3', 'leaf 4', 'leaf 1', 'leaf 1 open'):
        u, k = spots(u, 4, 7, 12, seed=len(n) * 7 + ord(n[-1])); print(n, k)
    elif n == 'death_still':
        u, k = spots(u, 14, 8, 15, seed=7)
    new[n] = u
    if n in ('back petals', 'leaf 1', 'leaf 1 open', 'leaf 2', 'leaf 3', 'leaf 4'):
        g = SPOTMASK[0]; sp = np.zeros(u.shape, np.uint8); sp[..., :3] = 255; sp[..., 3] = (g * 255).clip(0, 255).astype(np.uint8)
        new[n + ' spots'] = sp
# pack
PAD = 3
def pack(PW, PH):
    rects = {}; x = y = shelf = 0
    for n in sorted(new, key=lambda k: -new[k].shape[0]):
        h, w = new[n].shape[:2]; w += 2 * PAD; h += 2 * PAD
        if x + w > PW: x = 0; y += shelf; shelf = 0
        if y + h > PH: return None
        rects[n] = (x + PAD, y + PAD); x += w; shelf = max(shelf, h)
    return rects
for PW, PH in [(1024, 1024), (2048, 1024), (2048, 2048)]:
    rects = pack(PW, PH)
    if rects: break
P = np.zeros((PH, PW, 4), np.uint8)
for n, (x, y) in rects.items():
    h, w = new[n].shape[:2]; P[y:y + h, x:x + w] = new[n]
# colour bleed
col = P[..., :3].astype(np.float32); known = P[..., 3] > 0
for _ in range(4):
    k = cv2.dilate(known.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    s = cv2.blur(col * known[..., None], (3, 3)); c = cv2.blur(known.astype(np.float32), (3, 3))
    nw = k & ~known; col[nw] = s[nw] / np.maximum(c[nw, None], 1e-6); known = k
P[..., :3] = col.clip(0, 255).astype(np.uint8)
K = 'origin_eye_with_teeth'
Image.fromarray(P).save(f'{K}.png', optimize=True)
at = [f'{K}.png', f'size: {PW},{PH}', 'format: RGBA8888', 'filter: Linear,Linear', 'repeat: none']
for n, (x, y) in rects.items():
    h, w = new[n].shape[:2]
    at += [n, '  rotate: false', f'  xy: {x}, {y}', f'  size: {w}, {h}', f'  orig: {w}, {h}', '  offset: 0, 0', '  index: -1']
open(f'{K}.atlas', 'w', newline='\n').write('\n'.join(at) + '\n')
print(PW, PH, {n: new[n].shape[:2] for n in new})
v = P.copy(); bg = np.zeros_like(v); bg[...] = (60, 64, 72, 255); a = v[..., 3:4] / 255
Image.fromarray((v[..., :3] * a + bg[..., :3] * (1 - a)).astype(np.uint8)).save('/home/user/og2/eye_atlas_view.jpg')
