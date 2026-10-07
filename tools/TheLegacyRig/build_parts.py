"""Stage B: every opaque pixel -> exactly one layer; occlusion fill for back layers."""
import numpy as np, cv2, json
from PIL import Image
from scipy import ndimage as ndi
im=np.array(Image.open('src.png').convert('RGBA'))
H,W=im.shape[:2]; rgb=im[...,:3]; a=im[...,3]
m=a>0
F=np.load('masks_front.npy',allow_pickle=True).item()
labels=np.load('labels_body.npy'); PARTS=json.load(open('parts_body.json'))
front_names=['coral_purple','coral_pink']+list(F['sprigs'].keys())
front_masks={'coral_purple':F['coral_purple'],'coral_pink':F['coral_pink'],**F['sprigs']}
body_true0=np.load('body_true.npy')
known0=labels>0
stray=(known0&~body_true0)|((labels>0)&(a<=24)&~body_true0)
for k in list(F['sprigs'].keys()):
    mk=F['sprigs'][k]
    near=cv2.dilate(mk.astype(np.uint8),np.ones((15,15),np.uint8))>0
    add=stray&near
    mk|=add; stray&=~add; labels[add]=0
    front_masks[k]=mk
# unified label map; faint halo px -> nearest solid layer
fk=list(front_masks.keys())
U=np.zeros((H,W),np.int32)
kn=labels>0
ii=ndi.distance_transform_edt(~kn,return_distances=False,return_indices=True)
U[m]=labels[ii[0],ii[1]][m]
for j,k in enumerate(fk): U[front_masks[k]]=100+j
faint=m&(a<=24)&~body_true0
solid=(U>0)&~faint
ii=ndi.distance_transform_edt(~solid,return_distances=False,return_indices=True)
U[faint]=U[ii[0],ii[1]][faint]
for j,k in enumerate(fk): front_masks[k]=(U==100+j)
labels=np.where(U<100,U,0)
front_any=np.zeros((H,W),bool)
for k in front_masks: front_any|=front_masks[k]
# 1) body labels for all opaque non-front px (nearest labelled)
known=labels>0
idx=ndi.distance_transform_edt(~known,return_distances=False,return_indices=True)
full_under=labels[idx[0],idx[1]]          # owner for every pixel (incl. under front layers)
full_under[~m]=0
body_lab=full_under.copy(); body_lab[front_any]=0
# draw order back->front
body_sil=np.load('body_true.npy')
# never let the silhouette swallow front pixels that sit on fully transparent-surround
np.save('body_sil.npy',body_sil)
ORDER=['purple_top','purple_mass','purple_lr','blue_bottom','blue_main','blue_down',
       'right_lobe','mid_lobe','bottom_lobe','atrium','bulb']
rank={p:i for i,p in enumerate(ORDER)}
pid={p:i+1 for i,p in enumerate(PARTS)}
layers={}
EXT=34
for p in ORDER:
    vis=(body_lab==pid[p])
    under=(full_under==pid[p])&front_any&body_sil          # hidden under corals/weeds -> always own it
    # hidden under body parts drawn in front
    infront=np.zeros((H,W),bool)
    for q in ORDER[rank[p]+1:]: infront|=(body_lab==pid[q])
    own=vis|under
    grow=cv2.dilate((own&body_sil).astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*EXT+1,2*EXT+1)))>0
    ext=grow&(infront|(front_any&body_sil))&m
    # shape it: close so extension follows blob continuation, then keep only opaque
    big=cv2.morphologyEx((own&body_sil).astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(81,81)))>0
    big=ndi.binary_fill_holes(big)
    ext|=big&(infront|front_any)&m
    ext&=(body_sil|big)
    full=own|ext
    full=cv2.morphologyEx(full.astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))>0
    full|=own
    # keep only the component(s) touching own
    layers[p]=dict(vis=vis,known=own,full=full&m)
np.save('layers_body.npy',{k:{kk:vv for kk,vv in v.items()} for k,v in layers.items()},allow_pickle=True)
np.save('front_masks.npy',front_masks,allow_pickle=True)
json.dump({'order':ORDER,'front':front_names},open('order.json','w'))
print({p:int(layers[p]['full'].sum()) for p in ORDER})
