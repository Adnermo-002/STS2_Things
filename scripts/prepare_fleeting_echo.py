"""Extract painted layers, preserving the source; remove the unwanted exterior haze."""
from pathlib import Path
import json
import argparse
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'source_assets/monsters/fleeting_echo'
PARTS = ROOT/'tools/FleetingEchoRig/parts'
PARTS.mkdir(parents=True, exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--white',action='store_true');args=parser.parse_args()
source='character-white-v1.png' if args.white else 'character-v2.png'
rgba = np.array(Image.open(ROOT/'output/imagegen/fleeting_echo'/source).convert('RGBA'))
# The model returns a real alpha channel, but adds broad low-opacity haze.
# Keep the dense paint, give its actual contour a one-pixel antialias edge.
contour = np.array(Image.open(ROOT/'output/imagegen/fleeting_echo/character-v2.png').convert('RGBA')) if args.white else rgba
mask = np.uint8(contour[...,3] >= 251) * 255
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8))
rgba[...,3] = cv2.GaussianBlur(mask, (3,3), .55)
image = Image.fromarray(rgba)
image.save(SRC/'character_cutout.png')

polys = {
 'upper_left': [(0,0),(500,0),(525,277),(660,344),(652,411),(532,452),(0,432)],
 'upper_right': [(790,0),(1536,0),(1536,527),(1050,527),(840,460),(807,368)],
 'lower_left': [(0,414),(532,414),(667,450),(736,518),(676,622),(486,701),(489,1024),(0,1024)],
 'lower_right': [(892,440),(1046,457),(1536,511),(1536,1024),(1010,1024),(973,751),(831,615),(827,511)],
 'body': [(630,276),(802,254),(881,308),(928,408),(880,537),(871,640),(925,804),(969,1024),(679,1024),(660,730),(627,573),(568,382)],
}
layers={}
for name, points in polys.items():
    region=Image.new('L', image.size)
    ImageDraw.Draw(region).polygon(points, fill=255)
    pixels=rgba.copy(); pixels[...,3]=np.minimum(pixels[...,3],np.asarray(region))
    layers[name]=Image.fromarray(pixels)

gold=((rgba[...,0]<100)&(rgba[...,1]<100)&(rgba[...,2]>60)) if args.white else ((rgba[...,0]>155)&(rgba[...,1]>122)&(rgba[...,2]<178))
gold &= rgba[...,3]>200
gold[:, :650]=False; gold[:, 805:]=False
gold_mask=cv2.dilate(np.uint8(gold)*255,np.ones((3,3),np.uint8))
core=rgba.copy(); core[...,3]=np.minimum(core[...,3],gold_mask)
layers['core']=Image.fromarray(core)
# Cover the old luminous slit under the separately animated painted core.
body=np.array(layers['body']); clean=cv2.inpaint(body[...,:3],gold_mask,5,cv2.INPAINT_TELEA)
body[...,:3]=clean; layers['body']=Image.fromarray(body)

meta={}
for name,part in layers.items():
    box=part.getbbox()
    if not box: raise RuntimeError('Empty painted part: '+name)
    part.crop(box).save(PARTS/(name+'.png'))
    meta[name]={'x':box[0],'y':box[1],'w':box[2]-box[0],'h':box[3]-box[1]}
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
assembled=Image.new('RGBA',image.size)
for name in ['upper_left','upper_right','lower_right','body','lower_left','core']:
    assembled.alpha_composite(layers[name])
assembled.save(SRC/'assembled.png')
review=Image.new('RGBA',image.size,'#52605c');review.alpha_composite(assembled)
review.convert('RGB').save(SRC/'character_review.jpg',quality=94)
sheet=Image.new('RGB',(900,600),'#35404a');draw=ImageDraw.Draw(sheet)
for i,(name,part) in enumerate(layers.items()):
    thumb=ImageOps.contain(part.crop(part.getbbox()),(280,255))
    at=((i%3)*300+10,(i//3)*300+30)
    sheet.paste(thumb,at,thumb);draw.text(((i%3)*300+10,(i//3)*300+8),name,fill='white')
sheet.save(SRC/'parts_review.jpg',quality=94)
(ROOT/'images/vfx').mkdir(parents=True,exist_ok=True)
fragment=assembled.crop((663,342,798,529))
fragment=ImageOps.contain(fragment,(58,78),Image.Resampling.LANCZOS)
fragment.save(ROOT/'images/vfx/fleeting_shadow.png')
print('Painted parts:',meta)
