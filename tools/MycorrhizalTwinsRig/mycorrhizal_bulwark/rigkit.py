"""rigkit — small generic toolkit shared by the STS2_Things native Spine 4.2 rigs.

A rig folder provides:
  rigdef.py : NAME, ORIGIN (source px -> spine 0,0), BONES [(name, parent, (px,py))],
              ORDER (slot draw order, back -> front), SKIN {part: [(bone, a, b), ...]}
              (one entry = rigid; several = gaussian blend by distance to segment a-b),
              optional SIGMA {part: px}, SPACING {part: px}, GLOW_OF {glow_part: base_part},
              CHAINS {name: dict(bones=[...], freq=Hz, zeta=, clamp=deg, gain=, rgain=)},
              optional post(P, W, f, sk) hook (IK etc.) called after springs.
  parts/    : <part>.png + meta.json {part: {x, y, w, h}} in source pixels.
  anims.py  : ANIMS {name: (duration, loop)}, FUNCS {name: fn(t) -> Frame}.
Commands:  python -m rigkit build | export | render <anim> <i,j,..|gif> <tag>
"""
import json, math, os, pickle, sys, importlib
import numpy as np, cv2
from PIL import Image

sys.path.insert(0, os.getcwd())
R = importlib.import_module('rigdef')
NAME = R.NAME
ORIGIN = R.ORIGIN
GLOW_OF = getattr(R, 'GLOW_OF', {})
CHAINS = getattr(R, 'CHAINS', {})
FPS = 60


def S(p):
    return (round(p[0] - ORIGIN[0], 2), round(ORIGIN[1] - p[1], 2))


from rigutil import *  # noqa: F401,F403  (chain_skin, easing helpers, Pose, Frame)


# ---------------------------------------------------------------- skeleton
def bone_list():
    return [dict(name=n, parent=p, pos=tuple(pos)) for n, p, pos in R.BONES]


class Skel:
    def __init__(self, bones):
        self.bones = bones; self.idx = {b['name']: i for i, b in enumerate(bones)}
        self.setup = {b['name']: S(b['pos']) for b in bones}
        self.parent = {b['name']: b['parent'] for b in bones}
        self.local = {}
        for b in bones:
            p = b['parent']; sp = self.setup[b['name']]
            self.local[b['name']] = sp if p is None else (sp[0] - self.setup[p][0], sp[1] - self.setup[p][1])

    def world(self, pose):
        W = {}
        for b in self.bones:
            n = b['name']; r, dx, dy, sx, sy = pose.get(n, (0, 0, 0, 1, 1))
            lx, ly = self.local[n]
            c, s = math.cos(math.radians(r)), math.sin(math.radians(r))
            M = np.array([[c * sx, -s * sy, lx + dx], [s * sx, c * sy, ly + dy], [0, 0, 1]])
            W[n] = M if b['parent'] is None else W[b['parent']] @ M
        return W


def ang(v): return math.atan2(v[1], v[0])
def wrap(x): return (x + 180) % 360 - 180


def ik2(sk, W, pose, b_hip, b_knee, b_end, target, bend=1.0):
    """Two-bone IK in spine space. target: world point for b_end's origin. bend: +1/-1 knee side."""
    host = sk.parent[b_hip]; Mh = W[host]
    H = (Mh @ np.array([*sk.local[b_hip], 1.0]))[:2]
    L1 = np.hypot(*sk.local[b_knee]); L2 = np.hypot(*sk.local[b_end])
    T = np.array(target, float); D = np.linalg.norm(T - H)
    D = min(max(D, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    a = math.acos(clamp((L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), -1, 1))
    th1 = ang(T - H) + bend * a
    K = H + L1 * np.array([math.cos(th1), math.sin(th1)])
    th2 = ang(T - K)
    r1 = math.degrees(th1 - ang(Mh[:2, :2] @ np.array(sk.local[b_knee])))
    r1 = wrap(r1 + 0.0)
    c, s = math.cos(math.radians(r1)), math.sin(math.radians(r1))
    Mhip = Mh @ np.array([[c, -s, sk.local[b_hip][0]], [s, c, sk.local[b_hip][1]], [0, 0, 1]])
    r2 = wrap(math.degrees(th2 - ang(Mhip[:2, :2] @ np.array(sk.local[b_end]))))
    pose[b_hip] = (r1, 0, 0, 1, 1); pose[b_knee] = (r2, 0, 0, 1, 1)
    return r1, r2


# ---------------------------------------------------------------- build (atlas + meshes)
def seg_dist(p, a, b):
    a = np.array(a, float); b = np.array(b, float); ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-6), 0, 1)
    return np.hypot(*(p - (a + t[:, None] * ab)).T), t


