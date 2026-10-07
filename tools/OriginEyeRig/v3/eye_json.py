"""Origin Eye With Teeth v3 skeleton JSON  (input: eye_raw.json = faithful vanilla conversion by node/skel2json.mjs).

Vanilla skeleton, constraints (5 path-driven tentacles + tentacle_rot_const) and the vanilla idle_loop / attack / die
timelines are kept exactly (incl. Bezier curves).  v3 look (user decisions Q3=c, Q5=normal, Q6, Q8):
  * NORMAL blending on every slot; grey slot colours (the grey V1-style texture carries the look)
      body slots  : rgb = max(rgb) (vanilla idle max is 1.0; attack dips kept), alpha = a/0.91 (breathing 0.75..1)
      eye slots   : rgb = max(rgb), alpha = sqrt(a/0.91) (mostly opaque so the black slit pupil reads)
      extra eye   : rgb = max(rgb), alpha unchanged (attack pulse rings)
      death_still : additive dim afterimage (max rgb 0.29) -> alpha ghost, peak 0.55
  * tentacles drawn behind the flower; debug slots test_BG/guide dropped; colour keys on invisible path slots dropped
  * mod-only animations (C# OriginEyeWithTeeth: Hit -> hurt, IllusionPower wake-up -> revive):
      hurt   0.5 s = idle_loop 0..0.5 s (curves split exactly) + recoil on `cog` (unkeyed in idle) + light red flash
      revive 1.2 s = die reversed (Bezier control points mirrored, stepped/attachment keys shifted), time-scaled
"""
import json, math, copy, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'out', 'eye_raw.json')          # node skel2json.mjs <ref>/eye_with_teeth.skel <ref>/eye_with_teeth.atlas out/eye_raw.json
OUT = os.path.join(HERE, 'out', 'origin_eye_with_teeth.spjson')
DROP = {'test_BG', 'guide'}
VINES = ['extra vine', 'extra vine3', 'extra vine4', 'extra vine5', 'extra vine2']
BODY = {'back petals', 'leaf 1', 'leaf 2', 'leaf 3', 'leaf 4', *VINES}
EYE = {'eyeball', 'iris 2', 'pupil'}
EXTRA_EYE = {'eyeball2', 'iris', 'pupil2'}
PATH_SLOTS = {'tentacle_path_a', 'tentacle_path_a2', 'tentacle_path_a3', 'tentacle_path_a4', 'tentacle_path_a5'}
DEATH_PEAK = 0.29
HURT_T = 0.5
REVIVE_T = 1.2
EPS = 1e-4


def hx(h):
    return [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]


def fmt(vals):
    return ''.join('%02x' % max(0, min(255, round(v * 255))) for v in vals)


def r6(v):
    return round(v, 6)


# ------------------------------------------------------------------ generic key access
# a "channel view" of a key list: kind -> (names of value channels)
BONE_CH = {'rotate': ['value'], 'translatex': ['value'], 'translatey': ['value'], 'scalex': ['value'], 'scaley': ['value'],
           'shearx': ['value'], 'sheary': ['value'], 'translate': ['x', 'y'], 'scale': ['x', 'y'], 'shear': ['x', 'y']}
DEFAULT = {'rotate': 0, 'translatex': 0, 'translatey': 0, 'translate': 0, 'shearx': 0, 'sheary': 0, 'shear': 0,
           'scalex': 1, 'scaley': 1, 'scale': 1}


def get_vals(kind, k):
    """values of a key as a list of floats (colours unpacked)."""
    if kind in BONE_CH: return [k.get(c, DEFAULT[kind]) for c in BONE_CH[kind]]
    if kind == 'alpha': return [k.get('value', 1)]
    if kind in ('rgb', 'rgba'): return hx(k['color'])
    raise ValueError(kind)


def set_vals(kind, k, v):
    if kind in BONE_CH:
        for c, x in zip(BONE_CH[kind], v): k[c] = round(x, 5)
    elif kind == 'alpha': k['value'] = r6(v[0])
    elif kind in ('rgb', 'rgba'): k['color'] = fmt(v)
    else: raise ValueError(kind)


