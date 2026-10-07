"""Remove generated low-alpha halos while preserving the painted snail silhouettes."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
NAMES=('crystal_snail','slime_snail','rock_snail')
sheet=Image.new('RGB',(1536,420),'#29353f')
draw=ImageDraw.Draw(sheet)
for i,name in enumerate(NAMES):
    src=ROOT/f'output/imagegen/depths_snails/{name}_v1.png'
    a=np.array(Image.open(src).convert('RGBA'))
    a[...,3]=np.uint8(np.clip((a[...,3].astype(float)-230)/18,0,1)*255)
    a[a[...,3]==0,:3]=0
    dest=ROOT/f'source_assets/monsters/depths_snails/{name}'
    dest.mkdir(parents=True,exist_ok=True)
    clean=Image.fromarray(a)
    clean.save(dest/'character.png')
    preview=ImageOps.contain(clean.crop(clean.getbbox()),(470,350),Image.Resampling.LANCZOS)
    sheet.paste(preview,(i*512+(512-preview.width)//2,388-preview.height),preview)
    draw.text((i*512+18,14),name,fill='#f2e8cc')
    print(name,'cleaned bounds',clean.getbbox())
sheet.save(ROOT/'build/depths_snails/character-review.jpg',quality=95)
