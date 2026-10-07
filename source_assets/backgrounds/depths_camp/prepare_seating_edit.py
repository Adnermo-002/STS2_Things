from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
base=Image.open(ROOT/'images/rooms/depths_camp/depths_camp_00.png').convert('RGBA')
base.save(HERE/'seating_edit_target.png')
actors=Image.open(ROOT/'build/depths/camp_review/native_actors_transparent.png').convert('RGBA')
actors=actors.resize((1422,800),Image.Resampling.LANCZOS)
guide=base.copy();guide.alpha_composite(actors,(310,48))
draw=ImageDraw.Draw(guide)
planes=[(717,587,838,587),(1185,581,1300,581),(832,532,930,532),(1076,533,1170,533)]
for x1,y1,x2,y2 in planes:draw.line((x1,y1,x2,y2),fill=(240,58,199,255),width=5)
draw.ellipse((991,615,1021,645),outline=(240,58,199,255),width=4)
guide.save(HERE/'native_seating_guide.png')
mask=Image.new('L',base.size,255);d=ImageDraw.Draw(mask)
for box in [(560,385,945,704),(1050,390,1510,700),(887,539,1215,743)]:d.rounded_rectangle(box,radius=28,fill=0)
mask=mask.filter(ImageFilter.GaussianBlur(8))
rgba=Image.new('RGBA',base.size,'white');rgba.putalpha(mask);rgba.save(HERE/'seating_edit_mask.png')
