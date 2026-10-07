import json, math, numpy as np
from PIL import Image
from rigdef import *
meta=json.load(open('parts/meta.json'))
order=json.load(open('order.json'))
axes=json.load(open('weed_axes.json'))

# ---------------- bones
bones=[dict(name=n,parent=p,pos=pos) for n,p,pos in BONES]
chains={}
front=[n for n in meta if n.startswith('coral')]+[n for n in order['front'] if n.startswith('weed') and n in meta]
for n in front:
    base,tip=CHAIN_OVERRIDE.get(n,(tuple(axes[n]['base']),tuple(axes[n]['tip'])))
    L=math.dist(base,tip)
    nb=3 if L>150 else 2
    names=[]
    for i in range(nb):
        t=i/nb
        pos=(base[0]+(tip[0]-base[0])*t, base[1]+(tip[1]-base[1])*t)
        bn=f'{n}_{i}'
        bones.append(dict(name=bn,parent=(CHAIN_PARENT[n] if i==0 else names[-1]),pos=pos))
        names.append(bn)
    chains[n]=dict(base=base,tip=tip,bones=names,len=L)
bidx={b['name']:i for i,b in enumerate(bones)}
bpos={b['name']:b['pos'] for b in bones}

# ---------------- atlas packing
GLOW_SCALE=0.5
imgs={}
for n in meta:
    im=Image.open(f'parts/{n}.png').convert('RGBA')
    if n in GLOW_OF: im=im.resize((max(1,round(im.width*GLOW_SCALE)),max(1,round(im.height*GLOW_SCALE))),Image.LANCZOS)
    imgs[n]=im
PAD=2
def pack(PW,PH):
    rects={}; x=y=shelf=0
    for n in sorted(imgs,key=lambda k:-imgs[k].height):
        w,h=imgs[n].width+2*PAD,imgs[n].height+2*PAD
        if x+w>PW: x=0; y+=shelf; shelf=0
        if y+h>PH: return None
        rects[n]=(x+PAD,y+PAD); x+=w; shelf=max(shelf,h)
    return rects
for PW,PH in [(2048,1024),(2048,1536),(2048,2048)]:
    rects=pack(PW,PH)
    if rects: break
page=Image.new('RGBA',(PW,PH),(0,0,0,0))
for n,(x,y) in rects.items():
    im=imgs[n]
    # bleed: extrude edge pixels into padding, rgb only (alpha 0) to avoid dark fringes
    arr=np.array(im); rgb=arr[...,:3].astype(np.float32); a=arr[...,3:].astype(np.float32)/255
    page.paste(im,(x,y))
# colour-bleed transparent texels so bilinear filtering never pulls black
import cv2
P=np.array(page).astype(np.float32); A=P[...,3]
known=A>0
col=P[...,:3].copy()
for _ in range(6):
    k=cv2.dilate(known.astype(np.uint8),np.ones((3,3),np.uint8))>0
    s=cv2.blur(col*known[...,None],(3,3)); c=cv2.blur(known.astype(np.float32),(3,3))
    new=k&~known
    col[new]=s[new]/np.maximum(c[new,None],1e-6)
    known=k
P[...,:3]=col
page=Image.fromarray(np.clip(P,0,255).astype(np.uint8))
page.save('out/the_legacy.png',optimize=True)
atlas=[f'the_legacy.png',f'size: {PW},{PH}','format: RGBA8888','filter: Linear,Linear','repeat: none']
for n,(x,y) in rects.items():
    w,h=imgs[n].size
    atlas+= [n,'  rotate: false',f'  xy: {x}, {y}',f'  size: {w}, {h}',f'  orig: {w}, {h}','  offset: 0, 0','  index: -1']
open('out/the_legacy.atlas','w',newline='\n').write('\n'.join(atlas)+'\n')

# ---------------- meshes
def seg_dist(p,a,b):
    a=np.array(a,float); b=np.array(b,float); ab=b-a
    t=np.clip(((p-a)@ab)/max(ab@ab,1e-6),0,1)
    q=a+t[:,None]*ab
    return np.hypot(*(p-q).T), t
