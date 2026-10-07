"""Extract only AI-painted furniture; native character anchors remain untouched."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFilter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
raw=Image.open(HERE/'camp_seats_source.png').convert('RGBA')
definitions={
'seat_front_left':([(498,550),(508,528),(518,492),(532,475),(541,459),(569,452),(603,440),(640,440),(670,445),(686,451),(710,464),(717,486),(715,502),(732,533),(731,547),(714,552),(701,559),(670,563),(632,568),(589,569),(550,562),(520,559)],(618,493),(606,654),(1.05,1.05)),
'seat_front_right':([(1139,552),(1149,523),(1157,486),(1171,466),(1206,449),(1240,449),(1280,453),(1302,475),(1312,511),(1333,545),(1322,561),(1304,567),(1200,568)],(1228,493),(1236,642),(1.05,1.05)),
'seat_back_left':([(684,439),(701,409),(704,391),(733,381),(785,379),(819,389),(832,416),(838,441),(822,448),(726,450)],(767,411),(748,576),(1.,1.)),
'seat_back_right':([(1008,442),(1025,411),(1030,390),(1058,382),(1107,383),(1142,398),(1150,424),(1163,442),(1150,453),(1110,455),(1044,449)],(1084,413),(1084,581),(.96,.96)),
'hearth':([(748,555),(770,522),(803,513),(820,500),(857,504),(883,498),(900,492),(922,508),(961,507),(974,517),(1008,523),(1046,552),(1040,580),(1013,593),(966,601),(866,608),(804,596),(752,578)],(899,549),(912,714),(1.18,1.18))}
dest=ROOT/'images/rooms/depths_camp';dest.mkdir(parents=True,exist_ok=True)
meta={}
for name,(poly,anchor,position,scale) in definitions.items():
    mask=Image.new('L',(raw.width*4,raw.height*4));ImageDraw.Draw(mask).polygon([(x*4,y*4) for x,y in poly],fill=255)
    mask=mask.resize(raw.size,Image.Resampling.LANCZOS)
    im=raw.copy();im.putalpha(mask);box=im.getbbox();im.crop(box).save(dest/(name+'.png'))
    meta[name]={'anchor':[anchor[0]-box[0],anchor[1]-box[1]],'position':position,'scale':scale,'source_box':box}
(HERE/'props.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
mask=Image.new('L',raw.size,255);d=ImageDraw.Draw(mask)
for box in [(470,365,865,580),(991,365,1360,588),(731,470,1074,629)]:d.rounded_rectangle(box,radius=18,fill=0)
mask=mask.filter(ImageFilter.GaussianBlur(7))
rgba=Image.new('RGBA',raw.size,'white');rgba.putalpha(mask);rgba.save(HERE/'empty_floor_mask.png')
