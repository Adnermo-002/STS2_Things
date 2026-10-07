"""Release metadata for the first exclusive Depths event."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.18.1' not in text and '1.19.0' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.18.1','1.19.0'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.18.1`','当前 Mod 版本：`1.19.0`')
entry='- 1.19.0 加入深处专属事件「对齐之屋」：复制一张牌并获得悔恨，或付出 10 点生命移除一张牌，也可从蓝屋离开。以 Backrooms Level 995 为灵感，配套原创事件插画、双语剧情和原版选牌流程。[设计、美术与来源](docs/reality-aligned-houses.md)。\n'
if entry not in text:text=text.replace('- 1.18.1 精修',entry+'- 1.18.1 精修',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.19.0')
