"""Bump only release metadata for the snail motion refinement."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.18.0' not in text and '1.18.1' not in text:raise RuntimeError('Unexpected release version: '+name)
    path.write_text(text.replace('1.18.0','1.18.1'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig')
text=text.replace('当前 Mod 版本：`1.18.0`','当前 Mod 版本：`1.18.1`')
entry='- 1.18.1 精修三只蜗牛的骨骼动作：腹足逐段发力，晶壳先收触角再缩头，涎丝鼓喉吐涎，爬岩蓄力后推着重壳前冲；硬壳保持刚性并约束落地，死亡时完整壳随倒下动作保留。[动作制作记录](docs/depths-snails-animation-polish.md)。\n'
if entry not in text:text=text.replace('- 1.18.0 加入',entry+'- 1.18.0 加入',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.18.1')
