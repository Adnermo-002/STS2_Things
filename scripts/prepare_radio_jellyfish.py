"""Clean the generated alpha and layer the six separated ribbons for Spine."""
from pathlib import Path
import json,shutil
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image,ImageDraw,ImageOps

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'source_assets/monsters/radio_jellyfish'
PARTS=ROOT/'tools/RadioJellyfishRig/parts'
PARTS.mkdir(parents=True,exist_ok=True)


def clean(path,largest=False):
    p=np.array(Image.open(path).convert('RGBA'))
    p[...,3]=np.uint8(np.clip((p[...,3].astype(float)-195)/60,0,1)*255)
    fringe=(p[...,:3].max(axis=2)-p[...,:3].min(axis=2)>180)&(p[...,:3].max(axis=2)>235)
    p[fringe,3]=0
    if largest:
        n,labels,stats,_=cv2.connectedComponentsWithStats((p[...,3]>0).astype('uint8'))
        if n>1:p[labels!=(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])),3]=0
    p[p[...,3]==0,:3]=0
    return Image.fromarray(p)


shutil.copy2(ROOT/'output/imagegen/radio_jellyfish_v1.png',SRC/'character_generated.png')
art=clean(SRC/'character_generated.png',True).resize((1152,1382),Image.Resampling.LANCZOS)
canvas=Image.new('RGBA',(1152,1408));canvas.alpha_composite(art,(0,13))
canvas.save(SRC/'character_final.png')
p=np.asarray(canvas).copy();h,w=p.shape[:2];yy,xx=np.mgrid[0:h,0:w]
opaque=p[...,3]>10
masks={}


def polygon(points):
    mask=Image.new('L',(w,h));ImageDraw.Draw(mask).polygon(points,fill=255)
    return np.asarray(mask)


# The roots overlap the bell by several pixels and are hidden by its skirt.
lower=(opaque&(yy>=800)).astype('uint8')
n,labels,stats,_=cv2.connectedComponentsWithStats(lower)
valid=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>1500]
valid.sort(key=lambda i:stats[i,cv2.CC_STAT_LEFT])
if len(valid)!=6:raise ValueError(f'Expected six separate painted ribbons, got {len(valid)}')
labels[~np.isin(labels,valid)]=0
_,near=distance_transform_edt(labels==0,return_indices=True)
assigned=labels[near[0],near[1]]
for index,label in enumerate(valid):
    masks[f'tentacle_{index}']=np.uint8((assigned==label)&(yy>=712)&opaque)*255

masks['antenna_left']=polygon([(195,15),(366,15),(434,130),(459,233),(483,279),(448,316),
    (402,330),(335,324),(338,287),(376,250),(374,181),(331,150),(245,157),(204,122)])
masks['antenna_right']=polygon([(817,364),(846,291),(868,205),(924,169),(997,170),
    (1070,198),(1120,263),(1098,326),(1024,335),(969,285),(946,246),(924,288),(932,382)])

for name,box in {
    'channel_0':(234,365,402,551),'channel_1':(539,378,755,576),
    'eye_0':(311,551,391,611),'eye_1':(505,568,600,628),
}.items():
    mask=Image.new('L',(w,h));ImageDraw.Draw(mask).ellipse(box,fill=255)
    masks[name]=np.asarray(mask)

