"""Sample the procedural animations at 30 fps, solve legs (IK) and crest springs,
reduce keys and write the Spine 4.2 JSON skeleton."""
import json, math, pickle, numpy as np
import anims as A
from fk import Skel
from rigdef import S, J, CREST
NAME = 'bowlbug_progenitor'
rig = json.load(open('out/rig_static.json'))
sk = Skel(rig)
FPS = 30
GLOWS = A.GLOWS

# ------------------------------------------------------------------ leg IK setup
def v2(p): return np.array(S(p), float)
LEG = {}
for i in range(1, 6):
    H, K, An, T = v2(J[i]['hip'] if i != 1 else (585, 588)), v2(J[i]['knee']), v2(J[i]['ankle']), v2(J[i]['toe'])
    L1, L2 = np.linalg.norm(K - H), np.linalg.norm(An - K)
    u, a = K - H, An - H
    cr = u[0] * a[1] - u[1] * a[0]
    g0 = math.acos(np.clip(((H - K) @ (An - K)) / (L1 * L2), -1, 1))
    LEG[i] = dict(L1=L1, L2=L2, s0=1.0 if cr >= 0 else -1.0, g0=g0, Rs=np.linalg.norm(An - H),
                  ankle=An, claw_ang=math.atan2(*(T - An)[::-1]), side=1.0 if An[0] >= H[0] else -1.0,
                  dmax=math.radians(45 if i == 1 else 16), kdeg=None if i == 1 else math.radians(1.3))
def ang(v): return math.atan2(v[1], v[0])
def rotm(r):
    c, s = math.cos(math.radians(r)), math.sin(math.radians(r)); return np.array([[c, -s], [s, c]])
def mat(M, local, r):
    c, s = math.cos(math.radians(r)), math.sin(math.radians(r))
    return M @ np.array([[c, -s, local[0]], [s, c, local[1]], [0, 0, 1]])
def solve_leg(i, W, pose, foot):
    L = LEG[i]; hip, knee, ank = f'leg{i}_hip', f'leg{i}_knee', f'leg{i}_ankle'
    host = sk.bones[sk.idx[hip]]['parent']; Mh = W[host]
    Hw = (Mh @ np.array([*sk.local[hip], 1.0]))[:2]
    Tg = L['ankle'] + np.array([foot[0], foot[1]])
    D = max(np.linalg.norm(Tg - Hw), 1e-3)
    L1, L2 = L['L1'], L['L2']
    cosg = np.clip((L1 * L1 + L2 * L2 - D * D) / (2 * L1 * L2), -1, 1)
    d_exact = L['g0'] - math.acos(cosg)
    if L['kdeg'] is None:
        d = d_exact
    else:                               # short thigh: flex a little, slide the foot for the rest
        d_lim = L['kdeg'] * (L['Rs'] - D) / math.radians(1.0) * math.radians(1.0)
        d = min(d_exact, d_lim) if d_exact > 0 else max(d_exact, d_lim)
    d = float(np.clip(d, -L['dmax'], L['dmax']))
    g = min(math.pi, L['g0'] - d)
    R = math.sqrt(max(L1 * L1 + L2 * L2 - 2 * L1 * L2 * math.cos(g), 1e-6))
    if abs(R - D) > 1e-6:
        dy = Tg[1] - Hw[1]
        if R > D:                       # can't fold that far: slide outward along the ground
            Tg = np.array([Hw[0] + L['side'] * math.sqrt(R * R - dy * dy), Tg[1]])
        else:                           # too short: slide inward a little, then lift
            xs = Hw[0] + L['side'] * math.sqrt(max(R * R - dy * dy, 0.0))
            Tg = np.array([Tg[0] + float(np.clip(xs - Tg[0], -12.0, 12.0)), Tg[1]])
            dd = np.linalg.norm(Tg - Hw)
            if dd > R: Tg = Hw + (Tg - Hw) / dd * R
    D = np.linalg.norm(Tg - Hw)
    al = math.acos(np.clip((L1 * L1 + D * D - L2 * L2) / (2 * L1 * D), -1, 1))
    th_u = ang(Tg - Hw) - L['s0'] * al
    Kw = Hw + L1 * np.array([math.cos(th_u), math.sin(th_u)])
    th_s = ang(Tg - Kw)
    r_h = math.degrees(th_u - ang(Mh[:2, :2] @ np.array(sk.local[knee])))
    Mhip = mat(Mh, sk.local[hip], r_h)
    r_k = math.degrees(th_s - ang(Mhip[:2, :2] @ np.array(sk.local[ank])))
    Mk = mat(Mhip, sk.local[knee], r_k)
    claw_vec = v2(J[i]['toe']) - L['ankle']
    r_a = math.degrees(L['claw_ang'] + math.radians(foot[2] * (-L['side'])) - ang(Mk[:2, :2] @ claw_vec))
    wrap = lambda x: (x + 180) % 360 - 180
    pose[hip] = (wrap(r_h), 0, 0, 1, 1); pose[knee] = (wrap(r_k), 0, 0, 1, 1); pose[ank] = (wrap(r_a), 0, 0, 1, 1)

