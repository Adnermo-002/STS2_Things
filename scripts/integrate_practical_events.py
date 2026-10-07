"""Author and merge bilingual text for the three practical Depths events."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = {}


def event(slug, title_zh, title_en):
    tables = {'zhs': {'events': {}, 'settings_ui': {}}, 'eng': {'events': {}, 'settings_ui': {}}}
    DATA[slug] = tables
    prefix = slug.upper()

    def text(key, zh, en):
        for lang, value in (('zhs', zh), ('eng', en)):
            tables[lang]['events'][prefix + '.' + key] = value

    def option(page, key, title_zh, desc_zh, title_en, desc_en):
        text(f'pages.{page}.options.{key}.title', title_zh, title_en)
        text(f'pages.{page}.options.{key}.description', desc_zh, desc_en)

    text('title', title_zh, title_en)
    for lang, title in (('zhs', title_zh), ('eng', title_en)):
        tables[lang]['settings_ui'][f'STS2_THINGS-EVENT_{prefix}_ENABLED.title'] = title + (' · 启用' if lang == 'zhs' else ' — enabled')
    return text, option


t, o = event('relic_workshop', '遗物修补摊', 'Relic Workshop')
t('commonRelic', '一件普通遗物', 'a Common Relic')
t('pages.INITIAL.description',
  '你循着敲打声找到一个小摊。一只戴着护目镜的甲虫，正在给断成两截的[gold]遗物[/gold]缠绷带。\n\n“修不好的也别扔！拿来换，拿来卖，都行！”\n\n他拍了拍身旁鼓鼓的[gold]钱袋[/gold]。',
  'You follow the sound of hammering to a small stall. A beetle in goggles is bandaging a [gold]relic[/gold] that has snapped in half.\n\n“Do not throw it out! Trade it in! Sell it!”\n\nHe pats the bulging [gold]purse[/gold] beside him.')
o('INITIAL', 'TRADE', '交换', '失去一件可交易的[gold]遗物[/gold]。支付[red]{Gold}[/red][gold]金币[/gold]。获得[gold]{Offer}[/gold]。',
  'Trade', 'Lose a tradable [gold]Relic[/gold]. Pay [red]{Gold}[/red] [gold]Gold[/gold]. Obtain [gold]{Offer}[/gold].')
o('INITIAL', 'NO_OFFER', '锁定', '没有可供交换的普通遗物。', 'Locked', 'No Common Relic is available for exchange.')
o('INITIAL', 'NO_RELIC', '锁定', '没有可交易的遗物。', 'Locked', 'You have no tradable Relics.')
o('INITIAL', 'NO_GOLD', '锁定', '需要[blue]{Gold}[/blue][gold]金币[/gold]才能换取[gold]{Offer}[/gold]。',
  'Locked', 'Requires [blue]{Gold}[/blue] [gold]Gold[/gold] to trade for [gold]{Offer}[/gold].')
o('INITIAL', 'SELL', '出售', '失去一件可交易的[gold]遗物[/gold]。获得[blue]{SaleGold}[/blue][gold]金币[/gold]。',
  'Sell', 'Lose a tradable [gold]Relic[/gold]. Gain [blue]{SaleGold}[/blue] [gold]Gold[/gold].')
o('INITIAL', 'SELL_LOCKED', '锁定', '没有可交易的遗物。', 'Locked', 'You have no tradable Relics.')
o('INITIAL', 'COINS', '扶稳桌脚', '获得[blue]{SmallGold}[/blue][gold]金币[/gold]。',
  'Steady the Table', 'Gain [blue]{SmallGold}[/blue] [gold]Gold[/gold].')
t('pages.SELECT_TRADE.description', '甲虫清出一小块桌面。\n\n“让我看看，你带了什么？”',
  'The beetle clears a little space on the table.\n\n“Let us see what you have.”')
t('pages.SELECT_SELL.description', '甲虫倒出一堆[gold]金币[/gold]，冲你的背包招了招手。\n\n“哪件不想要了？”',
  'The beetle empties a heap of [gold]coins[/gold] onto the table and beckons toward your pack.\n\n“Which one are you tired of?”')
o('SELECT', 'TRADE', '交出{Relic}', '支付[red]{Gold}[/red][gold]金币[/gold]。获得[gold]{Offer}[/gold]。',
  'Give {Relic}', 'Pay [red]{Gold}[/red] [gold]Gold[/gold]. Obtain [gold]{Offer}[/gold].')
o('SELECT', 'SELL', '出售{Relic}', '获得[blue]{SaleGold}[/blue][gold]金币[/gold]。',
  'Sell {Relic}', 'Gain [blue]{SaleGold}[/blue] [gold]Gold[/gold].')
o('SELECT', 'MORE', '翻一翻背包', '查看其他遗物。（{Page}/{Pages}）',
  'Search Your Pack', 'View more Relics. ({Page}/{Pages})')
o('SELECT', 'BACK', '再想想', '返回。', 'Reconsider', 'Go back.')
t('pages.TRADED.description', '甲虫收下旧遗物和[gold]金币[/gold]，把新遗物推给你。\n\n“好眼光！这件我才刚修好。”\n\n你小心地把它收进背包。',
  'The beetle takes your old relic and [gold]coins[/gold], then slides the replacement across the table.\n\n“Good eye! I just finished fixing that one.”\n\nYou carefully put it in your pack.')
t('pages.SOLD.description', '甲虫一把接过遗物，把[gold]钱袋[/gold]塞到你手里。\n\n“正缺这个！”\n\n你还没走远，就听见了拆东西的声音。',
  'The beetle snatches up the relic and presses a [gold]purse[/gold] into your hands.\n\n“Just what I needed!”\n\nYou have barely left when you hear him taking it apart.')
t('pages.COINS.description', '你捡起一块石头，垫在晃动的桌脚下面。\n\n甲虫停下手里的活，盯着石头看了一会儿，然后递给你几枚[gold]金币[/gold]。\n\n“这个办法不错。”',
  'You wedge a stone under the wobbling table leg.\n\nThe beetle stops working and stares at it for a moment, then hands you a few [gold]coins[/gold].\n\n“That works.”')

t, o = event('potion_tasting', '药水试饮会', 'Potion Tasting')
t('separator', '、', ', ')
t('pages.INITIAL.description', '一阵奇怪的甜味引你来到一个药水摊前。系着围裙的蝾螈正搅动一口冒泡的锅，桌上摆着几瓶[gold]五颜六色的药水[/gold]。\n\n“一瓶免费！想多带一瓶，就拿金币，或者拿你自己的来换。”\n\n它指了指你腰间的瓶子。',
  'A strange, sweet smell leads you to a potion stall. A newt in an apron stirs a bubbling pot beside several [gold]colorful bottles[/gold].\n\n“One is free! For another, bring coins. Or trade one of yours.”\n\nIt points at the bottles on your belt.')
o('INITIAL', 'SAMPLE', '收下', '获得[blue]1[/blue]瓶随机[gold]药水[/gold]。',
  'Accept', 'Obtain [blue]1[/blue] random [gold]Potion[/gold].')
o('INITIAL', 'BUY', '购买', '支付[red]{Gold}[/red][gold]金币[/gold]。获得[blue]2[/blue]瓶随机[gold]药水[/gold]。',
  'Buy', 'Pay [red]{Gold}[/red] [gold]Gold[/gold]. Obtain [blue]2[/blue] random [gold]Potions[/gold].')
o('INITIAL', 'BUY_LOCKED', '锁定', '需要[blue]{Gold}[/blue][gold]金币[/gold]。',
  'Locked', 'Requires [blue]{Gold}[/blue] [gold]Gold[/gold].')
o('INITIAL', 'BARTER', '交换', '失去[red]1[/red]瓶[gold]药水[/gold]。获得[blue]2[/blue]瓶随机[gold]药水[/gold]。',
  'Trade', 'Lose [red]1[/red] [gold]Potion[/gold]. Obtain [blue]2[/blue] random [gold]Potions[/gold].')
o('INITIAL', 'BARTER_LOCKED', '锁定', '你没有药水。', 'Locked', 'You have no Potions.')
o('INITIAL', 'WATER', '喝水', '回复[green]{Heal}[/green]生命。',
  'Have Some Hot Water', 'Heal [green]{Heal}[/green] HP.')
o('INITIAL', 'CANNOT_RECEIVE', '锁定', '无法获得两瓶药水。',
  'Locked', 'You cannot obtain two Potions.')
# The retired selection-page keys remain for 1.23.0 run-history localization.
t('pages.CHOOSE_FREE.description', '[green]“挑一瓶。”[/green]\n\n蝾螈擦了擦每个瓶口。',
  '[green]“Pick one.”[/green]\n\nThe newt wipes the mouth of each bottle.')
t('pages.CHOOSE_BUY.description', '蝾螈把瓶子推近了一点。\n\n选好两瓶后，支付[gold]{Gold}金币[/gold]。',
  'The newt nudges the bottles closer.\n\nChoose two, then pay [gold]{Gold} Gold[/gold].')
t('pages.CHOOSE_BARTER.description', '蝾螈把三瓶药水排好。\n\n[green]“先挑你要的，再让我看看你的。”[/green]',
  'The newt lines up the three bottles.\n\n[green]“Pick the ones you want. Then show me yours.”[/green]')
o('CHOOSE', 'SINGLE', '拿这一瓶', '获得[blue]{Potions}[/blue]。',
  'Take This One', 'Obtain [blue]{Potions}[/blue].')
o('CHOOSE', 'PAIR', '拿这两瓶', '获得[blue]{Potions}[/blue]。',
  'Take These Two', 'Obtain [blue]{Potions}[/blue].')
o('CHOOSE', 'BACK', '再想想', '返回。', 'Reconsider', 'Go back.')
t('pages.PAYMENT.description', '蝾螈放下勺子，向你伸出手。\n\n“让我尝尝你的。”',
  'The newt puts down its spoon and holds out a hand.\n\n“Let me try yours.”')
o('PAYMENT', 'GIVE', '交出{Potion}', '获得[blue]2[/blue]瓶随机[gold]药水[/gold]。',
  'Give {Potion}', 'Obtain [blue]2[/blue] random [gold]Potions[/gold].')
o('PAYMENT', 'MORE', '看看其他药水', '查看其他药水。（{Page}/{Pages}）',
  'Other Potions', 'View more Potions. ({Page}/{Pages})')
o('PAYMENT', 'BACK', '返回', '重新选择。', 'Back', 'Choose another option.')
t('pages.SAMPLED.description', '蝾螈随手从柜子里拿出一瓶药水，在围裙上擦了擦，塞到你手里。\n\n“下次再来！”',
  'The newt grabs a potion from the cupboard, wipes it on its apron, and presses it into your hand.\n\n“Come back soon!”')
t('pages.BOUGHT.description', '你把[gold]金币[/gold]放到桌上。蝾螈从柜子里摸出两瓶药水，一起递给你。\n\n“别混着喝。我还没试过。”',
  'You place the [gold]coins[/gold] on the table. The newt fishes two potions out of the cupboard and hands them over.\n\n“Do not mix them. I have not tried that yet.”')
t('pages.BARTERED.description', '蝾螈接过你的药水，凑到鼻子下面闻了闻。\n\n“好东西！”\n\n它把瓶子收起来，换给你另外两瓶。',
  'The newt takes your potion and holds it beneath its nose.\n\n“Good stuff!”\n\nIt puts the bottle away and hands you two others.')
t('pages.WATER.description', '你摇了摇头。蝾螈耸耸肩，从锅边舀了一杯热水。\n\n你小心地喝完，身子总算暖和了一点。',
  'You shake your head. The newt shrugs and ladles a cup of hot water from beside the pot.\n\nYou drink it carefully, grateful for a little warmth.')

t, o = event('narrow_gate', '窄门', 'Narrow Gate')
t('card', '一张牌', 'a card')
t('pages.INITIAL.description', '你来到一扇窄小的石门前。刚试着挤过去，门缝就夹住了你的背包，还拽出了几张牌。\n\n门楣上的脸睁开眼睛。\n\n“带得太多了！留下一张。”',
  'You try to squeeze through a narrow stone door. The gap catches your pack and pulls out a few cards.\n\nThe face on the lintel opens its eyes.\n\n“Too much luggage! Leave one.”')
# Preserve the old generic-removal title for existing run histories.
o('INITIAL', 'REMOVE', '轻装通过', '从展示的[blue]{Candidates}[/blue]张牌中移除[blue]1[/blue]张。',
  'Travel Light', 'Remove [blue]1[/blue] of the [blue]{Candidates}[/blue] shown cards.')
o('INITIAL', 'REMOVE_CARD', '放下{Card}', '从你的[gold]牌组[/gold]中移除这张牌。',
  'Leave {Card}', 'Remove this card from your [gold]Deck[/gold].')
o('INITIAL', 'REMOVE_LOCKED', '锁定', '没有可移除的牌。', 'Locked', 'You have no removable cards.')
o('INITIAL', 'REROLL', '换个姿势', '支付[red]{Gold}[/red][gold]金币[/gold]。更换可移除的牌。仅限一次。',
  'Try Another Angle', 'Pay [red]{Gold}[/red] [gold]Gold[/gold] to reroll the cards. Once only.')
o('INITIAL', 'REROLLED', '锁定', '已经换过一次了。', 'Locked', 'You have already rerolled the cards.')
o('INITIAL', 'NO_ALTERNATIVES', '锁定', '没有其他可供选择的牌。', 'Locked', 'There are no other eligible cards.')
o('INITIAL', 'NO_GOLD', '锁定', '需要[blue]{Gold}[/blue][gold]金币[/gold]。',
  'Locked', 'Requires [blue]{Gold}[/blue] [gold]Gold[/gold].')
o('INITIAL', 'REST', '靠墙歇脚', '回复[green]{Heal}[/green]生命。',
  'Rest by the Wall', 'Heal [green]{Heal}[/green] HP.')
t('pages.REROLLED.description', '你把[gold]金币[/gold]塞进门缝，换了个角度再挤。\n\n石门松开原先的牌，又夹住了另外几张。\n\n“就这些。别再扭了！”',
  'You slip [gold]coins[/gold] into the gap and turn the other way.\n\nThe door releases the first cards and catches a different set.\n\n“These will do. Stop squirming!”')
t('pages.REMOVED.description', '你松开那张牌。石门咔哒一声，把它吞了进去。\n\n“这就对了。”\n\n门缝终于宽了些，你侧身挤了过去。',
  'You let go of the card. The door swallows it with a click.\n\n“Much better.”\n\nThe gap widens just enough for you to squeeze through.')
t('pages.REST.description', '石门在你的背包上挤了半天，什么也没夹出来。\n\n你索性坐下来歇了一会儿。等你站起身时，它已经睡着了，门缝也松开了一些。',
  'The door squeezes your pack for a while, but fails to extract anything.\n\nYou sit down to rest. By the time you stand, it has fallen asleep and the gap has loosened.')

for slug, tables in DATA.items():
    source = ROOT / f'source_assets/events/{slug}/localization.json'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(tables, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    for lang, additions in tables.items():
        for table, entries in additions.items():
            path = ROOT / f'STS2_Things/localization/{lang}/{table}.json'
            current = json.loads(path.read_text('utf-8-sig'))
            if table == 'events':
                current = {key: value for key, value in current.items()
                           if not key.startswith(slug.upper() + '.') or key in entries}
            current.update(entries)
            path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print(json.dumps({slug: len(tables['zhs']['events']) for slug, tables in DATA.items()}, ensure_ascii=False))
