import json,numpy as np
from PIL import Image
meta=json.load(open('parts/meta.json')); O=json.load(open('order.json'))
names=O['order']+[n for n in ['coral_purple','coral_pink'] if n in meta]+[n for n in O['front'] if n.startswith('weed') and n in meta]
src=Image.open('src.png').convert('RGBA'); c=Image.new('RGBA',src.size,(0,0,0,0))
for n in names:
    p=Image.open(f'parts/{n}.png'); c.alpha_composite(p,(meta[n]['x'],meta[n]['y']))
a=np.array(c).astype(float); b=np.array(src).astype(float)
def over(x): return x[...,:3]*x[...,3:]/255
d=np.abs(over(a)-over(b)); print('mean abs diff',d.mean(),'max',d.max(),'px>20:',(d.max(-1)>20).sum())
bg=Image.new('RGBA',src.size,(40,40,48,255)); bg.alpha_composite(c); bg.convert('RGB').save('recomp.jpg',quality=90)
Image.fromarray(np.clip(d.max(-1)*3,0,255).astype('uint8')).save('recomp_diff.png')
print(names)
