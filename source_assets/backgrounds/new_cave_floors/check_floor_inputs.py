"""Check future generated paintings without accepting any stock-floor fallback."""
from pathlib import Path
import hashlib
import json
from PIL import Image

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
VANILLA = MOD.parent / "STS2-V111"
SLUGS = ["hollow_grotto", "hollow_grotto_moss", "hollow_grotto_ember", "hollow_grotto_violet"]
known_stock = {}
for path in ["overgrowth/overgrowth_00.png", "hive/hive_00.png", "glory/glory_00.png", "underdocks/underdocks_00.png"]:
    p = VANILLA / "images/rooms" / path
    known_stock[hashlib.sha256(p.read_bytes()).hexdigest()] = path

report = {"ready": True, "originality_scope": "Hash check only rejects exact stock copies; generation provenance and visual review are still required.", "floors": {}}
for slug in SLUGS:
    p = HERE / "generated" / (slug + "_floor.png")
    row = {"path": str(p), "present": p.exists(), "errors": []}
    if not p.exists():
        row["errors"].append("New painting has not been generated.")
    else:
        im = Image.open(p)
        if im.size != (2048,960):
            row["errors"].append("Expected 2048 x 960.")
        if im.convert("RGBA").getchannel("A").getextrema() != (255,255):
            row["errors"].append("The base floor layer must be fully opaque.")
        row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        if row["sha256"] in known_stock:
            row["errors"].append("This is an unchanged stock floor, not a new painting.")
    report["ready"] &= not row["errors"]
    report["floors"][slug] = row
(HERE / "input_status.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
