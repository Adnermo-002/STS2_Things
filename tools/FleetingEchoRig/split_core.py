"""Separate the existing painted negative star/slits without repainting the character."""
from pathlib import Path
import json
from PIL import Image
HERE=Path(__file__).resolve().parent
root=HERE.parents[1];parts=HERE/'parts'
base=root/'source_assets/monsters/fleeting_echo/rig_base'
original=json.loads((base/'meta.json').read_text('utf-8'))['core']
paint=Image.open(base/'core.png').convert('RGBA')
meta=json.loads((parts/'meta.json').read_text('utf-8'))
for name,(low,high) in {'core_top':(300,368),'core':(368,485),'core_mid':(485,579),'core_low':(579,637)}.items():
    y0=max(0,low-original['y']);y1=min(paint.height,high-original['y'])
    piece=paint.crop((0,y0,paint.width,y1));box=piece.getbbox()
    if box is None:raise RuntimeError('Empty core segment: '+name)
    piece.crop(box).save(parts/(name+'.png'))
    meta[name]={'x':original['x']+box[0],'y':original['y']+y0+box[1],'w':box[2]-box[0],'h':box[3]-box[1]}
(parts/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
print('Separated the original star and three fissures, preserving painted pixels.')