for name in ('eye_0','eye_1'):
    seed=(masks[name]>0)&(p[...,:3].max(axis=2)<98)&opaque
    contours,_=cv2.findContours(seed.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    iris=np.zeros((h,w),np.uint8)
    cv2.drawContours(iris,[max(contours,key=cv2.contourArea)],-1,255,cv2.FILLED)
    masks[name]=cv2.dilate(iris,np.ones((3,3),np.uint8))

bell=p.copy();bell[yy>=785,3]=0
for name in ['antenna_left','antenna_right','channel_0','channel_1','eye_0','eye_1']:
    bell[masks[name]>0,3]=0
known=bell[...,3]>10
_,near=distance_transform_edt(~known,return_indices=True)
paint=cv2.GaussianBlur(p[...,:3][near[0],near[1]],(43,43),0)
fill=(cv2.dilate(known.astype('uint8'),np.ones((41,41),np.uint8))>0)&~known&opaque&(yy<785)
for name in ('channel_0','channel_1','eye_0','eye_1'):
    fill|=(masks[name]>0)&opaque
bell[fill,:3]=paint[fill];bell[fill,3]=p[fill,3]
# Replace the eye and its painted rim with continuous surrounding skin. A flat
# median-colour patch becomes visible as a hard cap when the eyelid closes.
eye_repair=cv2.dilate(np.maximum(masks['eye_0'],masks['eye_1']),np.ones((13,13),np.uint8))
skin=cv2.inpaint(p[...,:3],eye_repair,5,cv2.INPAINT_TELEA)
bell[eye_repair>0,:3]=skin[eye_repair>0]
n,labels,stats,_=cv2.connectedComponentsWithStats((bell[...,3]>0).astype('uint8'))
bell[labels!=(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])),3]=0
layers={'bell':Image.fromarray(bell)}
for name,mask in masks.items():
    q=p.copy();q[...,3]=np.minimum(q[...,3],mask);layers[name]=Image.fromarray(q)

meta={}
for name,im in layers.items():
    box=im.getbbox()
    im.crop(box).save(PARTS/f'{name}.png')
    meta[name]=dict(x=box[0],y=box[1],w=box[2]-box[0],h=box[3]-box[1])
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')

# Readable coloured light, cut from the actual two amber chambers.
vfx=ROOT/'images/vfx';vfx.mkdir(parents=True,exist_ok=True)
for index in range(2):
    name=f'channel_{index}';box=layers[name].getbbox()
    q=np.array(layers[name].crop(box));r,g,b=[q[...,i].astype(float) for i in range(3)]
    gold=(r>g*1.08)&(g>b*1.35)&(q[...,3]>0)
    mask=cv2.GaussianBlur(np.uint8(gold)*255,(7,7),0)
    luminance=np.uint8(155+.39*np.mean(q[...,:3],axis=2))
    original=q.copy()
    q[...,:3]=luminance[...,None]
    q[...,3]=np.minimum(q[...,3],mask)
    Image.fromarray(q).save(vfx/f'radio_channel_{index}.png')
    darkness=1-.40*(mask.astype(float)/255)
    original[...,:3]=np.uint8(original[...,:3]*darkness[...,None])
    Image.fromarray(original).save(PARTS/f'{name}.png')

review=Image.new('RGBA',canvas.size,'#303d43');review.alpha_composite(canvas)
review.convert('RGB').save(SRC/'character_review.jpg',quality=94)
sheet=Image.new('RGB',(900,((len(layers)+3)//4)*230),'#303d43');draw=ImageDraw.Draw(sheet)
for i,(name,im) in enumerate(layers.items()):
    crop=ImageOps.contain(im.crop(im.getbbox()),(210,198))
    xy=((i%4)*225+7,(i//4)*230+25)
    sheet.paste(crop,xy,crop);draw.text(((i%4)*225+7,(i//4)*230+6),name,fill='white')
sheet.save(SRC/'parts_review.jpg',quality=92)

shutil.copy2(ROOT/'output/imagegen/radio_reception_power_v1.png',SRC/'power_generated.png')
icon=clean(SRC/'power_generated.png')
icon=ImageOps.contain(icon.crop(icon.getbbox()),(224,224),Image.Resampling.LANCZOS)
big=Image.new('RGBA',(256,256));big.alpha_composite(icon,((256-icon.width)//2,(256-icon.height)//2))
key='radio_reception_power';big.save(ROOT/f'images/powers/{key}.png')
big.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/f'images/powers/{key}_packed.png')
(ROOT/f'images/atlases/power_atlas.sprites/{key}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/{key}_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')
print('Prepared radio jellyfish:',len(layers),'painted layers; six individual tentacles.')
