"""Remove duplicated torso paint inside the arm attachments, keeping joint overlap."""
from pathlib import Path
import json
import cv2,numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
backup=ROOT/'build/fleeting_echo/animation-polish/before';parts=HERE/'parts'
meta=json.loads((parts/'meta.json').read_text('utf-8'))
base=ROOT/'source_assets/monsters/fleeting_echo/rig_base'
original=json.loads((base/'meta.json').read_text('utf-8'))
body=np.zeros((1024,1536),np.uint8)
m=meta['body'];alpha=np.array(Image.open(parts/'body.png'))[...,3]
body[m['y']:m['y']+m['h'],m['x']:m['x']+m['w']]=alpha
interior=cv2.distanceTransform(np.uint8(body>120),cv2.DIST_L2,5)
keep=np.uint8(np.clip((19-interior)/10,0,1)*255)
for name in ['upper_left','upper_right','lower_left','lower_right']:
    path=base/(name+'.png')
    m=original[name];paint=np.array(Image.open(path).convert('RGBA'))
    paint[...,3]=np.minimum(paint[...,3],keep[m['y']:m['y']+m['h'],m['x']:m['x']+m['w']])
    yy,xx=np.mgrid[:paint.shape[0],:paint.shape[1]];xx=xx+m['x'];yy=yy+m['y']
    # Old broad polygons captured thin strips from the upper arm as well.
    if name=='lower_left':paint[...,3]=np.where(yy>=430-.58*(xx-640),paint[...,3],0)
    if name=='lower_right':paint[...,3]=np.where(yy>=450+.52*(xx-850),paint[...,3],0)
    image=Image.fromarray(paint);box=image.getbbox()
    image.crop(box).save(parts/(name+'.png'))
    image.crop(box).save(parts/('source-'+name+'.png'))
    meta[name]={'x':m['x']+box[0],'y':m['y']+box[1],'w':box[2]-box[0],'h':box[3]-box[1]}
(parts/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
(parts/'clean-arm-meta.json').write_text(json.dumps({n:meta[n] for n in ['upper_left','upper_right','lower_left','lower_right']},indent=2),'utf-8')
print('Cleaned inner shoulder overlap; retained exterior paint and 9-pixel joint caps.')
