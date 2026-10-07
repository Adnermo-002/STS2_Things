"""Prepare both native event portraits, Bottled Echo and offline menu previews."""
from pathlib import Path
import json
import re
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from native_event_preview import render_event

ROOT = Path(__file__).resolve().parents[1]
SIZE = (3440, 1616)
BUILD = ROOT / 'build/well_and_maw'
BUILD.mkdir(parents=True, exist_ok=True)

def smooth(t):
    t = np.clip(t, 0, 1)
    return t*t*t*(t*(t*6-15)+10)

x = np.arange(SIZE[0], dtype=np.float32)[None, :] * (2662/3440) - 371
y = np.arange(SIZE[1], dtype=np.float32)[:, None] * (1251/1616) - 79
radius = ((x-460)/800)**2 + ((y-540)/680)**2
light = (.55 + .45*np.exp(-radius)) * smooth((x+170)/370)
light *= smooth((y+110)/320) * (1-smooth((y-830)/380))
light *= 1-smooth((x-780)/740)
portraits, report = {}, {}
for event in ('echoing_well', 'polite_maw'):
    source = ROOT / f'source_assets/events/{event}'
    output = BUILD / event
    output.mkdir(exist_ok=True)
    raw = Image.open(ROOT / f'output/imagegen/{event}/portrait_v1.png').convert('RGB')
    raw = raw.crop((2, 2, raw.width-2, raw.height-2))
    painting = ImageOps.fit(raw, SIZE, Image.Resampling.LANCZOS)
    painting.save(source / 'portrait_unframed.png')
    portrait = Image.fromarray(np.uint8(np.clip(np.rint(np.asarray(painting)*light[:,:,None]),0,255))).convert('RGBA')
    portrait.save(source / 'portrait_master.png')
    Image.fromarray(np.uint8(np.rint(light*255))).save(source / 'peripheral_fade_mask.png')
    portrait.save(ROOT / f'images/events/{event}.png')
    portrait.convert('RGB').resize((1720,808), Image.Resampling.LANCZOS).save(output / 'event-art.jpg', quality=95)
    portraits[event] = portrait

icon = Image.open(ROOT / 'output/imagegen/echoing_well/bottled_echo_v1.png').convert('RGBA')
rgba = np.array(icon)
alpha = rgba[:,:,3].copy()
alpha[alpha < 12] = 0
magenta = (rgba[:,:,0] > 150) & (rgba[:,:,2] > 150) & (rgba[:,:,1] < 80)
alpha[magenta] = 0
count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha>0).astype('uint8'),8)
if count < 2:
    raise RuntimeError('Bottled Echo has no visible subject')
alpha[labels != 1+np.argmax(stats[1:,cv2.CC_STAT_AREA])] = 0
rgba[:,:,3] = alpha
icon = Image.fromarray(rgba)
icon.save(ROOT / 'source_assets/events/echoing_well/bottled_echo_cutout.png')
icon = icon.resize((256,256), Image.Resampling.LANCZOS)
icon_path = ROOT / 'images/relics/bottled_echo.png'
icon.save(icon_path)
outline = Image.new('RGBA',(256,256),'white')
outline.putalpha(icon.getchannel('A').filter(ImageFilter.MaxFilter(9)))
outline_path = ROOT / 'images/atlases/relic_outline_atlas.sprites/bottled_echo_outline.png'
outline.save(outline_path)
for folder, path in (('relic_atlas.sprites',icon_path),('relic_outline_atlas.sprites',outline_path)):
    texture = 'res://'+path.relative_to(ROOT).as_posix()
    (ROOT/'images/atlases'/folder/'bottled_echo.tres').write_text(
        '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n'
        f'[ext_resource type="Texture2D" path="{texture}" id="1"]\n\n'
        '[resource]\natlas = ExtResource("1")\nregion = Rect2(0, 0, 256, 256)\n','utf-8')
sheet = Image.new('RGBA',(640,320),'#16212b')
sheet.alpha_composite(icon,(24,32))
sheet.alpha_composite(icon.resize((64,64),Image.Resampling.LANCZOS),(350,88))
sheet.alpha_composite(icon.resize((48,48),Image.Resampling.LANCZOS),(490,96))
ImageDraw.Draw(sheet).text((345,182),'64 px',fill='white')
ImageDraw.Draw(sheet).text((482,182),'48 px',fill='white')
sheet.convert('RGB').save(BUILD/'relic-review.jpg',quality=95)

report['echoing_well'] = render_event(ROOT,'ECHOING_WELL',portraits['echoing_well'],{'Combats':3,'SmallGold':15},
                                     ('RECORD','COINS'),BUILD/'echoing_well')
maw_source = (ROOT/'STS2_Things/Events/PoliteMaw.cs').read_text('utf-8')
maw_description_height = int(re.search(r'DescriptionMinimumHeight\s*=\s*(\d+)',maw_source).group(1))
for shared in (False,True):
    mode = 'multiplayer' if shared else 'solo'
    for page, options in [('INITIAL',('ATTACK','SKILL','POWER','CURSE','TIP'))]:
        output = BUILD/'polite_maw' if page=='INITIAL' and not shared else BUILD/'polite_maw'/mode/page.lower()
        report[f'polite_maw_{mode}_{page.lower()}'] = render_event(ROOT,'POLITE_MAW',portraits['polite_maw'],
            {'Gold':50,'SmallGold':15,'Relic':{'zhs':'石化蟾蜍','eng':'Petrified Toad'}},options,output,page=page,shared=shared,
            description_min_height=maw_description_height)
report['review'] = 'Offline Pillow authoring previews, not game captures. Preview relic is an example; actual relic is selected by the native reward pool.'
(BUILD/'art-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(report,ensure_ascii=False))
