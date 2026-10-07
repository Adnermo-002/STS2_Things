"""Compose comparison/preview artifacts from generated art and actual runtime captures."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/lantern_fish/review'; OUT.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
board=Image.new('RGB',(1200,550),(35,39,46));draw=ImageDraw.Draw(board)
draw.text((28,22),'画风对照 · 原版鱼类与原创灯笼鱼',font=font,fill=(237,227,196))
vanilla=Image.open(ROOT.parent/'STS2-V111/animations/monsters/soul_fysh/soul_fysh.png').convert('RGBA').crop((565,103,1120,483))
fish=Image.open(ROOT/'source_assets/monsters/lantern_fish/floating_fish_final.png').convert('RGBA')
fish=fish.crop(fish.getbbox())
for i,(im,label) in enumerate([(vanilla,'原版灵魂鱼 · 解包绘画局部'),(fish,'灯笼鱼 · 最终纯鱼形原画')]):
    im.thumbnail((560,365),Image.Resampling.LANCZOS)
    x=20+i*600+(560-im.width)//2;y=103+(365-im.height)//2
    board.paste(im,(x,y),im)
    draw.text((30+i*600,490),label,font=small,fill=(212,222,226))
board.save(OUT/'style_comparison.jpg',quality=95)
frames=[]
for path in sorted((ROOT/'build/lantern_fish/visuals').glob('sequence_*.png')):
    im=Image.open(path).convert('RGB');im.thumbnail((1280,720),Image.Resampling.LANCZOS);frames.append(im)
if len(frames)==24:
    frames[0].save(OUT/'lantern_fish_demo.gif',save_all=True,append_images=frames[1:],duration=83,loop=0,optimize=False)
    frames[0].save(OUT/'lantern_fish_demo.webp',save_all=True,append_images=frames[1:],duration=83,loop=0,quality=85)
poses=['idle_loop','attack','tail_swipe','cast','guard','hurt','die','revive','summon','power_up']
sheet=Image.new('RGB',(1500,1200),(35,39,46));d=ImageDraw.Draw(sheet)
for i,name in enumerate(poses):
    # These crops come from native Spine renders; no character pixels are synthesized.
    p=ROOT/f'build/lantern_fish/visuals/pose_{name}_2.png'
    if p.exists():
        im=Image.open(p).crop((900,420,1300,810));im.thumbnail((285,510),Image.Resampling.LANCZOS)
        x=(i%5)*300;y=(i//5)*600;sheet.paste(im,(x+(300-im.width)//2,y+90))
        d.text((x+15,y+25),name,font=small,fill=(230,226,206))
sheet.save(OUT/'animation_contact_sheet.jpg',quality=93)
print('Review artifacts:',OUT)
