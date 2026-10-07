import json, sys, numpy as np, cv2
from PIL import Image
def render(dump, pages, scale=0.5, W=420, H=420, ox=210, oy=380, bg=(32, 36, 44)):
    fr_out = []
    for fr in json.load(open(dump)):
        cv = np.zeros((H, W, 3), np.float32); cv[...] = np.array(bg) / 255
        for it in fr['items']:
            tex = pages[it['page']]; th, tw = tex.shape[:2]
            v = np.array(it['v']).reshape(-1, 2); uv = np.array(it['uv']).reshape(-1, 2) * [tw, th]
            scr = np.stack([ox + v[:, 0] * scale, oy - v[:, 1] * scale], 1)
            col = np.array(it['col'], np.float32)
            if col[3] < 0.01: continue
            for tri in np.array(it['tri']).reshape(-1, 3):
                d = scr[tri].astype(np.float32); s = uv[tri].astype(np.float32)
                if abs(np.cross(s[1] - s[0], s[2] - s[0])) < 1e-6: continue
                x0, y0 = np.floor(d.min(0)).astype(int); x1, y1 = np.ceil(d.max(0)).astype(int) + 1
                x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W); y1 = min(y1, H)
                if x1 <= x0 or y1 <= y0: continue
                M = cv2.getAffineTransform(s, d - np.array([x0, y0], np.float32))
                p = cv2.warpAffine(tex, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR)
                m = np.zeros((y1 - y0, x1 - x0), np.float32)
                cv2.fillConvexPoly(m, np.round((d - [x0, y0]) * 4).astype(np.int32), 1.0, lineType=cv2.LINE_AA, shift=2)
                a = p[..., 3] * m * col[3]; reg = cv[y0:y1, x0:x1]
                if it['add']: reg += p[..., :3] * col[:3] * a[..., None]
                else: reg[...] = reg * (1 - a[..., None]) + p[..., :3] * col[:3] * a[..., None]
        fr_out.append((fr['t'], (np.clip(cv, 0, 1) * 255).astype(np.uint8)))
    return fr_out
if __name__ == '__main__':
    dump, out = sys.argv[1], sys.argv[2]; pg = dict(a.split('=') for a in sys.argv[3:])
    pages = {k: np.array(Image.open(v).convert('RGBA')).astype(np.float32) / 255 for k, v in pg.items()}
    frs = render(dump, pages)
    h, w = frs[0][1].shape[:2]; cols = min(6, len(frs)); rows = (len(frs) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, (t, im) in enumerate(frs):
        cv2.putText(im, f't={t:.2f}', (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        sheet[(k // cols) * h:(k // cols + 1) * h, (k % cols) * w:(k % cols + 1) * w] = im
    Image.fromarray(sheet).save(out, quality=88); print(out)
