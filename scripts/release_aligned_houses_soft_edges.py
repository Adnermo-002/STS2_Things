"""Release metadata for the landscape-to-black transition polish."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.19.2' not in text and '1.19.3' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.19.2','1.19.3'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.19.2`','当前 Mod 版本：`1.19.3`')
entry='- 1.19.3 打磨「对齐之屋」插画：主体集中在画区中部约 2/3，四周柔和留白，删除右侧直切边缘；房屋与道路保持清晰，沿用原版文字布局。此构图记为后续事件基准。[制作记录](docs/reality-aligned-houses.md) · [事件美术规范](docs/event-art-guidelines.md)。\n'
if entry not in text:text=text.replace('- 1.19.2 修正',entry+'- 1.19.2 修正',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.19.3')
