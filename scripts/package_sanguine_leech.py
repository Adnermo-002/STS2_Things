"""Package only verified leech gameplay/assets and derive previews from native captures."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import zipfile
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/sanguine_leech'
DEST=BUILD/'delivery'
DEST.mkdir(parents=True,exist_ok=True)

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def check_log(path,pattern):
    text=path.read_text(encoding='utf-8-sig',errors='replace')
    matches=re.findall(pattern,text)
    if not matches:
        raise RuntimeError(f'Missing verification marker: {path}')
    return int(matches[-1])

checks={}
for target in ['v111','v107.1']:
    checks[target]={
        'behavior_assertions':check_log(BUILD/f'behavior-{target}.stdout.log',r'Sanguine Leech probe: PASS \((\d+) assertions\)'),
        'chapter_assertions':check_log(BUILD/f'chapter-verification/probe-{target}.stdout.log',r'Depths act probe: PASS \((\d+) assertions\)'),
        'implementation_sha256':sha(BUILD/target/'STS2_Things.dll')}
    for path in [BUILD/f'behavior-{target}.stderr.log',BUILD/f'chapter-verification/probe-{target}.stderr.log']:
        if re.search(r'(^|\n)(ERROR:|SCRIPT ERROR)',path.read_text(encoding='utf-8-sig')):
            raise RuntimeError(f'Native errors remain: {path}')
checks['visual_assertions']=check_log(BUILD/'visual.stdout.log',r'Sanguine Leech probe: PASS \((\d+) assertions\)')
if re.search(r'(^|\n)(ERROR:|SCRIPT ERROR)',(BUILD/'visual.stderr.log').read_text(encoding='utf-8-sig')):
    raise RuntimeError('Native visual errors remain')
unified=(BUILD/'unified-verification.log').read_text(encoding='utf-8-sig')
for target in ['v107.1','v111']:
    if f'Unified package probe: PASS ({target},' not in unified:
        raise RuntimeError('Unified package not verified')
    if checks[target]['implementation_sha256'].upper() not in unified:
        raise RuntimeError('Unified package does not contain the tested implementation')
checks['spine']=json.loads((ROOT/'tools/SanguineLeechRig/pkg/verification.json').read_text())
if checks['spine']['result']!='PASS' or checks['spine']['invertedTriangles']:
    raise RuntimeError('Spine geometry not verified')
with Image.open(BUILD/'visuals/pose_idle_loop_0.png') as a, Image.open(BUILD/'visuals/pose_die_3.png') as b:
    region=(870,585,1245,812)
    change=ImageStat.Stat(ImageChops.difference(a.convert('RGB').crop(region),b.convert('RGB').crop(region))).mean
    if sum(change)/3 < 5:
        raise RuntimeError('Native captures did not advance the leech pose; flush CanvasItem redraws before capture')
    checks['native_death_pose_mean_pixel_change']=round(sum(change)/3,3)

folder=DEST/'STS2_Things'
folder.mkdir(exist_ok=True)
versions=[]
for target in ['v111','v107.1']:
    dependencies=json.loads((BUILD/target/'STS2_Things.deps.json').read_text(encoding='utf-8-sig'))
    entries=[name.split('/',1)[1] for name in dependencies['libraries'] if name.startswith('STS2_Things/')]
    if len(entries)!=1:
        raise RuntimeError('Cannot determine tested implementation version')
    versions.extend(entries)
if len(set(versions))!=1:
    raise RuntimeError('Tested implementation versions differ')
tested_version=versions[0]
for name,source in {
 'STS2_Things.dll':BUILD/'bootstrap/STS2_Things.Bootstrap.dll',
 'STS2_Things.pck':BUILD/'v111/STS2_Things.pck'
}.items():
    shutil.copy2(source,folder/name)
# Other work may advance the workspace manifest while this isolated task is being
# verified. Label the staged snapshot with its tested DLL version, not that later version.
manifest=json.loads((ROOT/'STS2_Things.json').read_text(encoding='utf-8-sig'))
manifest['version']=tested_version
(folder/'STS2_Things.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checks['snapshot_version']=tested_version

readme='''# 深处：吸血血蛭整合构建

这是本任务验证过的源码快照，模组版本为 SNAPSHOT_VERSION。一个安装包兼容 v107.1 和 v111，入口按实际游戏 API 选择已验证的实现。
包含原有内容、弱池两只血蛭、强池三只血蛭，以及寄生牌、原创贴图和完整骨骼动画。

安装：关闭游戏，备份已有模组，将 STS2_Things 文件夹内的同名 DLL / PCK / JSON 覆盖到游戏 mods/STS2_Things。
保留你已有的可选桥接文件与配置。本任务没有自动改动游戏安装目录。

测试控制台：

    fight SANGUINE_LEECH_WEAK
    fight SANGUINE_LEECH_ENCOUNTER

定位第二章深处时先 act 2，再 act DEPTHS。名称命令替换当前章节。

生命 26–30（高进阶 30–34），啜血 4（高进阶 5），按造成的实际生命伤害回血；完全格挡可阻止回血。
行动循环：啜血 → 寄生 → 再啜 → 盘伏 6 格挡。两只／三只错开起手，不会全部同时施加寄生。
每只在战斗开始给予玩家一张战斗内寄生，原版固有将其带入起手。寄生为 1 费、固有、消耗。
每张在回合结束时留手，所有存活血蛭各获得 2 再生、2 力量；提前打出、丢弃或消耗可避免。
没有血蛭时不强化其他怪物。使用原版再生与力量效果，兼容两个版本各自的原生回合结算。

角色与卡面通过用户指定图像接口、imagegen CLI gpt-image-2/high 重新生成，以原版尸蛞蝓／绒毛蠕虫贴图作风格参考。
17 骨骼、10 动作、连续加权网格。源码、提示词、制作方法与自审记录保存在项目 design/sanguine_leech.md 和 tools/SanguineLeechRig/。
角色立绘、卡牌插画、三只实际战斗排布与地面接触已经自审，最终画风采用带卡通比例的宽阔手绘色块。

验证结果见 verification.json。截图与动图来自真实 Godot 的原生 NCreature / NCard / Spine 渲染，属于隔离测试场景；
尚未宣称长局平衡或双机联网已经人工通关验证。工作流没有使用或修改玩家存档。
'''
(DEST/'README.md').write_text(readme.replace('SNAPSHOT_VERSION',tested_version),encoding='utf-8')
(DEST/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(ROOT/'design/sanguine_leech.md',DEST/'design.md')
for name in ['weak_pair','strong_colony','parasite_feeding','parasite_card_native']:
    shutil.copy2(BUILD/'visuals'/f'{name}.png',DEST/f'{name}.png')
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
names=['idle_loop','attack','cast','curl','feed','hurt','die','revive','summon','power_up']
sheet=Image.new('RGB',(1440,790),'#182630')
for i,name in enumerate(names):
    with Image.open(BUILD/'visuals'/f'pose_{name}_1.png') as im:
        tile=im.convert('RGB').crop((820,415,1285,830)).resize((288,255),Image.Resampling.LANCZOS)
    x,y=(i%5)*288,(i//5)*390
    sheet.paste(tile,(x,y+43))
    ImageDraw.Draw(sheet).text((x+16,y+11),name,font=font,fill='#e6d9b9')
sheet=sheet.crop((0,0,1440,700))
sheet.save(DEST/'animation_contact_sheet.jpg',quality=94)
frames=[]
for path in sorted((BUILD/'visuals').glob('sequence_*.png')):
    with Image.open(path) as im:
        frames.append(im.convert('RGB').resize((960,540),Image.Resampling.LANCZOS))
if len(frames)!=36:
    raise RuntimeError('Expected 36 native animation frames')
frames[0].save(DEST/'leech_demo.webp',save_all=True,append_images=frames[1:],duration=83,loop=0,quality=85)
palette=frames[0].quantize(colors=192)
gif=[frame.quantize(palette=palette) for frame in frames]
gif[0].save(DEST/'leech_demo.gif',save_all=True,append_images=gif[1:],duration=80,loop=0,optimize=False)
zip_path=DEST/'STS2_Things_Leeches_Integrated.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for file in folder.iterdir():
        archive.write(file,'STS2_Things/'+file.name)
    for name in ['README.md','verification.json','design.md']:
        archive.write(DEST/name,name)
with zipfile.ZipFile(zip_path) as archive:
    if archive.testzip() is not None:
        raise RuntimeError('ZIP integrity failure')
manifest={'file':zip_path.name,'bytes':zip_path.stat().st_size,'sha256':sha(zip_path),
          'artifacts':{file.name:sha(file) for file in folder.iterdir()}}
(DEST/'checksums.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
