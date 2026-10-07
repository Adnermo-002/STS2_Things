import sys,time
from PIL import Image
b=Image.open('vis_bnd.png');tag=sys.argv[1]
boxes={'head':(150,380,650,700),'mid':(650,250,1150,700),'crest':(150,40,650,380),'rear':(950,0,1437,700),'face':(0,380,420,720)}
for k in sys.argv[2:]:
    x0,y0,x1,y1=boxes[k];c=b.crop(boxes[k]);f=1000/max(c.size);c.resize((int(c.width*f),int(c.height*f))).save(f'v/{k}_{tag}.jpg',quality=88)
