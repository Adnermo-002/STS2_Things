import json, numpy as np, sys
from PIL import Image
meta = json.load(open('parts/meta.json')); O = json.load(open('order.json'))
src = Image.open('src.png').convert('RGBA'); c = Image.new('RGBA', src.size, (0, 0, 0, 0))
for n in O['order']:
    c.alpha_composite(Image.open(f'parts/{n}.png'), (meta[n]['x'], meta[n]['y']))
A = np.array(c).astype(float); B = np.array(src).astype(float)
def over(x): return x[..., :3] * x[..., 3:] / 255
d = np.abs(over(A) - over(B))
print('mean abs diff', round(d.mean(), 3), 'max', d.max(), 'px>20:', int((d.max(-1) > 20).sum()))
tag = sys.argv[1] if len(sys.argv) > 1 else 'x'
bg = Image.new('RGBA', src.size, (40, 40, 48, 255)); bg.alpha_composite(c); bg.convert('RGB').save(f'v/recomp_{tag}.jpg', quality=88)
Image.fromarray(np.clip(d.max(-1) * 3, 0, 255).astype('uint8')).save(f'v/recomp_diff_{tag}.png')
