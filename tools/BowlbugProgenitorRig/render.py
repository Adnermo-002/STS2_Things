"""CPU preview renderer (mesh skinning identical to the Spine data) -> contact sheets / gif."""
import json, math, numpy as np, cv2, pickle, sys, os
from PIL import Image
from fk import Skel
from rigdef import S
rig = json.load(open('out/rig_static.json')); sk = Skel(rig)
meta = json.load(open('parts/meta.json'))
GLOW_OF = rig['glow_of']
tex = {n: np.array(Image.open(f'parts/{n}.png').convert('RGBA')).astype(np.float32) / 255 for n in meta}
bpos = {b['name']: b['pos'] for b in rig['bones']}
binds = {}
for src, m in rig['mesh'].items():
    binds[src] = [[(b, np.array(S(p)) - np.array(S(bpos[b])), w) for b, w in wl] for p, wl in zip(m['world'], m['wts'])]
def render(frame, scale=0.55, W=880, H=500, ox=430, oy=475, bg=(38, 40, 52)):
    Wm = sk.world(frame['pose'])
    canvas = np.zeros((H, W, 3), np.float32); canvas[...] = np.array(bg) / 255
    cv2.line(canvas, (0, oy), (W, oy), (0.3, 0.3, 0.36), 1)
    for sl in rig['slots']:
        n = sl['name']; m = rig['mesh'][n]
        add = n in GLOW_OF
        amul = 0.85 * frame['glow'].get(n, 0) if add else 1.0
        col = np.array([1, 1, 1], np.float32) if add else np.array(frame['tint'], np.float32)
        if amul < 0.01: continue
        pts = np.array([sum(w * (Wm[b] @ np.array([l[0], l[1], 1]))[:2] for b, l, w in bl) for bl in binds[n]])
        scr = np.stack([ox + pts[:, 0] * scale, oy - pts[:, 1] * scale], 1)
        t = tex[n]; th, tw = t.shape[:2]
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
if __name__ == '__main__':
    frames = pickle.load(open('out/frames.pkl', 'rb'))
    name = sys.argv[1]; tag = sys.argv[3] if len(sys.argv) > 3 else 'x'
    idxs = [int(x) for x in sys.argv[2].split(',')] if sys.argv[2] != 'gif' else None
    os.makedirs('prev', exist_ok=True)
    if idxs is None:
        ims = [Image.fromarray(render(f, scale=0.4, W=640, H=360, ox=315, oy=345)) for f in frames[name][::2]]
        ims[0].save(f'prev/{name}_{tag}.gif', save_all=True, append_images=ims[1:], duration=66, loop=0)
        print(f'prev/{name}_{tag}.gif'); sys.exit()
    ims = [render(frames[name][i]) for i in idxs]
    cols = 3; h, w = ims[0].shape[:2]; rows = (len(ims) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, im in enumerate(ims):
        cv2.putText(im, f'{name} f{idxs[k]} t={frames[name][idxs[k]]["t"]:.2f}', (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        sheet[(k // cols) * h:(k // cols + 1) * h, (k % cols) * w:(k % cols + 1) * w] = im
    fn = f'prev/{name}_{tag}.jpg'; Image.fromarray(sheet).save(fn, quality=85); print(fn)
