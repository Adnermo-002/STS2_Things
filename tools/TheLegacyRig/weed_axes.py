import json,numpy as np
from PIL import Image
meta=json.load(open('parts/meta.json'))
bt=np.load('body_true.npy'); ys,xs=np.nonzero(bt); C=np.array([xs.mean(),ys.mean()])
out={}
for n in meta:
    if not (n.startswith('weed') or n.startswith('coral')): continue
    im=np.array(Image.open(f'parts/{n}.png'))[...,3]; mm=meta[n]
    yy,xx=np.nonzero(im>128); P=np.stack([xx+mm['x'],yy+mm['y']],1).astype(float)
    # base: lowest 8% points' mean for upright, else nearest to body centre
    ext_h=P[:,1].max()-P[:,1].min(); ext_w=P[:,0].max()-P[:,0].min()
    if n.startswith('coral'):
        base=np.array([P[:,0].mean(),P[:,1].max()-8]); tip=np.array([P[:,0].mean(),P[:,1].min()])
    else:
        low=P[P[:,1]>np.percentile(P[:,1],94)]
        base=low.mean(0)
        d=np.hypot(*(P-base).T); tip=P[np.argsort(d)[-max(1,len(d)//200):]].mean(0)
    out[n]=dict(base=[round(float(base[0]),1),round(float(base[1]),1)],tip=[round(float(tip[0]),1),round(float(tip[1]),1)],w=float(ext_w),h=float(ext_h))
    print(n,out[n])
json.dump(out,open('weed_axes.json','w'),indent=1)
