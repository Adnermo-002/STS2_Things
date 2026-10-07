"""Preserve opaque teal/cream interior; chroma soft-key is used only at the boundary."""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
src=ROOT/'source_assets/monsters/lantern_fish'
raw=np.array(Image.open(src/'floating_fish_generated.png').convert('RGBA'))
keyed=np.array(Image.open(src/'floating_fish.png').convert('RGBA'))
c=raw[:,:,:3].astype(np.int16)
green=(c[:,:,1]>140)&(c[:,:,1]-c[:,:,0]>60)&(c[:,:,1]-c[:,:,2]>60)
inside=cv2.erode((~green).astype(np.uint8),np.ones((7,7),np.uint8))>0
keyed[inside,:3]=raw[inside,:3];keyed[inside,3]=255
Image.fromarray(keyed).save(src/'floating_fish_final.png')
assert keyed[800,800,3]==255
preview=Image.fromarray(keyed);preview.thumbnail((768,512),Image.Resampling.LANCZOS)
bg=Image.new('RGBA',preview.size,(38,42,49,255));bg.alpha_composite(preview)
bg.convert('RGB').save(src/'floating_preview.jpg',quality=95)
print('Opaque interior restored without changing the generated painting; antialiased boundary retained.')
