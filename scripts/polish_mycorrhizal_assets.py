"""Preserve native standing space and prepare the generated painted root strip."""
from pathlib import Path
import json,shutil
import numpy as np,cv2
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
layer=ROOT/'images/rooms/hollow_grotto_moss/hollow_grotto_moss_03.png'
backup=ROOT/'source_assets/backgrounds/hollow_grotto_moss/standing_space_original.png'
backup.parent.mkdir(parents=True,exist_ok=True)
if not backup.exists():shutil.copy2(layer,backup)
pixels=np.array(Image.open(backup).convert('RGBA'))
n,labels,stats,_=cv2.connectedComponentsWithStats((pixels[...,3]>12).astype('uint8'))
removed=[]
for i,(x,y,w,h,area) in enumerate(stats[1:],1):
    if y>450 and h>45 and area>200:
        # Only the two isolated high plants: canopy and low floor stones remain.
        mask=cv2.dilate((labels==i).astype('uint8'),np.ones((7,7),np.uint8))>0
        pixels[mask]=0;removed.append(dict(x=int(x),y=int(y),width=int(w),height=int(h)))
Image.fromarray(pixels).save(layer)
source=ROOT/'output/imagegen/mycorrhizal_root_v1.png'
raw=np.array(Image.open(source).convert('RGBA'))
raw[...,3]=np.uint8(np.clip((raw[...,3].astype(float)-220)/33,0,1)*255)
n,labels,stats,_=cv2.connectedComponentsWithStats((raw[...,3]>0).astype('uint8'))
if n>1:raw[labels!=(1+np.argmax(stats[1:,cv2.CC_STAT_AREA])),3]=0
raw[raw[...,3]==0,:3]=0
im=Image.fromarray(raw);im=im.crop(im.getbbox())
im.thumbnail((1536,192),Image.Resampling.LANCZOS)
dest=ROOT/'images/vfx/mycorrhizal_root.png';im.save(dest)
shutil.copy2(source,ROOT/'source_assets/monsters/mycorrhizal_twins/root_generated.png')
(ROOT/'source_assets/monsters/mycorrhizal_twins/root_preparation.json').write_text(json.dumps(dict(model='gpt-image-2.5-sunburst',size=im.size,removed_decorations=removed),indent=2),'utf-8')
print('Standing decorations removed:',removed,'; root strip:',im.size)
