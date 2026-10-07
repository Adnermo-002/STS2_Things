"""Give each painted digit its own mesh, preventing cross-finger skinning."""
from pathlib import Path
import json,shutil
import numpy as np,cv2
from PIL import Image
from rigdef import ARMS,FINGERS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];parts=HERE/'parts'
backup=ROOT/'build/fleeting_echo/animation-polish/before'
meta=json.loads((parts/'meta.json').read_text('utf-8'))
saved=backup/'painted-arm-meta.json'
if not saved.exists():
    saved.write_text(json.dumps({n:meta[n] for n in ARMS},indent=2),'utf-8')
    for n in ARMS:shutil.copy2(parts/(n+'.png'),backup/('painted-'+n+'.png'))
clean=parts/'clean-arm-meta.json'
source=json.loads((clean if clean.exists() else saved).read_text('utf-8'))
def distance(p,a,b):
    a=np.array(a,float);v=np.array(b,float)-a
    u=np.clip(((p-a)@v)/max(float(v@v),1e-6),0,1)
    return np.sum((p-a-u[:,None]*v)**2,axis=1)
for name,knots in ARMS.items():
    source_path=parts/('source-'+name+'.png') if clean.exists() else backup/('painted-'+name+'.png')
    paint=np.array(Image.open(source_path).convert('RGBA'))
    m=source[name];h,w=paint.shape[:2];yy,xx=np.mgrid[:h,:w]
    p=np.stack([xx.ravel()+m['x'],yy.ravel()+m['y']],1)
    shaft=np.min(np.stack([distance(p,a,b) for a,b in zip(knots[:-1],knots[1:])],1),1)
    shaft=np.minimum(shaft,np.sum((p-np.array(knots[-1]))**2,axis=1))
    fields=[shaft]
    for curve in FINGERS[name]:
        fields.append(np.minimum(distance(p,curve[0],curve[1]),distance(p,curve[1],curve[2]))+64)
    owner=np.argmin(np.stack(fields,1),axis=1).reshape(h,w)
    for i,key in enumerate([name]+[name+'_digit'+str(j) for j in range(len(FINGERS[name]))]):
        mask=cv2.dilate(np.uint8(owner==i)*255,np.ones((9,9),np.uint8))
        layer=paint.copy();layer[...,3]=np.minimum(layer[...,3],mask)
        im=Image.fromarray(layer);box=im.getbbox()
        if not box:raise RuntimeError('Empty digit: '+key)
        im.crop(box).save(parts/(key+'.png'))
        meta[key]={'x':m['x']+box[0],'y':m['y']+box[1],'w':box[2]-box[0],'h':box[3]-box[1]}
(parts/'meta.json').write_text(json.dumps(meta,indent=2),'utf-8')
print('Separated 13 painted digits with small overlapping joint caps.')
