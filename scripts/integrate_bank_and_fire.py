"""Merge new events and persist the Depths' small-reward fallback convention."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def update_source(event, additions):
    path=ROOT/f'source_assets/events/{event}/localization.json'
    values=json.loads(path.read_text('utf-8'))
    for lang, entries in additions.items(): values[lang]['events'].update(entries)
    path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')

update_source('polite_maw',{
 'zhs':{
  'POLITE_MAW.pages.INITIAL.description':'地上的大嘴铺好餐巾，把[gold]药水和金币[/gold]推到你面前，盯着你的牌组。\n\n[green]“请问，能分我一点吃的吗？”[/green]',
  'POLITE_MAW.pages.INITIAL.options.TIP.title':'收下小费',
  'POLITE_MAW.pages.INITIAL.options.TIP.description':'{IsMultiplayer:每人|}获得[blue]{SmallGold}[/blue][gold]金币[/gold]。',
  'POLITE_MAW.pages.TIP.description':'洞胃推来几枚[gold]金币[/gold]。\n\n[green]“谢谢你没踩到我。”[/green]\n\n你收下了。它说得有道理。'},
 'eng':{
  'POLITE_MAW.pages.INITIAL.description':'The mouth spreads its napkin and pushes [gold]a potion and some coins[/gold] toward you, watching your deck.\n\n[green]“Could you spare something to eat?”[/green]',
  'POLITE_MAW.pages.INITIAL.options.TIP.title':'Accept the Tip',
  'POLITE_MAW.pages.INITIAL.options.TIP.description':'{IsMultiplayer:Each player gains|Gain} [blue]{SmallGold}[/blue] [gold]Gold[/gold].',
  'POLITE_MAW.pages.TIP.description':'The maw slides over a few [gold]coins[/gold].\n\n[green]“Thank you for not stepping on me.”[/green]\n\nYou accept. It has a point.'}})
path=ROOT/'source_assets/events/polite_maw/localization.json'
values=json.loads(path.read_text('utf-8'))
for tables in values.values():
    events=tables['events']
    for key in ('POWER','POWER_LOCKED','CURSE','CURSE_LOCKED'):
        for part in ('title','description'):
            events[f'POLITE_MAW.pages.INITIAL.options.{key}.{part}']=events[f'POLITE_MAW.pages.SPECIAL.options.{key}.{part}']
path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')

update_source('shadow_cloakroom',{
 'zhs':{'SHADOW_CLOAKROOM.pages.INITIAL.options.COINS.title':'认领零钱',
        'SHADOW_CLOAKROOM.pages.INITIAL.options.COINS.description':'获得[blue]{SmallGold}[/blue][gold]金币[/gold]。',
        'SHADOW_CLOAKROOM.pages.COINS.description':'影子从柜台缝里摸出几枚[gold]金币[/gold]。柜员看了一眼，没有拦它。\n\n[green]“失物终于有人领了。”[/green]'},
 'eng':{'SHADOW_CLOAKROOM.pages.INITIAL.options.COINS.title':'Claim the Loose Change',
        'SHADOW_CLOAKROOM.pages.INITIAL.options.COINS.description':'Gain [blue]{SmallGold}[/blue] [gold]Gold[/gold].',
        'SHADOW_CLOAKROOM.pages.COINS.description':'Your shadow fishes a few [gold]coins[/gold] out of a crack in the counter. The clerk makes no objection.\n\n[green]“Finally. Someone claimed them.”[/green]'}})
update_source('echoing_well',{
 'zhs':{'ECHOING_WELL.pages.INITIAL.options.COINS.title':'捡起井边的金币',
        'ECHOING_WELL.pages.INITIAL.options.COINS.description':'获得[blue]{SmallGold}[/blue][gold]金币[/gold]。',
        'ECHOING_WELL.pages.COINS.description':'你捡起井沿上的几枚[gold]金币[/gold]。\n\n井里传来了一声清脆的道谢。\n\n你还没来得及开口。'},
 'eng':{'ECHOING_WELL.pages.INITIAL.options.COINS.title':'Take the Coins',
        'ECHOING_WELL.pages.INITIAL.options.COINS.description':'Gain [blue]{SmallGold}[/blue] [gold]Gold[/gold].',
        'ECHOING_WELL.pages.COINS.description':'You collect a few [gold]coins[/gold] from the rim.\n\nA clear voice thanks the well.\n\nYou had not spoken yet.'}})

# The grassland event keeps its original authoring table and blue-door branch.
path=ROOT/'source_assets/events/reality_aligned_houses/aero_text.json'
values=json.loads(path.read_text('utf-8'))
for lang in ('zhs','eng'):
    values[lang]['pages.INITIAL.options.BLUE.description']=('获得[blue]{SmallGold}[/blue][gold]金币[/gold]。' if lang=='zhs' else 'Gain [blue]{SmallGold}[/blue] [gold]Gold[/gold].')
    values[lang]['pages.BLUE.description']=('蓝屋的门后放着一只碟子，里面是替你留好的[gold]零钱[/gold]。\n\n你收好金币，穿过后门。洞穴里的水滴声又回来了。' if lang=='zhs' else 'A little dish waits behind the blue door, holding [gold]change[/gold] set aside for you.\n\nYou pocket it and take the back door. The cave resumes dripping.')
path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')

for event in ('polite_maw','shadow_cloakroom','echoing_well','mycelial_bank','unlit_fire'):
    values=json.loads((ROOT/f'source_assets/events/{event}/localization.json').read_text('utf-8'))
    for lang,tables in values.items():
        for name,entries in tables.items():
            path=ROOT/f'STS2_Things/localization/{lang}/{name}.json'
            data=json.loads(path.read_text('utf-8-sig')) if path.exists() else {}
            data.update(entries)
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
grass=json.loads((ROOT/'source_assets/events/reality_aligned_houses/aero_text.json').read_text('utf-8'))
for lang,entries in grass.items():
    path=ROOT/f'STS2_Things/localization/{lang}/events.json'
    data=json.loads(path.read_text('utf-8-sig'))
    data.update({'REALITY_ALIGNED_HOUSES.'+key:value for key,value in entries.items()})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
print('Integrated Mycelial Bank, Unlit Fire, and small-benefit choices for all custom Depths events.')
