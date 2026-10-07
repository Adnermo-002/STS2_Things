import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi
im=np.array(Image.open('src.png').convert('RGBA'))
rgb=im[...,:3]; a=im[...,3]
hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
h=hsv[...,0].astype(int)*2; s=hsv[...,1].astype(int); v=hsv[...,2].astype(int)
m=a>8
green=(h>=45)&(h<=110)&m&(s>50)
# green components
g=cv2.morphologyEx(green.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
n,lab,st,cen=cv2.connectedComponentsWithStats(g,8)
order=np.argsort(-st[:,4])
vis=np.zeros_like(rgb)
rng=np.random.default_rng(1)
for i in order[1:40]:
    x,y,w,hh,area=st[i]
    if area<150: continue
    vis[lab==i]=rng.integers(60,255,3)
    print(i,'bbox',x,y,w,hh,'area',area)
out=Image.fromarray(vis)
from PIL import ImageDraw
d=ImageDraw.Draw(out)
for i in order[1:40]:
    if st[i,4]<150: continue
    d.text(tuple(cen[i].astype(int)),str(i),fill='white')
out.save('vis_green.jpg')
