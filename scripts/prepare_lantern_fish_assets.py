"""Package approved original artwork and additive encounter-local resources."""
from pathlib import Path
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'source_assets/monsters/lantern_fish'
import runpy
runpy.run_path(str(ROOT / 'scripts/prepare_depths_power_icons.py'), run_name='__main__')
old=ROOT/'scenes/backgrounds/cave_riverbend'; dest=ROOT/'scenes/backgrounds/lantern_fish_encounter'
(dest/'layers').mkdir(exist_ok=True,parents=True)
atomic_background = dest/'layers/lantern_fish_encounter_bg_00_a_cave_riverbend.tscn'
# Once Depths owns the complete layered riverbank, do not reintroduce the old
# independent layers alongside it when refreshing fish art or icons.
for scene in ([] if atomic_background.exists() else old.rglob('*.tscn')):
    path=dest/scene.relative_to(old).as_posix().replace('cave_riverbend','lantern_fish_encounter')
    path.write_text(scene.read_text(encoding='utf-8-sig'),encoding='utf-8')

texts={
'zhs':{
'monsters':{'LANTERN_FISH.name':'灯笼鱼','LANTERN_FISH.moves.BITE_MOVE.title':'啮咬','LANTERN_FISH.moves.FLASH_MOVE.title':'耀闪','LANTERN_FISH.moves.TAIL_MOVE.title':'甩尾','LANTERN_FISH.moves.GUARD_MOVE.title':'收灯'},
'encounters':{'LANTERN_FISH_ENCOUNTER.title':'深处：灯笼鱼','LANTERN_FISH_ENCOUNTER.loss':'{character}在[gold]{encounter}[/gold]的强光中失去了方向……'},
'powers':{'LANTERN_BLINDNESS_POWER.title':'致盲','LANTERN_BLINDNESS_POWER.description':'接下来抽到的牌无法辨认，耗能随机变为[blue]1[/blue]到[blue]3[/blue]，直到你的回合结束。（最多[blue]6[/blue]层）','LANTERN_BLINDNESS_POWER.smartDescription':'接下来抽到的[blue]{Amount}[/blue]张牌无法辨认，耗能随机变为[blue]1[/blue]到[blue]3[/blue]，直到你的回合结束。（最多[blue]6[/blue]层）'}},
'eng':{
'monsters':{'LANTERN_FISH.name':'Lantern Fish','LANTERN_FISH.moves.BITE_MOVE.title':'Bite','LANTERN_FISH.moves.FLASH_MOVE.title':'Dazzle','LANTERN_FISH.moves.TAIL_MOVE.title':'Tail Swipes','LANTERN_FISH.moves.GUARD_MOVE.title':'Dim the Lure'},
'encounters':{'LANTERN_FISH_ENCOUNTER.title':'Depths: Lantern Fish','LANTERN_FISH_ENCOUNTER.loss':'{character} lost their bearings in the blinding light of [gold]{encounter}[/gold].'},
'powers':{'LANTERN_BLINDNESS_POWER.title':'Blinded','LANTERN_BLINDNESS_POWER.description':'The next cards you draw are obscured and their costs are randomized from [blue]1[/blue] to [blue]3[/blue] until the end of your turn. (Max [blue]6[/blue] stacks.)','LANTERN_BLINDNESS_POWER.smartDescription':'The next [blue]{Amount}[/blue] cards you draw are obscured and their costs are randomized from [blue]1[/blue] to [blue]3[/blue] until the end of your turn. (Max [blue]6[/blue] stacks.)'}}}
for lang,tables in texts.items():
    for table,entries in tables.items():
        file=ROOT/f'STS2_Things/localization/{lang}/{table}.json'
        raw=file.read_text(encoding='utf-8-sig'); existing=json.loads(raw)
        missing={k:v for k,v in entries.items() if k not in existing}
        if missing:
            pos=raw.rfind('}'); prefix=raw[:pos].rstrip()
            if not prefix.endswith('{'): prefix+=','
            extra=json.dumps(missing,ensure_ascii=False,indent=2)[2:-2]
            file.write_text(prefix+'\n'+extra+'\n}\n',encoding='utf-8')
print('Prepared icon, standalone riverbend scene, English and Chinese localization.')
