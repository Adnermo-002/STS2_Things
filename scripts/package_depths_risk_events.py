"""Write art provenance and a verified four-file local development package."""
import hashlib
import json
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/depths-risk-events-20261010"
PACKAGE = BUILD / "package"
FILES = ("STS2_Things.json", "STS2_Things.dll", "STS2_Things.pck", "STS2_Things.BaseLibBridge.dll")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record(path):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    refs = ("doll_room", "abyssal_baths", "sunken_treasury", "brain_leech", "tea_master", "potion_courier",
            "ranwid_the_elder", "symbiote", "luminous_choir", "hungry_for_mushrooms", "war_historian_repy")
    references = [{"path": "STS2-V111/images/events/" + name + ".png",
                   "sha256": sha(ROOT.parent / "STS2-V111/images/events" / (name + ".png"))} for name in refs]
    for key, selected_version in (("biting_chest", 3), ("crowded_ward", 6)):
        source = ROOT / "source_assets/events" / (key + "_20261010")
        variants = [record(path) for path in sorted(source.glob("portrait-v*.png"))]
        save_json(source / "generation.json", {"date": "2026-10-10", "generator": "built-in image_gen",
            "model": "not exposed", "selected_version": selected_version, "selected": record(source / "portrait-selected.png"),
            "variants": variants, "prompts": [record(p) for p in sorted(source.glob("prompt*.txt"))],
            "native_references_reviewed": references,
            "user_constraints": "No human figures; original event style is not reducible to large flat colour blocks; continuous peripheral scenery and dimming",
            "preparation": "scripts/prepare-depths-risk-events.gd; original canvas, independent mask and master retained",
            "runtime": record(ROOT / "images/events" / (key + ".png"))})
    source = ROOT / "source_assets/relics/anesthetic_chart_20261010"
    save_json(source / "generation.json", {"date": "2026-10-10", "generator": "built-in image_gen", "model": "not exposed",
        "selected": record(source / "icon-generated.png"), "prompt": record(source / "prompt.txt"),
        "preparation": "scripts/export-depths-event-relic-icons.gd, optional key anesthetic_chart",
        "exports": [record(ROOT / "images/relics" / ("anesthetic_chart" + suffix + ".png")) for suffix in ("", "_packed")]})
    version = json.loads((PACKAGE / "STS2_Things.json").read_text(encoding="utf-8"))["version"]
    destination = ROOT / "dist" / ("v" + version)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ("STS2_Things-v" + version + ".zip")
    if archive.exists():
        raise FileExistsError("Preserve existing same-version package: " + str(archive))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name in FILES:
            bundle.write(PACKAGE / name, "STS2_Things/" + name)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert sorted(bundle.namelist()) == sorted("STS2_Things/" + name for name in FILES)
        for name in FILES:
            assert hashlib.sha256(bundle.read("STS2_Things/" + name)).hexdigest() == sha(PACKAGE / name)
    sums = sha(archive) + "  " + archive.name + "\n"
    sums += "".join(sha(PACKAGE / name) + "  STS2_Things/" + name + "\n" for name in FILES)
    (destination / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
    receipt = {"date": "2026-10-10", "version": version, "archive": record(archive),
               "runtime_files": [record(PACKAGE / name) for name in FILES], "zip_crc_and_entry_hashes": "PASS",
               "native_v111": json.loads((BUILD / "native/v111/behavior-report.json").read_text()),
               "native_v107": json.loads((BUILD / "native/v107.1/behavior-report.json").read_text()),
               "limitations": "V107 uses its real saved DLL with current V111 PCK/shared dependencies; probes simulate 1-4 players in one process, not real multiplayer",
               "publication": "Not published"}
    save_json(destination / "verification.json", receipt)
    save_json(BUILD / "delivery.json", receipt)
    # Review sheet only. Runtime art is prepared with Godot, never redrawn here.
    preview = Image.new("RGB", (1440, 860), "black")
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 21)
    draw = ImageDraw.Draw(preview)
    draw.text((24, 8), "原版组件渲染 · 会咬人的宝箱 / 满员的病房", font=font, fill=(234,222,190))
    for index, key in enumerate(("biting_chest", "crowded_ward")):
        image = Image.open(BUILD / "native/v111" / ("event-" + key + "-zhs.png")).convert("RGB")
        image = image.resize((720, 405), Image.Resampling.LANCZOS)
        preview.paste(image, (720 * index, 47))
        image = Image.open(BUILD / "native/v111" / ("event-" + key + "-eng.png")).convert("RGB")
        preview.paste(image.resize((720, 405), Image.Resampling.LANCZOS), (720 * index, 455))
    preview.save(BUILD / "event-preview.jpg", quality=96)
    print("DEPTHS_RISK_DELIVERY_PASS " + str(archive))
    print("sha256=" + sha(archive))


if __name__ == "__main__":
    main()
