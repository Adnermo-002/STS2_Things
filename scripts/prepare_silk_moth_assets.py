"""Prepare the selected Sunburst sprite, separate wing meshes, and native resources."""
from pathlib import Path
import hashlib
import json
import shutil
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/monsters/silk_moth'
RIG = ROOT / 'tools/SilkMothRig'
PARTS = RIG / 'parts'
PARTS.mkdir(parents=True, exist_ok=True)


def cutout(path):
    pixels = np.array(Image.open(path).convert('RGBA'))
    alpha = np.uint8(np.clip((pixels[..., 3].astype(float)-220)/31, 0, 1)*255)
    rgb = pixels[..., :3].astype(float)
    chroma = (rgb[..., 0] > 190) & (rgb[..., 2] > 190) & (rgb[..., 1] < 90)
    alpha[chroma] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype('uint8'))
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] < 24:
            alpha[labels == label] = 0
    pixels[..., 3] = alpha
    pixels[alpha == 0, :3] = 0
    return Image.fromarray(pixels)


shutil.copy2(ROOT / 'output/imagegen/silk_moth_v1.png', SOURCE / 'character_generated.png')
character = cutout(SOURCE / 'character_generated.png')
assert character.size == (1402, 1122)
character.save(SOURCE / 'character_final.png')
polygons = {
    'wing_far': [(0,0),(650,0),(650,466),(620,480),(570,473),(535,448),(488,434),
                 (459,426),(442,411),(453,409),(435,388),(399,365),(365,362),
                 (329,363),(281,389),(249,418),(0,355)],
    'wing_near': [(590,485),(600,449),(695,361),(920,60),(1402,0),(1402,900),
                  (730,902),(655,756),(697,739),(696,701),(675,647),(650,594),
                  (612,552),(596,522)],
}
pixels = np.array(character)
masks = {}
for name, polygon in polygons.items():
    mask = Image.new('L', character.size)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    masks[name] = np.array(mask)
masks['body'] = 255-np.maximum(masks['wing_far'], masks['wing_near'])
yy,xx = np.indices(pixels.shape[:2])
threads = ((yy > 715) & (xx < 615)) | (yy > 795)
tracks = np.stack([abs(xx-(446+.11*(yy-660))),abs(xx-(536+.15*(yy-695))),abs(xx-(548+.45*(yy-695)))])
strand = tracks.argmin(axis=0)
for index,name in enumerate(['silk_a','silk_b','silk_c']):
    masks[name] = np.where(threads & (strand==index),masks['body'],0).astype('uint8')
masks['body'][threads] = 0
meta = {}
for name, mask in masks.items():
    part = pixels.copy()
    part[..., 3] = np.minimum(part[..., 3], mask)
    image = Image.fromarray(part)
    box = image.getbbox()
    image.crop(box).save(PARTS / f'{name}.png')
    meta[name] = dict(x=box[0], y=box[1], w=box[2]-box[0], h=box[3]-box[1])
(PARTS / 'meta.json').write_text(json.dumps(meta, indent=2), 'utf-8')
review = Image.new('RGBA', character.size, '#2a343b')
review.alpha_composite(character)
review.convert('RGB').save(SOURCE / 'character_review.jpg', quality=94)

