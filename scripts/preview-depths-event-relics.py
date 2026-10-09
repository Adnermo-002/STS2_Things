"""Comparison sheet only; shipped artwork is prepared by the Godot exporter."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
TASK=ROOT/"build/depths-event-relics-20261009"
KEYS=["bottled_echo","shadow_claim_ticket","mycelial_deposit","borrowed_ember","things_medusa_hair"]
REFS=["ink_bottle","meal_ticket","arcane_scroll","ember_tea","silken_tress"]
NAMES=["瓶中回声","寄存收据","菌根存单","余烬约定","美杜莎之发"]
FONT=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",20)
im=Image.new("RGB",(1150,910),(38,44,52));draw=ImageDraw.Draw(im)
for x,title in [(20,"旧版"),(240,"重制"),(440,"原版参考"),(690,"48px"),(830,"32px"),(980,"浅底边缘")]:
    draw.text((x,14),title,font=FONT,fill=(245,239,221))
for i,(key,ref,name) in enumerate(zip(KEYS,REFS,NAMES)):
    y=62+i*164
    for x,path,size in [(20,TASK/"before/icons"/(key+".png"),132),
                       (240,ROOT/"images/relics"/(key+".png"),132),
                       (440,ROOT.parent/"STS2-V111/images/relics"/(ref+".png"),132),
                       (710,ROOT/"images/relics"/(key+"_packed.png"),48),
                       (845,ROOT/"images/relics"/(key+"_packed.png"),32),
                       (970,ROOT/"images/relics"/(key+".png"),100)]:
        icon=Image.open(path).convert("RGBA").resize((size,size),Image.Resampling.LANCZOS)
        if x==970:
            draw.rectangle((x-8,y-8,x+size+8,y+size+8),fill=(223,216,195))
        im.paste(icon,(x,y),icon)
    draw.text((240,y+137),name,font=FONT,fill=(233,229,214))
im.save(TASK/"style-comparison.jpg",quality=96)
print(TASK/"style-comparison.jpg")

final=Image.new("RGB",(1050,252),(38,44,52))
draw=ImageDraw.Draw(final)
for i,(key,name) in enumerate(zip(KEYS,NAMES)):
    icon=Image.open(ROOT/"images/relics"/(key+".png")).convert("RGBA")
    icon.thumbnail((160,160),Image.Resampling.LANCZOS)
    final.paste(icon,(25+i*210+(160-icon.width)//2,20),icon)
    box=draw.textbbox((0,0),name,font=FONT)
    draw.text((i*210+(210-(box[2]-box[0]))//2,202),name,font=FONT,fill=(233,229,214))
final.save(TASK/"final-preview.png")
print(TASK/"final-preview.png")
