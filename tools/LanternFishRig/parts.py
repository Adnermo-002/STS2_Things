"""Prepare the approved AI painting for continuous, anatomically partitioned skinning.

No replacement character pixels are drawn here. One indexed painted mesh avoids
cutout gaps; hand-authored weights localize motion to fins, jaw, tail and lure.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
im = Image.open(ROOT / 'source_assets/monsters/lantern_fish/floating_fish_final.png').convert('RGBA')
out = HERE / 'parts'
out.mkdir(exist_ok=True)
im.save(out / 'skin.png')
data = np.array(im)
yy, xx = np.indices(data.shape[:2])
lamp = (xx < 268) & (yy > 325) & (yy < 590)
data[..., 3] = np.where(lamp, data[..., 3], 0)
Image.fromarray(data).save(out / 'lantern_glow.png')
(out / 'meta.json').write_text(json.dumps({n:dict(x=0,y=0,w=im.width,h=im.height)
                                         for n in ['skin','lantern_glow']}))
print('Prepared continuous skin and additive lamp,', im.size)
