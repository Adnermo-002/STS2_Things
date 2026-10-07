"""Advance release metadata for the three practical Depths events."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj', 'STS2_Things.json', 'manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json', 'bootstrap/STS2_Things.Bootstrap.csproj', 'bootstrap/UnifiedBootstrap.cs'):
    path = ROOT / name
    text = path.read_text('utf-8-sig')
    if '1.22.0' not in text and '1.23.0' not in text:
        raise RuntimeError('Unexpected version: ' + name)
    path.write_text(text.replace('1.22.0', '1.23.0'), 'utf-8')
path = ROOT / 'README.md'
text = path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.22.0`', '当前 Mod 版本：`1.23.0`')
entry = '- 1.23.0 加入深处事件「遗物修补摊」「药水试饮会」「窄门」：预览遗物交易与出售、三选一或三选二药水、三张随机候选牌的免费移除与一次付费重选。个人结算，使用原版奖励与选择流程，无损选项按主题提供零钱、免费药水或少量回复。[设计与交付](docs/practical-depths-events.md)。\n'
if entry not in text:
    text = text.replace('- 1.22.0 加入', entry + '- 1.22.0 加入', 1)
path.write_text(text, 'utf-8')
print('Release metadata: 1.23.0')
