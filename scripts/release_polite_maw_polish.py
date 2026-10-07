"""Release metadata for the direct Polite Maw options and prose revision."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json',
             'manifests/v107.1/STS2_Things.json','manifests/v111/STS2_Things.json',
             'bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name
    text=path.read_text('utf-8-sig')
    if '1.21.0' not in text and '1.21.1' not in text:
        raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.21.0','1.21.1'),'utf-8')
path=ROOT/'README.md'
text=path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.21.0`','当前 Mod 版本：`1.21.1`')
entry='- 1.21.1 将洞胃的攻击牌、技能牌交易分别放到首页；对照原版事件重写开场、各分支结果与选项文案，并调整正文留白以容纳多人四选项。[改动与预览](docs/polite-maw-polish.md)。\n'
if entry not in text:
    text=text.replace('- 1.21.0 加入',entry+'- 1.21.0 加入',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.21.1')
