"""Normalize the four API outputs to the native texture canvas; no stock input.

This performs image format/size normalization only. All geological paint and
composition come from the generated images. Never store API credentials here.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
RAW = MOD.parent / "output/imagegen/new_cave_floors/raw"
if not RAW.exists():
    RAW = HERE / "raw"
OUT = HERE / "generated"
SLUGS = ["hollow_grotto", "hollow_grotto_moss", "hollow_grotto_ember", "hollow_grotto_violet"]

inputs = {slug: RAW / (slug + "_floor_r01.png") for slug in SLUGS}
for slug, path in inputs.items():
    if not path.exists():
        raise FileNotFoundError(f"Generation is not complete: {path}")
    im = Image.open(path)
    if abs(im.width / im.height - 2048 / 960) > .02:
        raise ValueError(f"Review aspect ratio before normalization: {path} {im.size}")

OUT.mkdir(exist_ok=True)
records = {}
for slug, path in inputs.items():
    im = Image.open(path)
    original_size, original_format = im.size, im.format
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema() != (255,255):
        raise ValueError(f"Unexpected transparent base: {path}")
    im = im.resize((2048,960), Image.Resampling.LANCZOS)
    destination = OUT / (slug + "_floor.png")
    im.save(destination, optimize=True)
    records[slug] = {
        "requested_model": "gpt-image-2", "mode": "bundled imagegen CLI / reference-conditioned Image API edit",
        "provider": "user-specified OpenAI-compatible endpoint", "requested_size": [2048,960],
        "requested_quality": "high", "raw_file": str(path), "raw_size": original_size,
        "raw_format": original_format, "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "normalized_file": str(destination), "normalized_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "postprocess": "RGBA conversion and Lanczos normalization to 2048x960; no compositing with any old floor",
        "reference_images": [str(HERE / "references" / (slug + "_walls_only.png")), str(HERE / "references/vanilla_rock_style_only.jpg")],
        "prompt": str(HERE / "prompts" / (slug + ".txt")),
    }
(HERE / "generation_provenance.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
brief_path = HERE / "generation_brief.json"
brief = json.loads(brief_path.read_text(encoding="utf-8"))
brief["status"] = "generated_awaiting_native_visual_review"
brief["runtime_state"] = "ready for rebuilding; no stock floor fallback"
brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
print("FOUR_NEW_FLOORS_NORMALIZED", OUT)
