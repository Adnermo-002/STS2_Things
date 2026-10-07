import numpy as np, cv2, json
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.segmentation import watershed
im=np.array(Image.open('src.png').convert('RGBA'))
rgb=im[...,:3]; a=im[...,3]
H,W=a.shape
hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
h=hsv[...,0].astype(int)*2; s=hsv[...,1].astype(int); v=hsv[...,2].astype(int)
m=a>8
green=(h>=45)&(h<=110)&m&(s>50)
cyan=(h>170)&(h<=205)&m&(s>40)
blue=(h>205)&(h<=235)&m&(s>40)
purple=(h>235)&(h<=300)&m&(s>30)
pink=((h>300)|(h<20))&m&(s>40)
strongbody=(cyan|blue|purple)&(v>80)
bodyish=(cyan|blue|purple)&(v>35)&(s>35)

# ---- seaweed sprigs
g=cv2.morphologyEx(green.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
n,lab,st,cen=cv2.connectedComponentsWithStats(g,8)
SPRIGS={ # name: list of component ids
 'weed_top_left':[1],'weed_left':[22,97],'weed_bottom_mid':[209],'weed_bottom_right':[214,265,295],
 'weed_right':[12],'weed_ground_left':[264,248],'weed_back_a':[7],'weed_back_b':[3],'weed_back_c':[2],'weed_back_d':[14,32,63,85],
 'weed_blue':[120],'weed_ground_right':[282],'weed_edge_right':[244],'weed_ground_bl':[328,355],
}
cand=(~strongbody)&m&(~pink)
# ---- corals
def grow(core,it=4,c=None):
    c=cand|core if c is None else c
    gm=core.copy()
    for _ in range(it): gm=(cv2.dilate(gm.astype(np.uint8),np.ones((3,3),np.uint8))>0)&c | gm
    return gm
box=np.zeros((H,W),bool); box[330:520,160:400]=True
coralp=pink&box
coralp=cv2.morphologyEx(coralp.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))>0
coralp=grow(coralp&box, 3, (cand|pink)&box)
box2=np.zeros((H,W),bool); box2[455:689,740:1000]=True
cpu=purple&box2&(h<285)
cpu=grow(cpu,3,(cand|purple)&box2)
# purple coral vs bulb purple? fine

corals=coralp|cpu
bt=(strongbody|((pink)&(v>60)))&~corals
bt=cv2.morphologyEx(bt.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
bt=cv2.morphologyEx(bt,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(13,13)))>0
body_true=ndi.binary_fill_holes(bt)&m
np.save('body_true.npy',body_true)
outside=m&~body_true&~corals
sprig_masks={}
taken=corals.copy()
# geodesic growth: outside-body pixels freely, inside-body only candidate px near core
ker=np.ones((3,3),np.uint8)
cores={name:np.isin(lab,ids) for name,ids in SPRIGS.items()}
grown={k:v.copy() for k,v in cores.items()}
for it in range(14):
    for k in grown:
        d=cv2.dilate(grown[k].astype(np.uint8),ker)>0
        allow=(outside&~bodyish&(it<14)) | (cand&~bodyish&(it<7))
        grown[k]|=d&allow
urchin=disc(296,655,30) if False else None
yy,xx=np.ogrid[:H,:W]
urch=((xx-296)**2+(yy-656)**2<29**2)
for k in grown:
    g2=grown[k]&~taken&~urch
    sprig_masks[k]=g2; taken|=g2


np.save('masks_front.npy',{'sprigs':sprig_masks,'coral_pink':coralp,'coral_purple':cpu},allow_pickle=True)

# ---- body watershed
body=m&~taken
markers=np.zeros((H,W),np.int32)
PARTS=['purple_top','purple_mass','purple_lr','blue_main','blue_down','blue_bottom','atrium','mid_lobe','bottom_lobe','bulb','right_lobe']
def rect(x0,y0,x1,y1):
    r=np.zeros((H,W),bool); r[y0:y1,x0:x1]=True; return r
def disc(cx,cy,rr):
    yy,xx=np.ogrid[:H,:W]; return (xx-cx)**2+(yy-cy)**2<rr*rr
seeds={
 'purple_top':(purple,[rect(640,60,690,110),rect(700,25,760,80),rect(760,120,800,180)]),
 'purple_mass':(purple,[rect(830,140,1000,230),rect(700,215,800,245),rect(1000,250,1080,300)]),
 'purple_lr':(purple,[rect(1260,390,1330,440),rect(1170,560,1270,600),rect(1100,470,1150,520)]),
 'blue_main':(blue,[rect(920,340,1080,380),rect(1190,290,1240,340),rect(1110,360,1160,390)]),
 'blue_down':(blue,[rect(1180,440,1280,480)]),
 'blue_bottom':(blue,[rect(1010,520,1070,560),rect(1000,470,1040,500)]),
 'atrium':(cyan,[rect(180,240,330,285),rect(140,350,300,385),rect(380,190,600,240)]),
 'mid_lobe':(cyan,[rect(100,440,160,510),rect(420,420,600,470)]),
 'bottom_lobe':(cyan,[rect(180,570,400,640),rect(450,590,640,640)]),
 'bulb':(cyan|pink,[disc(770,360,80)]),
 'right_lobe':(cyan,[disc(945,470,35),rect(900,540,980,600)]),
}
for i,p in enumerate(PARTS,1):
    cls,regs=seeds[p]
    for r in regs: markers[r&cls&body]=i
lum=cv2.GaussianBlur(v.astype(np.float32),(0,0),2.0)
elev=255-lum
# hue boundary term
hue_cls=np.zeros((H,W),np.uint8); hue_cls[cyan]=1; hue_cls[blue]=2; hue_cls[purple]=3
edge=np.zeros((H,W),np.float32)
for k in (1,2,3):
    mk=(hue_cls==k).astype(np.float32); mk=cv2.GaussianBlur(mk,(0,0),1.5)
    edge+=np.hypot(cv2.Sobel(mk,cv2.CV_32F,1,0),cv2.Sobel(mk,cv2.CV_32F,0,1))
elev=elev+edge*120
labels=watershed(elev,markers,mask=body)
np.save('labels_body.npy',labels)
json.dump(PARTS,open('parts_body.json','w'))
# visual
pal=np.random.default_rng(3).integers(40,255,(40,3))
vis=rgb.copy().astype(float)*0.35
for i in range(1,len(PARTS)+1): vis[labels==i]=vis[labels==i]+pal[i]*0.65
for j,(nme,mk) in enumerate(sprig_masks.items()): vis[mk]=[0,255,0] if j%2==0 else [180,255,80]
vis[coralp]=[255,80,160]; vis[cpu]=[200,120,255]
out=Image.fromarray(np.clip(vis,0,255).astype(np.uint8)); d=ImageDraw.Draw(out)
for i,p in enumerate(PARTS,1):
    ys,xs=np.nonzero(labels==i)
    if len(xs): d.text((int(xs.mean()),int(ys.mean())),p,fill='white')
out.save('vis_seg.jpg',quality=90)
