"""Record the taller, sky-reaching column silhouette in release metadata."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for name in ('STS2_Things.csproj','STS2_Things.json','manifests/v107.1/STS2_Things.json',
             'manifests/v111/STS2_Things.json','bootstrap/STS2_Things.Bootstrap.csproj','bootstrap/UnifiedBootstrap.cs'):
    path=ROOT/name
    text=path.read_text('utf-8-sig')
    if '1.24.0' not in text and '1.24.1' not in text:
        raise RuntimeError('Unexpected version: '+name)
    path.write_text(text.replace('1.24.0','1.24.1'),'utf-8')
path=ROOT/'README.md'
text=path.read_text('utf-8-sig').replace('当前 Mod 版本：`1.24.0`','当前 Mod 版本：`1.24.1`')
entry='- 1.24.1 继续拉高人面柱：单层高约 310 像素，接触层距 190 像素，柱顶延伸至画面之外；同步调整命中区域和原生意图、血条的位置，普通动作仍只水平滑动。\n'
if entry not in text:
    text=text.replace('- 1.24.0 加入人面柱',entry+'- 1.24.0 加入人面柱',1)
path.write_text(text,'utf-8')
print('Release metadata: 1.24.1')
