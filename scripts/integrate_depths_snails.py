"""Native encounter/visual resources, generated UI art and concise localizations."""
from pathlib import Path
import json,shutil
from PIL import Image,ImageOps,ImageDraw
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
NAMES=('crystal_snail','slime_snail','rock_snail')
SCALES=(.215,.22,.225)
HEIGHTS=(198,190,164)
for name,scale,height in zip(NAMES,SCALES,HEIGHTS):
    folder=ROOT/f'STS2_Things/animations/monsters/{name}'
    shell=name!='slime_snail'
    shellres=f'[ext_resource type="Texture2D" path="res://STS2_Things/animations/monsters/{name}/shell.png" id="3"]' if shell else ''
    offset=json.loads((folder/'shell-offset.json').read_text()) if shell else dict(x=0,y=0)
    shellnodes=f'''[node name="ShellSocket" type="SpineBoneNode" parent="Visuals"]
bone_name = "shell"
[node name="Shell" type="Sprite2D" parent="Visuals/ShellSocket"]
position = Vector2({offset['x']},{offset['y']})
texture = ExtResource("3")
''' if shell else ''
    scene=f'''[gd_scene load_steps={6 if shell else 5} format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NDepthsSnailVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/{name}/{name}_skel_data.tres" id="2"]
{shellres}
[sub_resource type="Gradient" id="ShadowGradient"]
offsets = PackedFloat32Array(0,0.5,1)
colors = PackedColorArray(0.025,0.035,0.05,0.30,0.025,0.035,0.05,0.16,0.025,0.035,0.05,0)
[sub_resource type="GradientTexture2D" id="Shadow"]
gradient = SubResource("ShadowGradient")
width = 512
height = 64
fill = 1
fill_from = Vector2(0.5,0.5)
fill_to = Vector2(0.5,1)
[node name="{name}" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
position = Vector2(9,-1)
scale = Vector2({.56 if shell else .51},0.23)
texture = SubResource("Shadow")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2({scale},{scale})
{shellnodes}
[node name="MouthSocket" type="SpineBoneNode" parent="Visuals"]
bone_name = "mouth"
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -159.0
offset_top = -{height}.0
offset_right = 154.0
offset_bottom = 12.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-7,-{int(height*.46)})
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-10,-{height+42})
'''
    (ROOT/f'scenes/creature_visuals/{name}.tscn').write_text(scene,'utf-8')

