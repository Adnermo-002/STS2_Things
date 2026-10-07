"""Release the Mycelial Bank, Unlit Fire and positive fallback choices."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name
    text=path.read_text('utf-8-sig')
    if '1.21.1' not in text and '1.22.0' not in text: raise RuntimeError('Unexpected version: '+name)
    path.write_text(text.replace('1.21.1','1.22.0'),'utf-8')
path=ROOT/'README.md'
text=path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.21.1`','当前 Mod 版本：`1.22.0`')
entry='- 1.22.0 加入深处事件「菌根借贷所」「还没烧起来的火」：生命分期与最大生命存款、提前休息或锻造、未来火堆添柴；用原生存档和休息点流程结算。洞胃四种喂食直接展开，自制深处事件以 15 金币小收益替代空离开。[设计与交付](docs/mycelial-bank-and-unlit-fire.md)。\n'
if entry not in text: text=text.replace('- 1.21.1 将',entry+'- 1.21.1 将',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.22.0')
