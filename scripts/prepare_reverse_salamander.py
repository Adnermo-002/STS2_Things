"""Layer the selected Sunburst character; retain authoring sources and painted overlaps."""
from pathlib import Path
import json,shutil
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image,ImageDraw,ImageOps
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source_assets/monsters/reverse_salamander';RIG=ROOT/'tools/ReverseSalamanderRig';PARTS=RIG/'parts'
PARTS.mkdir(parents=True,exist_ok=True)
def clean(path):
 a=np.array(Image.open(path).convert('RGBA'));a[...,3]=np.uint8(np.clip((a[...,3].astype(float)-220)/33,0,1)*255)
 n,labels,stats,_=cv2.connectedComponentsWithStats((a[...,3]>0).astype('uint8'))
 if n>1:a[labels!=(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])),3]=0
 a[a[...,3]==0,:3]=0
 return Image.fromarray(a)
shutil.copy2(ROOT/'output/imagegen/reverse_salamander_v1.png',SRC/'character_generated.png')
image=clean(SRC/'character_generated.png');image.save(SRC/'character_final.png');p=np.array(image);h,w=p.shape[:2]
polygons={
 'tail':[(898,0),(1536,0),(1536,1000),(1225,921),(1090,854),(1031,776),(972,688),(928,621),(969,604),(1125,557),(1225,489),(1239,419),(1190,360),(1075,329),(956,379),(846,305),(845,60)],
 'leg_front_far':[(193,700),(281,709),(347,772),(323,856),(295,944),(197,989),(37,989),(37,880),(130,862),(146,796),(158,745)],
 'leg_front_near':[(607,648),(680,658),(736,699),(781,758),(815,820),(816,1006),(520,1006),(516,900),(611,869),(592,829),(567,781),(548,728),(550,691),(579,657)],
 'leg_hind_far':[(799,892),(889,884),(937,911),(945,959),(778,960),(769,919)],
 'leg_hind_near':[(1026,690),(1155,678),(1223,728),(1274,835),(1307,994),(1041,1004),(1037,920),(1059,884),(1002,859),(958,813),(967,753),(993,717)],
 'gill_0':[(490,504),(532,456),(536,413),(570,414),(592,444),(578,500),(554,528),(493,552)],
 'gill_1':[(510,542),(571,528),(610,490),(636,496),(651,528),(629,564),(579,585),(511,584)],
 'gill_2':[(507,576),(545,575),(584,589),(624,591),(629,612),(605,643),(548,649),(505,621)],
}
masks={}
for key,polygon in polygons.items():
 im=Image.new('L',image.size);ImageDraw.Draw(im).polygon(polygon,fill=255);masks[key]=np.array(im)
for key,box in [('eye_far',(56,416,164,543)),('eye_near',(219,449,371,599))]:
 im=Image.new('L',image.size);ImageDraw.Draw(im).ellipse(box,fill=255);masks[key]=np.array(im)
legs=[k for k in masks if k.startswith('leg_')]
masks['tail'][np.maximum.reduce([masks[k] for k in legs])>0]=0
used=np.maximum.reduce(list(masks.values()));masks['body']=255-used
meta={};layers={}
for key,mask in masks.items():
 a=p.copy();a[...,3]=np.minimum(a[...,3],mask)
 n,labels,stats,_=cv2.connectedComponentsWithStats((a[...,3]>0).astype('uint8'))
 if n>1:a[labels!=(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])),3]=0
 if key in ['body','tail']:
  known=a[...,3]>0;expanded=cv2.dilate(known.astype('uint8'),np.ones((43,43),np.uint8))>0
  fill=expanded&(~known)&(p[...,3]>0)
  if key=='body':fill|=((masks['eye_far']>0)|(masks['eye_near']>0)|(masks['gill_0']>0)|(masks['gill_1']>0)|(masks['gill_2']>0))&(p[...,3]>0)
  _,indices=distance_transform_edt(~known,return_indices=True)
  col=cv2.GaussianBlur(p[...,:3][indices[0],indices[1]],(7,7),0)
  a[fill,:3]=col[fill];a[fill,3]=p[fill,3]
  if key=='body':
   # Nearest-neighbour padding copies the nostrils and eye rim into the
   # hidden socket. Reconstruct clean skin so blinking never reveals those
   # stretched dark marks. Fit each socket from adjacent painted skin.
   rng=np.random.default_rng(1151)
   for eye,samples in [('eye_far',[(173,510),(173,531),(174,550)]),
                       ('eye_near',[(394,489),(397,527),(392,563)])]:
    ys=np.array([y for x,y in samples],float)
    colors=np.array([p[y-3:y+4,x-3:x+4,:3].mean(axis=(0,1)) for x,y in samples])
    slope,intercept=np.linalg.lstsq(np.c_[ys,np.ones(len(ys))],colors,rcond=None)[0]
    yy,xx=np.nonzero((masks[eye]>0)&(p[...,3]>0))
    skin=yy[:,None]*slope+intercept+rng.normal(0,.7,(len(yy),1))
    # Limit extrapolation above the forehead to the sampled paint palette.
    a[yy,xx,:3]=np.uint8(np.clip(skin,colors.min(axis=0)-4,colors.max(axis=0)+4))
 layers[key]=Image.fromarray(a)
# Reconstruct the hidden far hind leg from the painted near leg. Its visible toe
# keeps the original pixels; the upper section only appears if the belly lifts.
near=layers['leg_hind_near'];crop=near.crop(near.getbbox()).resize((164,220),Image.Resampling.LANCZOS)
hidden=Image.new('RGBA',image.size);hidden.alpha_composite(crop,(790,711))
ha=np.array(hidden);ha[914:,:,3]=0;hidden=Image.fromarray(ha);hidden.alpha_composite(layers['leg_hind_far']);layers['leg_hind_far']=hidden
for key,im in layers.items():
 box=im.getbbox();im.crop(box).save(PARTS/f'{key}.png');meta[key]=dict(x=box[0],y=box[1],w=box[2]-box[0],h=box[3]-box[1])
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
review=Image.new('RGBA',image.size,'#344448');review.alpha_composite(image);review.convert('RGB').save(SRC/'character_review.jpg',quality=95)
shutil.copy2(ROOT/'output/imagegen/reverse_current_power_v1.png',SRC/'power_generated.png')
icon=clean(SRC/'power_generated.png');icon=ImageOps.contain(icon.crop(icon.getbbox()),(224,224),Image.Resampling.LANCZOS)
big=Image.new('RGBA',(256,256));big.alpha_composite(icon,((256-icon.width)//2,(256-icon.height)//2))
key='reverse_current_power';big.save(ROOT/f'images/powers/{key}.png');big.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/f'images/powers/{key}_packed.png')
(ROOT/f'images/atlases/power_atlas.sprites/{key}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/{key}_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')
print('Prepared transparent character, painted layers and native icon.')
