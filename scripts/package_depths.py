"""Package the verified dual-version loader and shared region resources, without installation."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/depths';OUT=BUILD/'delivery'
MOD=OUT/'STS2_Things';MOD.mkdir(parents=True,exist_ok=True)
files={'STS2_Things.dll':BUILD/'bootstrap/STS2_Things.Bootstrap.dll',
       'STS2_Things.pck':BUILD/'v111/STS2_Things.pck','STS2_Things.json':ROOT/'STS2_Things.json'}
bridge=ROOT/'build/v111/STS2_Things.BaseLibBridge.dll'
if bridge.exists():files['STS2_Things.BaseLibBridge.dll']=bridge
for name,path in files.items():assert path.is_file();shutil.copy2(path,MOD/name)
text='''# 尖塔：琐事 · 深处整合构建

本包包含自动选择 v0.107.1 / v0.111 实现的统一加载器。替换现有同名 STS2_Things 模组目录，勿与另一份同 ID 模组并列加载。版本号保持 1.10.9；这是当前工作区整合构建，尚未发布到 Steam/GitHub。

已接入：深处作为与巢穴并列的第二章候选；前两场普通战使用两条灯笼鱼的弱怪池，后续使用三条灯笼鱼的强怪池。精英暂用原版巢穴三场精英。活体巨岩可出现在巢穴与深处，深处默认使用它；禁用／零权重时回退帝王蟹以保证章节可生成。

灯笼鱼固定使用回水石湾。营地为单独新绘场景，四个石凳及火塘为独立新绘图层，按原版角色坐姿接触点定位，保留原坐标、0.5缩放与动画。营地地板独立生成，火焰与暖光可按原生逻辑熄灭。

正常新开局即可选到深处，旧存档不改写路线。要直接测试，在一局中依次执行：

    act 2
    act DEPTHS

独立遭遇指令：

    fight LANTERN_FISH_WEAK
    fight LANTERN_FISH_ENCOUNTER
    fight CAVE_GOD_BOSS_ENCOUNTER

验证：v111 原生章节／资源／渲染 768 项断言通过；v107.1 753 项通过；原版营地坐姿 159 项通过；灯笼鱼机制回归 66 项通过；统一加载器在两个目标上通过模型一致性及嵌入实现哈希验证。最终渲染错误日志为空。

尚未进行真人长局平衡或双机实测。新增的其他深处怪物仍是设计稿，本次没有用占位怪替代。

详细说明：项目 design/depths_act_integration.md。营地使用指定接口的 imagegen CLI gpt-image-2/high 生成；完整提示词及局部编辑记录位于 source_assets/backgrounds/depths_camp。重建和游戏运行均不需要 API 密钥。
'''
(OUT/'README.md').write_text(text,encoding='utf-8')
for source,name in [('camp_review/single_seat.png','camp_single.png'),('camp_review/four_seats.png','camp_four_players.png'),
                    ('camp_review/camp_fire_out.png','camp_fire_out.png'),('visuals/weak_pair.png','weak_pair.png'),
                    ('visuals/strong_shoal.png','strong_shoal.png'),('visuals/chapter_banner.png','chapter_banner.png'),
                    ('visuals/map_overview.png','map_route_overview.png')]:shutil.copy2(BUILD/source,OUT/name)
for name in ['visual.stdout.log','visual.stderr.log','probe-v107.1.stdout.log','probe-v107.1.stderr.log','camp.stdout.log','camp.stderr.log','unified-verification.log','fish-regression-v111.log']:
    shutil.copy2(BUILD/name,OUT/name)
for path in OUT.glob('*.stderr.log'):assert not path.read_text(encoding='utf-8-sig').strip(),path.name
archive=OUT/'STS2_Things_Depths_Integrated.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for file in MOD.iterdir():z.write(file,'STS2_Things/'+file.name)
    z.write(OUT/'README.md','README.md')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
manifest=[]
for file in [archive,*MOD.iterdir()]:
    with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest.append({'file':file.relative_to(OUT).as_posix(),'bytes':file.stat().st_size,'sha256':digest})
(OUT/'checksums.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
