"""Build the native three-section map from one continuous generated stone painting."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np
import cv2
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_assets/backgrounds/depths_stone_map'
BUILD=ROOT/'build/depths_stone_map'
TARGET=ROOT/'images/packed/map/map_bgs/depths'
WIDTH,HEIGHT=2036,1440
NAMES=['top','middle','bottom']

def build(deploy=False):
    BUILD.mkdir(parents=True,exist_ok=True)
    selected=json.loads((SOURCE/'selection.json').read_text(encoding='utf-8'))
    raw=Image.open(SOURCE/selected['image']).convert('RGBA')
    data=np.array(raw)
    rgb=data[...,:3].astype(np.int16)
    # The upstream result has alpha, but may contain a few neon chroma remnants.
    neon=(rgb.max(2)-rgb.min(2)>125)&(rgb.max(2)>205)
    opaque=((data[...,3]>175)&~neon).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(opaque,8)
    if count<2:
        raise RuntimeError('No stone silhouette found')
    core=labels==(1+np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    border=cv2.dilate(core.astype(np.uint8),np.ones((3,3),np.uint8))>0
    alpha=np.where(core,255,np.where(border&~neon,data[...,3],0)).astype(np.uint8)
    data[...,3]=alpha
    data[alpha==0,:3]=0
    cleaned=Image.fromarray(data)
    # Normalize once before slicing. There is never a per-tile color, scale or
    # filtering pass that could introduce a visible join.
    face=cleaned.resize((WIDTH,HEIGHT*3-112),Image.Resampling.LANCZOS)
    master=Image.new('RGBA',(WIDTH,HEIGHT*3))
    master.alpha_composite(face,(0,56))
    master.save(SOURCE/selected['master'])
    images=BUILD/'images/packed/map/map_bgs/depths'
    images.mkdir(parents=True,exist_ok=True)
    sections=[]
    for i,name in enumerate(NAMES):
        section=master.crop((0,i*HEIGHT,WIDTH,(i+1)*HEIGHT))
        section.save(images/f'map_{name}_depths.png')
        sections.append(section)
    reassembled=Image.new('RGBA',master.size)
    for i,section in enumerate(sections):
        reassembled.paste(section,(0,i*HEIGHT))
    if not np.array_equal(np.array(master),np.array(reassembled)):
        raise RuntimeError('The three native map textures do not reproduce the continuous master')
    arr=np.array(master)
    reports=[]
    for y in [HEIGHT,HEIGHT*2]:
        mask=(arr[y-1,:,3]>250)&(arr[y,:,3]>250)
        seam=np.abs(arr[y,:,:3].astype(float)-arr[y-1,:,:3].astype(float))[mask].mean()
        neighborhood=np.abs(arr[y-20:y+20,:,:3].astype(float)[1:]-arr[y-20:y+20,:,:3].astype(float)[:-1])
        ordinary=neighborhood[:,mask,:].mean()
        reports.append({'source_y':y,'mean_adjacent_row_delta':round(float(seam),4),
                        'nearby_row_delta':round(float(ordinary),4),
                        'alpha_edge_pixels_matching':int(np.sum(arr[y-1,:,3]==arr[y,:,3]))})
        if seam>max(ordinary*2.5,2.5):
            raise RuntimeError(f'Unexpected horizontal discontinuity at {y}')
    background=Image.new('RGBA',master.size,'#172932')
    background.alpha_composite(master)
    background.convert('RGB').resize((680,1443),Image.Resampling.LANCZOS).save(BUILD/'stone_full_preview.jpg',quality=95)
    joins=Image.new('RGB',(1200,640),'#172932')
    for i,y in enumerate([HEIGHT,HEIGHT*2]):
        strip=background.crop((0,y-260,WIDTH,y+260)).convert('RGB').resize((1200,307),Image.Resampling.LANCZOS)
        joins.paste(strip,(0,i*320+13))
    joins.save(BUILD/'seams_preview.jpg',quality=96)
    if deploy:
        before=BUILD/'before'
        before.mkdir(exist_ok=True)
        for name in NAMES:
            filename=f'map_{name}_depths.png'
            if (TARGET/filename).exists() and not (before/filename).exists():
                shutil.copy2(TARGET/filename,before/filename)
            TARGET.mkdir(parents=True,exist_ok=True)
            shutil.copy2(images/filename,TARGET/filename)
    report={'selected_art':selected,'source_size':list(raw.size),'master_size':list(master.size),
        'native_section_size':[WIDTH,HEIGHT],'sections':NAMES,'reassembly_pixel_identical':True,
        'joins':reports,'deployed':deploy,'scope':'One source image, adjacent slices; natural painted texture, no independent tile blending.',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in images.glob('*.png')}}
    (BUILD/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--deploy',action='store_true',help='Replace the three Depths source textures, retaining a backup')
    options=parser.parse_args()
    build(options.deploy)
