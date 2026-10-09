"""Extract the selected matriarch, prepare eyelids and native scene/localization contracts."""
from pathlib import Path
import json,shutil,hashlib
import numpy as np
import cv2
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_assets/monsters/leech_mother'
RIG=ROOT/'tools/LeechMotherRig'
PARTS=RIG/'parts'
PARTS.mkdir(parents=True,exist_ok=True)
raw=np.array(Image.open(SOURCE/'character-generated.png').convert('RGB')).astype(float)
rb=np.maximum(raw[:,:,0],raw[:,:,2])
alpha=1-np.clip((raw[:,:,1]-rb)/np.maximum(255-rb,1),0,1)
alpha[alpha<.06]=0
rgb=np.clip((raw-(1-alpha[:,:,None])*np.array([0,255,0]))/np.maximum(alpha[:,:,None],.01),0,255)
rgba=np.concatenate([rgb,alpha[:,:,None]*255],axis=2).astype('uint8')
count,labels,stats,_=cv2.connectedComponentsWithStats((rgba[:,:,3]>8).astype('uint8'),8)
for i in range(1,count):
    if stats[i,cv2.CC_STAT_AREA]<80:rgba[labels==i,3]=0
image=Image.fromarray(rgba)
image.save(SOURCE/'character-final.png')
image.save(PARTS/'skin.png')
meta={'skin':dict(x=0,y=0,w=image.width,h=image.height)}
for name,box,ellipse,line in [
    ('lid_far',(207,386,292,452),(217,405,272,438),[(219,421),(239,432),(265,432)]),
    ('lid_near',(297,428,370,492),(308,446,356,478),[(308,460),(328,474),(353,475)])]:
    x0,y0,x1,y1=box
    patch=rgba[y0:y1,x0:x1].copy()
    mask=np.zeros(patch.shape[:2],np.uint8)
    cv2.ellipse(mask,((ellipse[0]+ellipse[2])//2-x0,(ellipse[1]+ellipse[3])//2-y0),
                ((ellipse[2]-ellipse[0])//2,(ellipse[3]-ellipse[1])//2),0,0,360,255,-1)
    patch[:,:,:3]=cv2.inpaint(patch[:,:,:3],mask,7,cv2.INPAINT_TELEA)
    lid=Image.fromarray(patch)
    draw=ImageDraw.Draw(lid)
    draw.line([(x-x0,y-y0) for x,y in line],fill=(75,42,50,255),width=4,joint='curve')
    # Soft edge blends the painted lid into the moving head surface.
    yy,xx=np.mgrid[:patch.shape[0],:patch.shape[1]]
    edge=np.minimum.reduce([xx,yy,patch.shape[1]-1-xx,patch.shape[0]-1-yy])
    a=np.array(lid);a[:,:,3]=(a[:,:,3]*np.clip(edge/5,0,1)).astype('uint8')
    Image.fromarray(a).save(PARTS/(name+'.png'))
    meta[name]=dict(x=x0,y=y0,w=x1-x0,h=y1-y0)
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
for name in ['rigkit.py','rigutil.py']:
    shutil.copyfile(ROOT/'tools/SanguineLeechRig'/name,RIG/name)
# Eyelid alpha is an ordinary overlay, never a glowing additive patch.
kit=(RIG/'rigkit.py').read_text(encoding='utf-8')
kit=kit.replace("GLOW_OF = getattr(R, 'GLOW_OF', {})","GLOW_OF = getattr(R, 'GLOW_OF', {})\nALPHA_ONLY = set(getattr(R, 'ALPHA_ONLY', ()))")
kit=kit.replace("if base == n: slot_list.append(g)","if base == n and g not in slot_list: slot_list.append(g)")
kit=kit.replace("if n in GLOW_OF: sl['blend'] = 'additive'; sl['color'] = 'ffffff00'",
                "if n in GLOW_OF:\n            sl['color'] = 'ffffff00'\n            if n not in ALPHA_ONLY: sl['blend'] = 'additive'")
kit=kit.replace("add = n in GLOW_OF","add = n in GLOW_OF and n not in ALPHA_ONLY")
kit=kit.replace("amul = self.ga * frame['glow'].get(n, 0) if add else tint[3]",
                "amul = self.ga * frame['glow'].get(n, 0) if n in GLOW_OF else tint[3]")
(RIG/'rigkit.py').write_text(kit,encoding='utf-8')
for lang in ['zhs','eng']:
    def update(name,entries):
        p=ROOT/f'STS2_Things/localization/{lang}/{name}.json'
        values=json.loads(p.read_text(encoding='utf-8-sig'));values.update(entries)
        p.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    moves={'SLEEP':'沉眠','BROOD':'唤子','SIP':'吮血','CRUSH':'重压','REST':'蜷伏'} if lang=='zhs' else {
        'SLEEP':'Slumber','BROOD':'Call the Brood','SIP':'Siphon','CRUSH':'Crush','REST':'Curl Up'}
    update('monsters',{'LEECH_MOTHER.name':'血蛭之母' if lang=='zhs' else 'Leech Mother',
                      **{f'LEECH_MOTHER.moves.{key}.title':value for key,value in moves.items()}})
    update('powers',{'LEECH_MOTHER_SLUMBER_POWER.title':'沉眠' if lang=='zhs' else 'Slumber',
        'LEECH_MOTHER_SLUMBER_POWER.description':
        '再经过[blue]{Amount}[/blue]回合后，若未被攻击，则离开战斗。不会获得战斗奖励。[n]被攻击或受到伤害时醒来。' if lang=='zhs' else
        'After [blue]{Amount}[/blue] more turns without being attacked, leaves combat. No combat rewards are granted.[n]Wakes when attacked or damaged.'})
    update('encounters',{'LEECH_MOTHER_ENCOUNTER.title':'血蛭之母' if lang=='zhs' else 'Leech Mother',
        'LEECH_MOTHER_ENCOUNTER.loss':'{character}惊扰了[gold]{encounter}[/gold]的沉眠。' if lang=='zhs' else
        '{character} disturbed the [gold]{encounter}[/gold] from her slumber.'})
# Follow the existing native icon filenames and atlas contract.
icon=ROOT.parent/'STS2-V111/images/powers/slumber_power.png'
target=ROOT/'images/powers/leech_mother_slumber_power.png';target.parent.mkdir(exist_ok=True)
shutil.copyfile(icon,target)
Image.open(icon).resize((64,64),Image.Resampling.LANCZOS).save(ROOT/'images/powers/leech_mother_slumber_power_packed.png')
atlas=ROOT/'images/atlases/power_atlas.sprites/leech_mother_slumber_power.tres'
atlas.parent.mkdir(parents=True,exist_ok=True)
atlas.write_text('''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/leech_mother_slumber_power_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''',encoding='utf-8')
(ROOT/'scenes/encounters/leech_mother_encounter.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="mother" type="Marker2D" parent="."]
position = Vector2(1430, 713)
[node name="brood_front" type="Marker2D" parent="."]
position = Vector2(910, 757)
[node name="brood_rear" type="Marker2D" parent="."]
position = Vector2(1740, 733)
''',encoding='utf-8')
bg=ROOT/'scenes/backgrounds/leech_mother_encounter'
(bg/'layers').mkdir(parents=True,exist_ok=True)
shutil.copyfile(ROOT/'scenes/backgrounds/sanguine_leech_encounter/sanguine_leech_encounter_background.tscn',bg/'leech_mother_encounter_background.tscn')
for name,source in [('leech_mother_encounter_bg_00_a.tscn','scenes/backgrounds/depths/layers/depths_bg_00_f_hollow_grotto_moss.tscn'),
                    ('leech_mother_encounter_fg_a.tscn','scenes/backgrounds/sanguine_leech_encounter/layers/sanguine_leech_encounter_fg_a.tscn')]:
    shutil.copyfile(ROOT/source,bg/'layers'/name)
Image.fromarray(rgba).crop((68,240,665,750)).resize((88,88),Image.Resampling.LANCZOS).save(ROOT/'images/monsters/leech_mother.png')
(SOURCE/'generation.json').write_text(json.dumps({'model':'gpt-image-2.5-sunburst','endpoint':'https://cpa.yuseus.io/v1/',
    'mode':'official imagegen CLI edit','prompt':'character-prompt.txt',
    'reference':'source_assets/monsters/sanguine_leech/character_final.png','rejected':'character-v1-rejected.png',
    'selection':'new hooded face, tiny slit eyes, toothless sucker and swollen pale body folds',
    'source_sha256':hashlib.sha256((SOURCE/'character-generated.png').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print('Matriarch extracted; lids, native icon, scene slots, background and bilingual text prepared.')
