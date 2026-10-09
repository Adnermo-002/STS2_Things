"""Record selected art and package a private four-file runtime build."""
from pathlib import Path
import hashlib
import json
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "build/depths-event-relics-20261009"
SOURCE = ROOT / "source_assets/relics/depths_event_refresh_20261009"
KEYS = ["bottled_echo", "shadow_claim_ticket", "mycelial_deposit", "borrowed_ember", "things_medusa_hair"]
REFERENCES = ["ink_bottle", "meal_ticket", "membership_card", "lantern", "maw_bank", "ember_tea", "silken_tress", "arcane_scroll"]
PAYLOAD = ["STS2_Things.json", "STS2_Things.dll", "STS2_Things.pck", "STS2_Things.BaseLibBridge.dll"]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def entry(path):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    baseline = ROOT / "build/bug-report-fix-20261009/package"
    package = TASK / "package"
    version = json.loads((package / "STS2_Things.json").read_text(encoding="utf-8"))["version"]
    pack_report = json.loads((TASK / "pack-report.json").read_text(encoding="utf-8"))
    assert digest(package / "STS2_Things.pck") == pack_report["output_sha256"]
    for name in PAYLOAD:
        if name != "STS2_Things.pck":
            assert digest(package / name) == digest(baseline / name), name
    for change in pack_report["changes"]:
        assert any(key in change["path"] for key in KEYS), change["path"]

    relics = []
    for key in KEYS:
        generated = SOURCE / "generated" / (key + "-v1.png")
        with Image.open(generated) as im:
            assert im.mode == "RGBA" and im.getextrema()[3][0] == 0
            original_size = list(im.size)
        exports = [ROOT / "images/relics" / (key + ".png"),
                   ROOT / "images/relics" / (key + "_packed.png"),
                   ROOT / "images/atlases/relic_outline_atlas.sprites" / (key + "_outline.png"),
                   ROOT / "images/atlases/relic_atlas.sprites" / (key + ".tres"),
                   ROOT / "images/atlases/relic_outline_atlas.sprites" / (key + ".tres")]
        for path, size in zip(exports[:3], [(256, 256), (85, 85), (85, 85)]):
            with Image.open(path) as im:
                assert im.size == size and im.mode == "RGBA", path
        relics.append({"key": key, "selected": entry(generated), "generated_dimensions": original_size,
                       "prompt": entry(SOURCE / "prompts" / (key + ".txt")),
                       "exports": [entry(path) for path in exports]})
    refs = []
    for key in REFERENCES:
        path = ROOT.parent / "STS2-V111/images/relics" / (key + ".png")
        refs.append({"path": path.relative_to(ROOT.parent).as_posix(), "sha256": digest(path),
                     "usage": "native art inspected during comparison; not a shipped custom icon"})
    write_json(SOURCE / "generation.json", {"completed_date": "2026-10-10", "generator": "built-in image_gen",
        "model": "not exposed by tool", "selection": "v1 for all five", "transparent_background": True,
        "authorization": "User allowed built-in image generation in the active art work; do not label outputs Sunburst",
        "style_references_inspected": refs, "relics": relics,
        "preparation": "scripts/export-depths-event-relic-icons.gd; native Godot crop/resize, alpha cleanup and outline export",
        "self_review": "Compared with native relics at 132/48/32px on dark and light backgrounds; final native component render reviewed"})

    destination = ROOT / "dist" / ("v" + version) / "depths-event-relics"
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ("STS2_Things-v" + version + "-event-relic-art.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipout:
        for name in PAYLOAD:
            zipout.write(package / name, "STS2_Things/" + name)
    with zipfile.ZipFile(archive) as zipin:
        assert zipin.testzip() is None
        assert sorted(zipin.namelist()) == sorted("STS2_Things/" + name for name in PAYLOAD)
        for name in PAYLOAD:
            assert hashlib.sha256(zipin.read("STS2_Things/" + name)).hexdigest() == digest(package / name)
    files = [entry(package / name) for name in PAYLOAD]
    sha_text = digest(archive) + "  " + archive.name + "\n"
    for name in PAYLOAD:
        sha_text += digest(package / name) + "  STS2_Things/" + name + "\n"
    (destination / "SHA256SUMS.txt").write_text(sha_text, encoding="ascii")
    v111 = json.loads((TASK / "native/v111/report.json").read_text())
    v107 = json.loads((TASK / "native/v107.1/report.json").read_text())
    report = {"completed_date": "2026-10-10", "version": version, "files": files, "archive": entry(archive),
              "zip_crc_and_entry_hashes": "PASS", "pack_report": "build/depths-event-relics-20261009/pack-report.json",
              "v111_native_component_assertions": v111["assertions"], "v107_native_component_assertions": v107["assertions"],
              "v107_limit": "Actual preserved V107 DLL + current V111 resource pack/shared dependencies; not a full V107 client",
              "installation": "Not installed: game is running", "publication": "Not published"}
    write_json(TASK / "delivery.json", report)
    write_json(destination / "verification.json", report)
    (destination / "README.txt").write_text(
        "尖塔：琐事 — 深处事件遗物重绘开发包\n\n"
        "版本 " + version + "；与其他同号开发包用 SHA256 区分。\n"
        "重制：瓶中回声、寄存收据、菌根存单、余烬约定、美杜莎之发。\n"
        "包含完整四文件统一运行包；仅在关闭游戏后安装。未发布到 Steam/GitHub。\n"
        "以当前 bug-report-fix-20261009 安装基线为底，仅替换这五件遗物资源；"
        "不包含其他聊天随后产生的独立构件。\n"
        "原生 NRelic/遗物栏组件渲染及 ZIP 校验通过；详见 verification.json。\n",
        encoding="utf-8")
    print("DEPTHS_RELIC_DELIVERY_PASS " + str(archive))
    print("sha256=" + digest(archive))


if __name__ == "__main__":
    main()
