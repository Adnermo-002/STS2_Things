"""Release metadata for Echoing Well and Polite Maw."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj', 'STS2_Things.json',
             'manifests/v107.1/STS2_Things.json', 'manifests/v111/STS2_Things.json',
             'bootstrap/STS2_Things.Bootstrap.csproj', 'bootstrap/UnifiedBootstrap.cs'):
    path = ROOT / name
    text = path.read_text('utf-8-sig')
    if '1.20.0' not in text and '1.21.0' not in text:
        raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.20.0','1.21.0'),'utf-8')
path = ROOT/'README.md'
text = path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.20.0`','当前 Mod 版本：`1.21.0`')
entry = '- 1.21.0 加入深处事件「收音井」与「礼貌的洞胃」：封存攻击或技能换取三场首回合免费回响；按喂食牌型领取药水、金币或预览遗物，喂诅咒则除咒并进入洞胃战斗。配套新插画、回声遗物、中英文文本与原生多人投票流程。[设计与交付](docs/echoing-well-and-polite-maw.md)。\n'
if entry not in text:
    text = text.replace('- 1.20.0 加入',entry+'- 1.20.0 加入',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.21.0')
