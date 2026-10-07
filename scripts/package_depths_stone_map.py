"""Check native stitched-vs-whole rendering and package only the selected map art."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/depths_stone_map'
SOURCE=ROOT/'source_assets/backgrounds/depths_stone_map'
OUT=BUILD/'delivery'
OUT.mkdir(exist_ok=True)
report=json.loads((BUILD/'verification.json').read_text(encoding='utf-8'))
selected=json.loads((SOURCE/'selection.json').read_text(encoding='utf-8'))
revision=int(selected['revision'])
with Image.open(BUILD/'native_full.png') as im:
    stitched=np.array(im.convert('RGBA')).astype(np.int16)
with Image.open(BUILD/'native_uncut_reference.png') as im:
    whole=np.array(im.convert('RGBA')).astype(np.int16)
delta=np.abs(stitched-whole)
if delta.max()>2:
    raise RuntimeError('Native tiled rendering diverges from the uncut artwork')
native_log=(BUILD/'native.stdout.log').read_text(encoding='utf-8-sig')
if 'Depths stone map render: PASS' not in native_log:
    raise RuntimeError('No native layout verification')
for name in ['native.stderr.log','import.stderr.log']:
    if 'ERROR:' in (BUILD/name).read_text(encoding='utf-8-sig'):
        raise RuntimeError('Godot error: '+name)
report['native_render']={
    'engine':'Godot 4.5.1 / OpenGL',
    'layout':'Original map VBoxContainer geometry: 3 x 1080, separation 0, TextureRect KEEP_ASPECT_CENTERED',
    'stitched_vs_uncut_max_channel_delta':int(delta.max()),
    'stitched_vs_uncut_mean_channel_delta':float(delta.mean()),
    'join_max_deltas':{str(y):int(delta[y-6:y+6].max()) for y in [1080,2160]},
    'readability_sample':'Original atlas icons on an illustrative route, not a gameplay screenshot'}
report['visual_review']=selected['direction']
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
readme='''# 深处大地图：SELECTED_TITLE

SELECTED_DESCRIPTION

本包是贴图资源包，不是完整模组 DLL/PCK。三个 PNG 已在本项目的原生地图路径中更新并经过 Godot 重新导入。
其他工程使用时，将 images 目录合并到对应模组工程，重新导入并导出模组 PCK；使用原来的 Depths 贴图路径，无需修改游戏地图布局。

- 上／中／下各 2036×1440 RGBA，完整母图 2036×4320。
- 三张从同一张归一化后的绘画相邻裁切，重组与完整母图逐像素一致。
- Godot 原版尺寸和缩放方式的三段渲染与单张完整图最大差异为 1/255，接缝没有额外色带或空隙。
- 保留原版的路径与节点绘制。route_readability_sample.png 是使用原版图标的可读性示意，不是实际游戏存档截图。

source_assets 中保留各版原始生成图片和最终母图；本包附带当前选定版本的提示词。图像通过此前指定接口、imagegen CLI gpt-image-2/high 生成。
重建：python scripts/build_depths_stone_map.py --deploy。整章资产准备脚本也会使用已选定的石板方案，不再覆盖回旧洞穴淡化贴图。
'''
title='石板（第一版）' if revision==1 else '沉海化石板（第二版）'
description=('按用户最终选择恢复第一版：浅蓝灰石面、风化边缘和细微矿物纹理，中部保留路线空间。'
             if revision==1 else '宽阔扁平色面、粗断层和边缘化石轮廓，菊石与鱼骨用于区分深处。')
(OUT/'README.md').write_text(readme.replace('SELECTED_TITLE',title).replace('SELECTED_DESCRIPTION',description),encoding='utf-8')
for name in ['stone_full_preview.jpg','seams_preview.jpg','route_readability_sample.png','native_scroll_540.png','native_scroll_1620.png']:
    shutil.copy2(BUILD/name,OUT/name)
shutil.copy2(SOURCE/selected['master'],OUT/'depths_stone_master.png')
shutil.copy2(SOURCE/selected['prompt'],OUT/'prompt.txt')
archive_path=OUT/f'Depths_Stone_Map_v{revision}.zip'
with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted((BUILD/'images').rglob('*.png')):
        z.write(p,p.relative_to(BUILD).as_posix())
    for name in ['README.md','verification.json','prompt.txt','depths_stone_master.png','stone_full_preview.jpg','seams_preview.jpg','route_readability_sample.png']:
        z.write(OUT/name,name)
with zipfile.ZipFile(archive_path) as z:
    assert z.testzip() is None
with archive_path.open('rb') as f:
    sha=hashlib.file_digest(f,'sha256').hexdigest()
print(json.dumps({'package':str(archive_path),'bytes':archive_path.stat().st_size,'sha256':sha,'native_max_delta':int(delta.max())},ensure_ascii=False,indent=2))
