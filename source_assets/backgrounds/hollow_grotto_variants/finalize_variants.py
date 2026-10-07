"""Review captures, prepare a native PCK manifest, or package the approved set."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import build_variants as build

HERE, MOD, BASE = build.HERE, build.MOD, build.BASE
FINAL = HERE / "review/final"
NATIVE = HERE / "review/native_r02"
DELIVERY = HERE / "delivery"
LOGS = MOD.parent / ".tmp/cave_scene"
SLUGS = [v["slug"] for v in build.VARIANTS.values()]


def review():
    FINAL.mkdir(parents=True, exist_ok=True)
    DELIVERY.mkdir(exist_ok=True)
    title_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
    sub_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    plate = Image.new("RGB", (1920, 1204), "#12161f")
    draw = ImageDraw.Draw(plate)
    entries = [(v["slug"], v["name"], v["subtitle"]) for v in build.VARIANTS.values()]
    entries.append(("hollow_grotto", "幽蓝溶洞 · 上一版对照", "保持原方案，供构图与色调比较"))
    for i, (slug, name, subtitle) in enumerate(entries):
        x, y = (i % 2) * 960, (i // 2) * 602
        im = Image.open(NATIVE / (slug + ".png")).convert("RGB")
        plate.paste(im.resize((960, 540), Image.Resampling.LANCZOS), (x, y + 62))
        draw.text((x + 18, y + 4), name, font=title_font, fill="#e4e9ed")
        draw.text((x + 18, y + 37), subtitle, font=sub_font, fill="#9caab9")
    plate.save(FINAL / "variants_comparison.jpg", quality=95, subsampling=0)

    # Common rendering and source provenance checks; the aesthetic decision
    # is recorded separately in STYLE_AUDIT.md after visual inspection.
    report = {"revision": "r02", "engine": "Godot 4.5.1 / D3D12 / Forward Mobile", "variants": {}}
    pack_entries = []
    for slug in SLUGS:
        im = np.asarray(Image.open(NATIVE / (slug + ".png")).convert("RGB"), dtype=np.float32)
        t2 = np.asarray(Image.open(NATIVE / (slug + "_t2.png")).convert("RGB"), dtype=np.float32)
        delta = np.max(np.abs(im - t2), axis=2)
        assert np.count_nonzero(delta > 2) > 100, "No visible animation: " + slug
        luma = im @ np.array([.2126, .7152, .0722])
        row = {"luma_p05_p50_p95": np.percentile(luma, [5,50,95]).round(2).tolist(),
               "animation_pixels_delta_gt_2": int(np.count_nonzero(delta > 2)),
               "frames_apart": 120, "fps": 60, "textures": {}}
        for suffix in ["", "_2560x1080", "_1440x1080"]:
            shutil.copy2(NATIVE / (slug + suffix + ".png"), FINAL / (slug + suffix + ".png"))
        image_dir = MOD / "images/rooms" / slug
        for png in sorted(image_dir.glob("*.png")):
            tex = Image.open(png)
            alpha = np.asarray(tex)[..., 3]
            assert tex.size == (2048,960) and tex.mode == "RGBA"
            if png.name.endswith("_00.png"):
                assert np.all(alpha == 255)
            else:
                assert np.any(alpha == 0) and np.any(alpha == 255)
            row["textures"][png.name] = {"size": list(tex.size), "sha256": hashlib.sha256(png.read_bytes()).hexdigest()}
            imported = HERE / "preview_project" / png.relative_to(MOD).with_suffix(".png.import")
            cfg = imported.read_text()
            assert "compress/mode=2" in cfg and "process/fix_alpha_border=false" in cfg
            shutil.copy2(imported, png.with_suffix(".png.import"))
        scene_dir = MOD / "scenes/backgrounds" / slug
        root = (scene_dir / (slug + "_background.tscn")).read_text()
        assert "NCombatBackground.cs" in root
        for slot in ["Layer_00", "Layer_01", "Layer_02", "Layer_03", "Foreground"]:
            assert f'name="{slot}"' in root
        assert len(list((scene_dir / "layers").glob("*.tscn"))) == 5
        for src_dir in [image_dir, scene_dir]:
            for src in sorted(src_dir.rglob("*")):
                if not src.is_file() or src.suffix not in {".png", ".import", ".tscn"}:
                    continue
                pack_entries.append({"resource": "res://" + src.relative_to(MOD).as_posix(), "file": str(src)})
                if src.suffix == ".import":
                    for path in set(re.findall(r'res://(\.godot/imported/[^"\n]+)', src.read_text())):
                        cached = HERE / "preview_project" / path
                        assert cached.is_file()
                        pack_entries.append({"resource": "res://" + path, "file": str(cached)})
        report["variants"][slug] = row
    assert len(pack_entries) == 63
    (HERE / "pack_manifest.json").write_text(json.dumps(pack_entries, indent=2), encoding="utf-8")
    shutil.copy2(BASE / "pack.gd", HERE / "preview_project/pack.gd")
    (FINAL / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("VARIANT_RESOURCE_CHECKS_PASS", json.dumps({k: {"luma": v["luma_p05_p50_p95"], "motion": v["animation_pixels_delta_gt_2"]} for k,v in report["variants"].items()}))


def package():
    pck = DELIVERY / "hollow_grotto_variants.pck"
    assert pck.is_file() and pck.stat().st_size > 1000000
    assert "PACK_ROUNDTRIP_PASS" in (FINAL / "pack_check.log").read_text(encoding="utf-8-sig", errors="replace")
    sources = {}
    for slug in SLUGS:
        for directory in [MOD / "images/rooms" / slug, MOD / "scenes/backgrounds" / slug]:
            for src in directory.rglob("*"):
                if src.is_file() and src.suffix in {".png", ".import", ".tscn"}:
                    sources["runtime/" + src.relative_to(MOD).as_posix()] = src
    for src in (HERE / "preview_project").rglob("*"):
        if src.is_file() and ".godot" not in src.relative_to(HERE).parts and src.name != "pack.gd":
            sources["preview_project/" + src.relative_to(HERE / "preview_project").as_posix()] = src
    for src in FINAL.iterdir():
        if src.is_file():
            sources["review/final/" + src.name] = src
    for name in ["README.md", "STYLE_AUDIT.md", "variants_manifest.json"]:
        sources[name] = HERE / name
    for name in ["build_variants.py", "finalize_variants.py", "preview.gd"]:
        sources["source/hollow_grotto_variants/" + name] = HERE / name
    for name in ["build_art.py", "build_scene.py", "pack.gd"]:
        sources["source/hollow_grotto/" + name] = BASE / name
    for name in ["variants_render_r02.log", "variants_render_r02_errors.log"]:
        log = LOGS / name
        content = log.read_text(encoding="utf-8-sig", errors="replace")
        assert not re.search(r'^(?:SCRIPT )?ERROR:', content, re.M)
        sources["review/logs/" + name] = log
    sources[pck.name] = pck
    manifest = {name: {"sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "bytes": src.stat().st_size}
                for name, src in sorted(sources.items())}
    data = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    out = DELIVERY / "hollow_grotto_variants.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, src in sorted(sources.items()):
            archive.write(src, name)
        archive.writestr("delivery_manifest.json", data)
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
        for name, item in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == item["sha256"]
    (DELIVERY / "SHA256SUMS.txt").write_text(hashlib.sha256(out.read_bytes()).hexdigest() + "  " + out.name + "\n", encoding="ascii")
    print("VARIANTS_PACKAGE_PASS", out, "BYTES", out.stat().st_size, "FILES", len(sources) + 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["review", "package"])
    args = parser.parse_args()
    review() if args.mode == "review" else package()
