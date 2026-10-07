"""Prepare the event portrait and an offline layout review using native UI assets.

The review is a Pillow composition, not a game capture or Godot render probe.
"""
from pathlib import Path
import json,re,argparse
from PIL import Image,ImageOps,ImageDraw,ImageFont
from aligned_houses_composite import compose,viewport
ROOT=Path(__file__).resolve().parents[1];NATIVE=ROOT.parent/'STS2-V111'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lang',choices=('zhs','eng'),default='zhs');args=parser.parse_args()
SOURCE=ROOT/'source_assets/events/reality_aligned_houses'
BUILD=ROOT/'build/reality_aligned_houses_radial_fade';BUILD.mkdir(exist_ok=True)
src=ROOT/'output/imagegen/reality_aligned_houses/event_portrait_v3_grassland.png'
art=Image.open(src).convert('RGBA')
background=Image.new('RGBA',art.size,'#0c0e18');background.alpha_composite(art)
art=ImageOps.fit(background,(3440,1616),Image.Resampling.LANCZOS)
art.save(SOURCE/'portrait_unframed.png')
# The full scene continues behind a gradual center-to-periphery light falloff.
art,frame_mask=compose(Image.open(src),width_factor=1.)
frame_mask.save(SOURCE/'peripheral_fade_mask.png')
art.save(ROOT/'images/events/reality_aligned_houses.png')
art.save(SOURCE/'portrait_master.png')
copy=NATIVE/'images/events/field_of_man_sized_holes.png'
if not (SOURCE/'references'/copy.name).exists():
    __import__('shutil').copy2(copy,SOURCE/'references'/copy.name)

values=json.loads((ROOT/f'STS2_Things/localization/{args.lang}/events.json').read_text('utf-8'))
prefix='REALITY_ALIGNED_HOUSES.'
font_path=str(NATIVE/('fonts/zhs/SourceHanSerifSC-Medium.otf' if args.lang=='zhs' else 'fonts/kreon_regular.ttf'))
font=ImageFont.truetype(font_path,26);button_font=ImageFont.truetype(font_path,24)
title_font=ImageFont.truetype(str(NATIVE/('fonts/zhs/SourceHanSerifSC-Bold.otf' if args.lang=='zhs' else 'fonts/spectral_bold.ttf')),36)
small=ImageFont.truetype(font_path,17)
palette={'default':'#fff6e2','gold':'#efcd73','red':'#ef8584','blue':'#88cbe4','purple':'#c89adb'}

def formatted(text):
    variables={'Cards':'1','HpLoss':'10','Curse':'悔恨','AddressMaxHpLoss':'5','SmallGold':'15',
        'RoadHpLoss':'4','Gold':'35','Enchantment':'完美契合' if args.lang=='zhs' else 'Perfect Fit','MaximumLaps':'3','NextLap':'2'}
    for key,value in variables.items():text=text.replace('{'+key+'}',value)
    return text

def rich_lines(text,face,width):
    colour='default';stack=[];line=[];lines=[];length=0
    for token in re.split(r'(\[[^\]]+\])',formatted(text)):
        if token.startswith('['):
            tag=token[1:-1]
            if tag in palette:stack.append(colour);colour=tag
            elif tag.startswith('/') and tag[1:] in palette:colour=stack.pop() if stack else 'default'
            continue
        for char in token:
            if char=='\n':lines.append(line);line=[];length=0;continue
            advance=face.getlength(char)
            if length+advance>width:
                spaces=[i for i,item in enumerate(line) if item[0]==' ']
                if args.lang=='eng' and spaces:
                    split=spaces[-1];lines.append(line[:split]);line=line[split+1:];length=sum(item[2] for item in line)
                else:lines.append(line);line=[];length=0
            if not line and char==' ':continue
            line.append((char,colour,advance));length+=advance
    lines.append(line);return lines

def paint_text(draw,lines,x,y,width,face,line_height,center=True,outline=0):
    for line in lines:
        cursor=x+(width-sum(v[2] for v in line))/2 if center else x
        for char,colour,advance in line:
            baseline=y+face.getmetrics()[0]
            draw.text((cursor+2,baseline+2),char,font=face,fill='#000000',anchor='ls')
            draw.text((cursor,baseline),char,font=face,fill=palette[colour],anchor='ls',
                stroke_width=outline,stroke_fill='#061624');cursor+=advance
        y+=line_height
    return y

