"""Check and package the four new caves plus four existing readable versions."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
BASE = HERE.parent/"hollow_grotto"
PREVIEW = HERE/"preview_project"
NATIVE = HERE/"review/native_r01"
FINAL = HERE/"review/final"
DELIVERY = HERE/"delivery"
OLD_CAPTURE = HERE.parent/"new_cave_floors/review/native_r01"
SPECS = json.loads((PREVIEW/"scene_specs.json").read_text(encoding="utf-8"))
PAINT_MATERIALS = ["materials/backgrounds/cave_readable_existing.tres","materials/backgrounds/cave_readable_new.tres","shaders/backgrounds/cave_readability.gdshader"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgb(path):
    return np.asarray(Image.open(path).convert("RGB"),dtype=np.float32)


def luma(a):
    return a @ np.array([.2126,.7152,.0722])


def gallery(slugs, filename):
    title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",25)
    subtitle = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",17)
    canvas = Image.new("RGB",(1920,1204),"#11161d")
    d = ImageDraw.Draw(canvas)
    for i, slug in enumerate(slugs):
        x,y=(i%2)*960,(i//2)*602
        picture=Image.open(NATIVE/(slug+".png")).convert("RGB").resize((960,540),Image.Resampling.LANCZOS)
        canvas.paste(picture,(x,y+62))
        d.text((x+18,y+4),SPECS[slug]["name"],font=title,fill="#e4e8ee")
        d.text((x+18,y+37),SPECS[slug]["subtitle"],font=subtitle,fill="#a7b0bc")
    canvas.save(FINAL/filename,quality=96,subsampling=0)


def review():
    FINAL.mkdir(parents=True,exist_ok=True)
    DELIVERY.mkdir(exist_ok=True)
    report={"engine":"Godot 4.5.1 / D3D12 / Forward Mobile","scenes":{}}
    pack=[]
    for slug,spec in SPECS.items():
        a=rgb(NATIVE/(slug+".png"));b=rgb(NATIVE/(slug+"_t2.png"))
        delta=np.max(np.abs(a-b),axis=2)
        assert np.count_nonzero(delta)>100,slug+" atmosphere did not animate"
        lum=luma(a)
        row={"kind":spec["kind"],"luma_p05_p50_p95":np.percentile(lum,[5,50,95]).round(2).tolist(),"motion_pixels":int(np.count_nonzero(delta)),"viewports":[[1920,1080],[2560,1080],[1440,1080]]}
        if spec["kind"]=="brightened_existing":
            before=luma(rgb(OLD_CAPTURE/(slug+".png")))
            row["previous_luma_p50"]=round(float(np.median(before)),2)
            row["median_brightness_ratio"]=round(float(np.median(lum)/np.median(before)),3)
            assert row["median_brightness_ratio"]>1.20,slug+" did not get visibly brighter"
        for suffix in ["","_2560x1080","_1440x1080"]:
            shutil.copy2(NATIVE/(slug+suffix+".png"),FINAL/(slug+suffix+".png"))
        image_dir=MOD/"images/rooms"/slug
        for png in image_dir.glob("*.png"):
            im=Image.open(png).convert("RGBA")
            assert im.size==(2048,960)
            if png.name.endswith("_00.png"):
                assert im.getchannel("A").getextrema()==(255,255)
            imported=PREVIEW/png.relative_to(MOD).with_suffix(".png.import")
            text=imported.read_text(encoding="utf-8")
            assert "compress/mode=2" in text and "process/fix_alpha_border=false" in text
            shutil.copy2(imported,png.with_suffix(".png.import"))
        for folder in [image_dir,MOD/"scenes/backgrounds"/slug]:
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.suffix not in {".png",".import",".tscn"}:
                    continue
                pack.append({"resource":"res://"+path.relative_to(MOD).as_posix(),"file":str(path)})
                if path.suffix==".import":
                    for cached in set(re.findall(r'res://(\.godot/imported/[^"\n]+)',path.read_text(encoding="utf-8"))):
                        source=PREVIEW/cached
                        assert source.exists()
                        pack.append({"resource":"res://"+cached,"file":str(source)})
        report["scenes"][slug]=row
    for rel in PAINT_MATERIALS:
        pack.append({"resource":"res://"+rel,"file":str(MOD/rel)})
    assert len(pack)==127
    assert len(set(item["resource"] for item in pack))==127
    (HERE/"pack_manifest.json").write_text(json.dumps(pack,indent=2),encoding="utf-8")
    shutil.copy2(BASE/"pack.gd",PREVIEW/"pack.gd")
    (FINAL/"validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    new=[s for s,v in SPECS.items() if v["kind"]=="new"]
    old=[s for s,v in SPECS.items() if v["kind"]!="new"]
    gallery(new,"new_caves.jpg")
    gallery(old,"existing_caves_brighter.jpg")
    compare=Image.new("RGB",(1600,1936),"#11161d")
    d=ImageDraw.Draw(compare)
    font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",22)
    for i,slug in enumerate(old):
        y=i*484
        d.text((12,y+5),SPECS[slug]["name"].split(" · ")[0]+" · 提亮前 / 提亮后",font=font,fill="white")
        for x,path in [(0,OLD_CAPTURE/(slug+".png")),(800,NATIVE/(slug+".png"))]:
            compare.paste(Image.open(path).convert("RGB").resize((800,450),Image.Resampling.LANCZOS),(x,y+34))
    compare.save(FINAL/"brightness_before_after.jpg",quality=95,subsampling=0)
    print("EIGHT_CAVE_RESOURCE_CHECKS_PASS",json.dumps(report,ensure_ascii=False))


def package():
    pck=DELIVERY/"cave_region_diverse_readable.pck"
    assert pck.is_file()
    assert "PACK_ROUNDTRIP_PASS" in (FINAL/"pack_check.log").read_text(encoding="utf-8-sig",errors="replace")
    files={}
    for slug in SPECS:
        for folder in [MOD/"images/rooms"/slug,MOD/"scenes/backgrounds"/slug]:
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix in {".png",".import",".tscn"}:
                    files["runtime/"+path.relative_to(MOD).as_posix()]=path
    for rel in PAINT_MATERIALS:
        files["runtime/"+rel]=MOD/rel
    for path in PREVIEW.rglob("*"):
        if path.is_file() and ".godot" not in path.relative_to(PREVIEW).parts and path.name!="pack.gd":
            files["preview_project/"+path.relative_to(PREVIEW).as_posix()]=path
    for path in FINAL.iterdir():
        if path.is_file():
            files["review/"+path.name]=path
    for folder in [HERE/"prompts",HERE/"references",HERE/"generated"]:
        for path in folder.iterdir():
            if path.is_file():
                files["source/cave_diversity/"+path.relative_to(HERE).as_posix()]=path
    provenance=json.loads((HERE/"generation_provenance.json").read_text(encoding="utf-8"))
    for record in provenance.values():
        path=Path(record["raw_file"])
        files["source/cave_diversity/raw/"+path.name]=path
    for name in ["build_scenes.py","brighten_existing.py","prepare_generation.py","preview.gd","finalize.py","scenes.json","generation_provenance.json"]:
        files["source/cave_diversity/"+name]=HERE/name
    for name in ["build_scene.py","pack.gd"]:
        files["source/hollow_grotto/"+name]=BASE/name
    for name in ["README.md","STYLE_AUDIT.md"]:
        files[name]=HERE/name
    files[pck.name]=pck
    logs=MOD.parent/".tmp/cave_scene"
    for name in ["diversity_render.log","diversity_render_errors.log"]:
        content=(logs/name).read_text(encoding="utf-8-sig",errors="replace")
        assert not re.search(r'^(?:SCRIPT )?ERROR:',content,re.M)
        files["review/logs/"+name]=logs/name
    manifest={name:{"bytes":path.stat().st_size,"sha256":sha(path)} for name,path in sorted(files.items())}
    output=DELIVERY/"cave_region_diverse_readable.zip"
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,path in sorted(files.items()):
            archive.write(path,name)
        archive.writestr("delivery_manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name,item in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==item["sha256"]
    (DELIVERY/"SHA256SUMS.txt").write_text(sha(output)+"  "+output.name+"\n",encoding="ascii")
    print("EIGHT_CAVE_PACKAGE_PASS",output,"BYTES",output.stat().st_size,"FILES",len(files)+1)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["review","package"])
    args=parser.parse_args()
    review() if args.mode=="review" else package()
