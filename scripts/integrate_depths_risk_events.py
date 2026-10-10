"""Merge bilingual event/relic text without replacing unrelated localisation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = {lang: {name: {} for name in ("events", "relics", "settings_ui")} for lang in ("zhs", "eng")}


def text(key, zh, en, table="events"):
    for lang, value in (("zhs", zh), ("eng", en)):
        TABLES[lang][table][key] = value


def option(event, key, zh_title, zh_description, en_title, en_description):
    prefix = event + ".pages.INITIAL.options." + key
    text(prefix + ".title", zh_title, en_title)
    text(prefix + ".description", zh_description, en_description)


text("BITING_CHEST.title", "会咬人的宝箱", "Biting Chest")
text("BITING_CHEST.pages.INITIAL.description",
     "洞穴里躺着一只半开的[gold]宝箱[/gold]。金币堆里露出一件遗物。\n\n你刚伸手，箱盖便轻轻合了一下。两排黄牙碰得[red]咔哒[/red]作响。\n\n几枚金币已经漏到了外面。旁边还有一块木楔。",
     "A [gold]chest[/gold] sits half-open in the cave. A relic peeks out from its pile of coins.\n\nYou reach toward it. The lid snaps shut with a quiet [red]click[/red] of yellow teeth.\n\nSome coins have spilled onto the floor. A wooden wedge lies beside them.")
option("BITING_CHEST", "REACH", "伸手",
       "[blue]{Chance}%[/blue]：获得一件[gold]稀有遗物[/gold]。[red]{Chance}%[/red]：失去[red]{BiteDamage}[/red]生命，获得[red]诅咒[/red]——[purple]{Curse}[/purple]。",
       "Reach Inside", "[blue]{Chance}%[/blue]: Obtain a [gold]Rare Relic[/gold]. [red]{Chance}%[/red]: Lose [red]{BiteDamage}[/red] HP and become [red]Cursed[/red] — [purple]{Curse}[/purple].")
option("BITING_CHEST", "WEDGE", "撑住箱盖",
       "失去[red]{WedgeDamage}[/red]生命。获得一件[gold]普通遗物[/gold]。",
       "Wedge the Lid", "Lose [red]{WedgeDamage}[/red] HP. Obtain a [gold]Common Relic[/gold].")
option("BITING_CHEST", "COINS", "捡起金币", "获得[blue]{Gold}[/blue][gold]金币[/gold]。",
       "Gather the Coins", "Gain [blue]{Gold}[/blue] [gold]Gold[/gold].")
option("BITING_CHEST", "EMPTY", "锁定", "箱子里没有这种遗物了。", "Locked", "No Relics of this rarity remain.")
text("BITING_CHEST.pages.RELIC.description", "你抢出遗物，赶在牙齿合拢前缩回手。\n\n箱子不高兴地嚼起了金币。",
     "You snatch the relic and pull back before the teeth meet.\n\nThe chest sulkily chews a coin.")
text("BITING_CHEST.pages.BITTEN.description", "你只抓住了箱子的舌头。\n\n它很快让你松了手。",
     "Your fingers close around the chest's tongue.\n\nIt persuades you to let go.")
text("BITING_CHEST.pages.WEDGED.description", "木楔撑住了箱盖。箱子换了个角度，还是咬到了你。\n\n至少这次，你带走了东西。",
     "The wedge holds the lid open. The chest finds another angle and bites you anyway.\n\nAt least you leave with something.")
text("BITING_CHEST.pages.COINS.description", "你捡起外面的金币。\n\n箱子等了一会儿，又慢慢张开嘴。",
     "You pocket the coins on the floor.\n\nThe chest waits a moment, then slowly opens its mouth again.")

text("CROWDED_WARD.title", "满员的病房", "Crowded Ward")
text("CROWDED_WARD.pages.INITIAL.description",
     "洞穴里的病床挤得满满当当。一只眼柄上架着镜片的蜗牛，正往几团鼓起的被子上贴绷带。\n\n它用触须拍了拍唯一空着的[gold]担架[/gold]。\n\n“这里还能躺。别碰瓶子。”",
     "Every bed in the cave is occupied. A snail with lenses balanced on its eyestalks sticks bandages onto several bulging blankets.\n\nIt pats the only empty [gold]stretcher[/gold] with a tentacle.\n\n“Room for one more. Do not touch the bottles.”")
option("CROWDED_WARD", "TREAT", "彻底治疗", "回复全部生命。获得[red]诅咒[/red]——[purple]{Curse}[/purple]。",
       "Full Treatment", "Heal to full HP. Become [red]Cursed[/red] — [purple]{Curse}[/purple].")
option("CROWDED_WARD", "ANESTHETIZE", "局部麻醉",
       "回复[green]{LocalHeal}[/green]生命。接下来[red]{Combats}[/red]场战斗，首回合少抽[red]{Cards}[/red]张牌。",
       "Local Anesthetic", "Heal [green]{LocalHeal}[/green] HP. Draw [red]{Cards}[/red] fewer cards on the first turn of your next [red]{Combats}[/red] combats.")
option("CROWDED_WARD", "BANDAGES", "拿些绷带", "回复[green]{BandageHeal}[/green]生命。",
       "Take Some Bandages", "Heal [green]{BandageHeal}[/green] HP.")
text("CROWDED_WARD.pages.TREATED.description", "蜗牛把你从头到脚裹了一遍，塞来一口苦得发麻的药。\n\n你活动了一下身体。伤口都好了。有一处却仍然隐隐作痛。",
     "The snail wraps you from top to bottom and gives you a mouthful of bitter medicine.\n\nYou stretch. The wounds are closed. One spot still aches.")
text("CROWDED_WARD.pages.ANESTHETIZED.description", "伤口不痛了。手指也不太听使唤。\n\n蜗牛把一张折好的[gold]病历[/gold]塞给你。\n\n“过一阵就好。”",
     "The pain fades. Your fingers seem to have gone with it.\n\nThe snail hands you a folded [gold]chart[/gold].\n\n“It will wear off.”")
text("CROWDED_WARD.pages.BANDAGES.description", "你拿了几卷绷带。蜗牛已经转向下一张床。\n\n被子下面传来一声不满的咕噜。",
     "You take a few rolls of bandages. The snail is already moving to the next bed.\n\nSomething grumbles beneath the blanket.")
text("ANESTHETIC_CHART.title", "麻醉记录", "Anesthetic Chart", "relics")
text("ANESTHETIC_CHART.description", "接下来[blue]{Combats}[/blue]场战斗，首回合少抽[red]{Cards}[/red]张牌。",
     "Draw [red]{Cards}[/red] fewer cards on the first turn of your next [blue]{Combats}[/blue] combats.", "relics")
text("ANESTHETIC_CHART.flavor", "“别急着握拳。”", "“Give your fingers a moment.”", "relics")
for slug, zh, en in (("BITING_CHEST", "会咬人的宝箱", "Biting Chest"), ("CROWDED_WARD", "满员的病房", "Crowded Ward")):
    text("STS2_THINGS-EVENT_" + slug + "_ENABLED.title", zh + " · 启用", en + " — enabled", "settings_ui")
    text("STS2_THINGS-EVENT_" + slug + "_ENABLED.description", "允许在深处遇到此事件。", "Allow this event in the Depths.", "settings_ui")

for lang, tables in TABLES.items():
    for table, updates in tables.items():
        path = ROOT / f"STS2_Things/localization/{lang}/{table}.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        original.update(updates)
        path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("DEPTHS_RISK_EVENT_LOCALISATION_PASS")