# ------------------------------------------------------------------ crest springs
CH = {i: [f'crest{i}_0', f'crest{i}_1'] for i in CREST}
CDIR = {i: (v2(t) - v2(b)) / np.linalg.norm(v2(t) - v2(b)) for i, (b, t) in CREST.items()}

def simulate(name, dur, loop, init=None):
    n = int(round(dur * FPS)); sub = 8; dt = 1 / (FPS * sub)
    warm = 2 if loop else 0
    total = (warm + 1) * n * sub if loop else n * sub
    state = {b: ([0.0, 0.0] if init is None else list(init[b])) for c in CH.values() for b in c}
    prev = {}; out = []
    for k in range(total + 1):
        tt = (k * dt) % dur if loop else min(k * dt, dur)
        f = A.FUNCS[name](tt)
        P = dict(f.P)
        W = sk.world(P)
        for i, bl in CH.items():
            M = W['head']
            base = (M @ np.array([*sk.local[bl[0]], 1.0]))[:2]
            dw = M[:2, :2] @ CDIR[i]; dw /= np.linalg.norm(dw)
            if i in prev:
                vel = (base - prev[i][0]) / dt; acc = (vel - prev[i][1]) / dt
            else: vel = np.zeros(2); acc = np.zeros(2)
            prev[i] = (base, vel)
            cross = dw[0] * acc[1] - dw[1] * acc[0]
            w0 = TAUF[0]; z = 0.28
            for j, b in enumerate(bl):
                tgt = f.fan[i] * (1.0 if j == 0 else 0.7)
                th, om = state[b]
                accn = -w0 * w0 * (th - tgt) - 2 * z * w0 * om - 0.05 * (1 + 0.8 * j) * cross
                om += accn * dt; th += om * dt
                th = max(-28, min(28, th)); state[b] = [th, om]
        if k % sub == 0 and (not loop or k >= warm * n * sub):
            for i, bl in CH.items():
                for b in bl: P[b] = (state[b][0], 0, 0, 1, 1)
            W = sk.world(P)
            for i in range(1, 6): solve_leg(i, W, P, f.feet[i])
            t_out = tt if not loop else (k - warm * n * sub) * dt
            out.append({'t': round(t_out, 5), 'pose': P, 'glow': {g: min(1.0, max(0.0, f.glow[g])) for g in GLOWS},
                        'tint': tuple(f.tint)})
    return out[:n + 1], {b: tuple(state[b]) for b in state}
TAUF = [2 * math.pi * 2.1]

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
def hexcol(r, g, b, a): return ''.join(f'{int(round(max(0, min(1, v)) * 255)):02x}' for v in (r, g, b, a))
GLOW_ALPHA = 0.85
def build_anim(frames):
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
    for g in GLOWS:
        vals = [(GLOW_ALPHA * f['glow'][g],) for f in frames]
        ks = reduce_keys(times, vals, (0.01,))
        slots[g] = {'rgba': [{'time': round(times[k], 4), 'color': hexcol(1, 1, 1, vals[k][0])} for k in ks]}
    if any(f['tint'] != (1.0, 1.0, 1.0) for f in frames):
        vals = [tuple(f['tint']) for f in frames]
        ks = reduce_keys(times, vals, (0.004, 0.004, 0.004))
        for s in rig['slots']:
            if s['name'] in GLOWS: continue
            slots[s['name']] = {'rgba': [{'time': round(times[k], 4), 'color': hexcol(*vals[k], 1)} for k in ks]}
    for sl in slots.values():
        for arr in sl.values():
            if arr and arr[0].get('time') == 0: del arr[0]['time']
    return {'bones': bones, 'slots': slots}

def main():
    anim_json = {}; allframes = {}
    idle, idle_state = simulate('idle_loop', *A.ANIMS['idle_loop'])
    allframes['idle_loop'] = idle; anim_json['idle_loop'] = build_anim(idle)
    for name, (dur, loop) in A.ANIMS.items():
        if name == 'idle_loop': continue
        init = idle_state if name != 'revive' else None
        fr, _ = simulate(name, dur, loop, init=init)
        allframes[name] = fr; anim_json[name] = build_anim(fr)
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
    skel = {'skeleton': {'hash': 'bowlbugprogenitor1', 'spine': '4.2.0', 'x': round(float(x0), 2), 'y': round(float(y0), 2),
                         'width': round(float(x1 - x0), 2), 'height': round(float(y1 - y0), 2), 'images': './', 'audio': ''},
            'bones': bones, 'slots': rig['slots'],
            'skins': [{'name': 'default', 'attachments': rig['attachments']}],
            'animations': anim_json}
    json.dump(skel, open(f'out/{NAME}.json', 'w'), separators=(',', ':'))
    pickle.dump(allframes, open('out/frames.pkl', 'wb'))
    print('ok', {k: len(v) for k, v in allframes.items()})
if __name__ == '__main__': main()