enc='snail_trio_weak';bg=ROOT/f'scenes/backgrounds/{enc}'
(bg/'layers').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'scenes/backgrounds/sponge_leech_weak/sponge_leech_weak_background.tscn',bg/f'{enc}_background.tscn')
shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_c_cave_quartz.tscn',bg/f'layers/{enc}_bg_00_a.tscn')
(ROOT/f'scenes/encounters/{enc}.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="crystal" type="Marker2D" parent="."]
position = Vector2(1105,825)
[node name="slime" type="Marker2D" parent="."]
position = Vector2(1405,808)
[node name="rock" type="Marker2D" parent="."]
position = Vector2(1680,738)
''','utf-8')

# The generated shell is normalized to the native 256 / 64 icon convention.
icon=Image.open(ROOT/'output/imagegen/depths_snails/shell_icon_v1.png').convert('RGBA')
pixels=np.array(icon);pixels[...,3]=np.uint8(np.clip((pixels[...,3].astype(float)-160)/80,0,1)*255)
icon=Image.fromarray(pixels);icon=icon.crop(icon.getbbox())
big=Image.new('RGBA',(256,256));thumb=ImageOps.contain(icon,(222,222),Image.Resampling.LANCZOS)
big.paste(thumb,((256-thumb.width)//2,(256-thumb.height)//2))
big.save(ROOT/'images/powers/snail_shell_power.png')
big.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/'images/powers/snail_shell_power_packed.png')
(ROOT/'images/atlases/power_atlas.sprites/snail_shell_power.tres').write_text('''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/snail_shell_power_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0,0,64,64)
''','utf-8')
portrait=Image.open(ROOT/'output/imagegen/depths_snails/crystal_chip_portrait_v1.png').convert('RGBA')
back=Image.new('RGBA',portrait.size,'#35273e');back.alpha_composite(portrait)
dest=ROOT/'images/packed/card_portraits/token';dest.mkdir(parents=True,exist_ok=True)
ImageOps.fit(back.convert('RGB'),(250,190),centering=(.48,.48)).save(dest/'snail_crystal_chip.png')
master=ROOT/'source_assets/monsters/depths_snails/ui';master.mkdir(exist_ok=True)
big.save(master/'shell_icon.png');back.save(master/'crystal_chip_portrait.png')

text={
'zhs':{
 'monsters':{'CRYSTAL_SNAIL.name':'晶壳蜗牛','SLIME_SNAIL.name':'涎丝蜗牛','ROCK_SNAIL.name':'爬岩蜗牛',
 'CRYSTAL_SNAIL.moves.BUMP_MOVE.title':'撞击','CRYSTAL_SNAIL.moves.BARE_BUMP_MOVE.title':'撞击',
 'CRYSTAL_SNAIL.moves.RETREAT_MOVE.title':'缩壳','SLIME_SNAIL.moves.SPIT_MOVE.title':'吐涎',
 'SLIME_SNAIL.moves.REPAIR_MOVE.title':'补壳','SLIME_SNAIL.moves.BITE_MOVE.title':'顶撞',
 'ROCK_SNAIL.moves.CRAWL_2_MOVE.title':'爬行','ROCK_SNAIL.moves.CRAWL_1_MOVE.title':'爬行',
 'ROCK_SNAIL.moves.CRUSH_MOVE.title':'碾压','ROCK_SNAIL.moves.RECOIL_MOVE.title':'缩回',
 'ROCK_SNAIL.crawlLabel':'{Remaining}'},
 'powers':{'SNAIL_SHELL_POWER.title':'壳',
 'SNAIL_SHELL_POWER.description':'回合开始时不会失去[gold]格挡[/gold]。\n[gold]格挡[/gold]耗尽时破壳。',
 'SNAIL_SHELL_POWER.breakTitle':'破壳',
 'SNAIL_SHELL_POWER.crystalBreak':'每名玩家的弃牌堆加入一张[gold]晶片[/gold]。不再缩壳。',
 'SNAIL_SHELL_POWER.rockBreak':'碾压延后一回合。',
 'ROCK_CRAWL_STATE_POWER.title':'爬行进度','ROCK_CRAWL_STATE_POWER.description':'保存爬行进度。',
 'ROCK_CRAWL_STATE_POWER.intentDescription':'这个敌人将获得[gold]格挡[/gold]并爬行。\n再爬行[blue]{Remaining}[/blue]次后碾压。'},
 'cards':{'SNAIL_CRYSTAL_CHIP.title':'晶片','SNAIL_CRYSTAL_CHIP.description':'造成{Damage:diff()}点伤害。'},
 'encounters':{'SNAIL_TRIO_WEAK.title':'洞穴蜗牛','SNAIL_TRIO_WEAK.loss':'{character}被[gold]{encounter}[/gold]追上了。'}},
'eng':{
 'monsters':{'CRYSTAL_SNAIL.name':'Crystal Snail','SLIME_SNAIL.name':'Slime Snail','ROCK_SNAIL.name':'Rock Snail',
 'CRYSTAL_SNAIL.moves.BUMP_MOVE.title':'Bump','CRYSTAL_SNAIL.moves.BARE_BUMP_MOVE.title':'Bump',
 'CRYSTAL_SNAIL.moves.RETREAT_MOVE.title':'Withdraw','SLIME_SNAIL.moves.SPIT_MOVE.title':'Spit',
 'SLIME_SNAIL.moves.REPAIR_MOVE.title':'Mend Shell','SLIME_SNAIL.moves.BITE_MOVE.title':'Nudge',
 'ROCK_SNAIL.moves.CRAWL_2_MOVE.title':'Crawl','ROCK_SNAIL.moves.CRAWL_1_MOVE.title':'Crawl',
 'ROCK_SNAIL.moves.CRUSH_MOVE.title':'Crush','ROCK_SNAIL.moves.RECOIL_MOVE.title':'Recoil',
 'ROCK_SNAIL.crawlLabel':'{Remaining}'},
 'powers':{'SNAIL_SHELL_POWER.title':'Shell',
 'SNAIL_SHELL_POWER.description':'[gold]Block[/gold] is not removed at the start of the turn.\nBreaks when [gold]Block[/gold] is depleted.',
 'SNAIL_SHELL_POWER.breakTitle':'Shell Break',
 'SNAIL_SHELL_POWER.crystalBreak':"Add a [gold]Crystal Chip[/gold] to each player's discard pile. Stops withdrawing.",
 'SNAIL_SHELL_POWER.rockBreak':'Delay Crush by one turn.',
 'ROCK_CRAWL_STATE_POWER.title':'Crawl Progress','ROCK_CRAWL_STATE_POWER.description':'Tracks remaining crawls.',
 'ROCK_CRAWL_STATE_POWER.intentDescription':'This enemy intends to gain [gold]Block[/gold] and crawl.\nCrush follows [blue]{Remaining}[/blue] more crawls.'},
 'cards':{'SNAIL_CRYSTAL_CHIP.title':'Crystal Chip','SNAIL_CRYSTAL_CHIP.description':'Deal {Damage:diff()} damage.'},
 'encounters':{'SNAIL_TRIO_WEAK.title':'Cave Snails','SNAIL_TRIO_WEAK.loss':'{character} was overtaken by the [gold]{encounter}[/gold].'}}}
for lang,tables in text.items():
    for table,entries in tables.items():
        path=ROOT/f'STS2_Things/localization/{lang}/{table}.json';values=json.loads(path.read_text('utf-8-sig'))
        values.update(entries);path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')
path=ROOT/'export_presets.cfg';data=path.read_text('utf-8')
for name in NAMES:
    if f'/{name}/*.spjson' in data:continue
    i=data.index('"',data.index('include_filter="')+len('include_filter="'))
    added=','.join(f'STS2_Things/animations/monsters/{name}/*.{suffix}' for suffix in ('atlas','spatlas','spjson','png'))
    data=data[:i]+','+added+data[i:]
path.write_text(data,'utf-8')
print('Integrated three snails, one Depths weak encounter, native power/card assets and two locales.')
