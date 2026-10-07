"""Version metadata for the open-prairie event revision."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.19.0' not in text and '1.19.1' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.19.0','1.19.1'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.19.0`','当前 Mod 版本：`1.19.1`')
entry='- 1.19.1 重做「对齐之屋」：开放草原、双侧无尽住宅大道与 Frutiger Aero 式晴空；加入同名牌合并、升级并赋予完美契合、可逐圈加码的绕路收益，以及蓝屋出口。[当前设计与美术](docs/reality-aligned-houses.md)。\n'
if entry not in text:text=text.replace('- 1.19.0 加入',entry+'- 1.19.0 加入',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.19.1')
