"""Prepare Sunburst art and reproducible, overlapping skeletal layers (no API calls)."""
from pathlib import Path
import json, shutil
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image, ImageDraw, ImageOps
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_assets/monsters/mycorrhizal_twins'
RIG=ROOT/'tools/MycorrhizalTwinsRig'
SOURCE.mkdir(parents=True,exist_ok=True)

def clean(path):
    a=np.array(Image.open(path).convert('RGBA'))
    a[...,3]=np.uint8(np.clip((a[...,3].astype(float)-220)/33,0,1)*255)
    n,labels,stats,_=cv2.connectedComponentsWithStats((a[...,3]>0).astype('uint8'))
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]<35:a[labels==i,3]=0
    a[a[...,3]==0,:3]=0
    return Image.fromarray(a)

raw=ROOT/'output/imagegen/mycorrhizal_twins_v1.png'
shutil.copy2(raw,SOURCE/'character_generated.png')
image=clean(raw)
image.save(SOURCE/'character_final.png')
definitions={
 'mycorrhizal_vanguard':{
  'crop':(0,0,887,887),'origin':(520,878),
  'cap':[(0,0),(887,0),(887,525),(810,501),(744,446),(651,403),(560,353),(504,288),(451,213),(392,209),(357,248),(368,287),(330,340),(223,345),(101,306),(0,286)],
  'arm_far':[(420,427),(434,462),(405,512),(369,551),(350,592),(352,670),(333,791),(208,794),(201,624),(307,570),(358,497)],
  'arm_near':[(558,420),(612,440),(650,482),(677,566),(802,684),(817,798),(727,812),(640,708),(616,622),(617,537),(584,473)],
  'foot_far':[(385,784),(445,784),(479,827),(487,887),(278,887),(289,832)],
  'foot_near':[(559,787),(611,784),(666,822),(716,865),(710,887),(507,887),(507,838)],
  'eyes':[(321,316,379,378),(382,292,462,357)],
  'anchors':{'body':(521,747),'neck':(435,420),'cap':(411,250),'cap_l':(208,212),'cap_r':(644,349),'arm_far':(419,449),'elbow_far':(344,585),'hand_far':(287,665),'arm_near':(572,447),'elbow_near':(649,588),'hand_near':(725,688),'foot_far':(409,820),'foot_near':(588,832),'tail':(622,787)},
 },
 'mycorrhizal_bulwark':{
  'crop':(887,0,1774,887),'origin':(484,878),
  'cap':[(0,0),(887,0),(887,642),(745,631),(659,618),(595,604),(569,563),(530,544),(459,545),(400,539),(337,527),(327,557),(323,577),(228,575),(121,531),(68,510),(0,475)],
  'arm_far':[(339,610),(336,651),(298,673),(285,737),(253,793),(144,802),(133,691),(182,641),(269,630)],
  'arm_near':[(575,605),(623,604),(668,641),(713,685),(779,734),(779,795),(694,793),(653,730),(633,691),(591,672)],
  'foot_far':[(340,795),(404,796),(455,841),(455,887),(225,887),(244,839)],
  'foot_near':[(536,799),(602,798),(652,837),(728,887),(489,887),(492,850)],
  'eyes':[(312,565,392,618),(425,558,509,611)],
  'anchors':{'body':(493,757),'neck':(468,660),'cap':(439,539),'cap_l':(239,453),'cap_r':(654,525),'arm_far':(330,636),'elbow_far':(268,677),'hand_far':(211,728),'arm_near':(596,631),'elbow_near':(648,680),'hand_near':(714,738),'foot_far':(364,832),'foot_near':(581,842),'tail':(652,787)},
 }
}
for name,d in definitions.items():
    im=image.crop(d['crop']);p=np.array(im);h,w=p.shape[:2]
    masks={}
    for part in ['cap','arm_far','arm_near','foot_far','foot_near']:
        m=Image.new('L',(w,h));ImageDraw.Draw(m).polygon(d[part],fill=255);masks[part]=np.array(m)
    yy,xx=np.indices((h,w));rgb=p[...,:3].astype(float)
    # Every painted cap pixel belongs to the cap, including its asymmetric tip.
    colored=((rgb[...,0]-rgb[...,1]>42)&(rgb[...,0]-rgb[...,2]>85)&(yy<490)) if name.endswith('vanguard') else ((rgb[...,2]>rgb[...,0]*1.12)&(rgb[...,1]>rgb[...,0]*1.05)&(yy<640))
    masks['cap'][cv2.dilate(colored.astype('uint8'),np.ones((5,5),np.uint8))>0]=255
    if name.endswith('vanguard'):
        edge=np.interp(yy,[390,450,530,610,690,765,805],[403,431,441,426,394,393,413])
        masks['arm_far'][(xx<edge)&(yy>410)&(yy<805)]=255
        edge=np.interp(yy,[410,470,540,610,670,725],[536,577,599,612,616,626])
        masks['arm_near'][(xx>edge)&(yy>418)&(yy<726)]=255
        masks['arm_near'][(xx>707)&(yy>=726)&(yy<825)]=255
    else:
        edge=np.interp(yy,[602,650,710,770,806],[343,327,310,327,350])
        masks['arm_far'][(xx<edge)&(yy>602)&(yy<808)]=255
        edge=np.interp(yy,[602,650,700,735],[579,606,624,640])
        masks['arm_near'][(xx>edge)&(yy>602)&(yy<738)]=255
        masks['arm_near'][(xx>698)&(yy>=738)&(yy<813)]=255
    # Lower legs form complete parts; no stationary toe fragments remain in torso.
    masks['foot_far'][(yy>=809)&(xx<d['origin'][0]-15)]=255
    masks['foot_near'][(yy>=823)&(xx>=d['origin'][0]-15)]=255
    masks['arm_far'][masks['cap']>0]=0;masks['arm_near'][masks['cap']>0]=0
    for i,box in enumerate(d['eyes']):
        m=Image.new('L',(w,h));ImageDraw.Draw(m).ellipse(box,fill=255);masks[f'eye_{i}']=np.array(m)
        d['anchors'][f'eye_{i}']=((box[0]+box[2])/2,(box[1]+box[3])/2)
    used=np.maximum.reduce(list(masks.values()))
    masks['body']=255-used
    n,labels,stats,_=cv2.connectedComponentsWithStats(((masks['body']>0)&(p[...,3]>0)).astype('uint8'))
    if n>1:
        main=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
        scraps=(labels!=0)&(labels!=main)
        for lab in range(1,n):
            if lab==main:continue
            cy,cx=np.mean(np.argwhere(labels==lab),axis=0)
            part='cap' if cy<560 and (cy<380 if name.endswith('vanguard') else True) else ('arm_far' if cx<d['origin'][0] else 'arm_near')
            masks[part][labels==lab]=255
        masks['body'][scraps]=0
    out=RIG/name/'parts';out.mkdir(parents=True,exist_ok=True)
    meta={}
    for part,mask in masks.items():
        pix=p.copy();pix[...,3]=np.minimum(pix[...,3],mask)
        if part.startswith('arm_') or part.startswith('foot_'):
            count,parts,area,_=cv2.connectedComponentsWithStats((pix[...,3]>0).astype('uint8'))
            if count>1:pix[parts!=(1+np.argmax(area[1:,cv2.CC_STAT_AREA])),3]=0
        if part=='body':
            # Reconstruct hidden shoulder/neck/ankle overlaps for articulated motion.
            visible=pix[...,3]>0
            expanded=cv2.dilate(visible.astype('uint8'),np.ones((29,29),np.uint8))>0
            fill=expanded&(~visible)&(p[...,3]>0)&(used>0)
            fill |= ((masks['eye_0']>0)|(masks['eye_1']>0))&(p[...,3]>0)
            # Fill from the torso surface itself, never from black transparency,
            # cap pigment, or a neighboring limb that is about to move away.
            _,indices=distance_transform_edt(~visible,return_indices=True)
            colors=p[...,:3][indices[0],indices[1]]
            colors=cv2.GaussianBlur(colors,(7,7),0)
            pix[fill,:3]=colors[fill];pix[fill,3]=p[fill,3]
        item=Image.fromarray(pix);box=item.getbbox()
        item.crop(box).save(out/f'{part}.png')
        meta[part]=dict(x=box[0],y=box[1],w=box[2]-box[0],h=box[3]-box[1])
    (out/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
    (RIG/name/'definition.json').write_text(json.dumps(d,indent=2),'utf-8')
    im.save(SOURCE/f'{name}.png')
    review=Image.new('RGBA',im.size,'#344048');review.alpha_composite(im)
    review.convert('RGB').save(SOURCE/f'{name}_review.jpg',quality=94)

icon=clean(ROOT/'output/imagegen/mycorrhizal_link_power_v1.png')
shutil.copy2(ROOT/'output/imagegen/mycorrhizal_link_power_v1.png',SOURCE/'power_generated.png')
for name,fury in [('mycorrhizal_bond_power',False),('mycorrhizal_fury_power',True)]:
    small=ImageOps.contain(icon.crop(icon.getbbox()),(224,224),Image.Resampling.LANCZOS)
    if fury:
        arr=np.array(small);rgb=arr[...,:3].astype(float)
        rgb[...,0]*=1.24;rgb[...,1]*=.72;rgb[...,2]*=.65;arr[...,:3]=np.uint8(np.clip(rgb,0,255))
        # A torn gap clearly distinguishes severed fury from the intact bond.
        yy,xx=np.indices(arr.shape[:2]);arr[(abs(yy-(.28*xx+small.height*.52))<3),3]=0
        small=Image.fromarray(arr)
    big=Image.new('RGBA',(256,256));big.alpha_composite(small,((256-small.width)//2,(256-small.height)//2))
    big.save(ROOT/f'images/powers/{name}.png');big.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/f'images/powers/{name}_packed.png')
    (ROOT/f'images/atlases/power_atlas.sprites/{name}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/{name}_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')
print('Prepared paired sprites, eight layers per twin, and native power icons.')
