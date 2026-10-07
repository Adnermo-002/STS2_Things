import json, math, numpy as np, cv2, pickle, sys
from PIL import Image
from fk import Skel
rig=json.load(open('out/rig_static.json')); sk=Skel(rig)
meta=json.load(open('parts/meta.json'))
from rigdef import GLOW_OF, S
tex={}
for n in meta:
    im=np.array(Image.open(f'parts/{n}.png').convert('RGBA')).astype(np.float32)/255
    tex[n]=im
bindS={}
for src,m in rig['mesh'].items():
    world=np.array(m['world']); 
    binds=[]
    for p,wl in zip(world,m['wts']):
        sp=np.array(S(p)); binds.append([(b,sp-np.array(S(rig_b)),w) for b,w in wl for rig_b in [next(bb['pos'] for bb in rig['bones'] if bb['name']==b)]])
    bindS[src]=binds
def render(frame,scale=0.62,W=1000,H=540,ox=500,oy=500,bg=(38,40,52)):
    Wm=sk.world(frame['pose'])
    canvas=np.zeros((H,W,3),np.float32); canvas[...]=np.array(bg)/255
    for sl in rig['slots']:
        n=sl['name']; src=GLOW_OF.get(n,n); m=rig['mesh'][src]
        alpha_mul=1.0; col=np.array([1,1,1],np.float32)
        if n in GLOW_OF: alpha_mul=0.72*frame['glow'].get(n,0)
        else: col=np.array(frame['tint'],np.float32)
        if alpha_mul<0.01: continue
        pts=[]
        for bl in bindS[src]:
            v=np.zeros(2)
            for b,loc,w in bl: v+=w*(Wm[b]@np.array([loc[0],loc[1],1]))[:2]
            pts.append(v)
        pts=np.array(pts)
        scr=np.stack([ox+pts[:,0]*scale, oy-pts[:,1]*scale],1)
        t=tex[n]; th,tw=t.shape[:2]
        uv=np.array(m['uvs'])*np.array([tw,th])
        tris=np.array(m['tris']).reshape(-1,3)
        add=n in GLOW_OF
        for tri in tris:
            d=scr[tri].astype(np.float32); s=uv[tri].astype(np.float32)
            x0,y0=np.floor(d.min(0)).astype(int); x1,y1=np.ceil(d.max(0)).astype(int)+1
            x0=max(x0,0);y0=max(y0,0);x1=min(x1,W);y1=min(y1,H)
            if x1<=x0 or y1<=y0: continue
            Mt=cv2.getAffineTransform(s,d-np.array([x0,y0],np.float32))
            patch=cv2.warpAffine(t,Mt,(x1-x0,y1-y0),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            mask=np.zeros((y1-y0,x1-x0),np.float32)
            cv2.fillConvexPoly(mask,np.round((d-np.array([x0,y0]))*4).astype(np.int32),1.0,lineType=cv2.LINE_AA,shift=2)
            a=patch[...,3]*mask*alpha_mul
            reg=canvas[y0:y1,x0:x1]
            if add: reg+= patch[...,:3]*a[...,None]
            else: reg[...]=reg*(1-a[...,None])+patch[...,:3]*col*a[...,None]
    return (np.clip(canvas,0,1)*255).astype(np.uint8)
if __name__=='__main__':
    frames=pickle.load(open('out/frames.pkl','rb'))
    name=sys.argv[1]; idxs=[int(x) for x in sys.argv[2].split(',')]
    ims=[render(frames[name][i]) for i in idxs]
    cols=int(sys.argv[3]) if len(sys.argv)>3 else 2
    h,w=ims[0].shape[:2]; rows=(len(ims)+cols-1)//cols
    sheet=np.zeros((rows*h,cols*w,3),np.uint8)
    for k,im in enumerate(ims):
        cv2.putText(im,f'{name} f{idxs[k]} t={frames[name][idxs[k]]["t"]:.2f}',(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(255,255,255),2)
        sheet[(k//cols)*h:(k//cols+1)*h,(k%cols)*w:(k%cols+1)*w]=im
    import time; fn=f'prev/{name}_{int(time.time())%100000}.jpg'; Image.fromarray(sheet).save(fn,quality=85); print(fn)
