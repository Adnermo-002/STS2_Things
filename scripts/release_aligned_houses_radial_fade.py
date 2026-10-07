"""Release metadata for the complete landscape with continuous peripheral fade."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj', 'STS2_Things.json',
             'manifests/v107.1/STS2_Things.json', 'manifests/v111/STS2_Things.json',
             'bootstrap/STS2_Things.Bootstrap.csproj', 'bootstrap/UnifiedBootstrap.cs'):
    path = ROOT / name
    text = path.read_text('utf-8-sig')
    if '1.19.3' not in text and '1.19.4' not in text:
        raise RuntimeError('Unexpected release version: ' + name)
    path.write_text(text.replace('1.19.3', '1.19.4'), 'utf-8')

path = ROOT / 'README.md'
text = path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.19.3`', '当前 Mod 版本：`1.19.4`')
entry = '- 1.19.4 调整「对齐之屋」明暗构图：完整场景从中心向周边连续渐暗，天空、房屋与草地延伸到暗部，取消围绕主体的开窗遮罩。同步更新后续事件规范。[制作记录](docs/reality-aligned-houses.md) · [事件美术规范](docs/event-art-guidelines.md)。\n'
if entry not in text:
    text = text.replace('- 1.19.3 打磨', entry + '- 1.19.3 打磨', 1)
path.write_text(text, 'utf-8')
print('Release metadata: 1.19.4')
