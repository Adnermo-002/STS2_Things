"""Save comparison plates and objective asset checks alongside the visual audit."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
CAPTURES = HERE / "review/native_r04"
FINAL = HERE / "review/final"
FINAL.mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
SMALL = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)


def rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def metrics(path):
    a = rgb(path)
    luma = a @ np.array([.2126, .7152, .0722])
    stage = luma[330:790, 240:1680]
    return {
        "luma_p05_p50_p95_0_to_255": np.percentile(luma, [5, 50, 95]).round(2).tolist(),
        "combat_area_luma_p05_p50_p95": np.percentile(stage, [5, 50, 95]).round(2).tolist(),
        "combat_area_neighbor_delta_mean": round(float(np.abs(np.diff(stage, axis=1)).mean()), 3),
    }


rows = [
    ("hollow_grotto", "新场景 · 幽蓝溶洞 · 终版"),
    ("underdocks", "原版 · 沉没码头 · B 岩体变体"),
    ("overgrowth", "原版 · 蔓生遗迹 · A 变体"),
    ("glory", "原版 · 辉煌 · 原生灯光与粒子"),
]
sheet = Image.new("RGB", (1920, 1176), "#11161f")
draw = ImageDraw.Draw(sheet)
stats = {}
for i, (name, label) in enumerate(rows):
    src = CAPTURES / (name + "_native.png")
    im = Image.open(src).convert("RGB").resize((960, 540), Image.Resampling.LANCZOS)
    x, y = (i % 2) * 960, (i // 2) * 588
    sheet.paste(im, (x, y + 48))
    draw.text((x + 20, y + 9), label, font=FONT, fill="#d8dfe7")
    stats[name] = metrics(src)
sheet.save(FINAL / "style_comparison.jpg", quality=95, subsampling=0)

layer_sheet = Image.new("RGB", (1600, 970), "#141922")
d = ImageDraw.Draw(layer_sheet)
layers = [
    ("00", "00 · 远处空气 / 地表 · 不透明底层"),
    ("01", "01 · 远景岩群 · 附带原生雾与微光"),
    ("02", "02 · 中景洞壁与石笋 · 透明"),
    ("03", "03 · 洞顶 / 钟乳石 / 碎石 · 透明"),
    ("fg", "FG · 近处岩脊 · 透明"),
]
checks = {}
for i, (suffix, label) in enumerate(layers):
    p = MOD / "images/rooms/hollow_grotto" / ("hollow_grotto_" + suffix + ".png")
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im)
    assert im.size == (2048, 960)
    if i == 0:
        assert np.all(a[..., 3] == 255), "Base layer must prevent clear-color leaks"
    else:
        assert np.any(a[..., 3] == 0) and np.any(a[..., 3] == 255)
    checks[p.name] = {"size": list(im.size), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                      "fully_transparent_fraction": round(float(np.mean(a[..., 3] == 0)), 4)}
    x, y = (i % 2) * 800, (i // 2) * 323
    d.text((x + 16, y + 12), label, font=SMALL, fill="#d8dfe7")
    preview = Image.new("RGBA", (768, 270), "#343945")
    thumb = ImageOps.contain(im, (768, 270), Image.Resampling.LANCZOS)
    preview.alpha_composite(thumb, ((768 - thumb.width) // 2, 0))
    layer_sheet.paste(preview.convert("RGB"), (x + 16, y + 42))
preview = Image.open(CAPTURES / "hollow_grotto_native.png").convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
layer_sheet.paste(preview, (960, 688))
d.text((816, 658), "合成 · 1920 × 1080 · Godot D3D12", font=SMALL, fill="#d8dfe7")
layer_sheet.save(FINAL / "layer_breakdown.jpg", quality=95, subsampling=0)

original = rgb(CAPTURES / "hollow_grotto_native.png")
second = rgb(CAPTURES / "hollow_grotto_motion_t2.png")
diff = np.max(np.abs(original - second), axis=2)
motion = {"frames_apart": 120, "fixed_fps": 60, "pixels_changed": int(np.count_nonzero(diff)),
          "pixels_changed_more_than_2_levels": int(np.count_nonzero(diff > 2)), "max_channel_delta": int(diff.max())}
assert motion["pixels_changed_more_than_2_levels"] > 100, "VFX must actually animate"

for name in ["hollow_grotto_native", "hollow_grotto_2560x1080", "hollow_grotto_1440x1080", "hollow_grotto_paint_only"]:
    shutil.copy2(CAPTURES / (name + ".png"), FINAL / (name + ".png"))

root_path = MOD / "scenes/backgrounds/hollow_grotto/hollow_grotto_background.tscn"
root_text = root_path.read_text(encoding="utf-8")
layer_dir = root_path.parent / "layers"
assert 'res://src/Core/Nodes/Rooms/NCombatBackground.cs' in root_text
for i in range(4):
    assert f'name="Layer_{i:02}"' in root_text
assert 'name="Foreground"' in root_text
assert len(list(layer_dir.glob("*.tscn"))) == 5
deps = set()
for p in [root_path] + list(layer_dir.glob("*.tscn")):
    for path in re.findall(r'path="res://([^"]+)"', p.read_text(encoding="utf-8")):
        assert (MOD / path).is_file() or (MOD.parent / "STS2-V111" / path).is_file(), path
        deps.add(path)

# Preserve the actual, successfully imported native BPTC metadata for the
# project-bound resources; scene references use paths, not unstable UIDs.
for p in (HERE / "preview_project/images/rooms/hollow_grotto").glob("*.png.import"):
    text = p.read_text(encoding="utf-8")
    assert 'compress/mode=2' in text and 'process/fix_alpha_border=false' in text
    shutil.copy2(p, MOD / "images/rooms/hollow_grotto" / p.name)

report = {"review_revision": "r04", "engine": "Godot 4.5.1 / D3D12 / Forward Mobile",
          "color_measurement": "display-referred Rec.709 weighted RGB on native captures; diagnostic, not a style score",
          "style_reference_metrics": stats, "layers": checks, "motion": motion,
          "native_dependency_paths": sorted(deps),
          "viewports_rendered": [[1920,1080],[2560,1080],[1440,1080]],
          "runtime_root": str(root_path),
          "verification_scope": "Actual Godot layer rendering and resource contracts; no live combat was replaced or run."}
(FINAL / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"metrics": stats, "motion": motion, "result": "ASSET_CHECKS_PASS"}, ensure_ascii=False, indent=2))
