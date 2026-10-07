"""Prepare painted snail cutouts for weighted Spine meshes; retain source art."""
from pathlib import Path
import json, shutil
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'tools/DepthsSnailsRig'
DEST.mkdir(exist_ok=True)
for helper in ('rigkit.py','rigutil.py'):
    if not (DEST/helper).exists():
        shutil.copy2(ROOT/'tools/RadioJellyfishRig'/helper,DEST/helper)
sheet=Image.new('RGB',(1536,1024),'#29353f')
for index,name in enumerate(('crystal_snail','slime_snail','rock_snail')):
    src=ROOT/f'source_assets/monsters/depths_snails/{name}'
    orig=Image.open(src/'character.png').convert('RGBA');a=np.array(orig)
    parts=DEST/name/'parts';parts.mkdir(parents=True,exist_ok=True)
    layers={}
    if name!='slime_snail':
        raw=np.array(Image.open(ROOT/f'output/imagegen/depths_snails/{name}_body_v1.png').convert('RGBA'))
        raw[...,3]=np.uint8(np.clip((raw[...,3].astype(float)-230)/18,0,1)*255)
        raw[raw[...,3]==0,:3]=0
        bodyedit=Image.fromarray(raw);bodyedit.save(src/'body_edit_clean.png')
        r,g,b=a[...,:3].astype(float).transpose(2,0,1)
        yy,xx=np.indices(a.shape[:2])
        if name=='crystal_snail':mask=(g>r+9)&(xx>455)&(yy<885)
        else:mask=(r-g<28)&(r<g*1.35+5)&(xx>400)&(yy<825)
        mask=np.uint8(mask&(a[...,3]>0))*255
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        # Shell boundaries use their original alpha, with no generated halo.
        shell=a.copy();shell[...,3]=np.minimum(a[...,3],mask)
        layers['shell']=Image.fromarray(shell)
        # The identity-preserving body edit aligns with the original shell.
        # Retaining the old shell shadow would leave a seam after it shatters.
        layers['body']=bodyedit
    else:
        layers['body']=orig
    clean=np.array(layers['body'])
    if name=='slime_snail':
        r,g,b=clean[...,:3].astype(float).transpose(2,0,1);yy,xx=np.indices(clean.shape[:2])
        wet=(g>r+15)&(b>r+10)&(xx<288)&(yy>439)&(yy<649)&(clean[...,3]>0)
        wet=(cv2.dilate(np.uint8(wet),np.ones((3,3),np.uint8))>0)&(clean[...,3]>0)
        paths=[[(211,449),(204,489),(188,538)],[(229,462),(229,506),(227,551)],[(245,488),(252,548),(257,610)]]
        points=np.c_[xx[wet],yy[wet]];dist=[]
        for path in paths:
            path=np.array(path,float);start=path[:-1];delta=path[1:]-start
            t=np.clip(np.sum((points[:,None,:]-start)*delta,axis=2)/np.sum(delta*delta,axis=1),0,1)
            dist.append(np.min(np.sum((start+t[...,None]*delta-points[:,None,:])**2,axis=2),axis=1))
        choices=np.argmin(dist,axis=0)
        for i in range(3):
            mask=np.zeros(clean.shape[:2],bool);mask[wet]=choices==i
            layer=clean.copy();layer[~mask]=0;layers[f'drool_{i}']=Image.fromarray(layer)
        clean[wet]=0
    else:
        eyes=([
          [(116,550),(166,551),(181,567),(174,586),(155,599),(133,595),(120,582)],
          [(274,511),(326,513),(349,528),(346,549),(331,563),(307,565),(287,552),(274,536)]]
          if name=='crystal_snail' else [
          [(94,469),(139,467),(163,470),(160,491),(147,505),(120,505),(102,491)],
          [(266,481),(305,472),(337,475),(336,495),(322,508),(300,511),(279,501)]])
        for i,polygon in enumerate(eyes):
            mask=Image.new('L',layers['body'].size);ImageDraw.Draw(mask).polygon(polygon,fill=255)
            m=np.array(mask);layer=clean.copy();layer[...,3]=np.minimum(layer[...,3],m)
            layers[f'eye_{i}']=Image.fromarray(layer)
            xs=[p[0] for p in polygon];ys=[p[1] for p in polygon]
            sample=clean[max(0,min(ys)-18):min(ys)-3,min(xs)+15:max(xs)-10]
            skin=np.median(sample[...,:3][sample[...,3]>240],axis=0)
            # Do not inpaint from transparent black pixels outside the stalk.
            # A sampled painted eyelid plane stays clean when the eye closes.
            cover=cv2.dilate(m,np.ones((3,3),np.uint8))>0
            clean[cover,:3]=np.uint8(skin)
    n,labels,stats,_=cv2.connectedComponentsWithStats(np.uint8(clean[...,3]>0))
    for component in range(1,n):
        if stats[component,cv2.CC_STAT_AREA]<60:clean[labels==component]=0
    layers['body']=Image.fromarray(clean)
    layers['body'].save(src/'body.png')
    meta={}
    for layer,im in layers.items():
        box=im.getbbox();crop=im.crop(box);crop.save(parts/f'{layer}.png')
        meta[layer]=dict(x=box[0],y=box[1],w=crop.width,h=crop.height)
    (parts/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
    (DEST/name/'rigdef.py').write_text('from snail_rig import *\n','utf-8')
    (DEST/name/'anims.py').write_text('from snail_anims import *\n','utf-8')
    # A full-size annotated view makes contour and binding decisions reviewable.
    review=Image.new('RGBA',orig.size,'#29353f');review.alpha_composite(layers['body'])
    d=ImageDraw.Draw(review)
    for x in range(0,1536,100):d.line((x,0,x,1024),fill='#70808755');d.text((x+3,16),str(x),fill='white')
    for y in range(100,1024,100):d.line((0,y,1536,y),fill='#70808755');d.text((8,y+3),str(y),fill='white')
    review.convert('RGB').save(ROOT/f'build/depths_snails/{name}-binding.jpg',quality=90)
    for row,im in enumerate((layers['body'],orig)):
        thumb=im.resize((512,341),Image.Resampling.LANCZOS)
        sheet.paste(thumb,(index*512,row*440+70),thumb)
        ImageDraw.Draw(sheet).text((index*512+12,row*440+20),name+(' / bare' if row==0 else ' / shell'),fill='white')
    print(name,meta)
sheet.save(ROOT/'build/depths_snails/layers-review.jpg',quality=92)
