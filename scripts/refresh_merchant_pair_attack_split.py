"""Author just the changed bilingual event text; preserve other entries."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGES = {
    "zhs": {
        "ROBBERY_FAKE_MERCHANT.pages.INITIAL.description": "两名商人挤在同一块地毯上。一名举着[gold]遗物[/gold]，另一名正照着它[sine][purple]捏出一件赝品[/purple][/sine]。\n\n“如假包换！”\n“假一赔二！”\n\n他们正忙着互相捧场。货物和钱袋，就摆在地毯边。",
        "ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.BEGINFIGHT.description": "与[red]两名假商人[/red]战斗。胜利后获得[blue]{TrueRelicsCount}[/blue]件随机[gold]遗物[/gold]。",
        "ROBBERY_FAKE_MERCHANT.pages.TAKERELICS.description": "你抓起几件货物。边角软了些，分量也不太对。\n\n[red][jitter]“我的货！”\n“我们的货！”[/jitter][/red]\n\n你趁他们争论时溜走了。",
        "ROBBERY_FAKE_MERCHANT.pages.TAKEGOLDS.description": "你勾走钱袋。金币的声音让两名商人同时回过头。\n\n[red][jitter]“你不是在看钱吗？”\n“我在看你啊！”[/jitter][/red]\n\n你带着真金子，离开了这家卖假货的店。",
        "ROBBERY_FAKE_MERCHANT.pages.BEGINFIGHT.description": "你把真货和赝品摆到一起。\n\n一名商人将货架推到身后。另一名堵住了出口。\n\n[red][jitter]“朋友，别砸我们的招牌。”[/jitter][/red]",
        "ROBBERY_FAKE_MERCHANT.pages.TAKETRUERELICS.description": "两名商人都不见了。赝品散落一地，软得像没烤熟的面团。\n\n桌上那几件拿来仿制的[gold]真货[/gold]，倒还完好无损。",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description": "移除一张[gold]攻击牌[/gold]。获得[blue]2[/blue]张附有[purple]{Enchantment}[/purple]的复制品。",
        "CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt": "选择一张攻击牌进行分裂。",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE_LOCKED.title": "锁定",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE_LOCKED.description": "没有可分裂的攻击牌。",
    },
    "eng": {
        "ROBBERY_FAKE_MERCHANT.pages.INITIAL.description": "Two merchants share a crowded rug. One holds up a [gold]Relic[/gold]. The other [sine][purple]moulds a counterfeit[/purple][/sine] to match.\n\n“Guaranteed genuine!”\n“Twice your money back!”\n\nThey are busy applauding each other. Their wares and coin purse lie at the edge of the rug.",
        "ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.BEGINFIGHT.description": "Fight [red]2 Fake Merchants[/red]. Obtain [blue]{TrueRelicsCount}[/blue] random [gold]Relics[/gold] on victory.",
        "ROBBERY_FAKE_MERCHANT.pages.TAKERELICS.description": "You pocket a few pieces. The edges are soft. The weight is wrong.\n\n[red][jitter]“My wares!”\n“Our wares!”[/jitter][/red]\n\nYou slip away while they settle the matter.",
        "ROBBERY_FAKE_MERCHANT.pages.TAKEGOLDS.description": "You hook the purse. Both merchants turn at the sound of coins.\n\n[red][jitter]“Weren't you watching the money?”\n“I was watching you!”[/jitter][/red]\n\nYou leave the counterfeit shop with genuine gold.",
        "ROBBERY_FAKE_MERCHANT.pages.BEGINFIGHT.description": "You place the original beside the counterfeit.\n\nOne merchant pushes the shelf behind him. The other blocks the exit.\n\n[red][jitter]“Friend, let's not ruin our good name.”[/jitter][/red]",
        "ROBBERY_FAKE_MERCHANT.pages.TAKETRUERELICS.description": "Both merchants are gone. Counterfeits litter the floor, soft as underbaked dough.\n\nThe [gold]genuine Relics[/gold] they copied are still on the table, untouched.",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description": "Remove an [gold]Attack[/gold] card. Add [blue]2[/blue] copies [gold]Enchanted[/gold] with [purple]{Enchantment}[/purple] to your [gold]Deck[/gold].",
        "CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt": "Choose an Attack card to split.",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE_LOCKED.title": "Locked",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE_LOCKED.description": "You have no Attack cards that can be split.",
    },
}
ENCOUNTERS = {
    "zhs": {"ROBBERY_FAKE_MERCHANT_ENCOUNTER.title": "诡谲双商", "ROBBERY_FAKE_MERCHANT_ENCOUNTER.lossMessage": "下次，记得索要收据。"},
    "eng": {"ROBBERY_FAKE_MERCHANT_ENCOUNTER.title": "Shifty Partners", "ROBBERY_FAKE_MERCHANT_ENCOUNTER.lossMessage": "Next time, ask for a receipt."},
}
for lang in CHANGES:
    for table, updates in (("events", CHANGES[lang]), ("encounters", ENCOUNTERS[lang])):
        path = ROOT / f"STS2_Things/localization/{lang}/{table}.json"
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
        existing.update(updates)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("MERCHANT_PAIR_ATTACK_SPLIT_TEXT_PASS")
