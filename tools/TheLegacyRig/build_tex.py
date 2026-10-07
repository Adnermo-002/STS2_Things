import numpy as np, cv2, json, os
from PIL import Image
im=np.array(Image.open('src.png').convert('RGBA')).astype(np.float32)
H,W=im.shape[:2]; rgb=im[...,:3]; a=im[...,3]
L=np.load('layers_body.npy',allow_pickle=True).item()
Fm=np.load('front_masks.npy',allow_pickle=True).item()
O=json.load(open('order.json'))
os.makedirs('parts',exist_ok=True)
hsv=cv2.cvtColor(im[...,:3].astype(np.uint8),cv2.COLOR_RGB2HSV)
h=hsv[...,0].astype(int)*2; s=hsv[...,1].astype(int)
pinkm=((h>300)|(h<20))&(s>40)&(a>0)

def pushpull(col,wt):
    """fill colour where wt==0 using weighted pyramid (push-pull)."""
    levels=[(col*wt[...,None],wt)]
    c,w=levels[0]
    while min(w.shape)>2:
        c=cv2.pyrDown(c); w=cv2.pyrDown(w); levels.append((c,w))
    # reconstruct
    cc,ww=levels[-1]
    est=cc/np.maximum(ww,1e-6)[...,None]
    for c,w in reversed(levels[:-1]):
        up=cv2.resize(est,(w.shape[1],w.shape[0]),interpolation=cv2.INTER_LINEAR)
        here=c/np.maximum(w,1e-6)[...,None]
        k=np.clip(w*4,0,1)[...,None]
        est=here*k+up*(1-k)
    return est
meta={}
def save(name,rgbimg,alpha,bbox_mask):
    ys,xs=np.nonzero(bbox_mask)
    x0,x1,y0,y1=xs.min(),xs.max()+1,ys.min(),ys.max()+1
    out=np.dstack([rgbimg,alpha])[y0:y1,x0:x1]
    Image.fromarray(np.clip(out,0,255).astype(np.uint8)).save(f'parts/{name}.png')
    meta[name]=dict(x=int(x0),y=int(y0),w=int(x1-x0),h=int(y1-y0))
    return x0,y0,x1,y1

for p in O['order']:
    vis=L[p]['vis']; full=L[p]['full']
    # sources: visible px, minus 2px band touching non-part (contaminated antialias)
    other=~vis
    band=cv2.dilate(other.astype(np.uint8),np.ones((5,5),np.uint8))>0
    src=vis&~(band&~(cv2.dilate((a==0).astype(np.uint8),np.ones((5,5),np.uint8))>0))
    src&=a>250
    fill=pushpull(rgb,src.astype(np.float32))
    fill=cv2.GaussianBlur(fill,(0,0),1.2)
    col=np.where(vis[...,None],rgb,fill)
    alpha=np.where(full,a,0).astype(np.float32)
    # hidden fill should be fully opaque where original was opaque
    alpha=np.where(full&~vis,np.maximum(alpha,0),alpha)
    # soften hard mask edge of extension (inside silhouette) 1px
    soft=cv2.GaussianBlur(full.astype(np.float32),(0,0),0.7)*255
    alpha=np.where(vis,alpha,np.minimum(alpha,soft))
    bt=np.load('body_true.npy')
    alpha=np.where(full&~vis&~bt&(a<250),0,alpha)
    save(p,col,alpha,full)
    # vein glow for cyan layers
    if p in ('atrium','bulb'):
        vm=(pinkm&vis).astype(np.float32)
        if vm.sum()>200:
            g1=cv2.GaussianBlur(vm,(0,0),1.0); g2=cv2.GaussianBlur(vm,(0,0),5.0)
            ga=np.clip(g1*1.3+g2*1.6,0,1)*255
            gcol=np.zeros_like(rgb); gcol[...]=(255,70,110)
            ga=np.where(full,ga,0)
            save(p+'_glow',gcol,ga,full)
for k,mk in Fm.items():
    alpha=np.where(mk,a,0).astype(np.float32)
    if mk.sum()<50: continue
    save(k,rgb,alpha,mk)
json.dump(meta,open('parts/meta.json','w'),indent=1)
print(len(meta), sum(v['w']*v['h'] for v in meta.values()))
