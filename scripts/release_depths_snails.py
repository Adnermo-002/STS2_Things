"""Version metadata for the new weak encounter; build/install are separate steps."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.17.9' not in text and '1.18.0' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.17.9','1.18.0'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.17.9`','当前 Mod 版本：`1.18.0`')
entry='- 1.18.0 加入「洞穴蜗牛」弱池遭遇：晶壳、涎丝、爬岩各一只。破壳赠晶片、修补盟友与可打断的爬行碾压；按原版盛碗虫弱遭遇分配生命与输出。三个独立原画、29／42／29 骨骼、各 11 组动作，使用原创石英洞穴。[设计、数值与素材](docs/depths-snails.md)。\n'
if entry not in text:text=text.replace('- 1.17.9 将 Cave God',entry+'- 1.17.9 将 Cave God',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.18.0')
