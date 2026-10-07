"""Origin Eye With Teeth v3 textures: the user-chosen grey 'V1' design (tools/OriginEyeRig/design_mono_v1n2.png)
painted onto the VANILLA eye_with_teeth regions (same shapes / UVs, 2x), for NORMAL blending.

Vanilla regions are grey glow art drawn additively; their structure lives in the alpha channel (outlines & teeth
alpha 1, interiors ~0.5) plus a few dark luminance lines.  Painters per part type:
  back petals : dark-grey translucent fill, light opaque outlines/midribs, pale spots (design petals)
  jaws 2/3/4  : pale shell, dark contour, white teeth, black maw
  lid 1 (+open): pale shell, ink lip line, white teeth
  eyeball     : pale sphere, soft shading on the right, dark rim, small highlight
  iris        : light grey lens with a darker ring;  pupil: black vertical slit
  extra vine  : pale core, dark edges (thorny tentacle), vanilla tail fade kept
  death_still : whole dead flower, same palette (short alpha ghost during die)
Output: out/origin_eye_with_teeth.{png,atlas,spatlas} (+ out/tex_preview.jpg)
usage: EYE_REF=<vanilla eye_with_teeth dir> python eye_tex.py
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
import rectpack

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from regions import vanilla_regions

OUT = os.path.join(HERE, 'out')
K = 'origin_eye_with_teeth'
RES = 'res://STS2_Things/animations/monsters/origin_eye_with_teeth/'
UP = 2

INK, PETAL_LINE, SPOT = 0.17, 0.86, 0.94
SHELL, TOOTH, MAW = 0.80, 0.97, 0.05
EYE_WHITE, IRIS_FILL, IRIS_RING, PUPIL = 0.91, 0.80, 0.40, 0.04
VINE_CORE, VINE_EDGE = 0.80, 0.36


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def fill_holes(m):
    m = m.astype(np.uint8); h, w = m.shape
    ff = np.zeros((h + 4, w + 4), np.uint8); inv = (1 - m).copy()
    pad = np.pad(inv, 1, constant_values=1)
    cv2.floodFill(pad, ff, (0, 0), 2)
    outside = pad[1:-1, 1:-1] == 2
    return ~outside


def dist_in(m):
    return cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)


def soft(m, s=0.8):
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), s)


def up(im):
    return cv2.resize(im, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)


def channels(im):
    f = np.clip(up(im).astype(np.float32) / 255, 0, 1)
    return f[..., :3].mean(-1), f[..., 3]


def spots(allowed, n, rmin, rmax, seed, gap=4):
    """non-overlapping ellipses inside `allowed` -> soft mask."""
    rng = np.random.default_rng(seed); H, W = allowed.shape
    din = dist_in(allowed); placed = []; tries = 0
    while len(placed) < n and tries < 20000:
        tries += 1
        r = rng.uniform(rmin, rmax); x = rng.uniform(0, W); y = rng.uniform(0, H)
        if din[int(y), int(x)] < r + 2: continue
        if any(np.hypot(x - px, y - py) < r + pr + gap for px, py, pr in placed): continue
        placed.append((x, y, r))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); m = np.zeros((H, W), np.float32)
    for x, y, r in placed:
        ry = r * rng.uniform(0.72, 0.95); a = rng.uniform(0, np.pi)
        dx, dy = xx - x, yy - y; u = dx * np.cos(a) + dy * np.sin(a); v = -dx * np.sin(a) + dy * np.cos(a)
        d = np.sqrt((u / r) ** 2 + (v / ry) ** 2)
        m = np.maximum(m, np.clip((1 - d) * r * 0.9 + 0.5, 0, 1))
    return m, len(placed)


def rgba(g, a):
    g = np.clip(g, 0, 1); a = np.clip(a, 0, 1)
    return (np.dstack([g, g, g, a]) * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ painters
def paint_petals(im, seed=11, n_spots=44):
    L, A = channels(im)
    line = ss(0.50, 0.80, cv2.GaussianBlur(A, (0, 0), 0.6))
    body = ss(0.05, 0.20, A)
    core = ss(0.28, 0.12, A) * body                      # dim centre behind the eye
    fill = 0.33 + 0.12 * ss(0.25, 0.6, A) - 0.10 * core
    g = fill * (1 - line) + PETAL_LINE * line
    allowed = (body > 0.9) & (line < 0.05) & (core < 0.2)
    allowed = cv2.erode(allowed.astype(np.uint8), disk(3)) > 0
    sp, n = spots(allowed, n_spots, 2.4 * UP, 5.2 * UP, seed, gap=5)
    g = g * (1 - sp) + SPOT * sp
    a = np.maximum(np.maximum(0.80 * body, line), sp * body)
    return rgba(g, a), n


def paint_jaw(im, seed=0):
    """vanilla jaw = outer outline (alpha 1) + dark-line band / root (dark L) + inner lip & teeth (alpha 1)
    around an OPEN interior (alpha ~0.3-0.7, bright L).  -> pale shell, darker groove, white teeth, black maw."""
    L, A0 = channels(im)
    A = cv2.GaussianBlur(A0, (0, 0), 1.1); Ls = cv2.GaussianBlur(L, (0, 0), 1.1)
    S = fill_holes(A0 > 0.12); dS = dist_in(S)
    hi = A > 0.78
    dark = (Ls < 0.50) & (A > 0.22) & ~hi
    outer = hi & (dS < 6)
    teeth = hi & ~outer
    teeth = cv2.morphologyEx(teeth.astype(np.uint8), cv2.MORPH_OPEN, disk(1)) > 0
    maw = S & ~hi & ~dark & (A >= 0.16)
    maw = cv2.morphologyEx(maw.astype(np.uint8), cv2.MORPH_OPEN, disk(2)) > 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(maw.astype(np.uint8), 8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 60: maw[lab == i] = False
    maw_s = soft(maw, 1.0); teeth_s = soft(teeth, 0.8); groove = soft(dark, 1.0)
    g = np.full(A.shape, SHELL, np.float32)
    g = g * (1 - groove) + 0.60 * groove
    edge = np.clip(soft(cv2.dilate(teeth.astype(np.uint8), disk(1)) > 0, 0.8) - teeth_s, 0, 1) * (1 - maw_s)
    g = g * (1 - 0.5 * edge) + 0.5 * 0.5 * edge
    g = g * (1 - maw_s) + MAW * maw_s
    g = g * (1 - teeth_s) + TOOTH * teeth_s
    contour = soft(S & (dS < 2.0), 0.6) * (1 - teeth_s)
    g = g * (1 - contour) + INK * contour
    a = ss(0.10, 0.34, A0)
    a = np.maximum(a, maw_s * ss(0.12, 0.24, A))
    a = np.maximum(a, np.maximum(soft(hi, 0.7), teeth_s))
    return rgba(g, a * soft(S, 0.6))


def paint_lid(im, open_=False):
    L, A = channels(im)
    S = fill_holes(A > (0.18 if open_ else 0.3))
    body = cv2.morphologyEx(S.astype(np.uint8), cv2.MORPH_OPEN, disk(6 if not open_ else 4)) > 0
    teeth = S & ~(cv2.dilate(body.astype(np.uint8), disk(1)) > 0)
    if open_:
        teeth |= (A > 0.85) & S
    ink_l = ss(0.52, 0.40, L) * S
    g = np.full(A.shape, SHELL + 0.03, np.float32)
    g -= 0.10 * ss(0, 30, dist_in(S)) * 0                 # flat shell (kept simple)
    g = g * (1 - ink_l) + 0.34 * ink_l
    if open_:
        dark = (A > 0.25) & (A < 0.75) & S & ~teeth
        g[dark] = 0.20
    g[teeth] = TOOTH
    dS = dist_in(S)
    contour = soft(S & (dS < 1.6), 0.6)
    g = g * (1 - contour) + INK * contour
    a = (ss(0.10, 0.45, A) if open_ else soft(S, 0.7))
    if open_: a = np.maximum(a, teeth.astype(np.float32)) * soft(S, 0.7)
    return rgba(g, a)


def paint_eyeball(im):
    L, A = channels(im)
    S = fill_holes(A > 0.2); H, W = A.shape
    dS = dist_in(S)
    shade = ss(0.55, 0.85, A) * (dS > 3)
    shade = cv2.GaussianBlur(shade.astype(np.float32), (0, 0), 3)
    g = EYE_WHITE - 0.22 * shade
    yy, xx = np.mgrid[0:H, 0:W]
    hl = np.exp(-(((xx - W * 0.33) / (W * 0.10)) ** 2 + ((yy - H * 0.28) / (H * 0.07)) ** 2))
    g = g + 0.08 * hl
    rim = soft(S & (dS < 2.4), 0.7)
    g = g * (1 - rim) + 0.30 * rim
    return rgba(g, soft(S, 0.7))


def paint_iris(im):
    L, A = channels(im)
    S = fill_holes(A > 0.2); dS = dist_in(S); H, W = A.shape
    ring = ss(6.0, 3.5, dS)
    yy, xx = np.mgrid[0:H, 0:W]
    rad = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    g = IRIS_FILL + 0.06 * (1 - np.clip(rad, 0, 1))
    g = g * (1 - ring) + IRIS_RING * ring
    return rgba(g, soft(S, 0.7))


def paint_pupil(im):
    L, A = channels(im)
    S = fill_holes(A > 0.25)
    return rgba(np.full(A.shape, PUPIL, np.float32), soft(S, 0.7))


def paint_vine(im):
    L, A = channels(im)
    core = dist_in(A > 0.5)
    g = VINE_EDGE + (VINE_CORE - VINE_EDGE) * ss(0.8, 3.2, core)
    a = ss(0.10, 0.45, A)
    return rgba(g, a)


def paint_death(im, seed=5):
    L, A = channels(im)
    line = ss(0.60, 0.86, A)
    body = ss(0.05, 0.20, A)
    ink_l = ss(0.50, 0.38, L) * (A > 0.3)
    g = 0.38 + 0.14 * ss(0.3, 0.65, A)
    g = g * (1 - line) + PETAL_LINE * line
    g = g * (1 - ink_l) + 0.25 * ink_l
    allowed = (body > 0.9) & (line < 0.05) & (A < 0.55)
    allowed = cv2.erode(allowed.astype(np.uint8), disk(3)) > 0
    sp, n = spots(allowed, 26, 3.5 * UP, 6.0 * UP, seed)
    g = g * (1 - sp) + SPOT * sp
    a = np.maximum(np.maximum(0.82 * body, line), sp * body)
    return rgba(g, a)


def build():
    V = vanilla_regions(); new = {}
    sizes = {n: (v.shape[1] * UP, v.shape[0] * UP) for n, v in V.items()}
    new['back petals'], n = paint_petals(V['back petals']); print('back petals spots', n)
    for nm in ('leaf 2', 'leaf 3', 'leaf 4'): new[nm] = paint_jaw(V[nm])
    new['leaf 1'] = paint_lid(V['leaf 1']); new['leaf 1 open'] = paint_lid(V['leaf 1 open'], open_=True)
    new['eyeball'] = paint_eyeball(V['eyeball']); new['iris'] = paint_iris(V['iris']); new['pupil'] = paint_pupil(V['pupil'])
    new['extra vine'] = paint_vine(V['extra vine']); new['death_still'] = paint_death(V['death_still'])
    for nm, t in new.items():
        assert (t.shape[1], t.shape[0]) == sizes[nm], (nm, t.shape, sizes[nm])
    # pack (unrotated, 2px padding + bleed)
    PAD = 3
    for PW, PH in [(1024, 1024), (2048, 1024)]:
        pk = rectpack.newPacker(rotation=False, pack_algo=rectpack.MaxRectsBssf, sort_algo=rectpack.SORT_AREA)
        for nm, t in new.items(): pk.add_rect(t.shape[1] + 2 * PAD, t.shape[0] + 2 * PAD, nm)
        pk.add_bin(PW, PH); pk.pack()
        rects = {r[5]: (r[1] + PAD, r[2] + PAD) for r in pk.rect_list()}
        if len(rects) == len(new): break
    P = np.zeros((PH, PW, 4), np.uint8)
    for nm, (x, y) in rects.items():
        h, w = new[nm].shape[:2]; P[y:y + h, x:x + w] = new[nm]
    col = P[..., :3].astype(np.float32); known = P[..., 3] > 0
    for _ in range(PAD + 1):
        k = cv2.dilate(known.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        s = cv2.blur(col * known[..., None], (3, 3)); c = cv2.blur(known.astype(np.float32), (3, 3))
        nw = k & ~known; col[nw] = s[nw] / np.maximum(c[nw, None], 1e-6); known = k
    P[..., :3] = col.clip(0, 255).astype(np.uint8)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(P).save(os.path.join(OUT, K + '.png'), optimize=True)
    at = [K + '.png', f'size: {PW},{PH}', 'format: RGBA8888', 'filter: Linear,Linear', 'repeat: none']
    for nm in sorted(rects, key=lambda n: (rects[n][1], rects[n][0])):
        x, y = rects[nm]; h, w = new[nm].shape[:2]
        at += [nm, '  rotate: false', f'  xy: {x}, {y}', f'  size: {w}, {h}', f'  orig: {w}, {h}', '  offset: 0, 0', '  index: -1']
    atlas = '\n'.join(at) + '\n'
    open(os.path.join(OUT, K + '.atlas'), 'w', newline='\n').write(atlas)
    spatlas = {'source_path': RES + K + '.atlas', 'atlas_data': atlas, 'normal_texture_prefix': 'n', 'specular_texture_prefix': 's'}
    open(os.path.join(OUT, K + '.spatlas'), 'w', newline='\n').write(json.dumps(spatlas, separators=(',', ':')))
    print('atlas', PW, PH, {n: (new[n].shape[1], new[n].shape[0]) for n in new})
    # preview sheet on dark + light backgrounds
    tiles = []
    for nm in ['back petals', 'leaf 4', 'leaf 3', 'leaf 2', 'leaf 1', 'leaf 1 open', 'eyeball', 'iris', 'pupil', 'death_still', 'extra vine']:
        t = new[nm].astype(np.float32) / 255
        if nm == 'extra vine': t = np.ascontiguousarray(np.rot90(t, 1))
        a = t[..., 3:4]
        rows = [t[..., :3] * a + np.array(bg) * (1 - a) for bg in ((0.13, 0.14, 0.17), (0.55, 0.52, 0.48))]
        tiles.append((np.concatenate(rows, 0) * 255).astype(np.uint8))
    Wt = sum(t.shape[1] + 8 for t in tiles); Ht = max(t.shape[0] for t in tiles)
    sh = np.full((Ht, Wt, 3), (120, 0, 120), np.uint8); x = 0
    for t in tiles: sh[:t.shape[0], x:x + t.shape[1]] = t; x += t.shape[1] + 8
    Image.fromarray(sh).save(os.path.join(OUT, 'tex_preview.jpg'), quality=90)


if __name__ == '__main__':
    build()
