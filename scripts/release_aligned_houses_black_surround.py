"""Release metadata for the native black event-surround correction."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.19.1' not in text and '1.19.2' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.19.1','1.19.2'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.19.1`','当前 Mod 版本：`1.19.2`')
entry='- 1.19.2 修正「对齐之屋」黑边构图：恢复左侧独立插画、四周大面积黑色留白与右侧黑色文字区，使用原版文字样式。[构图与制作记录](docs/reality-aligned-houses.md)。\n'
if entry not in text:text=text.replace('- 1.19.1 重做',entry+'- 1.19.1 重做',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.19.2')
