"""Native event localization and attribution; actual game UI remains native."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
KEY='REALITY_ALIGNED_HOUSES'
tables={
 'zhs':{
  'title':'对齐之屋',
  'pages.INITIAL.description':'潮湿的石阶忽然接上一条干燥小路。两侧的屋檐、窗户、门阶，整齐得让人牙酸。\n\n你往旁边绕了几步，又回到同一扇门前。门框歪着。屋里的灯光却很熟悉——[gold]太熟悉了。[/gold]\n\n你还没想起这是哪儿，手已经摸向了门把。远处，一栋[blue]蓝色小屋[/blue]的门开着。它不认识你。',
  'pages.INITIAL.options.HOME.title':'认下家门',
  'pages.INITIAL.options.HOME.description':'复制你牌组中的[blue]{Cards}[/blue]张牌。获得[red]诅咒[/red]——[gold]{Curse}[/gold]。',
  'pages.INITIAL.options.HOME_LOCKED.title':'已锁定',
  'pages.INITIAL.options.HOME_LOCKED.description':'没有可复制的牌。',
  'pages.INITIAL.options.ALIGN.title':'拨正门框',
  'pages.INITIAL.options.ALIGN.description':'失去[red]{HpLoss}[/red]点生命。从你的牌组中移除[blue]{Cards}[/blue]张牌。',
  'pages.INITIAL.options.ALIGN_LOCKED.title':'已锁定',
  'pages.INITIAL.options.ALIGN_LOCKED.description':'没有可移除的牌。',
  'pages.INITIAL.options.BLUE.title':'走进蓝屋',
  'pages.INITIAL.options.BLUE.description':'离开。',
  'pages.HOME.selectionScreenPrompt':'选择一张牌，获得它的复制品。',
  'pages.HOME.description':'你推开门。桌上摆着一张牌，连折痕都与你选出的那张一模一样。\n\n你将它收好。屋里所有的椅子一齐朝向你。\n\n门外重新传来滴水声，你赶紧跨了出去。多出来的那张牌很轻。[purple]没能留下的念头，很重。[/purple]',
  'pages.ALIGN.description':'你把歪斜的门框推了回去。\n\n整条街同时响了一声。有什么从你的身体里[red][jitter]挤了出去[/jitter][/red]。\n\n疼痛过去后，牌组里少了一张牌。它原本是什么？你试着回想，牙根又开始发酸。\n\n算了。',
  'pages.BLUE.description':'你头也不回地穿过蓝屋。里面没有家具，只有另一扇门。\n\n门后仍是冰冷的洞穴。\n\n这一次，水滴落下的声音各不相同。你从没觉得它们这样悦耳。',
  'pages.ABORTED.description':'你伸出手，又停了下来。屋里的灯灭了。\n\n蓝屋的门还开着。你决定趁它没有改主意，赶快离开。',
  'pages.DEATH.description':'街道终于严丝合缝了。\n\n唯一多余的东西，是你。'},
 'eng':{
  'title':'Reality Aligned Houses',
  'pages.INITIAL.description':'The damp steps end at a dry little street. Every roof, window, and doorstep lines up so neatly that your teeth ache.\n\nYou try going around. The same crooked door meets you again. Its lamplight is familiar. [gold]Much too familiar.[/gold]\n\nYour hand finds the handle before you remember why. Farther down the street, a [blue]blue cottage[/blue] stands open. It does not recognize you.',
  'pages.INITIAL.options.HOME.title':'Call It Home',
  'pages.INITIAL.options.HOME.description':'Duplicate [blue]{Cards}[/blue] card in your deck. Become [red]Cursed[/red] — [gold]{Curse}[/gold].',
  'pages.INITIAL.options.HOME_LOCKED.title':'Locked',
  'pages.INITIAL.options.HOME_LOCKED.description':'No cards to duplicate.',
  'pages.INITIAL.options.ALIGN.title':'Straighten the Frame',
  'pages.INITIAL.options.ALIGN.description':'Lose [red]{HpLoss}[/red] HP. Remove [blue]{Cards}[/blue] card from your deck.',
  'pages.INITIAL.options.ALIGN_LOCKED.title':'Locked',
  'pages.INITIAL.options.ALIGN_LOCKED.description':'No cards to remove.',
  'pages.INITIAL.options.BLUE.title':'Take the Blue Door',
  'pages.INITIAL.options.BLUE.description':'Leave.',
  'pages.HOME.selectionScreenPrompt':'Choose a card to duplicate.',
  'pages.HOME.description':'A card waits on the table. Even its creases match the one you chose.\n\nYou pocket it. Every chair in the house turns toward you.\n\nWater drips beyond the door. You hurry through. The extra card weighs almost nothing. [purple]The thought of staying weighs much more.[/purple]',
  'pages.ALIGN.description':'You push the crooked frame into place.\n\nThe whole street clicks. Something is [red][jitter]squeezed out of you[/jitter][/red].\n\nWhen the pain passes, a card is missing. What was it? You try to remember. Your teeth begin to ache again.\n\nNever mind.',
  'pages.BLUE.description':'You pass through the blue cottage without looking back. No furniture. Just another door.\n\nBeyond it, the cold cave waits.\n\nThe drops of water all sound different now. You have never heard anything so pleasant.',
  'pages.ABORTED.description':'You reach out, then hesitate. The lamplight goes dark.\n\nThe blue door is still open. You leave before it changes its mind.',
  'pages.DEATH.description':'At last, everything on the street fits.\n\nExcept you.'}}
revision=json.loads((ROOT/'source_assets/events/reality_aligned_houses/aero_text.json').read_text('utf-8'))
for lang,entries in revision.items():tables[lang].update(entries)
for lang,entries in tables.items():
    path=ROOT/f'STS2_Things/localization/{lang}/events.json'
    values=json.loads(path.read_text('utf-8-sig'))
    values.update({f'{KEY}.{key}':value for key,value in entries.items()})
    path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n','utf-8')
    settings=ROOT/f'STS2_Things/localization/{lang}/settings_ui.json'
    data=json.loads(settings.read_text('utf-8-sig'))
    data['STS2_THINGS-EVENT_REALITY_ALIGNED_HOUSES_ENABLED.title']=(
        '对齐之屋 — 启用' if lang=='zhs' else 'Reality Aligned Houses — enabled')
    settings.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
path=ROOT/'export_presets.cfg';data=path.read_text('utf-8')
if 'STS2_Things/credits/*.txt' not in data:
    i=data.index('"',data.index('include_filter="')+len('include_filter="'))
    data=data[:i]+',STS2_Things/credits/*.txt'+data[i:]
    path.write_text(data,'utf-8')
print('Integrated native bilingual event text and packaged attribution.')
