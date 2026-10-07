"""Compose two continuous event portraits and native icon sizes from selected art."""
from pathlib import Path
import json, shutil
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from native_event_preview import render_event

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_assets/events/medusa_cutting_refresh_20261007'
BUILD=ROOT/'build/medusa-cutting-refresh-20261007'
SIZE=(3440,1616)

def backup(path):
    destination=SOURCE/'before'/path.relative_to(ROOT)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and not destination.exists(): shutil.copy2(path,destination)

def smooth(t):
    t=np.clip(t,0,1)
    return t*t*t*(t*(t*6-15)+10)

def portrait(raw):
    # Retain the whole painted figure instead of cropping a 3:2 painting into
    # the game's wide overscan. Unpainted margins lie outside the visible art;
    # the long light field reaches zero before either margin can form an edge.
    src=Image.open(raw).convert('RGB')
    scene=Image.new('RGB',SIZE,'black')
    resized=src.resize((round(src.width*SIZE[1]/src.height),SIZE[1]),Image.Resampling.LANCZOS)
    scene.paste(resized,(400,0))
    x=np.arange(SIZE[0],dtype=np.float32)[None,:]*(2662/3440)-371
    y=np.arange(SIZE[1],dtype=np.float32)[:,None]*(1251/1616)-79
    ambient=.80+.20*np.exp(-((x-510)/1000)**2-((y-540)/850)**2)
    light=ambient*smooth((x+210)/480)*(1-smooth((x-690)/830))
    light*=.70+.30*smooth((y+80)/380)
    light*=1-.60*smooth((y-850)/440)
    pixels=np.asarray(scene,dtype=np.float32)*light[:,:,None]
    return Image.fromarray(np.uint8(np.clip(np.rint(pixels),0,255))).convert('RGBA'),Image.fromarray(np.uint8(np.rint(light*255)))

def icon(raw,size,margin):
    src=Image.open(raw).convert('RGBA')
    alpha=src.getchannel('A')
    assert alpha.getextrema()==(0,255), 'Generated icon must have real transparent alpha'
    # Discard only imperceptible specks, retaining antialiased silhouette edges.
    alpha=alpha.point(lambda value:0 if value<=3 else value)
    src.putalpha(alpha)
    box=alpha.getbbox();assert box
    src=src.crop(box);src.thumbnail((size-2*margin,size-2*margin),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(size,size));canvas.alpha_composite(src,((size-src.width)//2,(size-src.height)//2))
    return canvas

def build():
    BUILD.mkdir(parents=True,exist_ok=True)
    SOURCE.mkdir(parents=True,exist_ok=True)
    media={}
    for event,raw in [('things_medusa','medusa-raw-v2.png'),('cutting_it_close','cutting-raw-v1.png')]:
        destination=ROOT/f'images/events/{event}.png';backup(destination)
        final,matte=portrait(SOURCE/raw);final.save(destination)
        matte.save(SOURCE/f'{event}-light-field.png')
        final.save(SOURCE/f'{event}-final.png')
        media[event]={'raw':raw,'portrait_size':SIZE,'continuous_light_field':True}
    hair=icon(SOURCE/'hair-raw-v1.png',256,22)
    p=ROOT/'images/relics/things_medusa_hair.png';backup(p);hair.save(p)
    outline=Image.new('RGBA',(256,256),'white');outline.putalpha(hair.getchannel('A').filter(ImageFilter.MaxFilter(13)))
    p=ROOT/'images/atlases/relic_outline_atlas.sprites/things_medusa_hair_outline.png';backup(p);outline.save(p)
    split=icon(SOURCE/'split-raw-v1.png',64,5)
    p=ROOT/'images/enchantments/things_split.png';backup(p);split.save(p)
    icons=Image.new('RGB',(1000,420),'#171b22');d=ImageDraw.Draw(icons)
    for i,(name,im) in enumerate([('Medusa hair',hair),('Split',split)]):
        for j,size in enumerate([256,64,32]):
            sample=im.resize((size,size),Image.Resampling.LANCZOS)
            x=i*500+[20,320,410][j];y=70
            icons.paste(sample,(x,y),sample);d.text((x,32),f'{name} {size}px',fill='white')
    icons.save(BUILD/'icon-scale-review.png')
    layouts={}
    specs=[('THINGS_MEDUSA','things_medusa',{'Gold':75},['RETURN_TO_OWNER','OFFER_GOLD','GREET'],['RETURN_TO_OWNER','OFFER_GOLD','GREET']),
           ('CUTTING_IT_CLOSE','cutting_it_close',{'Enchantment':{'zhs':'分裂','eng':'Split'}},['IMPROVISE','THROW'],['IMPROVISE','THROW','ABORTED'])]
    for event,asset,variables,options,pages in specs:
        final=Image.open(ROOT/f'images/events/{asset}.png').convert('RGBA')
        layouts[event]=render_event(ROOT,event,final,variables,options,BUILD/asset/'initial')
        for page in pages:
            render_event(ROOT,event,final,variables,[],BUILD/asset/page.lower(),page=page)
        if event=='THINGS_MEDUSA':
            render_event(ROOT,event,final,variables,['RETURN_TO_OWNER_LOCKED','OFFER_GOLD_LOCKED','GREET'],BUILD/asset/'locked')
    (BUILD/'layout-report.json').write_text(json.dumps(layouts,ensure_ascii=False,indent=2),encoding='utf-8')
    (SOURCE/'asset-record.json').write_text(json.dumps({'model':'gpt-image-2.5-sunburst','endpoint':'https://cpa.yuseus.io/v1/','mode':'official ImageGen CLI edit with original style references','selected':media,'icons':{'hair':256,'hair_outline':256,'split':64},'prompts':['medusa-prompt.txt','medusa-refine-prompt.txt','cutting-prompt.txt','hair-prompt.txt','split-prompt.txt']},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Composed native portraits, alpha icons, outline and bilingual page previews.')

if __name__=='__main__':build()
