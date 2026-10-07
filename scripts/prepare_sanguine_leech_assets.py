"""Prepare the original generated art, localization and leech-specific habitat resources."""
from pathlib import Path
import json
import runpy
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / 'scripts/prepare_depths_power_icons.py'), run_name='__main__')
SOURCE = ROOT / 'source_assets/monsters/sanguine_leech'
raw = np.array(Image.open(SOURCE / 'character_generated.png').convert('RGBA'))
# The generator returned genuine alpha. Remove its low-opacity decorative haze;
# keep all interior character colors and a narrow antialiased silhouette.
raw[..., 3] = np.uint8(np.clip((raw[..., 3].astype(float)-230)/20, 0, 1)*255)
raw[raw[..., 3] == 0, :3] = 0
character = Image.fromarray(raw)
character.save(SOURCE / 'character_final.png')
preview = Image.new('RGBA', character.size, '#223341')
preview.alpha_composite(character)
preview.convert('RGB').save(SOURCE / 'character_review.jpg', quality=95)
parts = ROOT / 'tools/SanguineLeechRig/parts'
parts.mkdir(parents=True, exist_ok=True)
character.save(parts / 'skin.png')
(parts / 'meta.json').write_text(json.dumps({'skin': {'x': 0, 'y': 0, 'w': character.width, 'h': character.height}}))
portrait = Image.open(SOURCE / 'parasite_card_generated.png').convert('RGB')
portrait = ImageOps.fit(portrait, (500, 380), method=Image.Resampling.LANCZOS)
(ROOT / 'images/cards').mkdir(parents=True, exist_ok=True)
portrait.save(ROOT / 'images/cards/leech_parasite.png')

for name in ['sanguine_leech_weak', 'sanguine_leech_encounter']:
    base = ROOT / 'scenes/backgrounds/cave_rootfungus'
    dest = ROOT / 'scenes/backgrounds' / name
    for scene in base.rglob('*.tscn'):
        output = dest / str(scene.relative_to(base)).replace('cave_rootfungus', name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(scene.read_text(encoding='utf-8-sig'), encoding='utf-8')

texts = {
 'zhs': {
  'powers': {'LEECH_INFESTATION_POWER.title': '顽固寄生', 'LEECH_INFESTATION_POWER.description': '每当一张[gold]寄生[/gold]被[gold]消耗[/gold]时，这个敌人的下次行动变为[gold]再寄生[/gold]。'},
  'monsters': {'SANGUINE_LEECH.name': '吸血血蛭', 'SANGUINE_LEECH.moves.SIP_MOVE.title': '啜血',
   'SANGUINE_LEECH.moves.SIP_AGAIN_MOVE.title': '再啜', 'SANGUINE_LEECH.moves.INFEST_MOVE.title': '寄生',
   'SANGUINE_LEECH.moves.CURL_MOVE.title': '盘伏', 'SANGUINE_LEECH.moves.REINFEST_MOVE.title': '再寄生'},
  'cards': {'LEECH_PARASITE.title': '寄生',
   'LEECH_PARASITE.description': '在你的回合结束时，如果这张牌在你的[gold]手牌[/gold]中，所有吸血血蛭获得{RegenPower:diff()}层[gold]再生[/gold]和{StrengthPower:diff()}点[gold]力量[/gold]。'},
  'encounters': {'SANGUINE_LEECH_WEAK.title': '深处：血蛭双生',
   'SANGUINE_LEECH_WEAK.loss': '{character}被[gold]{encounter}[/gold]一点点吸干了力气……',
   'SANGUINE_LEECH_ENCOUNTER.title': '深处：血蛭群落',
   'SANGUINE_LEECH_ENCOUNTER.loss': '{character}成了[gold]{encounter}[/gold]的温床……'}},
 'eng': {
  'powers': {'LEECH_INFESTATION_POWER.title': 'Persistent Infestation', 'LEECH_INFESTATION_POWER.description': "Whenever [gold]Parasitism[/gold] is [gold]Exhausted[/gold], this enemy's next move becomes [gold]Reinfest[/gold]."},
  'monsters': {'SANGUINE_LEECH.name': 'Sanguine Leech', 'SANGUINE_LEECH.moves.SIP_MOVE.title': 'Blood Sip',
   'SANGUINE_LEECH.moves.SIP_AGAIN_MOVE.title': 'Another Sip', 'SANGUINE_LEECH.moves.INFEST_MOVE.title': 'Infest',
   'SANGUINE_LEECH.moves.CURL_MOVE.title': 'Curl Up', 'SANGUINE_LEECH.moves.REINFEST_MOVE.title': 'Reinfest'},
  'cards': {'LEECH_PARASITE.title': 'Parasitism',
   'LEECH_PARASITE.description': 'At the end of your turn, if this is in your [gold]Hand[/gold], all Sanguine Leeches gain {RegenPower:diff()} [gold]Regeneration[/gold] and {StrengthPower:diff()} [gold]Strength[/gold].'},
  'encounters': {'SANGUINE_LEECH_WEAK.title': 'Depths: Leech Pair',
   'SANGUINE_LEECH_WEAK.loss': '{character} was drained by the [gold]{encounter}[/gold].',
   'SANGUINE_LEECH_ENCOUNTER.title': 'Depths: Leech Colony',
   'SANGUINE_LEECH_ENCOUNTER.loss': '{character} became a host to the [gold]{encounter}[/gold].'}}}
for language, tables in texts.items():
    for table, additions in tables.items():
        path = ROOT / f'STS2_Things/localization/{language}/{table}.json'
        original = path.read_text(encoding='utf-8-sig')
        current = json.loads(original)
        missing = {k: v for k, v in additions.items() if k not in current}
        if missing:
            prefix = original[:original.rfind('}')].rstrip()
            if not prefix.endswith('{'):
                prefix += ','
            path.write_text(prefix+'\n'+json.dumps(missing, ensure_ascii=False, indent=2)[2:-2]+'\n}\n', encoding='utf-8')

presets = ROOT / 'export_presets.cfg'
text = presets.read_text(encoding='utf-8-sig')
extra = ','.join('STS2_Things/animations/monsters/sanguine_leech/'+suffix for suffix in ['*.atlas','*.spatlas','*.spjson','sanguine_leech.png'])
if 'monsters/sanguine_leech/' not in text:
    lines = text.splitlines()
    lines = [line[:-1]+','+extra+'"' if line.startswith('include_filter="') else line for line in lines]
    presets.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('Prepared original leech art, card portrait, two habitats, localization and PCK includes.')