def bez_eval_time(p0, c1, c2, p1, T):
    """parameter u with x(u) == T on a monotone cubic (x = time)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        u = (lo + hi) / 2
        x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * c1[0] + 3 * (1 - u) * u * u * c2[0] + u ** 3 * p1[0]
        if x < T: lo = u
        else: hi = u
    return (lo + hi) / 2


def lerp2(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def bez_split(p0, c1, c2, p1, u):
    """first half of a cubic split at u: returns (c1', c2', end)."""
    a = lerp2(p0, c1, u); b = lerp2(c1, c2, u); c = lerp2(c2, p1, u)
    d = lerp2(a, b, u); e = lerp2(b, c, u); f = lerp2(d, e, u)
    return a, d, f


def value_at(kind, keys, T):
    """per-channel value of a curve timeline at time T (Spine semantics, incl. Bezier)."""
    if T <= keys[0].get('time', 0): return get_vals(kind, keys[0])
    for i in range(len(keys) - 1):
        t0, t1 = keys[i].get('time', 0), keys[i + 1].get('time', 0)
        if t0 <= T < t1:
            v0, v1 = get_vals(kind, keys[i]), get_vals(kind, keys[i + 1]); c = keys[i].get('curve')
            if c == 'stepped': return v0
            if not c: return [a + (b - a) * (T - t0) / (t1 - t0) for a, b in zip(v0, v1)]
            out = []
            for ch in range(len(v0)):
                cx1, cy1, cx2, cy2 = c[ch * 4: ch * 4 + 4]
                u = bez_eval_time((t0, v0[ch]), (cx1, cy1), (cx2, cy2), (t1, v1[ch]), T)
                out.append(bez_split((t0, v0[ch]), (cx1, cy1), (cx2, cy2), (t1, v1[ch]), u)[2][1])
            return out
    return get_vals(kind, keys[-1])


def truncate(kind, keys, T):
    """keys restricted to [0, T] with an exact final key at T (Bezier segments split)."""
    out = []
    for i, k in enumerate(keys):
        t = k.get('time', 0)
        if t >= T - 1e-9:
            break
        nk = copy.deepcopy(k)
        if i + 1 < len(keys) and keys[i + 1].get('time', 0) > T + 1e-9 and isinstance(k.get('curve'), list):
            t1 = keys[i + 1]['time']; v0 = get_vals(kind, k); v1 = get_vals(kind, keys[i + 1]); c = k['curve']; nc = []
            for ch in range(len(v0)):
                cx1, cy1, cx2, cy2 = c[ch * 4: ch * 4 + 4]
                u = bez_eval_time((t, v0[ch]), (cx1, cy1), (cx2, cy2), (t1, v1[ch]), T)
                a, d, f = bez_split((t, v0[ch]), (cx1, cy1), (cx2, cy2), (t1, v1[ch]), u)
                nc += [r6(a[0]), r6(a[1]), r6(d[0]), r6(d[1])]
            nk['curve'] = nc
        out.append(nk)
    end = {'time': T}; set_vals(kind, end, value_at(kind, keys, T)); out.append(end)
    return out


def reverse(kind, keys, D, s, setup_vals):
    """die -> revive: reverse a curve timeline over [0, D] and scale time by s."""
    keys = copy.deepcopy(keys)
    if keys[0].get('time', 0) > 1e-9:            # before the first key Spine shows the setup pose: make it explicit
        first = {'time': 0, 'curve': 'stepped'}; set_vals(kind, first, setup_vals); keys.insert(0, first)
    n = len(keys); out = []
    tt = lambda t: r6((D - t) * s)
    for j in range(n):
        i = n - 1 - j                           # original key index
        k = {'time': tt(keys[i].get('time', 0))}; set_vals(kind, k, get_vals(kind, keys[i]))
        if i > 0:
            c = keys[i - 1].get('curve')         # original segment (i-1 -> i) becomes new segment (j -> j+1)
            if c == 'stepped':
                # original holds v[i-1] on [t[i-1], t[i]); reversed the jump happens right after this key
                out.append(k)
                k2 = {'time': r6(k['time'] + EPS), 'curve': 'stepped'}; set_vals(kind, k2, get_vals(kind, keys[i - 1]))
                k = k2
            elif isinstance(c, list):
                nc = []
                for ch in range(len(c) // 4):
                    cx1, cy1, cx2, cy2 = c[ch * 4: ch * 4 + 4]
                    nc += [tt(cx2), cy2, tt(cx1), cy1]
                k['curve'] = nc
        out.append(k)
    if out[0]['time'] > 1e-9:                    # original holds its last key until D -> revive starts with it
        k0 = copy.deepcopy(out[0]); k0['time'] = 0; k0.pop('curve', None); out.insert(0, k0)
    for k in out:
        if k['time'] == 0: k.pop('time')
    return out


def reverse_attachment(keys, D, s, setup_name):
    ks = [(k.get('time', 0), k.get('name')) for k in keys]
    if ks[0][0] > 1e-9: ks.insert(0, (0.0, setup_name))
    out = []
    for i in range(len(ks) - 1, -1, -1):
        t_next = ks[i + 1][0] if i + 1 < len(ks) else D
        out.append({'time': r6((D - t_next) * s), 'name': ks[i][1]})
    for k in out:
        if k['time'] == 0: k.pop('time')
    return out


# ------------------------------------------------------------------ colour conversion
def grey_curve_from(c, v0, v1, nch):
    """curve for a grey value built from the channel that is brightest at both ends (else linear)."""
    if not isinstance(c, list): return c
    a0 = max(range(nch), key=lambda i: v0[i]); a1 = max(range(nch), key=lambda i: v1[i])
    ch = a0 if a0 == a1 else None
    if ch is None: return None
    return c[ch * 4: ch * 4 + 4]


def map_curve_y(cseg, f):
    return [cseg[0], r6(f(cseg[1])), cseg[2], r6(f(cseg[3]))]


def convert_colours(slot, tl):
    """tl: slot timeline dict (rgb/alpha/rgba/attachment) -> v3 grey version (in place)."""
    if slot in BODY or slot in EYE:
        af = (lambda a: min(1.0, a / 0.91)) if slot in BODY else (lambda a: math.sqrt(max(0.0, min(1.0, a / 0.91))))
        if 'rgb' in tl:
            keys = tl['rgb']; vals = [hx(k['color']) for k in keys]
            for i, k in enumerate(keys):
                g = max(vals[i]); c = k.get('curve')
                if isinstance(c, list):
                    seg = grey_curve_from(c, vals[i], vals[i + 1], 3)
                    if seg is None: k.pop('curve')
                    else: k['curve'] = seg * 3
                k['color'] = fmt([g, g, g])
        if 'alpha' in tl:
            for k in tl['alpha']:
                k['value'] = r6(af(k.get('value', 1)))
                if isinstance(k.get('curve'), list): k['curve'] = map_curve_y(k['curve'], af)
        assert 'rgba' not in tl, slot
    elif slot in EXTRA_EYE:
        if 'rgba' in tl:
            keys = tl['rgba']; vals = [hx(k['color']) for k in keys]
            for i, k in enumerate(keys):
                g = max(vals[i][:3]); c = k.get('curve')
                if isinstance(c, list):
                    seg = grey_curve_from(c[:12], vals[i], vals[i + 1], 3)
                    if not seg: seg = _linear_seg(k.get('time', 0), keys[i + 1]['time'], g, max(vals[i + 1][:3]))
                    k['curve'] = seg * 3 + c[12:16]
                k['color'] = fmt([g, g, g, vals[i][3]])
    elif slot == 'death_still':
        if 'rgba' in tl:
            keys = tl['rgba']; vals = [hx(k['color']) for k in keys]
            f = lambda m: min(1.0, m / DEATH_PEAK) * 0.55
            for i, k in enumerate(keys):
                m = max(vals[i][:3]); c = k.get('curve')
                if isinstance(c, list):
                    seg = grey_curve_from(c[:12], vals[i], vals[i + 1], 3) or _linear_seg(k.get('time', 0), keys[i + 1]['time'], m, max(vals[i + 1][:3]))
                    t1 = keys[i + 1]['time']
                    k['curve'] = _linear_seg(k.get('time', 0), t1, 1, 1) * 3 + map_curve_y(seg, lambda y: f(y) * vals[i][3])
                k['color'] = fmt([1, 1, 1, f(m) * vals[i][3]])
    elif slot in PATH_SLOTS:
        for kk in ('rgb', 'alpha', 'rgba'): tl.pop(kk, None)
    else:
        raise SystemExit('unhandled slot ' + slot)


def _linear_seg(t0, t1, v0, v1):
    return [r6(t0 + (t1 - t0) / 3), r6(v0 + (v1 - v0) / 3), r6(t0 + 2 * (t1 - t0) / 3), r6(v0 + 2 * (v1 - v0) / 3)]


# ------------------------------------------------------------------ build
def main():
    J = json.load(open(SRC))
    anims = J['animations']
    D_DIE = max(k.get('time', 0) for A in [anims['die']] for grp in ('bones', 'slots') for tls in A.get(grp, {}).values() for ks in tls.values() for k in ks)
    setup_bone = {b['name']: b for b in J['bones']}
    setup_slot = {s['name']: s for s in J['slots']}

    # ---- mod animations from the untouched vanilla timelines
    idle, die = anims['idle_loop'], anims['die']
    hurt = {'bones': {}, 'slots': {}}
    for bn, tls in idle.get('bones', {}).items():
        hurt['bones'][bn] = {kind: truncate(kind, ks, HURT_T) for kind, ks in tls.items()}
    for sn, tls in idle.get('slots', {}).items():
        h = {}
        for kind, ks in tls.items():
            if kind == 'attachment': h[kind] = [k for k in ks if k.get('time', 0) <= HURT_T + 1e-9]
            else: h[kind] = truncate(kind, ks, HURT_T)
        hurt['slots'][sn] = h
    assert 'cog' not in hurt['bones']
    hurt['bones']['cog'] = {
        'rotate': [{'value': 0, 'curve': [0.022, 0, 0.044, -14]}, {'time': 0.0667, 'value': -14, 'curve': [0.12, -14, 0.15, 3]},
                   {'time': 0.2, 'value': 3, 'curve': [0.25, 3, 0.3, -1]}, {'time': 0.3333, 'value': -1, 'curve': [0.38, -1, 0.45, 0]}, {'time': HURT_T, 'value': 0}],
        'translate': [{'x': 0, 'y': 0, 'curve': [0.022, 0, 0.044, 22, 0.022, 0, 0.044, 0]}, {'time': 0.0667, 'x': 22, 'y': 0, 'curve': [0.12, 22, 0.15, -4, 0.12, 0, 0.15, 0]},
                      {'time': 0.2, 'x': -4, 'y': 0, 'curve': [0.28, -4, 0.4, 0, 0.28, 0, 0.4, 0]}, {'time': HURT_T, 'x': 0, 'y': 0}],
        'scale': [{'x': 1, 'y': 1, 'curve': [0.022, 1, 0.044, 0.92, 0.022, 1, 0.044, 1.06]}, {'time': 0.0667, 'x': 0.92, 'y': 1.06, 'curve': [0.12, 0.92, 0.15, 1.02, 0.12, 1.06, 0.15, 0.99]},
                  {'time': 0.2, 'x': 1.02, 'y': 0.99, 'curve': [0.28, 1.02, 0.4, 1, 0.28, 0.99, 0.4, 1]}, {'time': HURT_T, 'x': 1, 'y': 1}],
    }
    revive = {'bones': {}, 'slots': {}}
    s = REVIVE_T / D_DIE
    for bn, tls in die.get('bones', {}).items():
        revive['bones'][bn] = {kind: reverse(kind, ks, D_DIE, s, [DEFAULT[kind]] * len(BONE_CH[kind])) for kind, ks in tls.items()}
    for sn, tls in die.get('slots', {}).items():
        r = {}
        sc = hx(setup_slot[sn].get('color', 'ffffffff'))
        for kind, ks in tls.items():
            if kind == 'attachment': r[kind] = reverse_attachment(ks, D_DIE, s, setup_slot[sn].get('attachment'))
            else: r[kind] = reverse(kind, ks, D_DIE, s, {'rgb': sc[:3], 'rgba': sc, 'alpha': [sc[3]]}[kind])
        revive['slots'][sn] = r
    assert 'attachments' not in die and 'drawOrder' not in die and 'events' not in die
    anims['hurt'] = hurt; anims['revive'] = revive

    # ---- v3 look
    J['slots'] = [x for x in J['slots'] if x['name'] not in DROP]
    for x in J['slots']:
        x.pop('blend', None)
        assert 'color' not in x, x
    order = VINES + [x['name'] for x in J['slots'] if x['name'] not in VINES]
    J['slots'].sort(key=lambda x: order.index(x['name']))
    for skin in J['skins']:
        for sn in DROP: skin['attachments'].pop(sn, None)
    for an, A in anims.items():
        for sn in list(A.get('slots', {})):
            if sn in DROP: A['slots'].pop(sn); continue
            convert_colours(sn, A['slots'][sn])
            if not A['slots'][sn]: A['slots'].pop(sn)
    # hurt flash (after conversion): rgb of body + eye slots -> quick light-red tint
    for sn in BODY | EYE:
        hurt['slots'].setdefault(sn, {})['rgb'] = [{'color': 'ffffff'}, {'time': 0.0333, 'color': 'ffb3b3'}, {'time': 0.1333, 'color': 'ffffff'}, {'time': HURT_T, 'color': 'ffffff'}]
    J['skeleton']['hash'] = 'origineye3'
    txt = json.dumps(J)
    for sn in DROP: assert '"%s"' % sn not in txt, sn
    json.dump(J, open(OUT, 'w'), separators=(',', ':'))
    dur = {}
    for an, A in anims.items():
        m = 0
        for grp in ('bones', 'slots'):
            for tls in A.get(grp, {}).values():
                for ks in tls.values():
                    for k in ks: m = max(m, k.get('time', 0))
        for sk in A.get('attachments', {}).values():
            for sl in sk.values():
                for at in sl.values():
                    for ks in at.values():
                        for k in ks: m = max(m, k.get('time', 0))
        dur[an] = round(m, 4)
    print('slots', len(J['slots']), [x['name'] for x in J['slots']])
    print('anims', dur, 'bytes', len(txt))


if __name__ == '__main__':
    main()