def button_background(width=800):
    path=NATIVE/'images/packed/common_ui/event_button.png'
    texture=Image.open(path).convert('RGBA')
    texture=texture.resize((texture.width,100),Image.Resampling.LANCZOS)
    edge=min(192,(texture.width-2)//2)
    result=Image.new('RGBA',(width,100))
    result.paste(texture.crop((0,0,edge,100)).resize((192,100)),(0,0))
    result.paste(texture.crop((edge,0,texture.width-edge,100)).resize((width-384,100)),(192,0))
    result.paste(texture.crop((texture.width-edge,0,texture.width,100)).resize((192,100)),(width-192,0))
    return result

# Portrait placement derives from default_event_layout.tscn (1920x1080 canvas,
# 2560x1200 portrait, 1.04 scale, -39 root offset). No custom in-game layout.
canvas=Image.new('RGBA',(1920,1080),'#0b0c14')
canvas.alpha_composite(art.resize((2662,1251),Image.Resampling.LANCZOS),(-371,-79))
draw=ImageDraw.Draw(canvas)
title=values[prefix+'title'];x=922;width=800;y=236
draw.text((x+(width-title_font.getlength(title))/2,y),title,font=title_font,fill='#efd06d',anchor='lt')
lines=rich_lines(values[prefix+'pages.INITIAL.description'],font,width)
description_height=max(280,len(lines)*34)
paint_text(draw,lines,x,y+64+(description_height-len(lines)*34)/2,width,font,34)
y+=64+description_height+24
button=button_background()
options=[]
for key in ('MERGE','ADDRESS','ROAD','BLUE'):
    canvas.alpha_composite(button,(x,int(y)))
    title=values[prefix+f'pages.INITIAL.options.{key}.title']
    description=values[prefix+f'pages.INITIAL.options.{key}.description']
    draw=ImageDraw.Draw(canvas)
    button_lines=rich_lines('[gold]'+title+'[/gold]\n'+description,button_font,716)
    paint_text(draw,button_lines,x+42,y+13,716,button_font,30,False)
    options.append(dict(key=key,lines=len(button_lines),bottom=y+13+len(button_lines)*30))
    y+=108
caption='离线排版预览 · 使用原版布局尺寸与字体 · 非游戏截图' if args.lang=='zhs' else 'Offline layout composition - not a game capture'
draw.text((22,1048),caption,font=small,fill='#e9eff6',anchor='lt',stroke_width=1,stroke_fill='#253f55')
suffix='' if args.lang=='zhs' else '-eng'
canvas.convert('RGB').save(BUILD/f'event-layout-review{suffix}.jpg',quality=94)
art.convert('RGB').resize((1720,808)).save(BUILD/'event-art.jpg',quality=94)
viewport(art).crop((0,0,1000,1080)).save(BUILD/'illustration-detail.jpg',quality=94)
sheet=Image.new('RGB',(1720,808*2),'#10111b')
for i,path in enumerate((NATIVE/'images/events/abyssal_baths.png',ROOT/'images/events/reality_aligned_houses.png')):
    image=Image.open(path).convert('RGBA').resize((1720,808),Image.Resampling.LANCZOS)
    sheet.paste(image,(0,i*808),image)
    ImageDraw.Draw(sheet).text((20,i*808+20),'Original: Abyssal Baths' if i==0 else 'Aligned Houses: complete landscape fading outward',font=small,fill='#ffefcf')
sheet.save(BUILD/'style-review.jpg',quality=93)
report=dict(source_size=Image.open(src).size,portrait_size=art.size,composition='Full landscape across native portrait; central focal area and continuously darkening peripheral scenery; original text layout retained',black_edge='No silhouette or cutout. Continuous light falloff from the center, with long peripheral tails into black.',description_lines=len(lines),
    approximate_options=options,review='offline Pillow layout, not native rendering')
(BUILD/f'art-layout{suffix}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(report,ensure_ascii=False))
