"""Prepare the selected generated art and only the new sponge encounter assets."""
from pathlib import Path
import json
import shutil
import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/monsters/water_sponge'
PARTS = ROOT / 'tools/WaterSpongeRig/parts'
PARTS.mkdir(parents=True, exist_ok=True)


def cutout(path):
    image = Image.open(path).convert('RGBA')
    pixels = np.array(image)
    # The endpoint returns a matte alpha near 252/253 in opaque regions, with
    # scattered chroma pixels at very low alpha. Preserve all interior RGB.
    alpha = np.uint8(np.clip((pixels[..., 3].astype(float) - 220) / 31, 0, 1) * 255)
    if (pixels[..., 3] == 255).mean() > .98:
        green = (pixels[..., 1] > 170) & (pixels[..., 1] > pixels[..., 0] * 1.45) & (pixels[..., 1] > pixels[..., 2] * 1.45)
        alpha[green] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype('uint8'))
    if count > 1:
        # Remove only isolated specks. Multi-part icon symbols remain intact.
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] < 24: alpha[labels == label] = 0
    pixels[..., 3] = alpha
    pixels[alpha == 0, :3] = 0
    return Image.fromarray(pixels)


shutil.copy2(ROOT / 'output/imagegen/water_sponge_v1.png', SOURCE / 'character_generated.png')
character = cutout(SOURCE / 'character_generated.png').resize((1280, 1280), Image.Resampling.LANCZOS)
character.save(SOURCE / 'character_final.png')
character.save(PARTS / 'skin.png')
(PARTS / 'meta.json').write_text(json.dumps({'skin': {'x': 0, 'y': 0, 'w': 1280, 'h': 1280}}), 'utf-8')
preview = Image.new('RGBA', character.size, '#24373c'); preview.alpha_composite(character)
preview.convert('RGB').save(SOURCE / 'character_review.jpg', quality=95)

# Approved flat power glyphs are shared with the fish/leech preparation steps.
import runpy
runpy.run_path(str(ROOT / 'scripts/prepare_depths_power_icons.py'), run_name='__main__')

for encounter, slots in {
    'sponge_leech_weak': [('sponge', 1260, 789), ('leech_1', 1620, 755)],
    'sponge_leech_encounter': [('sponge', 1095, 789), ('leech_1', 1415, 737), ('leech_2', 1730, 789)],
}.items():
    text = '''[gd_scene format=3]

[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
'''
    for name, x, y in slots:
        text += f'\n[node name="{name}" type="Marker2D" parent="."]\nposition = Vector2({x}, {y})\n'
    (ROOT / f'scenes/encounters/{encounter}.tscn').write_text(text, 'utf-8')
    base = ROOT / 'scenes/backgrounds/cave_rootfungus'
    for scene in base.rglob('*.tscn'):
        destination = ROOT / 'scenes/backgrounds' / encounter / str(scene.relative_to(base)).replace('cave_rootfungus', encounter)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(scene.read_text('utf-8-sig'), 'utf-8')

