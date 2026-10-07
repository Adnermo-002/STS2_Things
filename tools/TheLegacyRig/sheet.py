import json,sys
from PIL import Image, ImageDraw
meta=json.load(open('parts/meta.json'))
names=[n for n in meta if (sys.argv[1]=='body') == (n in json.load(open('order.json'))['order'])]
tiles=[]
for n in names:
    im=Image.open(f'parts/{n}.png'); im.thumbnail((440,300))
    t=Image.new('RGBA',(450,320),(70,70,85,255)); t.alpha_composite(im,(5,5)); ImageDraw.Draw(t).text((5,305),n,fill='white'); tiles.append(t)
C=3; R=(len(tiles)+C-1)//C
s=Image.new('RGB',(450*C,320*R))
for i,t in enumerate(tiles): s.paste(t,((i%C)*450,(i//C)*320))
s.save(f'sheet_{sys.argv[1]}.jpg',quality=88)
