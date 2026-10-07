"""Create reviewable test packages; never writes to the live game installation."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/lantern_fish'
DEST=BUILD/'delivery';DEST.mkdir(parents=True,exist_ok=True)
readme='''# 深处：三条灯笼鱼 · 独立测试构建

这是“尖塔：琐事”当前项目的测试快照，模组版本维持 1.10.9。请选择与游戏版本匹配的包，使用包内 STS2_Things 文件夹替换同名模组；不要把两个版本同时加载。本交付没有自动修改游戏目录。

进入一局后，在开发控制台执行：

    fight LANTERN_FISH_ENCOUNTER

三条漂浮灯笼鱼，38–42 HP（高进阶42–46），循环：啮咬6 → 耀闪2层致盲 → 甩尾4×2 → 收灯9格挡。三条起手错开。高进阶单次伤害+1。

致盲使接下来实际抽到的N张牌随机成1–3能量费用，牌面花屏、描述乱码，当前玩家回合结束恢复。X费、不可打出的牌保留特殊规则，星能不变；原生全局费用修正正常生效。未用完计数保留，上限6。人工制品可抵挡。

最终怪物为纯鱼形，无手脚，参考原版灵魂鱼的卡通比例与柔和手绘色块重新生成。24根Spine骨骼，10组动作，包含悬浮、啮咬、甩尾、耀闪、收灯、受击、死亡等。场景使用新画的河湾洞穴及新地板。

验证：v111与v107.1各65项原生玩法断言通过；官方Spine 4.2.43采样982帧，无翻折；v111完整原生视觉探针91项断言通过，最后布局复查41项断言通过，错误日志为空。已完成画风、实际战斗尺寸与回合恢复自审。

本场未加入章节随机池，后续接入“深处”。尚未进行真人长局平衡或双机实测。原版v111禁止局中加入，本次没有增加重连协议。

完整实现、原画、提示词、自审与重建方法在项目 design/lantern_fish_encounter.md、source_assets/monsters/lantern_fish/ 和 tools/LanternFishRig/。原画通过用户指定接口、imagegen CLI gpt-image-2/high生成；密钥没有写入资产或测试包。
'''
(DEST/'README.md').write_text(readme,encoding='utf-8')
manifest=[]
for version in ['v111','v107.1']:
    folder=DEST/version/'STS2_Things';folder.mkdir(parents=True,exist_ok=True)
    files={'STS2_Things.dll':BUILD/version/'STS2_Things.dll',
           'STS2_Things.pck':BUILD/'v111/STS2_Things.pck',
           'STS2_Things.json':ROOT/f'manifests/{version}/STS2_Things.json'}
    for name,source in files.items():
        assert source.is_file(),source
        shutil.copy2(source,folder/name)
    zip_path=DEST/f'LanternFish_Test_{version}.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in folder.iterdir():archive.write(file,'STS2_Things/'+file.name)
        archive.write(DEST/'README.md','README.md')
    with zipfile.ZipFile(zip_path) as archive:assert archive.testzip() is None
    manifest.append({'file':zip_path.name,'bytes':zip_path.stat().st_size,'sha256':hashlib.file_digest(zip_path.open('rb'),'sha256').hexdigest()})
for name in ['lantern_fish_demo.gif','lantern_fish_demo.webp','style_comparison.jpg','animation_contact_sheet.jpg']:
    shutil.copy2(BUILD/'review'/name,DEST/name)
shutil.copy2(BUILD/'visuals/cards_blinded.png',DEST/'encounter_preview.png')
shutil.copy2(ROOT/'tools/LanternFishRig/pkg/verification.json',DEST/'spine_verification.json')
for name in ['behavior-v111.log','behavior-v107.1.log','visual-full.stdout.log','visual-full.stderr.log','visual.stdout.log','visual.stderr.log']:
    shutil.copy2(BUILD/name,DEST/name)
(DEST/'checksums.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