texts = {
 'zhs': {
  'monsters': {'WATER_SPONGE.name': '吸水海绵', 'WATER_SPONGE.moves.SOAK_MOVE.title': '吸水', 'WATER_SPONGE.moves.SLAP_MOVE.title': '软拍', 'WATER_SPONGE.moves.SPRAY_MOVE.title': '喷淋'},
  'powers': {
   'ABSORBENT_SPONGE_POWER.title': '吸水体质',
   'ABSORBENT_SPONGE_POWER.description': '累计受到[blue]{DamagePerWater}[/blue]点攻击伤害时，获得[blue]1[/blue]层[gold]积水[/gold]。',
   'ABSORBENT_SPONGE_POWER.smartDescription': '累计受到[blue]{DamagePerWater}[/blue]点攻击伤害时，获得[blue]1[/blue]层[gold]积水[/gold]。',
   'SPONGE_DAMAGE_PROGRESS_POWER.title': '蓄水进度',
   'SPONGE_DAMAGE_PROGRESS_POWER.description': '记录尚未转为积水的伤害。',
   'SPONGE_RESERVOIR_POWER.title': '积水',
   'SPONGE_RESERVOIR_POWER.description': '达到[blue]3[/blue]层时，下次行动改为[gold]喷淋[/gold]，随后失去所有[gold]积水[/gold]。',
   'SPONGE_RESERVOIR_POWER.smartDescription': '达到[blue]3[/blue]层时，下次行动改为[gold]喷淋[/gold]，随后失去所有[gold]积水[/gold]。',
   'SPONGE_RESERVOIR_POWER.sprayTitle': '喷淋',
   'SPONGE_RESERVOIR_POWER.sprayDescription': '攻击后，使所有玩家的[gold]虚弱[/gold]、[gold]易伤[/gold]、[gold]脆弱[/gold]和[gold]致盲[/gold]各减少[blue]1[/blue]层，并给予[blue]1[/blue]层[gold]冲净[/gold]。\n随后回复自身最大生命值的[blue]10%[/blue]。',
   'SPONGE_RINSE_POWER.title': '冲净',
   'SPONGE_RINSE_POWER.description': '抽到状态牌时，将其[gold]消耗[/gold]，并失去[blue]1[/blue]层[gold]冲净[/gold]。（最多[blue]2[/blue]层）',
   'SPONGE_RINSE_POWER.smartDescription': '接下来抽到的[blue]{Amount}[/blue]张状态牌会被[gold]消耗[/gold]。（最多[blue]2[/blue]层）'},
  'encounters': {'SPONGE_LEECH_WEAK.title': '深处：湿地共生', 'SPONGE_LEECH_WEAK.loss': '{character}倒在了[gold]{encounter}[/gold]的浅水中……', 'SPONGE_LEECH_ENCOUNTER.title': '深处：浸水蛭群', 'SPONGE_LEECH_ENCOUNTER.loss': '{character}没能摆脱[gold]{encounter}[/gold]……'}},
 'eng': {
  'monsters': {'WATER_SPONGE.name': 'Water Sponge', 'WATER_SPONGE.moves.SOAK_MOVE.title': 'Soak', 'WATER_SPONGE.moves.SLAP_MOVE.title': 'Soft Slap', 'WATER_SPONGE.moves.SPRAY_MOVE.title': 'Rinse Spray'},
  'powers': {'ABSORBENT_SPONGE_POWER.title': 'Absorbent', 'ABSORBENT_SPONGE_POWER.description': 'Gain [blue]1[/blue] [gold]Stored Water[/gold] for every [blue]{DamagePerWater}[/blue] HP lost to attacks.',
   'ABSORBENT_SPONGE_POWER.smartDescription': 'Gain [blue]1[/blue] [gold]Stored Water[/gold] for every [blue]{DamagePerWater}[/blue] HP lost to attacks.',
   'SPONGE_DAMAGE_PROGRESS_POWER.title': 'Absorption Progress',
   'SPONGE_DAMAGE_PROGRESS_POWER.description': 'Tracks damage toward the next Stored Water stack.',
   'SPONGE_RESERVOIR_POWER.title': 'Stored Water', 'SPONGE_RESERVOIR_POWER.description': 'At [blue]3[/blue] stacks, use [gold]Rinse Spray[/gold] next, then lose ALL [gold]Stored Water[/gold].',
   'SPONGE_RESERVOIR_POWER.smartDescription': 'At [blue]3[/blue] stacks, use [gold]Rinse Spray[/gold] next, then lose ALL [gold]Stored Water[/gold].',
   'SPONGE_RESERVOIR_POWER.sprayTitle': 'Rinse Spray',
   'SPONGE_RESERVOIR_POWER.sprayDescription': 'After attacking, remove [blue]1[/blue] [gold]Weak[/gold], [gold]Vulnerable[/gold], [gold]Frail[/gold], and [gold]Blinded[/gold] from ALL players and grant [blue]1[/blue] [gold]Rinsed[/gold].\nThen heal [blue]10%[/blue] of its own Max HP.',
   'SPONGE_RINSE_POWER.title': 'Rinsed', 'SPONGE_RINSE_POWER.description': 'When you draw a Status, [gold]Exhaust[/gold] it and lose [blue]1[/blue] [gold]Rinsed[/gold]. (Max [blue]2[/blue] stacks.)',
   'SPONGE_RINSE_POWER.smartDescription': '[gold]Exhaust[/gold] the next [blue]{Amount}[/blue] Status cards you draw. (Max [blue]2[/blue] stacks.)'},
  'encounters': {'SPONGE_LEECH_WEAK.title': 'Depths: Wetland Partners', 'SPONGE_LEECH_WEAK.loss': '{character} sank into the shallows of the [gold]{encounter}[/gold].', 'SPONGE_LEECH_ENCOUNTER.title': 'Depths: Sodden Colony', 'SPONGE_LEECH_ENCOUNTER.loss': '{character} succumbed to the [gold]{encounter}[/gold].'}}}
for language, tables in texts.items():
    for table, additions in tables.items():
        path = ROOT / f'STS2_Things/localization/{language}/{table}.json'
        original = path.read_text('utf-8-sig') if path.exists() else '{}\n'; current = json.loads(original)
        missing = {key: value for key, value in additions.items() if key not in current}
        if missing:
            prefix = original[:original.rfind('}')].rstrip()
            if not prefix.endswith('{'): prefix += ','
            path.write_text(prefix + '\n' + json.dumps(missing, ensure_ascii=False, indent=2)[2:-2] + '\n}\n', 'utf-8')

presets = ROOT / 'export_presets.cfg'
text = presets.read_text('utf-8-sig')
extra = ','.join('STS2_Things/animations/monsters/water_sponge/' + suffix for suffix in ['*.atlas', '*.spatlas', '*.spjson', 'water_sponge.png'])
if 'monsters/water_sponge/' not in text:
    presets.write_text('\n'.join(line[:-1]+','+extra+'"' if line.startswith('include_filter="') else line for line in text.splitlines())+'\n', 'utf-8')
print('Prepared sponge art, icons, mixed encounters, backgrounds, localization and export includes.')
