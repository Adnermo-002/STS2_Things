"""Release metadata for the Depths' Shadow Cloakroom event."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj', 'STS2_Things.json',
             'manifests/v107.1/STS2_Things.json', 'manifests/v111/STS2_Things.json',
             'bootstrap/STS2_Things.Bootstrap.csproj', 'bootstrap/UnifiedBootstrap.cs'):
    path = ROOT / name
    text = path.read_text('utf-8-sig')
    if '1.19.4' not in text and '1.20.0' not in text:
        raise RuntimeError('Unexpected release version: ' + name)
    path.write_text(text.replace('1.19.4', '1.20.0'), 'utf-8')

path = ROOT / 'README.md'
text = path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.19.4`', '当前 Mod 版本：`1.20.0`')
entry = '- 1.20.0 加入深处事件「影子寄存处」：支付 25 金币寄存一张可升级牌，在本章 Boss 战前升级归还。原生收据保存完整卡牌信息，多人各自选择；配套事件插画、遗物图标与中英文文本。[设计与交付](docs/shadow-cloakroom.md)。\n'
if entry not in text:
    text = text.replace('- 1.19.4 调整', entry + '- 1.19.4 调整', 1)
path.write_text(text, 'utf-8')
print('Release metadata: 1.20.0')
