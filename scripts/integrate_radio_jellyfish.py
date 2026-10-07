"""Native scenes, original Depths backdrop, and bilingual receiver descriptions."""
from pathlib import Path
import json,shutil

ROOT=Path(__file__).resolve().parents[1]
scene='''[gd_scene load_steps=7 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NRadioJellyfishVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/radio_jellyfish/radio_jellyfish_skel_data.tres" id="2"]
[ext_resource type="Texture2D" path="res://images/vfx/radio_channel_0.png" id="3"]
[ext_resource type="Texture2D" path="res://images/vfx/radio_channel_1.png" id="4"]
[sub_resource type="Gradient" id="ShadowGradient"]
offsets = PackedFloat32Array(0,0.55,1)
colors = PackedColorArray(0.025,0.04,0.05,0.25,0.025,0.04,0.05,0.11,0.025,0.04,0.05,0)
[sub_resource type="GradientTexture2D" id="Shadow"]
gradient = SubResource("ShadowGradient")
width = 512
height = 64
fill = 1
fill_from = Vector2(0.5,0.5)
fill_to = Vector2(0.5,1)
[node name="RadioJellyfish" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
position = Vector2(0,-2)
scale = Vector2(0.57,0.32)
texture = SubResource("Shadow")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2(0.32,0.32)
[node name="Channel0" type="SpineBoneNode" parent="Visuals"]
bone_name = "channel_0"
[node name="Light" type="Sprite2D" parent="Visuals/Channel0"]
texture = ExtResource("3")
modulate = Color(1,1,1,0)
[node name="Channel1" type="SpineBoneNode" parent="Visuals"]
bone_name = "channel_1"
[node name="Light" type="Sprite2D" parent="Visuals/Channel1"]
texture = ExtResource("4")
modulate = Color(1,1,1,0)
[node name="Voice" type="SpineBoneNode" parent="Visuals"]
bone_name = "voice"
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -245.0
offset_top = -470.0
offset_right = 225.0
offset_bottom = 12.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0,-274)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-4,-515)
'''
(ROOT/'scenes/creature_visuals/radio_jellyfish.tscn').write_text(scene,'utf-8')
key='radio_jellyfish_elite';folder=ROOT/f'scenes/backgrounds/{key}'
(folder/'layers').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'scenes/backgrounds/sponge_leech_weak/sponge_leech_weak_background.tscn',folder/f'{key}_background.tscn')
shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_h_hollow_grotto_violet.tscn',folder/f'layers/{key}_bg_00_a.tscn')
(ROOT/f'scenes/encounters/{key}.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="jellyfish" type="Marker2D" parent="."]
position = Vector2(1450,819)
''','utf-8')

zhs='在回放回合，记录每名玩家前[blue]2[/blue]张攻击或技能牌。\n每层使回放伤害和技能回音的[gold]格挡[/gold]提高[blue]{BonusPerStack}[/blue]点。'
eng="On replay turns, record each player's first [blue]2[/blue] Attacks or Skills.\nEach stack increases replay damage and Skill Echo [gold]Block[/gold] by [blue]{BonusPerStack}[/blue]."
tables={
 'zhs':{
  'monsters':{'RADIO_JELLYFISH.name':'收音水母','RADIO_JELLYFISH.moves.TUNE_MOVE.title':'调频'},
  'encounters':{'RADIO_JELLYFISH_ELITE.title':'收音水母','RADIO_JELLYFISH_ELITE.loss':'{character}被[gold]{encounter}[/gold]的回音淹没了。'},
  'powers':{
   'RADIO_RECEPTION_POWER.title':'收音',
   'RADIO_RECEPTION_STATE_POWER.title':'收音序列',
   'RADIO_RECEPTION_STATE_POWER.description':'保存当前收音序列。',
   'RADIO_RECEPTION_POWER.description':zhs,
   'RADIO_RECEPTION_POWER.smartDescription':'在回放回合，记录每名玩家前[blue]2[/blue]张攻击或技能牌。\n回放伤害和技能回音的[gold]格挡[/gold]提高[blue]{ReplayBonus}[/blue]点。',
   'RADIO_RECEPTION_POWER.attackTitle':'攻击回音',
   'RADIO_RECEPTION_POWER.attackDescription':'每格攻击录音对所有玩家造成[blue]{EchoDamage}[/blue]点伤害。\n回放结束时，再攻击一次。',
   'RADIO_RECEPTION_POWER.skillTitle':'技能回音',
   'RADIO_RECEPTION_POWER.skillDescription':'每个技能录音使其获得[blue]{ShieldPerSkill}[/blue]点[gold]格挡[/gold]。'}},
 'eng':{
  'monsters':{'RADIO_JELLYFISH.name':'Receiver Jellyfish','RADIO_JELLYFISH.moves.TUNE_MOVE.title':'Tune In'},
  'encounters':{'RADIO_JELLYFISH_ELITE.title':'Receiver Jellyfish','RADIO_JELLYFISH_ELITE.loss':'{character} was drowned in the [gold]{encounter}[/gold]\'s echoes.'},
  'powers':{
   'RADIO_RECEPTION_POWER.title':'Reception',
   'RADIO_RECEPTION_STATE_POWER.title':'Reception Sequence',
   'RADIO_RECEPTION_STATE_POWER.description':'Tracks the current recording sequence.',
   'RADIO_RECEPTION_POWER.description':eng,
   'RADIO_RECEPTION_POWER.smartDescription':"On replay turns, record each player's first [blue]2[/blue] Attacks or Skills.\nReplay damage and Skill Echo [gold]Block[/gold] are increased by [blue]{ReplayBonus}[/blue].",
   'RADIO_RECEPTION_POWER.attackTitle':'Attack Echo',
   'RADIO_RECEPTION_POWER.attackDescription':'Each slot containing an Attack deals [blue]{EchoDamage}[/blue] damage to ALL players.\nAttack once more after replaying.',
   'RADIO_RECEPTION_POWER.skillTitle':'Skill Echo',
   'RADIO_RECEPTION_POWER.skillDescription':'Gain [blue]{ShieldPerSkill}[/blue] [gold]Block[/gold] for each recorded Skill.'}},
}
for lang,data in tables.items():
    for a in range(4):
        for b in range(4):
            data['monsters'][f'RADIO_JELLYFISH.moves.REPLAY_{a}_{b}_MOVE.title']='回放' if lang=='zhs' else 'Playback'
            data['monsters'][f'RADIO_JELLYFISH.moves.REPLAY_SECOND_{a}_{b}_MOVE.title']='回放' if lang=='zhs' else 'Playback'
    for table,entries in data.items():
        path=ROOT/f'STS2_Things/localization/{lang}/{table}.json'
        values=json.loads(path.read_text('utf-8-sig'))
        if table=='powers':
            values={key:value for key,value in values.items()
                    if not key.startswith('RADIO_RECEPTION_POWER.smartDescription_')}
        values.update(entries)
        path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')

path=ROOT/'export_presets.cfg';text=path.read_text('utf-8')
if '/radio_jellyfish/*.atlas' not in text:
    marker='include_filter="';i=text.index('"',text.index(marker)+len(marker))
    text=text[:i]+',STS2_Things/animations/monsters/radio_jellyfish/*.atlas,STS2_Things/animations/monsters/radio_jellyfish/*.spatlas,STS2_Things/animations/monsters/radio_jellyfish/*.spjson,STS2_Things/animations/monsters/radio_jellyfish/radio_jellyfish.png'+text[i:]
    path.write_text(text,'utf-8')
print('Integrated Radio Jellyfish elite, native intents, concise bilingual descriptions and purple grotto.')
