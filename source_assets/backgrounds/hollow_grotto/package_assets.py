"""Package editable runtime assets, a standalone preview and the approved audit."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
DELIVERY = HERE / "delivery"
DELIVERY.mkdir(exist_ok=True)
LOGS = MOD.parent / ".tmp/cave_scene"
if "--prepare-pack" in sys.argv:
    entries = []
    for part in ["images/rooms/hollow_grotto", "scenes/backgrounds/hollow_grotto"]:
        for src in sorted((MOD / part).rglob("*")):
            if not src.is_file() or src.suffix not in {".png", ".import", ".tscn"}:
                continue
            entries.append({"resource": "res://" + src.relative_to(MOD).as_posix(), "file": str(src)})
            if src.suffix == ".import":
                for cached in set(re.findall(r'res://(\.godot/imported/[^"\n]+)', src.read_text())):
                    imported = HERE / "preview_project" / cached
                    assert imported.is_file(), imported
                    entries.append({"resource": "res://" + cached, "file": str(imported)})
    (HERE / "pack_manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    shutil.copy2(HERE / "pack.gd", HERE / "preview_project/pack.gd")
    print("PACK_MANIFEST_READY", len(entries), HERE / "pack_manifest.json")
    sys.exit(0)
files = {}
for part in ["images/rooms/hollow_grotto", "scenes/backgrounds/hollow_grotto"]:
    for src in sorted((MOD / part).rglob("*")):
        if src.is_file() and src.suffix in {".png", ".import", ".tscn"}:
            files["runtime/" + src.relative_to(MOD).as_posix()] = src
for src in sorted((HERE / "preview_project").rglob("*")):
    if src.is_file() and ".godot" not in src.parts and src.name != "pack.gd":
        files["preview_project/" + src.relative_to(HERE / "preview_project").as_posix()] = src
for name in ["README.md", "STYLE_AUDIT.md"]:
    files[name] = HERE / name
for name in ["asset_manifest.json", "build_art.py", "build_scene.py", "preview.gd", "review_assets.py", "pack.gd", "package_assets.py"]:
    files[name] = HERE / name
for src in (HERE / "review/final").iterdir():
    if src.is_file():
        files["review/final/" + src.name] = src
files["hollow_grotto.pck"] = DELIVERY / "hollow_grotto.pck"
assert files["hollow_grotto.pck"].is_file()

for name in ["render_r04.log", "render_r04_errors.log", "import_standard_preview.log", "standard_preview_run.log"]:
    src = LOGS / name
    if src.exists():
        log_text = src.read_text(encoding="utf-8-sig", errors="replace")
        assert not re.search(r'(^|\n)(SCRIPT ERROR|ERROR):', log_text), name
        files["review/logs/" + name] = src
# Preserve the original import diagnostics with the environment explanation
# in STYLE_AUDIT.md; never classify the Mono SDK error as an asset error.
import_log = LOGS / "import_r04.log"
if import_log.exists():
    errors = re.findall(r'^(?:SCRIPT )?ERROR:.*$', import_log.read_text(encoding="utf-8-sig", errors="replace"), re.M)
    assert errors and all('.NET Sdk not found' in line for line in errors), errors
    files["review/logs/import_r04_mono_environment.log"] = import_log

manifest = {name: {"sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "bytes": src.stat().st_size}
            for name, src in sorted(files.items())}
data = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
(DELIVERY / "delivery_manifest.json").write_bytes(data)
zip_path = DELIVERY / "hollow_grotto_scene_assets.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, src in sorted(files.items()):
        archive.write(src, name)
    archive.writestr("delivery_manifest.json", data)
with zipfile.ZipFile(zip_path) as archive:
    assert archive.testzip() is None
    for name, item in manifest.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == item["sha256"], name
sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
(DELIVERY / "SHA256SUMS.txt").write_text(sha + "  " + zip_path.name + "\n", encoding="ascii")
print("PACKAGE_PASS", zip_path)
print("FILES", len(files) + 1, "BYTES", zip_path.stat().st_size, "SHA256", sha)
