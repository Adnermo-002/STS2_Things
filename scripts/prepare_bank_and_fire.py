"""Build the bank/fire assets and review every custom Depths event's live options."""
from pathlib import Path
import json,re
import numpy as np
import cv2
from PIL import Image,ImageOps,ImageFilter,ImageDraw
from native_event_preview import render_event

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/bank_and_fire'
BUILD.mkdir(parents=True,exist_ok=True)
SIZE=(3440,1616)

def smooth(t):
    t=np.clip(t,0,1)
    return t*t*t*(t*(t*6-15)+10)

x=np.arange(SIZE[0],dtype=np.float32)[None,:]*(2662/3440)-371
y=np.arange(SIZE[1],dtype=np.float32)[:,None]*(1251/1616)-79
radius=((x-460)/800)**2+((y-540)/680)**2
light=(.55+.45*np.exp(-radius))*smooth((x+170)/370)
light*=smooth((y+110)/320)*(1-smooth((y-830)/380))
light*=1-smooth((x-780)/740)
for event in ('mycelial_bank','unlit_fire'):
    source=ROOT/f'source_assets/events/{event}'
    raw=Image.open(ROOT/f'output/imagegen/{event}/portrait_v1.png').convert('RGB')
    raw=raw.crop((2,2,raw.width-2,raw.height-2))
    painting=ImageOps.fit(raw,SIZE,Image.Resampling.LANCZOS)
    painting.save(source/'portrait_unframed.png')
    portrait=Image.fromarray(np.uint8(np.clip(np.rint(np.asarray(painting)*light[:,:,None]),0,255))).convert('RGBA')
    portrait.save(source/'portrait_master.png')
    portrait.save(ROOT/f'images/events/{event}.png')
    Image.fromarray(np.uint8(np.rint(light*255))).save(source/'peripheral_fade_mask.png')

icons={}
for event,raw_name,relic in (('mycelial_bank','receipt','mycelial_deposit'),('unlit_fire','ember','borrowed_ember')):
    icon=Image.open(ROOT/f'output/imagegen/{event}/{raw_name}_v1.png').convert('RGBA')
    rgba=np.array(icon)
    alpha=rgba[:,:,3].copy()
    alpha[alpha<12]=0
    alpha[(rgba[:,:,0]>150)&(rgba[:,:,2]>150)&(rgba[:,:,1]<80)]=0
    count,labels,stats,_=cv2.connectedComponentsWithStats((alpha>0).astype('uint8'),8)
    if count<2: raise RuntimeError('Empty icon: '+relic)
    alpha[labels!=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])]=0
    rgba[:,:,3]=alpha
    icon=Image.fromarray(rgba)
    icon.save(ROOT/f'source_assets/events/{event}/{relic}_cutout.png')
    icon=icon.resize((256,256),Image.Resampling.LANCZOS)
    image_path=ROOT/f'images/relics/{relic}.png'
    icon.save(image_path)
    outline=Image.new('RGBA',(256,256),'white')
    outline.putalpha(icon.getchannel('A').filter(ImageFilter.MaxFilter(9)))
    outline_path=ROOT/f'images/atlases/relic_outline_atlas.sprites/{relic}_outline.png'
    outline.save(outline_path)
    for folder,path in (('relic_atlas.sprites',image_path),('relic_outline_atlas.sprites',outline_path)):
        texture='res://'+path.relative_to(ROOT).as_posix()
        (ROOT/'images/atlases'/folder/f'{relic}.tres').write_text(
            '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n'
            f'[ext_resource type="Texture2D" path="{texture}" id="1"]\n\n'
            '[resource]\natlas = ExtResource("1")\nregion = Rect2(0, 0, 256, 256)\n','utf-8')
    icons[relic]=icon

# Rest-site icons use a plain light silhouette, derived from the finished relic.
option=Image.new('RGBA',(256,256),'#eee2cc')
option.putalpha(icons['borrowed_ember'].getchannel('A'))
rest_path=ROOT/'images/ui/rest_site/option_things_spent_ember.png'
rest_path.parent.mkdir(parents=True,exist_ok=True)
option.save(rest_path)

sheet=Image.new('RGBA',(900,340),'#18222b')
for i,(name,icon) in enumerate(icons.items()):
    sheet.alpha_composite(icon,(i*430+10,20))
    sheet.alpha_composite(icon.resize((64,64),Image.Resampling.LANCZOS),(i*430+282,60))
    sheet.alpha_composite(icon.resize((48,48),Image.Resampling.LANCZOS),(i*430+352,70))
    ImageDraw.Draw(sheet).text((i*430+24,290),name,fill='white')
sheet.convert('RGB').save(BUILD/'icons-review.jpg',quality=95)

specs=[
 ('mycelial_bank','MYCELIAL_BANK',('SHORT','LONG','GIFT'),
  {'HpLoss':12,'Heal':6,'Payments':3,'MaxHpCost':6,'MaxHpReturn':12,'SmallGold':15},280),
 ('unlit_fire','UNLIT_FIRE',('REST','SMITH','FUEL','CHARCOAL'),
  {'Heal':24,'Gold':25,'BonusHeal':12,'SmallGold':15},220),
 ('polite_maw','POLITE_MAW',('ATTACK','SKILL','POWER','CURSE','TIP'),
  {'Gold':50,'SmallGold':15,'Relic':{'zhs':'石化蟾蜍','eng':'Petrified Toad'}},144),
 ('shadow_cloakroom','SHADOW_CLOAKROOM',('DEPOSIT','COINS'),{'Gold':25,'Cards':1,'SmallGold':15},280),
 ('echoing_well','ECHOING_WELL',('RECORD','COINS'),{'Combats':3,'SmallGold':15},280),
 ('reality_aligned_houses','REALITY_ALIGNED_HOUSES',('MERGE','ADDRESS','ROAD','BLUE'),
  {'Gold':35,'SmallGold':15,'AddressMaxHpLoss':5,'RoadHpLoss':4,'Enchantment':{'zhs':'完美契合','eng':'Perfect Fit'}},280),
]
report={}
for event,event_id,options,values,minimum in specs:
    art=Image.open(ROOT/f'images/events/{event}.png').convert('RGBA')
    report[event]=render_event(ROOT,event_id,art,values,options,BUILD/event,description_min_height=minimum)
    if event=='polite_maw':
        report['polite_maw_multiplayer']=render_event(ROOT,event_id,art,values,options,BUILD/event/'multiplayer',
            shared=True,description_min_height=minimum)
report['review']='Offline Pillow layout; not a native or gameplay capture. Fire healing and relic names are preview examples.'
(BUILD/'art-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
overview=Image.new('RGB',(2560,720),'black')
for i,event in enumerate(('mycelial_bank','unlit_fire')):
    overview.paste(Image.open(BUILD/event/'event-layout-review.jpg').resize((1280,720),Image.Resampling.LANCZOS),(i*1280,0))
overview.save(BUILD/'new-events-overview.jpg',quality=95)
print(json.dumps({k:v for k,v in report.items() if k in ('mycelial_bank','unlit_fire','polite_maw_multiplayer')},ensure_ascii=False))