def grid_mesh(n,spacing):
    im=np.array(Image.open(f'parts/{n}.png'))[...,3]
    h,w=im.shape
    xs=list(np.arange(0,w,spacing))+[w]; ys=list(np.arange(0,h,spacing))+[h]
    xs=sorted(set(int(v) for v in xs)); ys=sorted(set(int(v) for v in ys))
    occ=cv2.dilate((im>0).astype(np.uint8),np.ones((3,3),np.uint8))
    vid={}; verts=[]; tris=[]
    def V(i,j):
        if (i,j) not in vid: vid[(i,j)]=len(verts); verts.append((xs[i],ys[j]))
        return vid[(i,j)]
    for j in range(len(ys)-1):
        for i in range(len(xs)-1):
            if occ[ys[j]:ys[j+1],xs[i]:xs[i+1]].any():
                a,b,c,d=V(i,j),V(i+1,j),V(i+1,j+1),V(i,j+1)
                tris+=[a,b,c,a,c,d]
    verts=np.array(verts,float)
    uvs=np.stack([verts[:,0]/w,verts[:,1]/h],1)
    world=verts+np.array([meta[n]['x'],meta[n]['y']])
    return world,uvs,tris
def weights_body(n,world):
    segs=BODY_SKIN[n]
    D=np.stack([seg_dist(world,a,b)[0] for _,a,b in segs],1)
    sig=55.0
    W=np.exp(-(D/sig)**2)+1e-9
    # nearest segment always dominant
    W[np.arange(len(world)),D.argmin(1)]+=0.35
    W/=W.sum(1,keepdims=True)
    return [[(segs[k][0],W[i,k]) for k in range(len(segs)) if W[i,k]>0.02] for i in range(len(world))]
def weights_chain(n,world):
    c=chains[n]; nb=len(c['bones'])
    _,t=seg_dist(world,c['base'],c['tip'])
    res=[]
    for i in range(len(world)):
        tt=t[i]*nb-0.5
        ws=[]
        for k in range(nb):
            ws.append(max(0.0,1-abs(tt-k)))
        if tt<=0: ws=[1]+[0]*(nb-1)
        if tt>=nb-1: ws=[0]*(nb-1)+[1]
        s=sum(ws); res.append([(c['bones'][k],ws[k]/s) for k in range(nb) if ws[k]/s>0.02])
    return res
def spine_vertices(world,wts):
    out=[]
    for p,wl in zip(world,wts):
        s=sum(w for _,w in wl); out.append(len(wl))
        sp=S(p)
        for b,w in wl:
            bp=S(bpos[b])
            out+= [bidx[b], round(sp[0]-bp[0],2), round(sp[1]-bp[1],2), round(w/s,4)]
    return out
attachments={}; slots=[]
mesh_cache={}
slot_order=order['order']
slot_list=[]
for n in slot_order:
    slot_list.append(n)
    for g,base in GLOW_OF.items():
        if base==n and g in meta: slot_list.append(g)
slot_list+= [n for n in front]
for n in slot_list:
    src=GLOW_OF.get(n,n)
    if src not in mesh_cache:
        world,uvs,tris=grid_mesh(src,26 if src in BODY_SKIN else 16)
        wts=weights_body(src,world) if src in BODY_SKIN else weights_chain(src,world)
        mesh_cache[src]=(world,uvs,tris,wts)
    world,uvs,tris,wts=mesh_cache[src]
    attachments[n]={n:{'type':'mesh','uvs':[round(float(v),5) for v in uvs.flatten()],
        'triangles':tris,'vertices':spine_vertices(world,wts),'hull':0,
        'width':meta[n]['w'],'height':meta[n]['h']}}
    # slot bone: dominant bone
    bone=BODY_SKIN[src][0][0] if src in BODY_SKIN else chains[src]['bones'][0]
    sl={'name':n,'bone':bone,'attachment':n}
    if n in GLOW_OF: sl['blend']='additive'; sl['color']='ffffff00'
    slots.append(sl)
json.dump(dict(bones=bones,chains=chains,slots=slots,attachments=attachments,page=[PW,PH],
               mesh={k:dict(world=v[0].tolist(),uvs=v[1].tolist(),tris=v[2],wts=v[3]) for k,v in mesh_cache.items()}),
          open('out/rig_static.json','w'))
print('page',PW,PH,'bones',len(bones),'slots',len(slots),'verts',sum(len(v[0]) for v in mesh_cache.values()),'tris',sum(len(v[2])//3 for v in mesh_cache.values()))
