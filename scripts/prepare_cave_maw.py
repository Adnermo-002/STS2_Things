"""Separate the Sunburst painting into a grounded rim, cavity and mobile details."""
from pathlib import Path
import json, shutil
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image, ImageDraw, ImageOps

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'source_assets/monsters/cave_maw'
PARTS=ROOT/'tools/CaveMawRig/parts'
PARTS.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'output/imagegen/cave_maw_v1.png',SRC/'character_generated.png')
image=Image.open(SRC/'character_generated.png').convert('RGBA').resize((1792,896),Image.Resampling.LANCZOS)
p=np.array(image);p[p[...,3]<10]=0
image=Image.fromarray(p);image.save(SRC/'character_final.png')
h,w=p.shape[:2];r,g,b=[p[...,i].astype(float) for i in range(3)]
opaque=p[...,3]>20


def region(box):
    a=np.zeros((h,w),np.uint8)
    x0,y0,x1,y1=box;a[y0:y1,x0:x1]=255
    return a>0


def solid(mask,expand=0):
    contours,_=cv2.findContours(mask.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    out=np.zeros((h,w),np.uint8)
    if not contours:raise ValueError('Empty painted part')
    cv2.drawContours(out,[max(contours,key=cv2.contourArea)],-1,255,cv2.FILLED)
    if expand:out=cv2.dilate(out,np.ones((expand*2+1,expand*2+1),np.uint8))
    return out


masks={}
masks['tongue']=solid((r>g*1.25)&(r>b*1.25)&(r>85)&opaque&region((425,388,1290,657)),1)
teeth_boxes={
    'tooth_back_0':(766,345,832,412),'tooth_back_1':(848,355,937,446),
    'tooth_back_2':(958,381,1060,478),'tooth_front_0':(311,486,417,602),
    'tooth_front_1':(468,523,586,637),
}
for name,box in teeth_boxes.items():
    masks[name]=solid((r>g*1.015)&(g>b*1.11)&(r>132)&opaque&region(box),1)
for name,points in {
    'tooth_front_0':[(350,497),(381,497),(403,558),(409,595),(347,591),(313,565)],
    'tooth_front_1':[(523,534),(556,540),(578,597),(581,632),(518,631),(471,609),(489,565)],
}.items():
    clip=Image.new('L',(w,h));ImageDraw.Draw(clip).polygon(points,fill=255)
    masks[name]=np.minimum(masks[name],np.array(clip))
for name,box in {'eye_far':(974,250,1088,330),'eye_near':(1165,298,1261,367)}.items():
    seed=(r>g*1.06)&(g>b*1.30)&(r>100)&opaque&region(box)
    masks[name]=solid(seed,2)

blue=(b>r*1.08)&(b>g*1.035)&(r<125)&opaque&region((290,320,1370,675))
cavity=blue.copy()
for name,mask in masks.items():
    if not name.startswith('eye_'):cavity|=mask>0
cavity=solid(cv2.morphologyEx(cavity.astype('uint8'),cv2.MORPH_CLOSE,np.ones((7,7),np.uint8)))
rim_mask=255-cavity
for name,mask in masks.items():
    if name.startswith('eye_') or name.startswith('tooth_'):rim_mask[mask>0]=0
rim=p.copy();rim[...,3]=np.minimum(rim[...,3],rim_mask)

# A short painted gum overlap covers the roots when the rigid teeth rotate.
# Sampling neighbouring lip paint avoids retaining the old cream cutout strips.
for name,root_y,sample in [('tooth_front_0',586,(425,600)),
                          ('tooth_front_1',624,(606,643))]:
    root=(masks[name]>0)&(np.indices((h,w))[0]>=root_y)&opaque
    sx,sy=sample
    color=np.median(p[sy-4:sy+5,sx-4:sx+5,:3],axis=(0,1))
    rim[root,:3]=np.uint8(color);rim[root,3]=p[root,3]

# Filled, featureless sockets never duplicate the original pupil while blinking.
for name in ('eye_far','eye_near'):
    eye=masks[name]>0
    ring=(cv2.dilate(masks[name],np.ones((23,23),np.uint8))>0)&~eye&opaque
    ring&=(r<g*1.20)&(b>g*.76)&(r>55)
    color=np.median(p[ring,:3],axis=0)
    rim[eye,:3]=np.uint8(color);rim[eye,3]=p[eye,3]

# Paint clean cavity behind the tongue/teeth from only the dark source paint.
_,idx=distance_transform_edt(~blue,return_indices=True)
inside=p.copy()
yy,xx=np.mgrid[0:h,0:w]
radial=np.clip(((xx-895)/600)**2+((yy-550)/230)**2,0,1)
shade=np.array([25,30,45])[None,None,:]+radial[...,None]*np.array([10,11,14])
paint=cv2.GaussianBlur(p[...,:3][idx[0],idx[1]],(61,61),0)
inside[...,:3]=np.uint8(np.clip(shade*.85+paint*.15,0,255))
inside[...,3]=np.minimum(p[...,3],cv2.dilate(cavity,np.ones((61,61),np.uint8)))

layers={'cavity':Image.fromarray(inside),'rim':Image.fromarray(rim)}
for name,mask in masks.items():
    part=p.copy();part[...,3]=np.minimum(part[...,3],mask);layers[name]=Image.fromarray(part)
meta={}
for name,im in layers.items():
    box=im.getbbox()
    im.crop(box).save(PARTS/f'{name}.png')
    meta[name]=dict(x=box[0],y=box[1],w=box[2]-box[0],h=box[3]-box[1])
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
review=Image.new('RGBA',image.size,'#303b40');review.alpha_composite(image)
review.convert('RGB').save(SRC/'character_review.jpg',quality=94)
sheet=Image.new('RGB',(720,((len(layers)+2)//3)*190),'#303b40')
draw=ImageDraw.Draw(sheet)
for i,(name,im) in enumerate(layers.items()):
    tile=ImageOps.contain(im.crop(im.getbbox()),(225,155))
    pos=((i%3)*240+8,(i//3)*190+24)
    sheet.paste(tile,pos,tile);draw.text(((i%3)*240+8,(i//3)*190+5),name,fill='white')
sheet.save(SRC/'parts_review.jpg',quality=92)

shutil.copy2(ROOT/'output/imagegen/cave_maw_appetite_v1.png',SRC/'power_generated.png')
icon=Image.open(SRC/'power_generated.png').convert('RGBA')
icon=ImageOps.contain(icon.crop(icon.getbbox()),(226,226),Image.Resampling.LANCZOS)
big=Image.new('RGBA',(256,256));big.alpha_composite(icon,((256-icon.width)//2,(256-icon.height)//2))
key='cave_maw_appetite_power'
big.save(ROOT/f'images/powers/{key}.png')
big.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/f'images/powers/{key}_packed.png')
(ROOT/f'images/atlases/power_atlas.sprites/{key}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/{key}_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')
print('Prepared cave maw:',len(layers),'painted layers, retained original alpha.')
