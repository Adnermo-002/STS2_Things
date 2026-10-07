"""Verify the four new floor sources and package the complete cave region."""
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
BASE = HERE.parent / "hollow_grotto"
VARIANTS = HERE.parent / "hollow_grotto_variants"
PREVIEW = VARIANTS / "preview_project"
NATIVE = HERE / "review/native_r01"
FINAL = HERE / "review/final"
DELIVERY = HERE / "delivery"
RAW = MOD.parent / "output/imagegen/new_cave_floors/raw"
NAMES = {
    "hollow_grotto": ("幽蓝溶洞", "全新水蚀岩床 · 自然沟槽"),
    "hollow_grotto_moss": ("苔光岩窟", "全新石灰岩 · 苔土过渡"),
    "hollow_grotto_ember": ("余烬石窟", "全新冷却岩流 · 褶皱薄壳"),
    "hollow_grotto_violet": ("紫雾深窟", "全新层状片岩 · 细矿脉"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review():
    FINAL.mkdir(parents=True, exist_ok=True)
    DELIVERY.mkdir(exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 25)
    small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    scene_board = Image.new("RGB", (1920,1204), "#12161f")
    floor_board = Image.new("RGB", (1920,1024), "#12161f")
    draw_scene, draw_floor = ImageDraw.Draw(scene_board), ImageDraw.Draw(floor_board)
    report = {"version": "all_new_floors_r01", "engine": "Godot 4.5.1 / D3D12 / Forward Mobile", "variants": {}}
    pack = []
    floor_hashes = set()

    for i, (slug, (name, subtitle)) in enumerate(NAMES.items()):
        floor = HERE / "generated" / (slug + "_floor.png")
        runtime = MOD / "images/rooms" / slug / (slug + "_00.png")
        source_pixels = np.asarray(Image.open(floor).convert("RGBA"))
        runtime_pixels = np.asarray(Image.open(runtime).convert("RGBA"))
        assert source_pixels.shape == (960,2048,4) and np.all(source_pixels[...,3] == 255)
        assert np.array_equal(source_pixels, runtime_pixels), "Runtime floor is not the complete new painting: " + slug
        floor_hashes.add(sha(floor))
        a = np.asarray(Image.open(NATIVE / (slug + ".png")).convert("RGB"), dtype=np.float32)
        b = np.asarray(Image.open(NATIVE / (slug + "_t2.png")).convert("RGB"), dtype=np.float32)
        delta = np.max(np.abs(a-b), axis=2)
        assert np.count_nonzero(delta) > 1000, "Dynamic effect did not advance"
        luminance = a @ np.array([.2126,.7152,.0722])
        row = {"new_floor_sha256": sha(floor), "runtime_floor_pixel_identical_to_generated": True,
               "frame_size": [1920,1080], "rendered_sizes": [[1920,1080],[2560,1080],[1440,1080]],
               "motion_changed_pixels": int(np.count_nonzero(delta)),
               "motion_delta_gt_2_pixels": int(np.count_nonzero(delta > 2)),
               "luma_p05_p50_p95": np.percentile(luminance,[5,50,95]).round(2).tolist()}
        report["variants"][slug] = row
        for suffix in ["", "_2560x1080", "_1440x1080"]:
            shutil.copy2(NATIVE / (slug + suffix + ".png"), FINAL / (slug + suffix + ".png"))
        x, y = (i%2)*960, (i//2)*602
        scene_board.paste(Image.fromarray(a.astype(np.uint8)).resize((960,540),Image.Resampling.LANCZOS), (x,y+62))
        draw_scene.text((x+18,y+4),name,font=font,fill="#e3e7ee")
        draw_scene.text((x+18,y+37),subtitle,font=small,fill="#a4acb9")
        fy = (i//2)*512
        floor_board.paste(Image.open(floor).convert("RGB").resize((960,450),Image.Resampling.LANCZOS),(x,fy+62))
        draw_floor.text((x+18,fy+4),name+" · 新绘地面",font=font,fill="#e3e7ee")
        draw_floor.text((x+18,fy+37),subtitle,font=small,fill="#a4acb9")

        for imported in (PREVIEW / "images/rooms" / slug).glob("*.png.import"):
            config = imported.read_text()
            assert "compress/mode=2" in config and "process/fix_alpha_border=false" in config
            shutil.copy2(imported, MOD / "images/rooms" / slug / imported.name)
        for directory in [MOD / "images/rooms" / slug, MOD / "scenes/backgrounds" / slug]:
            for path in sorted(directory.rglob("*")):
                if not path.is_file() or path.suffix not in {".png", ".import", ".tscn"}:
                    continue
                pack.append({"resource":"res://"+path.relative_to(MOD).as_posix(), "file":str(path)})
                if path.suffix == ".import":
                    for cached in set(re.findall(r'res://(\.godot/imported/[^"\n]+)',path.read_text())):
                        p = PREVIEW / cached
                        assert p.is_file(), p
                        pack.append({"resource":"res://"+cached, "file":str(p)})
    assert len(floor_hashes) == 4
    assert len(pack) == 84
    forbidden = ["overgrowth/overgrowth_00.png", "hive/hive_00.png", "glory/glory_00.png", "underdocks/underdocks_00.png"]
    for recipe in [BASE / "build_art.py", VARIANTS / "build_variants.py"]:
        assert all(stock not in recipe.read_text(encoding="utf-8") for stock in forbidden)
    report["build_recipes_have_no_stock_floor_dependencies"] = True
    scene_board.save(FINAL / "new_floor_scenes.jpg", quality=96, subsampling=0)
    floor_board.save(FINAL / "new_floor_paintings.jpg", quality=96, subsampling=0)
    (FINAL / "validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (HERE / "pack_manifest.json").write_text(json.dumps(pack,indent=2),encoding="utf-8")
    shutil.copy2(BASE / "pack.gd", PREVIEW / "pack.gd")
    print("NEW_FLOOR_RESOURCE_CHECKS_PASS", json.dumps(report, ensure_ascii=False))


def package():
    pck = DELIVERY / "cave_region_new_floors.pck"
    assert pck.is_file()
    assert "PACK_ROUNDTRIP_PASS" in (FINAL / "pack_check.log").read_text(encoding="utf-8-sig",errors="replace")
    files = {}
    for slug in NAMES:
        for directory in [MOD / "images/rooms" / slug, MOD / "scenes/backgrounds" / slug]:
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in {".png", ".import", ".tscn"}:
                    files["runtime/"+path.relative_to(MOD).as_posix()] = path
    for path in PREVIEW.rglob("*"):
        if path.is_file() and ".godot" not in path.relative_to(PREVIEW).parts and path.name != "pack.gd":
            files["preview_project/"+path.relative_to(PREVIEW).as_posix()] = path
    for path in FINAL.iterdir():
        if path.is_file():
            files["review/final/"+path.name] = path
    for directory in [HERE/"generated", HERE/"prompts", HERE/"references"]:
        for path in directory.iterdir():
            if path.is_file():
                files["source/new_cave_floors/"+path.relative_to(HERE).as_posix()] = path
    for slug in NAMES:
        files["source/new_cave_floors/raw/"+slug+"_floor_r01.png"] = RAW/(slug+"_floor_r01.png")
    source_files = [
        (BASE,["build_art.py","build_scene.py","pack.gd","preview.gd"]),
        (VARIANTS,["build_variants.py","preview.gd"]),
        (HERE,["normalize_generated_floors.py","check_floor_inputs.py","finalize_new_floors.py","generation_provenance.json","generation_brief.json"]),
    ]
    for directory, names in source_files:
        for name in names:
            files["source/"+directory.name+"/"+name] = directory/name
    for name in ["README.md","STYLE_AUDIT.md"]:
        files[name] = HERE/name
    files[pck.name] = pck
    logs = MOD.parent / ".tmp/cave_scene"
    for name in ["new_floor_render.log","new_floor_render_errors.log"]:
        text = (logs/name).read_text(encoding="utf-8-sig",errors="replace")
        assert not re.search(r'^(?:SCRIPT )?ERROR:',text,re.M)
        files["review/logs/"+name] = logs/name
    manifest = {name:{"bytes":path.stat().st_size,"sha256":sha(path)} for name,path in sorted(files.items())}
    output = DELIVERY / "cave_region_new_floors.zip"
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,path in sorted(files.items()):
            archive.write(path,name)
        archive.writestr("delivery_manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name,entry in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == entry["sha256"]
    (DELIVERY/"SHA256SUMS.txt").write_text(sha(output)+"  "+output.name+"\n",encoding="ascii")
    print("NEW_FLOOR_PACKAGE_PASS",output,"BYTES",output.stat().st_size,"FILES",len(files)+1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=["review","package"])
    args = parser.parse_args()
    review() if args.mode == "review" else package()
