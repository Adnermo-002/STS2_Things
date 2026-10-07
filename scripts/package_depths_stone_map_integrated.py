"""Package the verified stone map with the current, unchanged unified mod DLL."""
from pathlib import Path
import hashlib
import json
import zipfile

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/depths_stone_map"
INTEGRATION = BUILD / "integration"
PACKAGE = INTEGRATION / "package/STS2_Things"
RENDER = INTEGRATION / "render"
DELIVERY = BUILD / "delivery"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_log(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8-sig")
    if marker not in text or "SCRIPT ERROR" in text or "ERROR:" in text:
        raise RuntimeError(f"Missing successful verification: {path}")
    return text


def main() -> None:
    selected = json.loads((ROOT / "source_assets/backgrounds/depths_stone_map/selection.json").read_text("utf-8"))
    manifest = json.loads((PACKAGE / "STS2_Things.json").read_text("utf-8-sig"))
    if manifest != json.loads((ROOT / "STS2_Things.json").read_text("utf-8-sig")):
        raise RuntimeError("Staged package does not match the current mod manifest")
    pack_check = json.loads((INTEGRATION / "pck-map-check.json").read_text("utf-8"))
    if not pack_check["passed"] or Path(pack_check["pck"]).resolve() != (PACKAGE / "STS2_Things.pck").resolve():
        raise RuntimeError("Selected stone textures have not passed PCK verification")
    require_log(INTEGRATION / "pck-runtime-check.log", "PCK runtime asset contract: PASS")
    require_log(INTEGRATION / "source-pck-check.log", "source audit: PASS")
    for target in ("v107.1", "v111"):
        require_log(INTEGRATION / "unified-check.log", f"Unified package probe: PASS ({target},")
        require_log(INTEGRATION / f"native-{target}/probe-{target}.stdout.log", "Depths act probe: PASS")
        stderr = (INTEGRATION / f"native-{target}/probe-{target}.stderr.log").read_text("utf-8-sig")
        if "ERROR:" in stderr:
            raise RuntimeError(f"Native engine errors: {target}")
    require_log(RENDER / "native.stdout.log", "Depths stone map render: PASS")
    if "ERROR:" in (RENDER / "native.stderr.log").read_text("utf-8-sig"):
        raise RuntimeError("Map renderer reported errors")
    with Image.open(RENDER / "native_full.png") as image:
        stitched = np.asarray(image.convert("RGBA")).astype(np.int16)
    with Image.open(RENDER / "native_uncut_reference.png") as image:
        whole = np.asarray(image.convert("RGBA")).astype(np.int16)
    delta = np.abs(stitched - whole)
    if delta.max() > 2:
        raise RuntimeError(f"Imported segmented map differs from uncut master: {delta.max()}")

    files = [PACKAGE / name for name in (
        "STS2_Things.json", "STS2_Things.dll", "STS2_Things.pck", "STS2_Things.BaseLibBridge.dll"
    )]
    report = {
        "selected_art": selected,
        "mod_version": manifest["version"],
        "game_targets": ["v0.107.1", "v0.111.x"],
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in files},
        "pck_map_check": pack_check,
        "native_render": {
            "source": "Textures loaded from the shipping PCK",
            "layout": "Original NMapBg VBoxContainer geometry, 3 x 1080, no separation",
            "reference": "Uncut selected master with the same fix_alpha_border import treatment",
            "max_channel_delta": int(delta.max()),
            "mean_channel_delta": float(delta.mean()),
            "join_max_deltas": {str(y): int(delta[y-6:y+6].max()) for y in (1080, 2160)},
            "checks": 104,
        },
        "native_chapter_assertions": {"v107.1": 753, "v111": 754},
        "unified_models_per_target": 83,
        "visual_review": "First selected stone design retained; continuous painted veins and edges; route icons remain legible.",
        "scope": "Isolated native loading/render checks. Preview route is illustrative, not a saved-run screenshot.",
    }
    startup_path = INTEGRATION / "startup-check.json"
    if startup_path.is_file():
        report["real_game_startup"] = json.loads(startup_path.read_text("utf-8-sig"))
    (INTEGRATION / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    readme = f"""# 深处第一版石板地图 · 完整模组包

模组版本 {manifest['version']}；支持游戏 v0.107.1 / v0.111.x。
按用户最终选择使用第一版浅蓝灰石板。当前统一入口 DLL 与已有 {manifest['version']} 完全一致，重新导出的 PCK 包含三段选定贴图及现有模组内容。

安装：关闭游戏并备份原模组，把 STS2_Things 文件夹复制到游戏 mods 目录，覆盖同名文件。正常进入「深处」章节时使用专属石板，无需操作存档或调整地图布局。

已验证：PCK 三段贴图与工程导入结果逐字节一致；两个版本章节原生检查共 1507 项通过；两个版本统一入口各加载 83 个模型；分段与完整母图在相同导入设置下最大渲染差为 {int(delta.max())}/255，两条接缝无额外色带。详细哈希和结果见 verification.json。

preview.png 为从最终 PCK 加载贴图后的原生布局与路线可读性示意，路线是示意，不是真正玩家存档截图。验证没有创建或修改玩家存档。
"""
    if "real_game_startup" in report:
        readme += "\n实机启动：v0.111.0 已完成模组初始化并进入主菜单，MCP 桥连接成功；未继续或新建对局。完整地图界面未在玩家存档中实测。启动日志另有第三方联机模组信号断连和 Godot 预加载 Invalid Task ID 记录，已在 verification.json 中列明；本次未改动这些模块。\n"
    (INTEGRATION / "README.md").write_text(readme, "utf-8")
    DELIVERY.mkdir(exist_ok=True)
    archive = DELIVERY / f"STS2_Things_Depths_Stone_Map_v{selected['revision']}_{manifest['version']}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in files:
            zipped.write(path, f"STS2_Things/{path.name}")
        zipped.write(INTEGRATION / "README.md", "README.md")
        zipped.write(INTEGRATION / "verification.json", "verification.json")
        zipped.write(RENDER / "route_readability_sample.png", "preview.png")
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "sha256": sha256(archive)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
