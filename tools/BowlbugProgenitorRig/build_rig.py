"""Atlas packing + weighted meshes -> out/rig_static.json, out/bowlbug_progenitor.{png,atlas}."""
import json, math, os, numpy as np, cv2
from PIL import Image
from rigdef import *

NAME = 'bowlbug_progenitor'
os.makedirs('out', exist_ok=True)
meta = json.load(open('parts/meta.json'))
order = json.load(open('order.json'))
GLOW_OF = order['glow_of']
bones = [dict(name=n, parent=p, pos=tuple(pos)) for n, p, pos in BONES]
bidx = {b['name']: i for i, b in enumerate(bones)}
bpos = {b['name']: b['pos'] for b in bones}

# ---------------- atlas
GLOW_SCALE = 0.5
imgs = {}
for n in meta:
    im = Image.open(f'parts/{n}.png').convert('RGBA')
    if n in GLOW_OF:
        im = im.resize((max(1, round(im.width * GLOW_SCALE)), max(1, round(im.height * GLOW_SCALE))), Image.LANCZOS)
    imgs[n] = im
PAD = 2
def pack(PW, PH):
    rects = {}; x = y = shelf = 0
    for n in sorted(imgs, key=lambda k: -imgs[k].height):
        w, h = imgs[n].width + 2 * PAD, imgs[n].height + 2 * PAD
        if x + w > PW: x = 0; y += shelf; shelf = 0
        if y + h > PH: return None
        rects[n] = (x + PAD, y + PAD); x += w; shelf = max(shelf, h)
    return rects
for PW, PH in [(2048, 1024), (2048, 1536), (2048, 2048), (4096, 2048)]:
    rects = pack(PW, PH)
    if rects: break
page = Image.new('RGBA', (PW, PH), (0, 0, 0, 0))
for n, (x, y) in rects.items(): page.paste(imgs[n], (x, y))
P = np.array(page).astype(np.float32); known = P[..., 3] > 0; col = P[..., :3].copy()
for _ in range(6):  # colour bleed so bilinear filtering never pulls black
    k = cv2.dilate(known.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    s = cv2.blur(col * known[..., None], (3, 3)); c = cv2.blur(known.astype(np.float32), (3, 3))
    new = k & ~known; col[new] = s[new] / np.maximum(c[new, None], 1e-6); known = k
P[..., :3] = col
Image.fromarray(np.clip(P, 0, 255).astype(np.uint8)).save(f'out/{NAME}.png', optimize=True)
atlas = [f'{NAME}.png', f'size: {PW},{PH}', 'format: RGBA8888', 'filter: Linear,Linear', 'repeat: none']
for n, (x, y) in rects.items():
    w, h = imgs[n].size
    atlas += [n, '  rotate: false', f'  xy: {x}, {y}', f'  size: {w}, {h}', f'  orig: {w}, {h}', '  offset: 0, 0', '  index: -1']
open(f'out/{NAME}.atlas', 'w', newline='\n').write('\n'.join(atlas) + '\n')

# ---------------- meshes
def seg_dist(p, a, b):
    a = np.array(a, float); b = np.array(b, float); ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-6), 0, 1)
    return np.hypot(*(p - (a + t[:, None] * ab)).T), t
def grid_mesh(n, spacing):
    al = np.array(Image.open(f'parts/{n}.png'))[..., 3]
    h, w = al.shape
    xs = sorted(set([int(v) for v in np.arange(0, w, spacing)] + [w]))
    ys = sorted(set([int(v) for v in np.arange(0, h, spacing)] + [h]))
    occ = cv2.dilate((al > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
    vid = {}; verts = []; tris = []
    def V(i, j):
        if (i, j) not in vid: vid[(i, j)] = len(verts); verts.append((xs[i], ys[j]))
        return vid[(i, j)]
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            if occ[ys[j]:ys[j + 1], xs[i]:xs[i + 1]].any():
                a, b, c, d = V(i, j), V(i + 1, j), V(i + 1, j + 1), V(i, j + 1)
                tris += [a, b, c, a, c, d]
    verts = np.array(verts, float)
    uvs = np.stack([verts[:, 0] / w, verts[:, 1] / h], 1)
    return verts + np.array([meta[n]['x'], meta[n]['y']]), uvs, tris
def weights(n, world):
    segs = SKIN[n]
    if len(segs) == 1: return [[(segs[0][0], 1.0)] for _ in world]
    if n.startswith('crest_'):
        (b0, a, mid), (b1, _, t) = segs
        _, tt = seg_dist(world, a, t)
        res = []
        for u in tt:
            w1 = float(np.clip((u - 0.3) / 0.4, 0, 1)); w1 = w1 * w1 * (3 - 2 * w1)
            res.append([(b, w) for b, w in ((b0, 1 - w1), (b1, w1)) if w > 0.02])
        return res
    D = np.stack([seg_dist(world, a, b)[0] for _, a, b in segs], 1)
    Wt = np.exp(-(D / SIGMA[n]) ** 2) + 1e-9
    Wt[np.arange(len(world)), D.argmin(1)] += 0.35
    Wt /= Wt.sum(1, keepdims=True)
    out = []
    for i in range(len(world)):
        wl = [(segs[k][0], Wt[i, k]) for k in range(len(segs)) if Wt[i, k] > 0.02]
        s = sum(w for _, w in wl); out.append([(b, w / s) for b, w in wl])
    return out
def spine_vertices(world, wts):
    out = []
    for p, wl in zip(world, wts):
        sp = S(p)
        if len(wl) == 1:
            pass
        out.append(len(wl))
        for b, w in wl:
            bp = S(bpos[b]); out += [bidx[b], round(sp[0] - bp[0], 2), round(sp[1] - bp[1], 2), round(w, 4)]
    return out
attachments = {}; slots = []; mesh_cache = {}
slot_list = []
for n in order['order']:
    slot_list.append(n)
    for g, base in GLOW_OF.items():
        if base == n: slot_list.append(g)
for n in slot_list:
    src = n
    if src not in mesh_cache:
        base = GLOW_OF.get(n, n)
        sp = 16 if n.startswith(('leg', 'crest', 'mand', 'pupil')) else (22 if n in ('eye',) else 28)
        if n in GLOW_OF: sp = 36
        world, uvs, tris = grid_mesh(n, sp)
        skin_key = base
        wts = weights(skin_key, world)
        mesh_cache[src] = (world, uvs, tris, wts)
    world, uvs, tris, wts = mesh_cache[src]
    attachments[n] = {n: {'type': 'mesh', 'uvs': [round(float(v), 5) for v in uvs.flatten()],
                          'triangles': tris, 'vertices': spine_vertices(world, wts), 'hull': 0,
                          'width': meta[n]['w'], 'height': meta[n]['h']}}
    sl = {'name': n, 'bone': SKIN[GLOW_OF.get(n, n)][0][0], 'attachment': n}
    if n in GLOW_OF: sl['blend'] = 'additive'; sl['color'] = 'ffffff00'
    slots.append(sl)
json.dump(dict(bones=bones, slots=slots, attachments=attachments, page=[PW, PH], glow_of=GLOW_OF,
               mesh={k: dict(world=v[0].tolist(), uvs=v[1].tolist(), tris=v[2], wts=v[3]) for k, v in mesh_cache.items()}),
          open('out/rig_static.json', 'w'))
print('page', PW, PH, 'bones', len(bones), 'slots', len(slots),
      'verts', sum(len(v[0]) for v in mesh_cache.values()), 'tris', sum(len(v[2]) // 3 for v in mesh_cache.values()))
