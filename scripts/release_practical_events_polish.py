"""Advance metadata for native-style event text and the revised choices."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj', 'STS2_Things.json', 'manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json', 'bootstrap/STS2_Things.Bootstrap.csproj', 'bootstrap/UnifiedBootstrap.cs'):
    path = ROOT / name
    text = path.read_text('utf-8-sig')
    if '1.23.0' not in text and '1.23.1' not in text:
        raise RuntimeError('Unexpected version: ' + name)
    path.write_text(text.replace('1.23.0', '1.23.1'), 'utf-8')
path = ROOT / 'README.md'
text = path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.23.0`', '当前 Mod 版本：`1.23.1`')
entry = '- 1.23.1 对照原版重写三个实用事件的文风；出售遗物改为 200 金币，试饮会直接给予随机药水，窄门前三项直接移除对应牌、第四项付费重选。[设计与交付](docs/practical-depths-events.md)。\n'
if entry not in text:
    text = text.replace('- 1.23.0 加入', entry + '- 1.23.0 加入', 1)
path.write_text(text, 'utf-8')
print('Release metadata: 1.23.1')