shutil.copy2(ROOT / 'output/imagegen/silk_thread_power_v1.png', SOURCE / 'power_generated.png')
icon = cutout(SOURCE / 'power_generated.png')
icon.save(SOURCE / 'power_final.png')
icon = ImageOps.contain(icon.crop(icon.getbbox()), (224,224), Image.Resampling.LANCZOS)
big = Image.new('RGBA', (256,256))
big.alpha_composite(icon, ((256-icon.width)//2, (256-icon.height)//2))
big.save(ROOT / 'images/powers/silk_thread_power.png')
big.resize((64,64), Image.Resampling.LANCZOS).save(ROOT / 'images/powers/silk_thread_power_packed.png')
(ROOT / 'images/atlases/power_atlas.sprites/silk_thread_power.tres').write_text('''[gd_resource type="AtlasTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://images/powers/silk_thread_power_packed.png" id="1"]

[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''', 'utf-8')

# Reuse the complete authored moss cavern, so wall, new floor and foreground stay together.
for key, slots in {
    'silk_moth_weak': [('moth',1230,750),('leech_1',1615,740)],
    'silk_moth_encounter': [('moth',1105,735),('leech_1',1430,800),('leech_2',1750,755)],
}.items():
    folder = ROOT / 'scenes/backgrounds' / key
    (folder / 'layers').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'scenes/backgrounds/sponge_leech_encounter/sponge_leech_encounter_background.tscn',
                 folder / f'{key}_background.tscn')
    shutil.copy2(ROOT / 'scenes/backgrounds/depths/layers/depths_bg_00_f_hollow_grotto_moss.tscn',
                 folder / 'layers' / f'{key}_bg_00_a.tscn')
    scene = '''[gd_scene format=3]

[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
'''
    for name,x,y in slots:
        scene += f'\n[node name="{name}" type="Marker2D" parent="."]\nposition = Vector2({x}, {y})\n'
    (ROOT / 'scenes/encounters' / f'{key}.tscn').write_text(scene, 'utf-8')

texts = {
 'zhs': {
  'monsters': {'SILK_MOTH.name':'垂丝蛾','SILK_MOTH.moves.WEAVE_MOVE.title':'牵丝',
               'SILK_MOTH.moves.SWOOP_MOVE.title':'掠翅','SILK_MOTH.moves.FLUTTER_MOVE.title':'连振'},
  'powers': {'SILK_THREAD_POWER.title':'牵丝',
    'SILK_THREAD_POWER.activeDescription':'先打出标记[gold]1[/gold]的手牌，才能打出标记[gold]2[/gold]的手牌。\n任一牌离开手牌、回合结束或垂丝蛾死亡时，解除连线。',
    'SILK_THREAD_POWER.description':'下回合抽牌后，将[blue]2[/blue]张手牌相连。先打出标记[gold]1[/gold]的牌，才能打出标记[gold]2[/gold]的牌。\n任一牌离开手牌、回合结束或垂丝蛾死亡时，解除连线。'},
  'afflictions': {
    'SILK_LEAD.title':'牵丝·1','SILK_LEAD.description':'打出这张牌，解除标记[gold]2[/gold]的牌的限制。',
    'SILK_LEAD.extraCardText':'[gold]牵丝·1[/gold]',
    'SILK_BOUND.title':'牵丝·2','SILK_BOUND.description':'打出标记[gold]1[/gold]的牌前，无法打出这张牌。',
    'SILK_BOUND.extraCardText':'[gold]牵丝·2[/gold]'},
  'encounters': {'SILK_MOTH_WEAK.title':'深处：垂丝来客','SILK_MOTH_WEAK.loss':'{character}被[gold]{encounter}[/gold]缠住了……',
    'SILK_MOTH_ENCOUNTER.title':'深处：丝下蛭群','SILK_MOTH_ENCOUNTER.loss':'{character}没能挣脱[gold]{encounter}[/gold]……'}},
 'eng': {
  'monsters': {'SILK_MOTH.name':'Silk Moth','SILK_MOTH.moves.WEAVE_MOVE.title':'Threadbind',
               'SILK_MOTH.moves.SWOOP_MOVE.title':'Wing Swoop','SILK_MOTH.moves.FLUTTER_MOVE.title':'Ragged Flurry'},
  'powers': {'SILK_THREAD_POWER.title':'Silken Link',
    'SILK_THREAD_POWER.activeDescription':'Play the card marked [gold]1[/gold] to unlock the card marked [gold]2[/gold].\nThe link ends when either card leaves your Hand, at the end of your turn, or when the Silk Moth dies.',
    'SILK_THREAD_POWER.description':'After drawing next turn, link [blue]2[/blue] cards in your Hand. Play the card marked [gold]1[/gold] to unlock the card marked [gold]2[/gold].\nThe link ends when either card leaves your Hand, at the end of your turn, or when the Silk Moth dies.'},
  'afflictions': {
    'SILK_LEAD.title':'Silken Link · 1','SILK_LEAD.description':'Play this card to unlock the card marked [gold]2[/gold].',
    'SILK_LEAD.extraCardText':'[gold]Silken Link · 1[/gold]',
    'SILK_BOUND.title':'Silken Link · 2','SILK_BOUND.description':'Cannot be played until you play the card marked [gold]1[/gold].',
    'SILK_BOUND.extraCardText':'[gold]Silken Link · 2[/gold]'},
  'encounters': {'SILK_MOTH_WEAK.title':'Depths: Hanging Threads','SILK_MOTH_WEAK.loss':'{character} was caught in the [gold]{encounter}[/gold].',
    'SILK_MOTH_ENCOUNTER.title':'Depths: Silken Colony','SILK_MOTH_ENCOUNTER.loss':'{character} could not escape the [gold]{encounter}[/gold].'}},
}
for language, tables in texts.items():
    for table, additions in tables.items():
        path = ROOT / f'STS2_Things/localization/{language}/{table}.json'
        existing = path.read_text('utf-8-sig') if path.exists() else '{}\n'
        current = json.loads(existing)
        missing = {key:value for key,value in additions.items() if key not in current}
        if missing:
            prefix = existing[:existing.rfind('}')].rstrip()
            if not prefix.endswith('{'): prefix += ','
            path.write_text(prefix+'\n'+json.dumps(missing,ensure_ascii=False,indent=2)[2:-2]+'\n}\n','utf-8')

presets = ROOT / 'export_presets.cfg'
content = presets.read_text('utf-8-sig')
extra = ','.join('STS2_Things/animations/monsters/silk_moth/'+suffix for suffix in ['*.atlas','*.spatlas','*.spjson','silk_moth.png'])
if 'monsters/silk_moth/' not in content:
    presets.write_text('\n'.join(line[:-1]+','+extra+'"' if line.startswith('include_filter="') else line for line in content.splitlines())+'\n','utf-8')
(SOURCE / 'generation.json').write_text(json.dumps({
 'model':'gpt-image-2.5-sunburst','mode':'imagegen bundled CLI edit with vanilla style references',
 'prompts':['character_prompt.txt','power_prompt.txt'],'quality':'high',
 'references':['STS2-V111/animations/monsters/thieving_hopper/thievinghopper.png',
               'STS2-V111/animations/monsters/wriggler/wriggler.png','source_assets/ui/depths_icons_v2/reference_native.png'],
 'files':{name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in
          ['character_generated.png','character_final.png','power_generated.png','power_final.png']}
},ensure_ascii=False,indent=2),'utf-8')
print('Prepared moth cutouts, native icon, encounters, complete moss cavern and localization.')
