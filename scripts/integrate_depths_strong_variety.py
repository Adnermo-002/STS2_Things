"""Author six independent Depths regular encounters using existing monsters and art."""
from pathlib import Path
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
# Keep the native power rows above the resting hand and end-turn button.
# These enemy-only slots are 64 px above the original 1.25.0 arrangement.
# Player positions remain controlled by the existing Depths player layout.
ENCOUNTERS = [
    dict(model='LanternSpongeEncounter', zhs='潭边生灵', eng='Pool Dwellers',
         background='b_cave_riverbend',
         roster=[('LanternFish', 'fish', 1030, 741), ('WaterSponge', 'sponge', 1410, 760), ('CrystalSnail', 'crystal', 1760, 768)],
         tactic='灯笼鱼扰乱手牌，海绵积水反击，击破晶壳可取得晶片。'),
    dict(model='SilkSnailEncounter', zhs='蛾与蜗牛', eng='Moth and Snails',
         background='d_cave_rootfungus',
         roster=[('SilkMoth', 'moth', 1040, 706), ('RockSnail', 'rock', 1425, 768), ('SlimeSnail', 'slime', 1760, 736)],
         tactic='垂丝蛾限制手牌，涎丝蜗牛修补爬岩蜗牛的壳，碾压前可先打断蓄势。'),
    dict(model='CaveMawSnailEncounter', zhs='洞胃与蜗牛', eng='Maw and Snails',
         background='f_hollow_grotto_moss',
         roster=[('CaveMaw', 'maw', 1010, 760), ('CrystalSnail', 'crystal', 1420, 768), ('SlimeSnail', 'slime', 1760, 736)],
         tactic='洞胃投食后吞食状态牌，涎丝保护晶壳；可以先拆辅助，或破壳取得晶片。'),
    dict(model='SpongeSnailEncounter', zhs='浸水石壳', eng='Waterlogged Shells',
         background='c_cave_quartz',
         roster=[('WaterSponge', 'sponge', 1040, 760), ('RockSnail', 'rock', 1425, 768), ('CrystalSnail', 'crystal', 1760, 736)],
         tactic='爬岩蜗牛积蓄碾压，海绵惩罚分散伤害，晶壳提供破壳回报。'),
    dict(model='LanternMothEncounter', zhs='灯下飞蛾', eng='Light and Silk',
         background='b_cave_riverbend',
         roster=[('LanternFish', 'fish', 1030, 741), ('SilkMoth', 'moth', 1410, 706), ('CrystalSnail', 'crystal', 1760, 768)],
         tactic='缠丝与致盲错开施放，晶壳蜗牛补充伤害；可先击杀较脆的控制目标。'),
    dict(model='CaveMawLanternEncounter', zhs='洞胃与灯鱼', eng='Maw and Lanternfish',
         background='b_cave_riverbend',
         roster=[('CaveMaw', 'maw', 1240, 760), ('LanternFish', 'fish', 1700, 761)],
         tactic='皮厚的洞胃持续投食，灯笼鱼扰乱抽牌；两只敌人各有清楚的输出窗口。'),
]


def slug(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def main():
    localizations = {lang: {} for lang in ('zhs', 'eng')}
    for entry in ENCOUNTERS:
        name = entry['model']
        key = slug(name)
        slots = ', '.join(f'"{slot}"' for _, slot, _, _ in entry['roster'])
        monsters = ', '.join(f'ModelDb.Monster<{monster}>()' for monster, _, _, _ in entry['roster'])
        spawn = ',\n         '.join(f'(ModelDb.Monster<{monster}>().ToMutable(), "{slot}")' for monster, slot, _, _ in entry['roster'])
        source = f'''using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class {name} : EncounterModel
{{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => [{slots}];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [{monsters}];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [{spawn}];
}}
'''
        (ROOT / f'STS2_Things/Encounters/{name}.cs').write_text(source, 'utf-8')
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
        for _, slot, x, y in entry['roster']:
            scene += f'[node name="{slot}" type="Marker2D" parent="."]\nposition = Vector2({x},{y})\n'
        (ROOT / f'scenes/encounters/{key}.tscn').write_text(scene, 'utf-8')
        background = ROOT / f'scenes/backgrounds/{key}'
        (background / 'layers').mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'scenes/backgrounds/lantern_fish_encounter/lantern_fish_encounter_background.tscn', background / f'{key}_background.tscn')
        shutil.copy2(ROOT / f"scenes/backgrounds/depths/layers/depths_bg_00_{entry['background']}.tscn", background / f'layers/{key}_bg_00_a.tscn')
        shutil.copy2(ROOT / 'scenes/backgrounds/lantern_fish_encounter/layers/lantern_fish_encounter_fg_a.tscn', background / f'layers/{key}_fg_a.tscn')
        for lang in localizations:
            localizations[lang][f'{key.upper()}.title'] = entry[lang]
            localizations[lang][f'{key.upper()}.loss'] = (
                '{character}没能逃出[gold]{encounter}[/gold]的围困。' if lang == 'zhs'
                else '{character} was overwhelmed by the [gold]{encounter}[/gold].')

    for lang, entries in localizations.items():
        path = ROOT / f'STS2_Things/localization/{lang}/encounters.json'
        values = json.loads(path.read_text('utf-8-sig'))
        values.update(entries)
        path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    manifest = ROOT / 'source_assets/encounters/depths_strong_variety.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(ENCOUNTERS, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print('Authored 6 regular encounters, slot scenes, complete background scenes and bilingual text.')


if __name__ == '__main__':
    main()
