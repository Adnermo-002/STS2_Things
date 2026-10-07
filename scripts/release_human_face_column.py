"""Advance release metadata for the column and its two Depths encounters."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name;text=path.read_text('utf-8-sig')
    if '1.23.1' not in text and '1.24.0' not in text:raise RuntimeError('Unexpected version: '+name)
    path.write_text(text.replace('1.23.1','1.24.0'),'utf-8')
path=ROOT/'README.md';text=path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.23.1`','当前 Mod 版本：`1.24.0`')
entry='- 1.24.0 加入人面柱：六层石饼、三层同时战斗、上层免伤与中层半减伤，击碎后补层并眩晕；独立错拍行动与双向人脸旋转。弱池单柱，强池搭配爬岩蜗牛。[设计与交付](docs/human-face-column.md)。\n'
if entry not in text:text=text.replace('- 1.23.1 对照',entry+'- 1.23.1 对照',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.24.0')