def build():
    os.makedirs('out', exist_ok=True)
    meta = json.load(open('parts/meta.json'))
    bones = bone_list(); bidx = {b['name']: i for i, b in enumerate(bones)}
    bpos = {b['name']: b['pos'] for b in bones}
    GS = getattr(R, 'GLOW_SCALE', 0.5)
    imgs = {}
    for n in R.ORDER + list(GLOW_OF):
        im = Image.open(f'parts/{n}.png').convert('RGBA')
        if n in GLOW_OF and n not in getattr(R, 'NOSCALE', ()):
            im = im.resize((max(1, round(im.width * GS)), max(1, round(im.height * GS))), Image.LANCZOS)
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
    for PW, PH in [(1024, 1024), (2048, 1024), (2048, 1536), (2048, 2048), (4096, 2048)]:
        rects = pack(PW, PH)
        if rects: break
    page = Image.new('RGBA', (PW, PH), (0, 0, 0, 0))
    for n, (x, y) in rects.items(): page.paste(imgs[n], (x, y))
    P = np.array(page).astype(np.float32); known = P[..., 3] > 0; col = P[..., :3].copy()
    for _ in range(6):   # colour bleed so bilinear filtering never pulls black into edges
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

    SIG = getattr(R, 'SIGMA', {}); SPC = getattr(R, 'SPACING', {})
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
    INHERIT = getattr(R, 'INHERIT', {})
    def weights(n, world):
        if hasattr(R, 'weights'):
            return R.weights(n, world)
        if n in INHERIT:
            # detail part rides on its host surface: sample the host weight field at the same
            # source pixels, then hand the host's anchor bone(s) over to the part's own bone(s)
            # (children of those anchors, identical at rest) so local blink/claw motion still applies.
            host, remap = INHERIT[n]
            out = []
            for wl in weights(host, world):
                acc = {}
                for b, w in wl:
                    b = remap.get(b, b); acc[b] = acc.get(b, 0) + w
                out.append(list(acc.items()))
            return out
        segs = R.SKIN[n]
        if len(segs) == 1: return [[(segs[0][0], 1.0)] for _ in world]
        D = np.stack([seg_dist(world, a, b)[0] for _, a, b in segs], 1)
        Wt = np.exp(-(D / SIG.get(n, 60.0)) ** 2) + 1e-9
        Wt[np.arange(len(world)), D.argmin(1)] += 0.35
        Wt /= Wt.sum(1, keepdims=True)
        out = []
        for i in range(len(world)):
            acc = {}
            for k in range(len(segs)):
                if Wt[i, k] > 0.02: acc[segs[k][0]] = acc.get(segs[k][0], 0) + Wt[i, k]
            s = sum(acc.values()); out.append([(b, w / s) for b, w in acc.items()])
        return out
    def spine_vertices(world, wts):
        out = []
        for p, wl in zip(world, wts):
            sp = S(p); out.append(len(wl))
            for b, w in wl:
                bp = S(bpos[b]); out += [bidx[b], round(sp[0] - bp[0], 2), round(sp[1] - bp[1], 2), round(w, 4)]
        return out
    slot_list = []
    for n in R.ORDER:
        slot_list.append(n)
        for g, base in GLOW_OF.items():
            if base == n: slot_list.append(g)
    slot_list += [g for g in GLOW_OF if g not in slot_list]
    attachments = {}; slots = []; mesh = {}
    for n in slot_list:
        base = GLOW_OF.get(n, n)
        mesh_source = base if n in GLOW_OF else n
        world, uvs, tris = grid_mesh(mesh_source, SPC.get(mesh_source, 24))
        wts = weights(getattr(R, 'GLOW_SKIN', {}).get(n, base), world)
        mesh[n] = dict(world=world.tolist(), uvs=uvs.tolist(), tris=tris, wts=wts)
        attachments[n] = {n: {'type': 'mesh', 'uvs': [round(float(v), 5) for v in uvs.flatten()],
                              'triangles': tris, 'vertices': spine_vertices(world, wts), 'hull': 0,
                              'width': meta[n]['w'], 'height': meta[n]['h']}}
        sl = {'name': n, 'bone': R.SKIN[getattr(R, 'GLOW_SKIN', {}).get(n, base)][0][0], 'attachment': n}
        if n in GLOW_OF: sl['blend'] = 'additive'; sl['color'] = 'ffffff00'
        slots.append(sl)
    json.dump(dict(bones=bones, slots=slots, attachments=attachments, page=[PW, PH], mesh=mesh),
              open('out/rig_static.json', 'w'))
    print('page', PW, PH, 'bones', len(bones), 'slots', len(slots),
          'verts', sum(len(m['world']) for m in mesh.values()), 'tris', sum(len(m['tris']) // 3 for m in mesh.values()))


# ---------------------------------------------------------------- simulate + export
def load_rig():
    rig = json.load(open('out/rig_static.json'))
    return rig, Skel(rig['bones'])


def simulate(sk, A, name, dur, loop, init=None):
    n = int(math.ceil(dur * FPS - 1e-9)); sub = 4; dt = 1 / (FPS * sub)
    warm = 2 if loop else 0
    total = (warm + 1) * n * sub if loop else n * sub
    cb = [b for c in CHAINS.values() for b in c['bones']]
    state = {b: (list(init[b]) if init and b in init else [0.0, 0.0]) for b in cb}
    prev = {}; out = []
    post = getattr(R, 'post', None)
    for k in range(total + 1):
        tt = (k * dt) % dur if loop else min(k * dt, dur)
        f = A.FUNCS[name](tt)
        P = Pose(f.P)
        if CHAINS:
            W = sk.world(P)
            for cname, c in CHAINS.items():
                b0 = c['bones'][0]; host = sk.parent[b0]; M = W[host]
                base = (M @ np.array([*sk.local[b0], 1.0]))[:2]
                hang = math.degrees(ang(M[:2, 0]))
                d = M[:2, :2] @ np.array(sk.local[c['bones'][1]] if len(c['bones']) > 1 else (1.0, 0.0))
                d = d / (np.linalg.norm(d) + 1e-9)
                if cname in prev:
                    pb, pv, ph, pw = prev[cname]
                    vel = (base - pb) / dt; acc = (vel - pv) / dt
                    om_h = wrap(hang - ph) / dt; al_h = (om_h - pw) / dt
                else:
                    vel = np.zeros(2); acc = np.zeros(2); om_h = 0.0; al_h = 0.0
                if k == 0: acc = np.zeros(2); al_h = 0.0
                prev[cname] = (base, vel, hang, om_h)
                cross = d[0] * acc[1] - d[1] * acc[0]
                for j, b in enumerate(c['bones']):
                    w0 = TAU * c['freq'] * (1 - c.get('taper', 0.06) * j)
                    th, om = state[b]
                    tgt = f.bias.get(b, 0.0)
                    a = (-w0 * w0 * (th - tgt) - 2 * c['zeta'] * w0 * om
                         - c['gain'] * (1 + 0.6 * j) * cross - c.get('rgain', 0.0) * (1 + 0.4 * j) * al_h)
                    om += a * dt; th += om * dt
                    th = max(-c['clamp'], min(c['clamp'], th)); state[b] = [th, om]
        if k % sub == 0 and (not loop or k >= warm * n * sub):
            for b in cb:
                r0 = P.get(b, (0, 0, 0, 1, 1))
                P[b] = (r0[0] + state[b][0] * f.extra.get('spring_mix', 1.0),) + tuple(r0[1:])
            if post:
                post(P, sk.world(P), f, sk)
            t_out = tt if not loop else (k - warm * n * sub) * dt
            out.append({'t': round(t_out, 5), 'pose': dict(P), 'feet': f.extra.get('feet', {}), 'glow': {g: clamp(f.glow.get(g, 0.0)) for g in GLOW_OF},
                        'tint': tuple(f.tint)})
    out = out[:n + 1]
    if loop:
        out[-1] = dict(out[0], t=round(dur, 5))
    return out, {b: tuple(state[b]) for b in state}


def reduce_keys(times, vals, eps):
    keep = [0]; i = 0; N = len(times)
    while i < N - 1:
        j = i + 2
        while j < N:
            ok = True; t0, t1 = times[i], times[j]
            for m in range(i + 1, j):
                u = (times[m] - t0) / (t1 - t0)
                for q in range(len(vals[0])):
                    if abs(vals[i][q] + (vals[j][q] - vals[i][q]) * u - vals[m][q]) > eps[q]: ok = False; break
                if not ok: break
            if not ok: break
            j += 1
        i = j - 1; keep.append(i)
    return keep


def hexcol(r, g, b, a): return ''.join(f'{int(round(clamp(v) * 255)):02x}' for v in (r, g, b, a))


def build_anim(sk, rig, frames, glow_alpha):
    times = [f['t'] for f in frames]; bones = {}
    for b in sk.idx:
        rot = [(f['pose'].get(b, (0, 0, 0, 1, 1))[0],) for f in frames]
        tr = [tuple(f['pose'].get(b, (0, 0, 0, 1, 1))[1:3]) for f in frames]
        sc = [tuple(f['pose'].get(b, (0, 0, 0, 1, 1))[3:5]) for f in frames]
        tl = {}
        if any(abs(v[0]) > 1e-3 for v in rot):
            ks = reduce_keys(times, rot, (0.05,)); tl['rotate'] = [{'time': round(times[k], 4), 'value': round(rot[k][0], 3)} for k in ks]
        if any(abs(v[0]) > 1e-3 or abs(v[1]) > 1e-3 for v in tr):
            ks = reduce_keys(times, tr, (0.06, 0.06)); tl['translate'] = [{'time': round(times[k], 4), 'x': round(tr[k][0], 2), 'y': round(tr[k][1], 2)} for k in ks]
        if any(abs(v[0] - 1) > 1e-4 or abs(v[1] - 1) > 1e-4 for v in sc):
            ks = reduce_keys(times, sc, (0.0006, 0.0006)); tl['scale'] = [{'time': round(times[k], 4), 'x': round(sc[k][0], 4), 'y': round(sc[k][1], 4)} for k in ks]
        if tl:
            for arr in tl.values():
                if arr[0]['time'] == 0: del arr[0]['time']
            bones[b] = tl
    slots = {}
    for g in GLOW_OF:
        vals = [(glow_alpha * f['glow'][g],) for f in frames]
        ks = reduce_keys(times, vals, (0.01,))
        slots[g] = {'rgba': [{'time': round(times[k], 4), 'color': hexcol(1, 1, 1, vals[k][0])} for k in ks]}
    if any(tuple(f['tint']) != (1.0, 1.0, 1.0, 1.0) for f in frames):
        vals = [tuple(f['tint']) for f in frames]
        ks = reduce_keys(times, vals, (0.004,) * 4)
        for s in rig['slots']:
            if s['name'] in GLOW_OF: continue
            slots[s['name']] = {'rgba': [{'time': round(times[k], 4), 'color': hexcol(*vals[k])} for k in ks]}
    for sl in slots.values():
        for arr in sl.values():
            if arr and arr[0].get('time') == 0: del arr[0]['time']
    return {'bones': bones, 'slots': slots}


def export():
    rig, sk = load_rig()
    A = importlib.import_module('anims')
    ga = getattr(R, 'GLOW_ALPHA', 0.85)
    anim_json = {}; allframes = {}
    idle, idle_state = simulate(sk, A, 'idle_loop', *A.ANIMS['idle_loop'])
    allframes['idle_loop'] = idle; anim_json['idle_loop'] = build_anim(sk, rig, idle, ga)
    for name, (dur, loop) in A.ANIMS.items():
        if name == 'idle_loop': continue
        fr, _ = simulate(sk, A, name, dur, loop, init=idle_state if name not in getattr(A, 'COLD_START', ()) else None)
        allframes[name] = fr; anim_json[name] = build_anim(sk, rig, fr, ga)
    bones = []
    for b in rig['bones']:
        e = {'name': b['name']}
        if b['parent']: e['parent'] = b['parent']
        lx, ly = sk.local[b['name']]
        if abs(lx) > 1e-6: e['x'] = round(lx, 2)
        if abs(ly) > 1e-6: e['y'] = round(ly, 2)
        bones.append(e)
    allw = np.array([S(p) for m in rig['mesh'].values() for p in m['world']])
    x0, y0 = allw.min(0); x1, y1 = allw.max(0)
    skel = {'skeleton': {'hash': NAME.replace('_', '') + '1', 'spine': '4.2.0', 'x': round(float(x0), 2), 'y': round(float(y0), 2),
                         'width': round(float(x1 - x0), 2), 'height': round(float(y1 - y0), 2), 'images': './', 'audio': ''},
            'bones': bones, 'slots': rig['slots'],
            'skins': [{'name': 'default', 'attachments': rig['attachments']}],
            'animations': anim_json}
    json.dump(skel, open(f'out/{NAME}.json', 'w'), separators=(',', ':'))
    pickle.dump(allframes, open('out/frames.pkl', 'wb'))
    json.dump({name:[{'t':f['t'],'feet':f['feet']} for f in frames] for name,frames in allframes.items()},
              open('out/foot-targets.json','w'),separators=(',',':'))
    print('ok', {k: len(v) for k, v in allframes.items()})


# ---------------------------------------------------------------- CPU preview
class Renderer:
    def __init__(self):
        self.rig, self.sk = load_rig()
        meta = json.load(open('parts/meta.json'))
        self.tex = {n: np.array(Image.open(f'parts/{n}.png').convert('RGBA')).astype(np.float32) / 255 for n in meta}
        bpos = {b['name']: b['pos'] for b in self.rig['bones']}
        self.binds = {n: [[(b, np.array(S(p)) - np.array(S(bpos[b])), w) for b, w in wl] for p, wl in zip(m['world'], m['wts'])]
                      for n, m in self.rig['mesh'].items()}
        self.ga = getattr(R, 'GLOW_ALPHA', 0.85)

    def render(self, frame, scale=0.5, W=800, H=600, ox=400, oy=560, bg=(32, 36, 44)):
        Wm = self.sk.world(frame['pose'])
        canvas = np.zeros((H, W, 3), np.float32); canvas[...] = np.array(bg) / 255
        cv2.line(canvas, (0, oy), (W, oy), (0.3, 0.3, 0.36), 1)
        tint = frame['tint'] if len(frame['tint']) == 4 else tuple(frame['tint']) + (1.0,)
        for sl in self.rig['slots']:
            n = sl['name']; m = self.rig['mesh'][n]
            add = n in GLOW_OF
            amul = self.ga * frame['glow'].get(n, 0) if add else tint[3]
            col = np.ones(3, np.float32) if add else np.array(tint[:3], np.float32)
            if amul < 0.01: continue
            pts = np.array([sum(w * (Wm[b] @ np.array([l[0], l[1], 1]))[:2] for b, l, w in bl) for bl in self.binds[n]])
            scr = np.stack([ox + pts[:, 0] * scale, oy - pts[:, 1] * scale], 1)
            t = self.tex[n]; th, tw = t.shape[:2]
            uv = np.array(m['uvs']) * np.array([tw, th])
            for tri in np.array(m['tris']).reshape(-1, 3):
                d = scr[tri].astype(np.float32); s = uv[tri].astype(np.float32)
                x0, y0 = np.floor(d.min(0)).astype(int); x1, y1 = np.ceil(d.max(0)).astype(int) + 1
                x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W); y1 = min(y1, H)
                if x1 <= x0 or y1 <= y0: continue
                Mt = cv2.getAffineTransform(s, d - np.array([x0, y0], np.float32))
                patch = cv2.warpAffine(t, Mt, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
                mask = np.zeros((y1 - y0, x1 - x0), np.float32)
                cv2.fillConvexPoly(mask, np.round((d - np.array([x0, y0])) * 4).astype(np.int32), 1.0, lineType=cv2.LINE_AA, shift=2)
                a = patch[..., 3] * mask * amul
                reg = canvas[y0:y1, x0:x1]
                if add: reg += patch[..., :3] * a[..., None]
                else: reg[...] = reg * (1 - a[..., None]) + patch[..., :3] * col * a[..., None]
        return (np.clip(canvas, 0, 1) * 255).astype(np.uint8)


def render_cli(args):
    rr = Renderer(); frames = pickle.load(open('out/frames.pkl', 'rb'))
    V = getattr(R, 'VIEW', dict(scale=0.5, W=800, H=600, ox=400, oy=560))
    name = args[0]; tag = args[2] if len(args) > 2 else 'x'
    os.makedirs('prev', exist_ok=True)
    if args[1] == 'gif':
        g = dict(V); g.update(scale=V['scale'] * 0.7, W=int(V['W'] * 0.7), H=int(V['H'] * 0.7), ox=int(V['ox'] * 0.7), oy=int(V['oy'] * 0.7))
        ims = [Image.fromarray(rr.render(f, **g)).quantize(128) for f in frames[name][::2]]
        ims[0].save(f'prev/{name}_{tag}.gif', save_all=True, append_images=ims[1:], duration=67, loop=0)
        print(f'prev/{name}_{tag}.gif'); return
    fr = frames[name]
    idxs = [int(x) for x in args[1].split(',')] if args[1] != 'auto' else [round(k * (len(fr) - 1) / 5) for k in range(6)]
    ims = [rr.render(fr[i], **V) for i in idxs]
    cols = 3; h, w = ims[0].shape[:2]; rows = (len(ims) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, im in enumerate(ims):
        cv2.putText(im, f'{name} f{idxs[k]} t={fr[idxs[k]]["t"]:.2f}', (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        sheet[(k // cols) * h:(k // cols + 1) * h, (k % cols) * w:(k % cols + 1) * w] = im
    fn = f'prev/{name}_{tag}.jpg'; Image.fromarray(sheet).save(fn, quality=85); print(fn)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'build': build()
    elif cmd == 'export': export()
    elif cmd == 'render': render_cli(sys.argv[2:])
