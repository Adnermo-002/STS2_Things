#!/usr/bin/env python3
"""Fast, deterministic source checks for STS2_Things."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "STS2_Things"
BOOTSTRAP = ROOT / "bootstrap"

# 可选配置页集成层：字符串/反射接入外部模组配置框架，豁免其源码扫描规则
# （禁依赖扫描与旧类名扫描），但仍禁止编译期引用（见 verify_config_contract）。
CONFIG_DIR = SOURCE / "Config"
CONFIG_PATHS = {p.resolve() for p in CONFIG_DIR.rglob("*.cs")} if CONFIG_DIR.is_dir() else set()


# ModelDb derives IDs from the concrete class name, not the namespace, assembly,
# or manifest. Keep this table explicit so generic names cannot quietly return.
MODEL_ID_NAMESPACE_EXPECTATIONS = (
    ("Cards/ThingsRecall.cs", "ThingsRecall", "CardModel", "CARD", "RECALL", "THINGS_RECALL", "cards", "title"),
    ("Cards/ThingsReuse.cs", "ThingsReuse", "CardModel", "CARD", "REUSE", "THINGS_REUSE", "cards", "title"),
    ("Cards/ThingsSurrender.cs", "ThingsSurrender", "CardModel", "CARD", "SURRENDER", "THINGS_SURRENDER", "cards", "title"),
    ("Cards/ThingsPackUp.cs", "ThingsPackUp", "CardModel", "CARD", "PACK_UP", "THINGS_PACK_UP", "cards", "title"),
    ("Enchantments/ThingsDisperse.cs", "ThingsDisperse", "EnchantmentModel", "ENCHANTMENT", "DISPERSE", "THINGS_DISPERSE", "enchantments", "title"),
    ("Events/ThingsBackrooms.cs", "ThingsBackrooms", "EventModel", "EVENT", "BACKROOMS", "THINGS_BACKROOMS", "events", "title"),
    ("Events/ThingsMedusa.cs", "ThingsMedusa", "EventModel", "EVENT", "MEDUSA", "THINGS_MEDUSA", "events", "title"),
    ("Relics/ThingsAlmondWater.cs", "ThingsAlmondWater", "RelicModel", "RELIC", "ALMOND_WATER", "THINGS_ALMOND_WATER", "relics", "title"),
    ("Relics/ThingsCurseRemover.cs", "ThingsCurseRemover", "RelicModel", "RELIC", "CURSE_REMOVER", "THINGS_CURSE_REMOVER", "relics", "title"),
    ("Relics/ThingsMagicGlove.cs", "ThingsMagicGlove", "RelicModel", "RELIC", "MAGIC_GLOVE", "THINGS_MAGIC_GLOVE", "relics", "title"),
    ("Relics/ThingsMedusaHair.cs", "ThingsMedusaHair", "RelicModel", "RELIC", "MEDUSA_HAIR", "THINGS_MEDUSA_HAIR", "relics", "title"),
    ("Relics/ThingsWhiteFlag.cs", "ThingsWhiteFlag", "RelicModel", "RELIC", "WHITE_FLAG", "THINGS_WHITE_FLAG", "relics", "title"),
    ("Powers/ThingsDazedPower.cs", "ThingsDazedPower", "PowerModel", "POWER", "DAZED_POWER", "THINGS_DAZED_POWER", "powers", "title"),
    ("Powers/ThingsOriginPower.cs", "ThingsOriginPower", "PowerModel", "POWER", "ORIGIN_POWER", "THINGS_ORIGIN_POWER", "powers", "title"),
    ("Powers/ThingsQuirkPower.cs", "ThingsQuirkPower", "PowerModel", "POWER", "QUIRK_POWER", "THINGS_QUIRK_POWER", "powers", "title"),
    ("Powers/ThingsRecallPower.cs", "ThingsRecallPower", "PowerModel", "POWER", "RECALL_POWER", "THINGS_RECALL_POWER", "powers", "title"),
    ("Powers/ThingsReusePower.cs", "ThingsReusePower", "PowerModel", "POWER", "REUSE_POWER", "THINGS_REUSE_POWER", "powers", "title"),
    ("Powers/ThingsScaleBeetlePower.cs", "ThingsScaleBeetlePower", "PowerModel", "POWER", "SCALE_BEETLE_POWER", "THINGS_SCALE_BEETLE_POWER", "powers", "title"),
    ("Powers/ThingsScaleDownPower.cs", "ThingsScaleDownPower", "PowerModel", "POWER", "SCALE_DOWN_POWER", "THINGS_SCALE_DOWN_POWER", "powers", "title"),
    ("Powers/ThingsScaleUpPower.cs", "ThingsScaleUpPower", "PowerModel", "POWER", "SCALE_UP_POWER", "THINGS_SCALE_UP_POWER", "powers", "title"),
    ("Monsters/ThingsScaleBeetle.cs", "ThingsScaleBeetle", "MonsterModel", "MONSTER", "SCALE_BEETLE", "THINGS_SCALE_BEETLE", "monsters", "name"),
    ("Monsters/ThingsTheLegacy.cs", "ThingsTheLegacy", "MonsterModel", "MONSTER", "THE_LEGACY", "THINGS_THE_LEGACY", "monsters", "name"),
)

MODEL_RESOURCE_RENAMES = (
    ("images/packed/card_portraits/defect/reuse.png", "images/packed/card_portraits/defect/things_reuse.png"),
    ("images/packed/card_portraits/event/surrender.png", "images/packed/card_portraits/event/things_surrender.png"),
    ("images/packed/card_portraits/silent/pack_up.png", "images/packed/card_portraits/silent/things_pack_up.png"),
    ("images/packed/card_portraits/silent/recall.png", "images/packed/card_portraits/silent/things_recall.png"),
    ("images/atlases/card_atlas.sprites/event/surrender.tres", "images/atlases/card_atlas.sprites/event/things_surrender.tres"),
    ("images/enchantments/disperse.png", "images/enchantments/things_disperse.png"),
    ("images/events/backrooms.png", "images/events/things_backrooms.png"),
    ("images/events/medusa.png", "images/events/things_medusa.png"),
    ("images/relics/almond_water.png", "images/relics/things_almond_water.png"),
    ("images/relics/curse_remover.png", "images/relics/things_curse_remover.png"),
    ("images/relics/magic_glove.png", "images/relics/things_magic_glove.png"),
    ("images/relics/medusa_hair.png", "images/relics/things_medusa_hair.png"),
    ("images/relics/white_flag.png", "images/relics/things_white_flag.png"),
    ("images/powers/dazed_power.png", "images/powers/things_dazed_power.png"),
    ("images/powers/origin_power.png", "images/powers/things_origin_power.png"),
    ("images/powers/quirk_power.png", "images/powers/things_quirk_power.png"),
    ("images/powers/recall_power.png", "images/powers/things_recall_power.png"),
    ("images/powers/reuse_power.png", "images/powers/things_reuse_power.png"),
    ("images/powers/scale_beetle_power.png", "images/powers/things_scale_beetle_power.png"),
    ("images/powers/scale_down_power.png", "images/powers/things_scale_down_power.png"),
    ("images/powers/scale_up_power.png", "images/powers/things_scale_up_power.png"),
    ("scenes/creature_visuals/scale_beetle.tscn", "scenes/creature_visuals/things_scale_beetle.tscn"),
    ("scenes/creature_visuals/the_legacy.tscn", "scenes/creature_visuals/things_the_legacy.tscn"),
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


# 可配置项（ThingsModConfig 键常量）与 BaseLib 桥属性/RitsuLib schema/本地化键的
# 一致性合同。键常量表是单一来源：桥属性名、互操作 schema 与 settings_ui 标签
# 都必须与它逐字一致，防止三套入口悄悄分叉。
def verify_config_contract(errors: list[str]) -> None:
    config_path = SOURCE / "Config" / "ThingsModConfig.cs"
    provider_path = SOURCE / "Config" / "RitsuLibInteropProvider.cs"
    integration_path = SOURCE / "Config" / "LibraryIntegration.cs"
    for path, label in (
        (config_path, "config model"),
        (provider_path, "RitsuLib interop provider"),
        (integration_path, "library integration"),
    ):
        if not path.is_file():
            fail(errors, f"config contract: {label} source is missing: {path.relative_to(ROOT)}")

    config_text = config_path.read_text(encoding="utf-8")
    # 键常量表 = Entries 列表中引用的常量名（不含 SchemaVersion/槽位等辅助常量）。
    entries_region = config_text[config_text.index("public static readonly IReadOnlyList<Entry> Entries"):]
    entries_region = entries_region[: entries_region.index("];")]
    key_names = set(re.findall(r"new\((\w+),", entries_region))
    # 键名与其字符串值必须一致（桥属性名 = JSON 键 = 常量名）。
    for name in key_names:
        if not re.search(rf'public const string {re.escape(name)} = "{re.escape(name)}";', config_text):
            fail(errors, f"config contract: key constant {name} must equal its JSON key string")

    # 1) BaseLib 桥属性名必须与键常量完全一致（且不允许缺失/多余）。
    bridge_path = ROOT / "bridges" / "STS2_Things.BaseLibBridge" / "ThingsBaseLibConfig.cs"
    if bridge_path.is_file():
        bridge_text = bridge_path.read_text(encoding="utf-8")
        bridge_props = set(re.findall(
            r"public static bool (\w+) \{[^}]*\}",
            bridge_text,
        ))
        if bridge_props != key_names:
            fail(
                errors,
                "config contract: BaseLib bridge properties differ from ThingsModConfig keys: "
                + ", ".join(sorted(bridge_props ^ key_values)),
            )
    else:
        fail(errors, "config contract: BaseLib bridge source is missing")

    # 2) RitsuLib 互操作提供器必须引用全部键常量（门控一致性）。
    provider_text = provider_path.read_text(encoding="utf-8") if provider_path.is_file() else ""
    missing_in_provider = key_names - set(re.findall(r"ThingsModConfig\.(\w+)", provider_text))
    if missing_in_provider:
        fail(errors, "config contract: RitsuLib provider misses keys: " + ", ".join(sorted(missing_in_provider)))
    # RitsuLib 文本映射必须用游戏语言码（zhs/zht/en），禁用旧的 zh-CN 键（不匹配会退回英文）。
    if '"zh-CN"' in provider_text:
        fail(errors, "config contract: RitsuLib provider must use game language codes, not zh-CN")

    # 3) BaseLib 标签本地化：每个键与区段标题都必须在 settings_ui 表中给出
    #    STS2_THINGS-<SLUG>.title（eng 与 zhs）。
    section_names = {"Bosses", "Other Encounters", "Events", "Merchant Bargain", "Neow Starting Relics"}
    label_names = key_names | section_names
    label_keys = {"STS2_THINGS-" + slugify_class_name(name) + ".title" for name in label_names}
    label_keys.add("STS2_THINGS.mod_title")  # BaseLib 配置列表标题（GetModTitle）
    for language in ("eng", "zhs"):
        loc_path = SOURCE / "localization" / language / "settings_ui.json"
        if not loc_path.is_file():
            fail(errors, f"config contract: {language} settings_ui localization is missing")
            continue
        try:
            loc = json.loads(loc_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exception:
            fail(errors, f"config contract: {language} settings_ui is invalid JSON: {exception}")
            continue
        missing_labels = label_keys - set(loc)
        if missing_labels:
            fail(
                errors,
                f"config contract: {language} settings_ui misses labels: "
                + ", ".join(sorted(missing_labels)),
            )

    # 4) 主 csproj 必须排除桥目录；PCK 导出必须排除 bridges/**。
    project_text = (ROOT / "STS2_Things.csproj").read_text(encoding="utf-8")
    if 'bridges\\**\\*.cs' not in project_text:
        fail(errors, "config contract: main csproj must exclude bridges\\**\\*.cs")
    export_preset = (ROOT / "export_presets.cfg").read_text(encoding="utf-8")
    if "bridges/**" not in export_preset:
        fail(errors, "config contract: PCK export must exclude bridges/**")



def slugify_class_name(name: str) -> str:
    # 与游戏 StringHelper.Slugify 一致：仅在小写后接大写处断词，再大写并压缩空白。
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name).upper().replace(" ", "_")


def audit_model_id_namespace(errors: list[str], pck: Path | None) -> None:
    localization_root = SOURCE / "localization"
    legacy_class_names: list[str] = []

    for (
        relative,
        type_name,
        base_type,
        category,
        legacy_entry,
        entry,
        table,
        suffix,
    ) in MODEL_ID_NAMESPACE_EXPECTATIONS:
        path = SOURCE / relative
        if not path.is_file():
            fail(errors, f"namespaced model source is missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(
            rf"public\s+sealed\s+class\s+{re.escape(type_name)}\s*:\s*{base_type}\b",
            text,
        ) is None:
            fail(errors, f"{relative} does not declare {type_name} : {base_type}")
        if not type_name.startswith("Things"):
            fail(errors, f"{relative} model type lacks the Things token: {type_name}")
        if slugify_class_name(type_name) != entry:
            fail(
                errors,
                f"{type_name} derives {slugify_class_name(type_name)}, expected {entry}",
            )
        expected_category = base_type.removesuffix("Model").upper()
        if category != expected_category:
            fail(errors, f"{type_name} category contract is {category}, expected {expected_category}")
        legacy_class_names.append(type_name.removeprefix("Things"))

        for language in ("eng", "zhs"):
            table_path = localization_root / language / f"{table}.json"
            if not table_path.is_file():
                fail(errors, f"missing {language} localization table: {table_path.relative_to(ROOT)}")
                continue
            values = json.loads(table_path.read_text(encoding="utf-8"))
            expected_key = f"{entry}.{suffix}"
            if not values.get(expected_key):
                fail(errors, f"{table_path.relative_to(ROOT)} missing non-empty {expected_key}")
            stale_keys = sorted(key for key in values if key.startswith(f"{legacy_entry}."))
            if stale_keys:
                fail(
                    errors,
                    f"{table_path.relative_to(ROOT)} retains legacy keys: {stale_keys}",
                )

    for legacy_relative, namespaced_relative in MODEL_RESOURCE_RENAMES:
        legacy_path = ROOT / legacy_relative
        namespaced_path = ROOT / namespaced_relative
        if legacy_path.exists():
            fail(errors, f"legacy ModelId resource remains: {legacy_relative}")
        if not namespaced_path.is_file():
            fail(errors, f"namespaced ModelId resource is missing: {namespaced_relative}")

    # Historical docs and art prompts retain original display names intentionally.
    # Runtime source and probe sources must not refer to the retired class symbols.
    source_paths = list(SOURCE.rglob("*.cs"))
    probe_paths = [
        path
        for path in (ROOT / "tools").rglob("*.cs")
        if "ThingsModelIdProbe" not in path.parts
    ]
    for path in sorted([*source_paths, *probe_paths]):
        text = path.read_text(encoding="utf-8")
        # 配置集成层（Config/）只含 UI 标签与键字符串，不是模型源码；显示名
        # （如 Backrooms/Medusa）天然包含旧类名词形，跳过旧类名扫描。
        if path.resolve() in CONFIG_PATHS:
            continue
        for legacy_class in legacy_class_names:
            # CacheMode.Reuse is an unrelated Godot enum member, so only reject
            # standalone class-symbol use rather than a dotted API member.
            if re.search(rf"(?<!\.)\b{re.escape(legacy_class)}\b", text):
                fail(errors, f"{path.relative_to(ROOT)} still uses legacy model type {legacy_class}")

    if pck is None:
        return
    if not pck.is_file():
        fail(errors, f"final PCK is missing: {pck}")
        return

    payload = pck.read_bytes()
    for (
        _relative,
        _type_name,
        _base_type,
        category,
        legacy_entry,
        entry,
        _table,
        suffix,
    ) in MODEL_ID_NAMESPACE_EXPECTATIONS:
        legacy_model_id = f"{category}.{legacy_entry}".encode("ascii")
        legacy_localization_key = f'"{legacy_entry}.'.encode("ascii")
        expected_localization_key = f'"{entry}.{suffix}"'.encode("ascii")
        if legacy_model_id in payload:
            fail(errors, f"final PCK retains legacy ModelId {legacy_model_id.decode('ascii')}")
        if legacy_localization_key in payload:
            fail(errors, f"final PCK retains legacy localization entry {legacy_entry}")
        if expected_localization_key not in payload:
            fail(errors, f"final PCK is missing localization entry {entry}.{suffix}")
    for legacy_relative, namespaced_relative in MODEL_RESOURCE_RENAMES:
        legacy_bytes = legacy_relative.encode("utf-8")
        namespaced_bytes = namespaced_relative.encode("utf-8")
        if legacy_bytes in payload:
            fail(errors, f"final PCK retains legacy ModelId resource {legacy_relative}")
        if namespaced_bytes not in payload:
            fail(errors, f"final PCK is missing namespaced ModelId resource {namespaced_relative}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pck",
        type=Path,
        help="scan the final exported PCK for retired ModelId entries and resources",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []

    audit_model_id_namespace(errors, args.pck)
    verify_config_contract(errors)

    def source_text(relative: str) -> str:
        return (SOURCE / relative).read_text(encoding="utf-8")

    def require_snippets(relative: str, snippets: list[str], contract: str) -> None:
        text = source_text(relative)
        for snippet in snippets:
            if snippet not in text:
                fail(errors, f"{relative} violates {contract}: missing {snippet!r}")

    root_manifest = json.loads((ROOT / "STS2_Things.json").read_text(encoding="utf-8"))
    target_manifest_paths = {
        "v107.1": ROOT / "manifests" / "v107.1" / "STS2_Things.json",
        "v111": ROOT / "manifests" / "v111" / "STS2_Things.json",
    }
    target_manifests: dict[str, dict] = {}
    for target, path in target_manifest_paths.items():
        if not path.is_file():
            fail(errors, f"target manifest missing: {path.relative_to(ROOT)}")
            continue
        target_manifests[target] = json.loads(path.read_text(encoding="utf-8"))
    project_root = ET.parse(ROOT / "STS2_Things.csproj").getroot()
    godot_project_text = (ROOT / "project.godot").read_text(encoding="utf-8")

    def project_value(name: str) -> str | None:
        node = project_root.find(f".//{name}")
        return node.text.strip() if node is not None and node.text else None

    release_version = root_manifest.get("version")
    if not isinstance(release_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", release_version):
        fail(errors, "unified manifest version must be a three-part semantic version")
        release_version = ""
    expected_min_versions = {"v107.1": "v0.107.1", "v111": "v0.111.0"}
    if project_value("Version") != release_version:
        fail(errors, f"implementation version must be {release_version}")
    for target, manifest in target_manifests.items():
        if manifest.get("version") != project_value("Version"):
            fail(errors, f"{target} manifest and assembly versions differ")
        if manifest.get("min_game_version") != expected_min_versions[target]:
            fail(errors, f"{target} manifest has the wrong min_game_version")
        if manifest.get("affects_gameplay") is not True:
            fail(errors, f"{target} manifest must set affects_gameplay=true")
        if manifest.get("dependencies"):
            fail(errors, f"{target} native build must not declare third-party dependencies")
    if root_manifest.get("version") != project_value("Version"):
        fail(errors, "unified manifest and implementation versions differ")
    if root_manifest.get("min_game_version") != "v0.107.1":
        fail(errors, "unified manifest must use the lowest supported game version")
    if root_manifest.get("affects_gameplay") is not True:
        fail(errors, "unified manifest must set affects_gameplay=true")
    if root_manifest.get("dependencies"):
        fail(errors, "unified native package must not declare third-party dependencies")
    for target, manifest in target_manifests.items():
        for field in ("id", "name", "author", "description", "version", "has_pck", "has_dll"):
            if manifest.get(field) != root_manifest.get(field):
                fail(errors, f"{target} manifest differs from unified manifest field {field}")
    if project_value("Nullable") != "enable":
        fail(errors, "Nullable must be enable")
    if project_value("TreatWarningsAsErrors") != "true":
        fail(errors, "TreatWarningsAsErrors must be true")
    project_text = (ROOT / "STS2_Things.csproj").read_text(encoding="utf-8")
    for required in (
        "Sts2TargetVersion",
        "STS2_V107_1",
        "STS2_V111",
        "<AssemblyName>STS2_Things</AssemblyName>",
        "Unsupported Sts2TargetVersion",
        '<Compile Remove="tools\\**\\*.cs" />',
        '<Compile Remove="bootstrap\\**\\*.cs" />',
        '<Compile Remove=".tmp\\**\\*.cs" />',
        '<Compile Remove="tmp\\**\\*.cs" />',
    ):
        if required not in project_text:
            fail(errors, f"dual-version project contract missing {required!r}")
    if "export/convert_text_resources_to_binary=false" not in godot_project_text:
        fail(
            errors,
            "project.godot must keep text resources unconverted so BackgroundAssets "
            "enumerates .tscn rather than unloadable .tscn.remap entries",
        )

    export_preset = (ROOT / "export_presets.cfg").read_text(encoding="utf-8")
    if "binary_format/convert_text_resources_to_binary=false" not in export_preset:
        fail(
            errors,
            "PCK export must preserve text-resource filenames; BackgroundAssets enumerates "
            "layer directories and cannot load exported .tscn.remap entries",
        )
    if "source_assets/**" not in export_preset:
        fail(errors, "editable monster source art must be excluded from the shipping PCK")
    if "bootstrap/**" not in export_preset:
        fail(errors, "bootstrap build outputs must be excluded from the shipping PCK")
    if "dotnet/include_scripts_content=false" not in export_preset:
        fail(errors, "PCK export must strip C# source content")
    if "**/*.cs," in export_preset:
        fail(
            errors,
            "PCK export must retain empty C# path placeholders for ScriptPath resolution",
        )
    if '<Compile Remove="STS2_Things\\Cards\\ThingsCollision.cs" />' in project_text:
        fail(errors, "published Things Collision is still excluded from compilation")
    if "images/packed/card_portraits/ironclad/things_collision.png" in export_preset:
        fail(errors, "published Things Collision card art is still excluded from the PCK")
    if "output/**" not in export_preset:
        fail(errors, "ImageGen working outputs must stay excluded from the shipping PCK")
    if not (ROOT / "output" / ".gdignore").is_file():
        fail(errors, "output/.gdignore must prevent Godot from importing ImageGen iterations")
    if not (ROOT / "source_assets" / ".gdignore").is_file():
        fail(errors, "source_assets/.gdignore must prevent Godot from importing build-time art")

    forbidden_patterns = {
        r"\bRandom\.Shared\b": "Random.Shared",
        r"\bSystem\.Random\b": "System.Random",
        r"\bGD\.Rand\w*\b": "Godot global RNG",
        r"\basync\s+void\b": "async void",
        r"\bRitsuLib\b": "RitsuLib dependency",
        r"\bBaseLib\b": "BaseLib dependency",
        r"\bMonsterRegistrar\b": "legacy global MonsterRegistrar",
        r"creature_visuals/fallback": "fallback creature visuals",
    }
    # 可选配置页集成层（Config/）用字符串与反射接入 BaseLib/RitsuLib，允许在注释与
    # 常量中提到两库；但绝不允许编译期引用（using/类型引用）。主目录的禁令不变。
    config_using_pattern = re.compile(
        r"^\s*using\s+(STS2RitsuLib|BaseLib)(\.|;|\s)", re.MULTILINE)
    for path in sorted([*SOURCE.rglob("*.cs"), *BOOTSTRAP.rglob("*.cs")]):
        text = path.read_text(encoding="utf-8")
        for pattern, label in forbidden_patterns.items():
            if path.resolve() in CONFIG_PATHS and pattern in (r"\bRitsuLib\b", r"\bBaseLib\b"):
                continue
            if re.search(pattern, text):
                fail(errors, f"{path.relative_to(ROOT)} contains forbidden {label}")
        if path.resolve() in CONFIG_PATHS and config_using_pattern.search(text):
            fail(errors, f"{path.relative_to(ROOT)} must not compile-reference BaseLib/RitsuLib")

    bootstrap_project_path = BOOTSTRAP / "STS2_Things.Bootstrap.csproj"
    bootstrap_source_path = BOOTSTRAP / "UnifiedBootstrap.cs"
    if not bootstrap_project_path.is_file():
        fail(errors, "unified bootstrap project is missing")
    else:
        bootstrap_project = ET.parse(bootstrap_project_path).getroot()

        def bootstrap_value(name: str) -> str | None:
            node = bootstrap_project.find(f".//{name}")
            return node.text.strip() if node is not None and node.text else None

        if bootstrap_value("AssemblyName") != "STS2_Things.Bootstrap":
            fail(errors, "bootstrap internal assembly name must not collide with the selected implementation")
        if bootstrap_value("Version") != project_value("Version"):
            fail(errors, "bootstrap and implementation versions differ")
        bootstrap_project_text = bootstrap_project_path.read_text(encoding="utf-8")
        for required in (
            "STS2_Things.Implementations.v107.1.dll",
            "STS2_Things.Implementations.v111.dll",
            "ImplementationV1071",
            "ImplementationV111",
        ):
            if required not in bootstrap_project_text:
                fail(errors, f"bootstrap embedding contract missing {required!r}")
    if not bootstrap_source_path.is_file():
        fail(errors, "unified bootstrap source is missing")
    else:
        bootstrap_text = bootstrap_source_path.read_text(encoding="utf-8")
        for required in (
            f"STS2_Things {release_version} supports",
            "ModifyDamageMultiplicative",
            "MegaCrit.Sts2.Core.Combat.CombatId",
            "AssociateAssemblyWithMod",
            "AppendV1071ImplementationTypes",
            "PromoteV1071ImplementationAssembly",
            "InvokeImplementationInitializer",
        ):
            if required not in bootstrap_text:
                fail(errors, f"bootstrap runtime contract missing {required!r}")

    compatibility_text = source_text("Compatibility/Sts2VersionCompatibility.cs")
    for snippet in (
        "#if STS2_V107_1",
        "SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ThingsCurseRemover));",
        "creature.GetCreatureNode()",
        "creature.SetNodeVisible(visible);",
    ):
        if snippet not in compatibility_text:
            fail(errors, f"dual-version compatibility bridge missing {snippet!r}")
    injection_sites: dict[str, set[str]] = {}
    for path in SOURCE.rglob("*.cs"):
        injected_types = set(
            re.findall(
                r"SavedPropertiesTypeCache\.InjectTypeIntoCache\(typeof\((\w+)\)\);",
                path.read_text(encoding="utf-8"),
            )
        )
        if injected_types:
            injection_sites[path.relative_to(SOURCE).as_posix()] = injected_types
    expected_injection_sites = {
        "Compatibility/Sts2VersionCompatibility.cs": {"ThingsCurseRemover"},
        "Enchantments/ThingsSplit.cs": {"ThingsSplit"},
    }
    if injection_sites != expected_injection_sites:
        fail(
            errors,
            "V107.1 SavedProperty injection sites differ: "
            f"expected {expected_injection_sites}, got {injection_sites}",
        )

    build_text = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8")
    for required in (
        "build_quirky_hopper_texture.py",
        "build_static_monster_scenes.py",
        "Sts2TargetVersion=$TargetVersion",
        "manifests\\$TargetVersion\\STS2_Things.json",
        "verify-harmony-targets.ps1",
        ".godot\\mono\\temp\\bin\\$Configuration\\STS2_Things.dll",
        "ReusePck",
        "--pck $Pck",
    ):
        if required not in build_text:
            fail(errors, f"target-aware build script missing {required!r}")

    build_all_text = (ROOT / "scripts" / "build-all.ps1").read_text(encoding="utf-8")
    for required in (
        "build-unified.ps1",
        "build\\unified",
        "DataDirV1071",
        "DataDirV111",
        "test-gravetide-slug.ps1",
        "test-merchant-bargain.ps1",
        "test-quirky-hopper.ps1",
        "test-things-collision.ps1",
        "test-things-split.ps1",
        "test-model-id-namespace.ps1",
    ):
        if required not in build_all_text:
            fail(errors, f"unified build orchestration missing {required!r}")
    unified_build_text = (ROOT / "scripts" / "build-unified.ps1").read_text(encoding="utf-8")
    for required in (
        "STS2_Things.Bootstrap.csproj",
        "verify-unified-package.ps1",
        "build\\v107.1\\STS2_Things.dll",
        "build\\v111\\STS2_Things.dll",
        "build\\unified",
    ):
        if required not in unified_build_text:
            fail(errors, f"unified package build missing {required!r}")
    for stale in (
        "Building image-generated semantic monster cutout rigs",
        "Building native Spine 4.2 monster assets",
        "SPINE_RUNTIME_PASS",
    ):
        if stale in build_text:
            fail(errors, f"static build script still executes old rig step {stale!r}")

    localization = SOURCE / "localization"

    if "ModHelper.AddModelToPool<IroncladCardPool, ThingsCollision>();" not in source_text(
        "STS2_ThingsInit.cs"
    ):
        fail(errors, "Things Collision is not registered in the Ironclad card pool")

    require_snippets(
        "Cards/ThingsCollision.cs",
        [
            "public sealed class ThingsCollision : CardModel",
            "CardRarity.Uncommon",
            "CardKeyword.Exhaust",
            "new DamageVar(10m, ValueProp.Move)",
            "new DynamicVar(StrengthLossKey, 2m)",
            "#if STS2_V107_1",
            ".FromCard(this, cardPlay)",
            "Owner.Creature, -strengthLoss",
            "cardPlay.Target, -strengthLoss",
            "DynamicVars.Damage.UpgradeValueBy(4m)",
        ],
        "Things Collision gameplay and dual-version contract",
    )

    card_portraits = {
        "ThingsReuse": ROOT / "images/packed/card_portraits/defect/things_reuse.png",
        "Things Collision": ROOT / "images/packed/card_portraits/ironclad/things_collision.png",
        "ThingsPackUp": ROOT / "images/packed/card_portraits/silent/things_pack_up.png",
        "ThingsRecall": ROOT / "images/packed/card_portraits/silent/things_recall.png",
        "Soulfysh Disease": ROOT / "images/packed/card_portraits/silent/soulfysh_disease.png",
    }
    for card_name, portrait_path in card_portraits.items():
        if not portrait_path.is_file():
            fail(errors, f"{card_name} shipping portrait is missing")
            continue
        with Image.open(portrait_path) as image:
            if image.size != (1000, 760) or image.mode not in {"RGB", "RGBA"}:
                fail(
                    errors,
                    f"{card_name} portrait must be RGB/RGBA 1000x760, "
                    f"got {image.mode} {image.size}",
                )
    for language in ("eng", "zhs"):
        cards_table = json.loads(
            (localization / language / "cards.json").read_text(encoding="utf-8")
        )
        for key in ("THINGS_COLLISION.title", "THINGS_COLLISION.description"):
            if not cards_table.get(key):
                fail(errors, f"{language}/cards.json missing {key}")

    require_snippets(
        "Events/CuttingItClose.cs",
        [
            "public sealed class CuttingItClose : EventModel",
            "public override bool IsAllowed(IRunState runState)",
            "runState.Players.All(player => player.Deck.Cards.Any(card => IsSplitCandidate(split, card)))",
            "ModelDb.Enchantment<ThingsSplit>()",
            "CardSelectCmd.FromDeckForEnchantment(",
            "card => card is not null && IsSplitCandidate(split, card)",
            "card.Type is CardType.Attack or CardType.Skill",
            "EventOwner.RunState.CloneCard(selected)",
            "CardCmd.Enchant<ThingsSplit>(copy, 1m);",
            "await CardPileCmd.RemoveFromDeck(selected);",
            "await CardPileCmd.Add(copies, PileType.Deck);",
            "CardSelectCmd.FromDeckForRemoval(",
            "FinishWithoutCard();",
            'L10NLookup("CUTTING_IT_CLOSE.pages.ABORTED.description")',
            "RunManager.Instance.EventSynchronizer.Events",
            "mutableEvents.Any(mutableEvent =>",
            "ShouldPrepareScreens(",
            "NOverlayStack.Instance?.Clear();",
            "NCapstoneContainer.Instance?.Close();",
            "NMapScreen.Instance?.Close(animateOut: false);",
        ],
        "native synchronized split/remove event flow and console screen cleanup",
    )
    cutting_source = source_text("Events/CuttingItClose.cs")
    if cutting_source.count("if (selected is null)") != 2:
        fail(
            errors,
            "Cutting It Close must close safely when either deck selector returns no card",
        )
    require_snippets(
        "Enchantments/ThingsSplit.cs",
        [
            "public sealed class ThingsSplit : EnchantmentModel",
            "#if STS2_V107_1",
            "SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ThingsSplit));",
            "[SavedProperty]",
            "public string SplitState",
            "return base.CanEnchant(card) && HasFixedEnergyCost(card) && !card.HasStarCostX;",
            'private const string SerializedStateVersion = "2";',
            "private int? _unsplitStarCost;",
            "nameof(CardModel.BaseStarCost)",
            '[HarmonyPatch(typeof(CardModel), "UpgradeStarCostBy")]',
            "private static decimal SplitDynamicValue(decimal value)",
            "return decimal.Ceiling(value / 2m);",
            "private static int SplitEnergyCost(int value)",
            "return value < 0 ? value : value / 2;",
            "state.UnsplitDynamicValues.GetValueOrDefault(",
            '[HarmonyPatch(typeof(TheScythe), "CurrentDamage", MethodType.Setter)]',
            "nameof(CardModel.ClearEnchantmentInternal)",
            "nameof(CardModel.FromSerializable)",
            "[HarmonyFinalizer]",
        ],
        "split rounding and permanent-card mutation contract",
    )

    init_text = source_text("STS2_ThingsInit.cs")
    cutting_registration = "ModelDb.Event<CuttingItClose>()"
    # 事件目录：Overgrowth/Underdocks 共用同一目录函数（两幕补丁各自追加），
    # Hive 使用独立目录函数；确定性追加合同在目录内实现。
    for act_name, catalog_call in (
        ("Overgrowth", "ThingsEventCatalog.AddOvergrowthAndUnderdocksEvents(__result)"),
        ("Underdocks", "ThingsEventCatalog.AddOvergrowthAndUnderdocksEvents(__result)"),
        ("Hive", "ThingsEventCatalog.AddHiveEvents(__result)"),
    ):
        event_patch = re.search(
            rf'\[HarmonyPatch\(typeof\({act_name}\), "get_AllEvents"\)\]'
            r"(?P<body>.*?)(?=\n\[HarmonyPatch|\Z)",
            init_text,
            re.DOTALL,
        )
        if event_patch is None:
            fail(errors, f"{act_name} event registration patch is missing")
            continue
        body = event_patch.group("body")
        if catalog_call not in body:
            fail(errors, f"{act_name} event patch must call {catalog_call}")
        if "HarmonyPriority(Priority.Last)" not in body:
            fail(errors, f"{act_name} event patch is missing HarmonyPriority(Priority.Last)")
    if init_text.count(cutting_registration) != 1:
        fail(errors, "Cutting It Close must be registered exactly once in the shared event catalog")
    catalog_region = init_text[init_text.index("ThingsEventCatalog"):]
    for deterministic_contract in (
        "DeterministicContentOrder.SortBaseThenMods(",
        ".Distinct()",
    ):
        if deterministic_contract not in catalog_region:
            fail(
                errors,
                f"event catalog is missing deterministic append contract {deterministic_contract!r}",
            )

    cutting_event_keys = {
        "CUTTING_IT_CLOSE.title",
        "CUTTING_IT_CLOSE.pages.INITIAL.description",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.title",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.THROW.title",
        "CUTTING_IT_CLOSE.pages.INITIAL.options.THROW.description",
        "CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt",
        "CUTTING_IT_CLOSE.pages.THROW.selectionScreenPrompt",
        "CUTTING_IT_CLOSE.pages.ABORTED.description",
        "CUTTING_IT_CLOSE.pages.IMPROVISE.description",
        "CUTTING_IT_CLOSE.pages.THROW.description",
    }
    expected_event_titles = {"eng": "Cutting It Close", "zhs": "命悬一线"}
    split_localization_phrases = {
        "eng": ("rounded down", "rounded up"),
        "zhs": ("向下取整", "向上取整"),
    }
    for lang in ("eng", "zhs"):
        events_table = json.loads(
            (localization / lang / "events.json").read_text(encoding="utf-8")
        )
        enchantments_table = json.loads(
            (localization / lang / "enchantments.json").read_text(encoding="utf-8")
        )
        missing_event_keys = cutting_event_keys - events_table.keys()
        if missing_event_keys:
            fail(
                errors,
                f"{lang}/events.json is missing Cutting It Close keys: "
                f"{sorted(missing_event_keys)}",
            )
        empty_event_keys = sorted(
            key for key in cutting_event_keys if not events_table.get(key)
        )
        if empty_event_keys:
            fail(
                errors,
                f"{lang}/events.json has empty Cutting It Close values: "
                f"{empty_event_keys}",
            )
        if events_table.get("CUTTING_IT_CLOSE.title") != expected_event_titles[lang]:
            fail(errors, f"{lang}/events.json has the wrong Cutting It Close title")
        improvise_description = events_table.get(
            "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description", ""
        )
        if (
            "{Enchantment}" not in improvise_description
            or "[blue]2[/blue]" not in improvise_description
        ):
            fail(errors, f"{lang} improvise option must describe two Split-enchanted copies")
        selection_prompt = events_table.get(
            "CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt", ""
        )
        required_card_type_terms = {
            "eng": ("Attack", "Skill"),
            "zhs": ("攻击牌", "技能牌"),
        }[lang]
        if any(
            term not in improvise_description or term not in selection_prompt
            for term in required_card_type_terms
        ):
            fail(
                errors,
                f"{lang} improvise option and prompt must limit selection to Attack or Skill cards",
            )

        for key in ("THINGS_SPLIT.title", "THINGS_SPLIT.description"):
            if not enchantments_table.get(key):
                fail(errors, f"{lang}/enchantments.json is missing non-empty {key}")
        split_description = enchantments_table.get("THINGS_SPLIT.description", "")
        for phrase in split_localization_phrases[lang]:
            if phrase not in split_description:
                fail(
                    errors,
                    f"{lang}/THINGS_SPLIT.description does not explain {phrase!r}",
                )

    # Shipping creature scenes use the reviewed full-texture PNGs. The local
    # Spine/cutout pipeline remains available as source material, but none of it
    # is referenced by the runtime scenes or exported into the PCK.
    rig_specs = {
        "origin_fogmog": ("origin_fogmog.tscn", 15, 16, "OriginFogmog", 1.90),
        "bowlbug_progenitor": (
            "bowlbug_progenitor.tscn", 45, 34, "BowlbugProgenitor", 0.92
        ),
        "scale_beetle": ("things_scale_beetle.tscn", 48, 29, "ThingsScaleBeetle", 1.37),
        "soul_roe_1": ("soul_roe.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roe_2": ("soul_roe_2.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roe_3": ("soul_roe_3.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roes": ("soul_roes.tscn", 12, 16, "SoulRoes", 0.78),
        "the_legacy": ("things_the_legacy.tscn", 36, 28, "ThingsTheLegacy", 0.92),
    }
    expected_total_parts = sum(spec[1] for spec in rig_specs.values())
    expected_total_bones = sum(spec[2] for spec in rig_specs.values())
    required_spine_animations = (
        "idle_loop",
        "attack",
        "cast",
        "hurt",
        "die",
        "summon",
        "power_up",
        "revive",
    )

    for rig_key, (name, _part_count, _bone_count, _model, _death_time) in sorted(
        rig_specs.items()
    ):
        path = ROOT / "scenes" / "creature_visuals" / name
        if not path.is_file():
            fail(errors, f"native creature scene missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        script_path = "res://STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs"
        texture_path = f"res://images/monsters/{rig_key}.png"
        if script_path not in text:
            fail(errors, f"{path.relative_to(ROOT)} does not use NThingsStaticCreatureVisuals")
        if texture_path not in text:
            fail(errors, f"{path.relative_to(ROOT)} does not reference {texture_path}")
        sprite_nodes = re.findall(
            r'^\[node name="([^"]+)" type="Sprite2D"[^\]]*\]', text, re.MULTILINE
        )
        if sprite_nodes != ["Visuals"]:
            fail(
                errors,
                f"{path.relative_to(ROOT)} must contain exactly one Sprite2D named "
                f"%Visuals; got {sprite_nodes!r}",
            )
        visuals_block = re.search(
            r'^\[node name="Visuals" type="Sprite2D"[^\]]*\]\s*\n'
            r'(.*?)(?=^\[node |\Z)',
            text,
            re.MULTILINE | re.DOTALL,
        )
        if visuals_block is None or "texture = ExtResource" not in visuals_block.group(1):
            fail(errors, f"{path.relative_to(ROOT)} %Visuals lacks its full texture resource")
        for forbidden_node_type in ("SpineSprite", "Polygon2D", "Skeleton2D", "Bone2D"):
            if re.search(rf'type="{forbidden_node_type}"', text):
                fail(
                    errors,
                    f"{path.relative_to(ROOT)} reintroduces {forbidden_node_type} animation",
                )
        if re.search(r"^z_(?:index|as_relative)\s*=", text, re.MULTILINE):
            fail(errors, f"{path.relative_to(ROOT)} overrides the creature canvas z-order")
        bounds_block = re.search(
            r'\[node name="Bounds"[^\]]*\](.*?)(?=\n\[node |\Z)', text, re.DOTALL
        )
        if bounds_block is None or "offset_bottom" not in bounds_block.group(1):
            fail(errors, f"{path.relative_to(ROOT)} does not include texture bounds padding")
        for node_name in ("Visuals", "Bounds", "CenterPos", "IntentPos"):
            node_block = re.search(
                rf'^\[node name="{node_name}"[^\]]*\]\s*\n'
                r'(.*?)(?=^\[node |\Z)',
                text,
                re.MULTILINE | re.DOTALL,
            )
            if node_block is None or not re.search(
                r"^unique_name_in_owner\s*=\s*true\s*$",
                node_block.group(1),
                re.MULTILINE,
            ):
                fail(errors, f"{path.relative_to(ROOT)} lacks unique %{node_name}")
    # Every self-owned shipping monster texture is an exact RGBA mirror of its
    # editable source.  No edge, grain, brightness, outline or palette pass may
    # alter even transparent-canvas pixels.
    source_monsters = ROOT / "source_assets" / "monsters"
    shipping_monsters = ROOT / "images" / "monsters"
    source_names = {path.name for path in source_monsters.glob("*.png")}
    shipping_names = {path.name for path in shipping_monsters.glob("*.png")}
    expected_source_textures = {
        "bowlbug_progenitor.png",
        "origin_fogmog.png",
        "scale_beetle.png",
        "soul_roe_1.png",
        "soul_roe_2.png",
        "soul_roe_3.png",
        "soul_roes.png",
        "the_legacy.png",
    }
    expected_shipping_textures = expected_source_textures | {
        # Derived from the final native Corpse Slug death-animation frame;
        # its reproducible source is the Spine render/crop pipeline rather
        # than a second editable master under source_assets/monsters.
        "gravetide_slug_corpse.png",
    }
    if source_names != expected_source_textures:
        fail(
            errors,
            f"monster source-art set differs: "
            f"{sorted(source_names ^ expected_source_textures)}",
        )
    if shipping_names != expected_shipping_textures:
        fail(
            errors,
            f"shipping monster-texture set differs: "
            f"{sorted(shipping_names ^ expected_shipping_textures)}",
        )
    for name in sorted(source_names & shipping_names):
        source_path = source_monsters / name
        shipping_path = shipping_monsters / name
        with Image.open(source_path) as source_image, Image.open(shipping_path) as shipping_image:
            source_image.load()
            shipping_image.load()
            if source_image.size != shipping_image.size:
                fail(errors, f"{shipping_path.relative_to(ROOT)} changed the scene canvas size")
                continue
            if source_image.mode != "RGBA":
                fail(errors, f"{source_path.relative_to(ROOT)} must be encoded as RGBA")
                continue
            if shipping_image.mode != "RGBA":
                fail(errors, f"{shipping_path.relative_to(ROOT)} must be encoded as RGBA")
                continue
            if source_image.getchannel("A").getbbox() is None:
                fail(errors, f"{source_path.relative_to(ROOT)} has no non-transparent pixels")
                continue
            if shipping_image.getchannel("A").getbbox() is None:
                fail(errors, f"{shipping_path.relative_to(ROOT)} must be a non-empty RGBA texture")
                continue
            source_pixels = source_image.tobytes()
            shipping_pixels = shipping_image.tobytes()
            if shipping_pixels != source_pixels:
                first_pixel = next(
                    pixel_index
                    for pixel_index, offset in enumerate(range(0, len(source_pixels), 4))
                    if source_pixels[offset : offset + 4] != shipping_pixels[offset : offset + 4]
                )
                x = first_pixel % source_image.width
                y = first_pixel // source_image.width
                offset = first_pixel * 4
                fail(
                    errors,
                    f"{shipping_path.relative_to(ROOT)} changes source RGBA pixel "
                    f"({x}, {y}) from {tuple(source_pixels[offset : offset + 4])} "
                    f"to {tuple(shipping_pixels[offset : offset + 4])}",
                )

    # Spine source pipeline: semantic cutout inputs are build-time data only.
    # The shipping creature scene consumes the generated atlas/skeleton pair.
    spine_required_visual_files = (
        ROOT / "scripts" / "build_ai_cutout_rigs.py",
        ROOT / "scripts" / "build_spine_monsters.py",
        ROOT / "scripts" / "build_static_monster_scenes.py",
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json",
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.qa.generated.json",
        ROOT / "source_assets" / "monsters" / "spine_monsters.generated.json",
        ROOT / "STS2_Things" / "Visuals" / "NThingsStaticCreatureVisuals.cs",
        ROOT / "STS2_Things" / "Visuals" / "NThingsSpineCreatureVisuals.cs",
        ROOT / "STS2_Things" / "Monsters" / "ThingsSpineMonster.cs",
    )
    for path in spine_required_visual_files:
        if not path.is_file():
            fail(errors, f"monster Spine pipeline file missing: {path.relative_to(ROOT)}")

    expected_rig_keys = set(rig_specs)
    ai_cutout_manifest_path = (
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json"
    )
    ai_cutout_manifest: dict[str, dict] = {}
    if ai_cutout_manifest_path.is_file():
        parsed_ai_cutout_manifest = json.loads(
            ai_cutout_manifest_path.read_text(encoding="utf-8")
        )
        if not isinstance(parsed_ai_cutout_manifest, dict):
            fail(errors, "AI cutout rig manifest root must be an object")
        else:
            ai_cutout_manifest = parsed_ai_cutout_manifest
            if set(ai_cutout_manifest) != expected_rig_keys:
                fail(
                    errors,
                    "AI cutout rig key set differs: "
                    f"{sorted(set(ai_cutout_manifest) ^ expected_rig_keys)}",
                )

    required_parent_edges = {
        "origin_fogmog": {
            "Body": "Root",
            "Face": "Body",
            "CapUnder": "Body",
            "CapTop": "CapUnder",
            "CapNeck": "Body",
            "LeftArm": "Body",
            "LeftForearm": "LeftArm",
            "LeftHand": "LeftForearm",
            "RightArm": "Body",
            "RightForearm": "RightArm",
            "RightHand": "RightForearm",
            "LeftLeg": "Body",
            "LeftFoot": "LeftLeg",
            "RightLeg": "Body",
            "RightFoot": "RightLeg",
        },
        "bowlbug_progenitor": {
            "Head": "FrontShell",
            "Mandible": "Head",
            "MandibleLower": "Head",
            "Crest": "Head",
            "FrontLeg": "FrontShell",
            "FrontLegLower": "FrontLeg",
            "FrontFoot": "FrontLegLower",
            "MidLegA": "MidShell",
            "MidLegALower": "MidLegA",
            "MidFootA": "MidLegALower",
            "MidLegB": "EggSac",
            "MidLegBLower": "MidLegB",
            "MidFootB": "MidLegBLower",
            "RearLegA": "RearShell",
            "RearLegALower": "RearLegA",
            "RearFootA": "RearLegALower",
            "RearLegB": "RearShell",
            "RearLegBLower": "RearLegB",
            "RearFootB": "RearLegBLower",
        },
        "scale_beetle": {
            "Head": "FrontShell",
            "JawUpper": "Head",
            "JawLower": "Head",
            "ForeClaw": "FrontShell",
            "ForeClawLower": "ForeClaw",
            "FrontLeg": "FrontShell",
            "FrontLegLower": "FrontLeg",
            "MidLeg": "Core",
            "MidLegLower": "MidLeg",
            "RearLeg": "RearShell",
            "RearLegLower": "RearLeg",
            "AntennaFrontBase": "Head",
            "AntennaFront1": "AntennaFrontBase",
            "AntennaFront2": "AntennaFront1",
            "AntennaFront3": "AntennaFront2",
            "AntennaFront4": "AntennaFront3",
            "AntennaFront5": "AntennaFront4",
            "AntennaFrontTip": "AntennaFront5",
            "AntennaBackBase": "Head",
            "AntennaBack1": "AntennaBackBase",
            "AntennaBack2": "AntennaBack1",
            "AntennaBack3": "AntennaBack2",
            "AntennaBack4": "AntennaBack3",
            "AntennaBack5": "AntennaBack4",
            "AntennaBackTip": "AntennaBack5",
        },
        "soul_roe_1": {"Core": "Root", "Nucleus": "Core"},
        "soul_roe_2": {"Core": "Root", "Nucleus": "Core"},
        "soul_roe_3": {"Core": "Root", "Nucleus": "Core"},
        "soul_roes": {
            "ClusterTop": "Root",
            "ClusterMiddle": "Root",
            "ClusterBottom": "Root",
            "RoeTop": "ClusterTop",
            "RoeCore": "ClusterMiddle",
            "RoeBottom": "ClusterBottom",
        },
        "the_legacy": {
            "HeartAnchor": "Root",
            "HeartCore": "HeartAnchor",
            "LeftLobe": "HeartAnchor",
            "RightLobe": "HeartAnchor",
            "TopPurple": "HeartAnchor",
            "RightTubes": "HeartAnchor",
            "RightTubesFar": "RightTubes",
            "RightTubesLower": "RightTubes",
        },
    }

    total_ai_parts = 0
    total_ai_bones = 0
    manifest_ai_textures: set[Path] = set()
    bone_maps: dict[str, dict[str, str]] = {}
    expected_slot_orders: dict[str, list[str]] = {}
    for rig_key in sorted(expected_rig_keys):
        rig = ai_cutout_manifest.get(rig_key)
        if not isinstance(rig, dict):
            fail(errors, f"AI cutout rig {rig_key} is missing or invalid")
            continue
        if rig.get("pipeline") != "ai_generated_complete_cutout_v1":
            fail(errors, f"AI cutout rig {rig_key} has the wrong pipeline provenance")
        bones = rig.get("bones")
        parts = rig.get("parts")
        if not isinstance(bones, list) or not isinstance(parts, list):
            fail(errors, f"AI cutout rig {rig_key} lacks bone/part arrays")
            continue

        _scene, expected_parts, expected_bones, _model, _death_time = rig_specs[rig_key]
        if len(parts) != expected_parts:
            fail(
                errors,
                f"cutout rig {rig_key} has {len(parts)} parts; expected {expected_parts}",
            )
        if len(bones) != expected_bones:
            fail(
                errors,
                f"cutout rig {rig_key} has {len(bones)} bones; expected {expected_bones}",
            )
        total_ai_parts += len(parts)
        total_ai_bones += len(bones)

        bone_by_name: dict[str, dict] = {}
        for bone in bones:
            if not isinstance(bone, dict):
                fail(errors, f"cutout rig {rig_key} contains a non-object bone")
                continue
            bone_name = bone.get("name")
            if (
                not isinstance(bone_name, str)
                or not bone_name
                or bone_name in bone_by_name
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key} has an invalid/duplicate bone: {bone_name!r}",
                )
                continue
            parent_name = bone.get("parent")
            if not isinstance(parent_name, str):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{bone_name} has invalid parent {parent_name!r}",
                )
            pivot = bone.get("pivot")
            if (
                not isinstance(pivot, list)
                or len(pivot) != 2
                or not all(isinstance(value, (int, float)) for value in pivot)
            ):
                fail(errors, f"cutout rig {rig_key}/{bone_name} has invalid bind pivot")
            bone_by_name[bone_name] = bone

        roots = [
            name for name, bone in bone_by_name.items() if bone.get("parent") == ""
        ]
        if roots != ["Root"]:
            fail(
                errors,
                f"cutout rig {rig_key} must have exactly one logical Root; got {roots!r}",
            )
        for bone_name, bone in bone_by_name.items():
            parent_name = bone.get("parent", "")
            if parent_name and parent_name not in bone_by_name:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{bone_name} has missing parent {parent_name!r}",
                )
            if parent_name == bone_name:
                fail(errors, f"cutout rig {rig_key}/{bone_name} parents itself")
            visited: set[str] = set()
            cursor = bone_name
            while cursor:
                if cursor in visited:
                    fail(
                        errors,
                        f"cutout rig {rig_key} hierarchy cycle reaches {cursor!r}",
                    )
                    break
                visited.add(cursor)
                cursor = str(bone_by_name.get(cursor, {}).get("parent", ""))

        actual_parents = {
            name: str(bone.get("parent", "")) for name, bone in bone_by_name.items()
        }
        bone_maps[rig_key] = actual_parents
        for child, expected_parent in required_parent_edges.get(rig_key, {}).items():
            if actual_parents.get(child) != expected_parent:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{child} parent is "
                    f"{actual_parents.get(child)!r}; expected {expected_parent!r}",
                )

        seen_parts: set[str] = set()
        indexed_parts: list[tuple[int, dict]] = []
        for source_index, part in enumerate(parts):
            if not isinstance(part, dict):
                fail(errors, f"cutout rig {rig_key} contains a non-object part")
                continue
            part_name = part.get("name")
            if (
                not isinstance(part_name, str)
                or not part_name
                or part_name in seen_parts
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key} has an invalid/duplicate part: {part_name!r}",
                )
                continue
            seen_parts.add(part_name)
            indexed_parts.append((source_index, part))
            if not part_name.startswith("ai_"):
                fail(errors, f"AI cutout rig {rig_key}/{part_name} lacks the ai_ prefix")
            if part.get("ai_generated_complete_component") is not True:
                fail(
                    errors,
                    f"AI cutout rig {rig_key}/{part_name} is not a complete generated component",
                )
            source_component = part.get("source_component_path")
            if not isinstance(source_component, str) or not source_component.startswith(
                "res://source_assets/monsters/ai_cutout_parts/"
            ):
                fail(
                    errors,
                    f"AI cutout rig {rig_key}/{part_name} has invalid source provenance "
                    f"{source_component!r}",
                )
            bone_name = part.get("bone")
            if bone_name not in bone_by_name:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} references unknown bone "
                    f"{bone_name!r}",
                )
            elif part.get("pivot") != bone_by_name[bone_name].get("pivot"):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} pivot differs from bone "
                    f"{bone_name!r}",
                )
            if not isinstance(part.get("z"), int):
                fail(errors, f"cutout rig {rig_key}/{part_name} has invalid z order")
            for vector_name in ("pivot", "sprite_offset"):
                vector = part.get(vector_name)
                if (
                    not isinstance(vector, list)
                    or len(vector) != 2
                    or not all(isinstance(value, (int, float)) for value in vector)
                ):
                    fail(
                        errors,
                        f"cutout rig {rig_key}/{part_name} has invalid {vector_name}",
                    )

            texture = part.get("texture")
            if not isinstance(texture, str) or not texture.startswith(
                f"res://images/monsters/ai_rig_parts/{rig_key}/"
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} has invalid intermediate "
                    f"texture path {texture!r}",
                )
                continue
            texture_path = (ROOT / texture.removeprefix("res://")).resolve()
            manifest_ai_textures.add(texture_path)
            if not texture_path.is_file():
                fail(
                    errors,
                    f"cutout texture missing: {texture_path.relative_to(ROOT)}",
                )
                continue
            with Image.open(texture_path) as cutout_image:
                cutout_image.load()
                if (
                    cutout_image.mode != "RGBA"
                    or cutout_image.getchannel("A").getbbox() is None
                ):
                    fail(
                        errors,
                        "cutout texture is not a non-empty RGBA image: "
                        f"{texture_path.relative_to(ROOT)}",
                    )

        expected_slot_orders[rig_key] = [
            str(part["name"])
            for _source_index, part in sorted(
                indexed_parts,
                key=lambda item: (int(item[1].get("z", 0)), item[0]),
            )
        ]

    if total_ai_parts != expected_total_parts:
        fail(
            errors,
            f"AI cutout rig total is {total_ai_parts} parts; "
            f"expected {expected_total_parts} from per-rig contracts",
        )
    if total_ai_bones != expected_total_bones:
        fail(
            errors,
            f"AI cutout rig total is {total_ai_bones} bones; "
            f"expected {expected_total_bones} from per-rig contracts",
        )

    rig_parts_root = shipping_monsters / "ai_rig_parts"
    actual_ai_textures = {
        path.resolve() for path in rig_parts_root.rglob("*.png")
    }
    # The AI directory is build-time-only and excluded from the PCK.  Previous
    # approved iterations may remain for visual comparison, so only referenced
    # textures are authoritative and required to exist.
    for path in sorted(manifest_ai_textures - actual_ai_textures):
        fail(errors, f"manifest AI cutout texture missing: {path.relative_to(ROOT)}")

    ai_qa_path = (
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.qa.generated.json"
    )
    if ai_qa_path.is_file():
        ai_qa = json.loads(ai_qa_path.read_text(encoding="utf-8"))
        if not isinstance(ai_qa, dict):
            fail(errors, "AI cutout QA report root must be an object")
        else:
            if ai_qa.get("pipeline") != "ai_generated_complete_cutout_v1":
                fail(errors, "AI cutout QA report has the wrong pipeline")
            if ai_qa.get("manifest") != (
                "source_assets/monsters/ai_cutout_rigs.generated.json"
            ):
                fail(errors, "AI cutout QA report references the wrong manifest")
            if ai_qa.get("output_root") != "images/monsters/ai_rig_parts":
                fail(errors, "AI cutout QA report references the wrong output root")

            qa_monsters = ai_qa.get("monsters")
            if not isinstance(qa_monsters, dict) or set(qa_monsters) != expected_rig_keys:
                actual_keys = set(qa_monsters) if isinstance(qa_monsters, dict) else set()
                fail(
                    errors,
                    "AI cutout QA key set differs: "
                    f"{sorted(actual_keys ^ expected_rig_keys)}",
                )
            else:
                for rig_key in sorted(expected_rig_keys):
                    entry = qa_monsters.get(rig_key, {})
                    _scene, part_count, bone_count, _model, _death_time = rig_specs[
                        rig_key
                    ]
                    if entry.get("written_parts") != part_count:
                        fail(errors, f"AI cutout QA {rig_key} part count differs")
                    if entry.get("mapped_parts") != part_count:
                        fail(errors, f"AI cutout QA {rig_key} did not write every mapped part")
                    if entry.get("bones") != bone_count:
                        fail(errors, f"AI cutout QA {rig_key} bone count differs")
                    if entry.get("errors") != []:
                        fail(errors, f"AI cutout QA {rig_key} contains build errors")
                    if entry.get("canvas") != ai_cutout_manifest.get(rig_key, {}).get("canvas"):
                        fail(errors, f"AI cutout QA {rig_key} canvas differs")
                    qa_parts = entry.get("parts")
                    if not isinstance(qa_parts, list) or len(qa_parts) != part_count:
                        fail(errors, f"AI cutout QA {rig_key} part evidence differs")

            summary = ai_qa.get("summary")
            if not isinstance(summary, dict):
                fail(errors, "AI cutout QA report lacks a summary")
            else:
                if summary.get("monsters") != len(expected_rig_keys):
                    fail(errors, "AI cutout QA monster total differs")
                if summary.get("parts") != expected_total_parts:
                    fail(errors, "AI cutout QA part total differs")
                if summary.get("bones") != expected_total_bones:
                    fail(errors, "AI cutout QA bone total differs")
                if summary.get("errors") != 0:
                    fail(errors, "AI cutout QA reports build errors")

            newest_input = max(
                (
                    path.stat().st_mtime_ns
                    for path in (ai_cutout_manifest_path, *manifest_ai_textures)
                    if path.is_file()
                ),
                default=0,
            )
            if ai_qa_path.stat().st_mtime_ns < newest_input:
                fail(errors, "AI cutout QA report is older than its generated inputs")

    def collect_frame_times(value: object) -> list[float]:
        times: list[float] = []
        if isinstance(value, dict):
            frame_time = value.get("time")
            if isinstance(frame_time, (int, float)):
                times.append(float(frame_time))
            for child in value.values():
                times.extend(collect_frame_times(child))
        elif isinstance(value, list):
            for child in value:
                times.extend(collect_frame_times(child))
        return times

    def animation_duration(animation: object) -> float:
        return max(collect_frame_times(animation), default=0.0)

    spine_report_path = (
        ROOT / "source_assets" / "monsters" / "spine_monsters.generated.json"
    )
    spine_report_entries: dict[str, dict] = {}
    if spine_report_path.is_file():
        spine_report = json.loads(spine_report_path.read_text(encoding="utf-8"))
        if not isinstance(spine_report, dict):
            fail(errors, "Spine generation report root must be an object")
        else:
            report_version = str(spine_report.get("spine_version", ""))
            if re.fullmatch(r"4\.2(?:\.\d+)?", report_version) is None:
                fail(
                    errors,
                    f"Spine generation report targets {report_version!r}, not 4.2",
                )
            if spine_report.get("source_manifest") != (
                "source_assets/monsters/ai_cutout_rigs.generated.json"
            ):
                fail(errors, "Spine generation report was not built from the AI cutout rig")
            report_rigs = spine_report.get("rigs")
            if not isinstance(report_rigs, list):
                fail(errors, "Spine generation report lacks a rigs array")
            else:
                for entry in report_rigs:
                    if not isinstance(entry, dict):
                        fail(errors, "Spine report contains a non-object rig")
                        continue
                    key = entry.get("key")
                    if not isinstance(key, str) or key in spine_report_entries:
                        fail(errors, f"Spine report has invalid/duplicate key {key!r}")
                        continue
                    spine_report_entries[key] = entry
                if set(spine_report_entries) != expected_rig_keys:
                    fail(
                        errors,
                        "Spine generation report key set differs: "
                        f"{sorted(set(spine_report_entries) ^ expected_rig_keys)}",
                    )

    total_spine_slots = 0
    total_spine_bones = 0
    for rig_key in sorted(expected_rig_keys):
        _scene, expected_parts, expected_bones, _model, expected_death = rig_specs[
            rig_key
        ]
        directory = ROOT / "animations" / "monsters" / "sts2_things" / rig_key
        spjson_path = directory / f"{rig_key}.spjson"
        atlas_path = directory / f"{rig_key}.atlas"
        spatlas_path = directory / f"{rig_key}.spatlas"
        atlas_png_path = directory / f"{rig_key}.png"
        tres_path = directory / f"{rig_key}_skel_data.tres"
        asset_paths = (
            spjson_path,
            atlas_path,
            spatlas_path,
            atlas_png_path,
            tres_path,
        )
        for path in asset_paths:
            if not path.is_file():
                fail(errors, f"Spine asset missing: {path.relative_to(ROOT)}")
        if not all(path.is_file() for path in asset_paths):
            continue

        report_entry = spine_report_entries.get(rig_key, {})
        for field, expected_path in {
            "spjson": spjson_path.relative_to(ROOT).as_posix(),
            "spatlas": spatlas_path.relative_to(ROOT).as_posix(),
            "tres": tres_path.relative_to(ROOT).as_posix(),
        }.items():
            if report_entry.get(field) != expected_path:
                fail(
                    errors,
                    f"Spine report {rig_key}/{field} does not reference {expected_path}",
                )
        if report_entry.get("bones") != expected_bones:
            fail(errors, f"Spine report {rig_key} bone count differs")
        if report_entry.get("slots") != expected_parts:
            fail(errors, f"Spine report {rig_key} slot count differs")
        if tuple(report_entry.get("animations", ())) != required_spine_animations:
            fail(errors, f"Spine report {rig_key} animation list differs")

        spine_json = json.loads(spjson_path.read_text(encoding="utf-8"))
        if not isinstance(spine_json, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} root is not an object")
            continue
        spine_version = str(spine_json.get("skeleton", {}).get("spine", ""))
        if re.fullmatch(r"4\.2(?:\.\d+)?", spine_version) is None:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} targets Spine {spine_version!r}",
            )

        json_bones = spine_json.get("bones")
        json_slots = spine_json.get("slots")
        if not isinstance(json_bones, list) or not isinstance(json_slots, list):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks bone/slot arrays")
            continue
        total_spine_bones += len(json_bones)
        total_spine_slots += len(json_slots)
        if len(json_bones) != expected_bones:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} has {len(json_bones)} bones; "
                f"expected {expected_bones}",
            )
        if len(json_slots) != expected_parts:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} has {len(json_slots)} slots; "
                f"expected {expected_parts}",
            )

        expected_parents = bone_maps.get(rig_key, {})
        actual_parents: dict[str, str] = {}
        seen_bones: set[str] = set()
        for bone in json_bones:
            if not isinstance(bone, dict) or not isinstance(bone.get("name"), str):
                fail(errors, f"{spjson_path.relative_to(ROOT)} has an invalid bone")
                continue
            bone_name = str(bone["name"])
            parent = str(bone.get("parent", ""))
            if bone_name in seen_bones:
                fail(errors, f"{spjson_path.relative_to(ROOT)} repeats {bone_name!r}")
            if parent and parent not in seen_bones:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} bone {bone_name!r} appears "
                    f"before parent {parent!r}",
                )
            seen_bones.add(bone_name)
            actual_parents[bone_name] = parent
        if actual_parents != expected_parents:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} bone hierarchy differs from cutout rig",
            )
        roots = [name for name, parent in actual_parents.items() if not parent]
        root_bone = roots[0] if len(roots) == 1 else ""
        if roots != ["Root"]:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} must have one Root; got {roots!r}",
            )

        expected_slot_order = expected_slot_orders.get(rig_key, [])
        actual_slot_order = [
            str(slot.get("name", "")) if isinstance(slot, dict) else ""
            for slot in json_slots
        ]
        if actual_slot_order != expected_slot_order:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} slot draw order is not "
                "back-to-front (z, source order)",
            )
        part_by_name = {
            str(part.get("name")): part
            for part in ai_cutout_manifest.get(rig_key, {}).get("parts", [])
            if isinstance(part, dict)
        }
        for slot in json_slots:
            if not isinstance(slot, dict):
                continue
            slot_name = str(slot.get("name", ""))
            expected_part = part_by_name.get(slot_name, {})
            if slot.get("bone") != expected_part.get("bone"):
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} slot {slot_name!r} "
                    "uses the wrong bone",
                )
            if slot.get("attachment") != slot_name:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} slot {slot_name!r} "
                    "does not use its same-name attachment",
                )

        skins = spine_json.get("skins")
        default_skin = None
        if isinstance(skins, list):
            default_skin = next(
                (
                    skin
                    for skin in skins
                    if isinstance(skin, dict) and skin.get("name") == "default"
                ),
                None,
            )
        attachments = (
            default_skin.get("attachments")
            if isinstance(default_skin, dict)
            else None
        )
        if not isinstance(attachments, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks the default skin")
        elif set(attachments) != set(expected_slot_order):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} default-skin attachments differ "
                "from slots",
            )

        animations = spine_json.get("animations")
        if not isinstance(animations, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks animations")
            continue
        if set(animations) != set(required_spine_animations):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} animation set differs: "
                f"{sorted(set(animations) ^ set(required_spine_animations))}",
            )
        durations: dict[str, float] = {}
        non_root_times: dict[str, list[float]] = {}
        for animation_name in required_spine_animations:
            animation = animations.get(animation_name)
            duration = animation_duration(animation)
            durations[animation_name] = duration
            if duration <= 0.0:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} animation "
                    f"{animation_name!r} has no positive duration",
                )
            animation_bones = (
                animation.get("bones") if isinstance(animation, dict) else {}
            )
            if not isinstance(animation_bones, dict):
                animation_bones = {}
            action_times = [
                time
                for bone_name, timelines in animation_bones.items()
                if bone_name != root_bone
                for time in collect_frame_times(timelines)
            ]
            non_root_times[animation_name] = action_times
            if not action_times:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} animation "
                    f"{animation_name!r} only contains its duration sentinel",
                )

        if not any(
            0.45 - 1e-6 <= value <= 0.50 + 1e-6
            for value in non_root_times.get("attack", [])
        ):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} attack lacks a 0.45-0.50s "
                "contact keyframe",
            )
        for animation_name, release_time in (
            ("cast", 0.50),
            ("power_up", 0.50),
            ("summon", 0.75),
        ):
            if not any(
                abs(value - release_time) <= 1e-6
                for value in non_root_times.get(animation_name, [])
            ):
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} {animation_name} lacks its "
                    f"{release_time:.2f}s release keyframe",
                )
        if abs(durations.get("die", 0.0) - expected_death) > 1e-6:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} die duration is "
                f"{durations.get('die', 0.0):.3f}s; expected {expected_death:.2f}s",
            )
        if rig_key == "origin_fogmog" and abs(
            durations.get("hurt", 0.0) - 0.34
        ) > 1e-6:
            fail(errors, "Origin Fogmog Spine hurt must remain a short 0.34s")

        if rig_key == "the_legacy":
            idle_bones = animations.get("idle_loop", {}).get("bones", {})
            scale_bones = sorted(
                bone_name
                for bone_name, timelines in idle_bones.items()
                if isinstance(timelines, dict) and "scale" in timelines
            )
            if scale_bones != ["HeartAnchor"]:
                fail(
                    errors,
                    "The Legacy heartbeat must scale HeartAnchor exactly once; "
                    f"got {scale_bones!r}",
                )
            heartbeat = idle_bones.get("HeartAnchor", {}).get("scale", [])
            expected_heartbeat = {
                0.00: 1.0000,
                0.10: 0.9940,
                0.17: 1.0010,
                0.28: 0.9925,
                0.37: 1.0010,
                0.62: 1.0000,
                1.50: 1.0000,
            }
            actual_heartbeat = {
                round(float(frame.get("time", 0.0)), 4): float(frame.get("x", 0.0))
                for frame in heartbeat
                if isinstance(frame, dict)
            }
            for time_value, scale_value in expected_heartbeat.items():
                if abs(actual_heartbeat.get(time_value, -1.0) - scale_value) > 1e-6:
                    fail(
                        errors,
                        "The Legacy lost its restrained 1.5s lub-dub key at "
                        f"{time_value:.2f}s",
                    )

        atlas_text = atlas_path.read_text(encoding="utf-8")
        region_names = re.findall(
            r"^([^\s:\r\n][^:\r\n]*)\r?\n  rotate:",
            atlas_text,
            re.MULTILINE,
        )
        if set(region_names) != set(expected_slot_order) or len(
            region_names
        ) != expected_parts:
            fail(
                errors,
                f"{atlas_path.relative_to(ROOT)} regions differ from Spine slots",
            )
        if (
            not atlas_text.startswith(f"{rig_key}.png\n")
            or "format: RGBA8888" not in atlas_text
            or "filter: Linear,Linear" not in atlas_text
        ):
            fail(errors, f"{atlas_path.relative_to(ROOT)} has an invalid page header")

        spatlas = json.loads(spatlas_path.read_text(encoding="utf-8"))
        expected_atlas_resource = (
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.atlas"
        )
        if spatlas.get("source_path") != expected_atlas_resource:
            fail(
                errors,
                f"{spatlas_path.relative_to(ROOT)} has the wrong atlas source",
            )
        if spatlas.get("atlas_data") != atlas_text:
            fail(errors, f"{spatlas_path.relative_to(ROOT)} atlas data is stale")

        with Image.open(atlas_png_path) as atlas_image:
            atlas_image.load()
            if (
                atlas_image.mode != "RGBA"
                or atlas_image.getchannel("A").getbbox() is None
            ):
                fail(
                    errors,
                    f"{atlas_png_path.relative_to(ROOT)} is not a non-empty RGBA atlas",
                )
            atlas_size = list(atlas_image.size)
        if report_entry.get("atlas_size") != atlas_size:
            fail(errors, f"Spine report {rig_key} atlas size differs")

        tres_text = tres_path.read_text(encoding="utf-8")
        for resource_path in (
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.spatlas",
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.spjson",
        ):
            if resource_path not in tres_text:
                fail(
                    errors,
                    f"{tres_path.relative_to(ROOT)} does not reference {resource_path}",
                )
        mix_match = re.search(
            r"^default_mix\s*=\s*([0-9.]+)\s*$", tres_text, re.MULTILINE
        )
        if mix_match is None or abs(float(mix_match.group(1)) - 0.05) > 1e-6:
            fail(errors, f"{tres_path.relative_to(ROOT)} default_mix must be 0.05")

    if total_spine_slots != expected_total_parts:
        fail(
            errors,
            f"Spine skeleton total is {total_spine_slots} slots; "
            f"expected {expected_total_parts} from the AI rig set",
        )
    if total_spine_bones != expected_total_bones:
        fail(
            errors,
            f"Spine skeleton total is {total_spine_bones} bones; "
            f"expected {expected_total_bones} from the AI rig set",
        )

    require_snippets(
        "Visuals/NThingsSpineCreatureVisuals.cs",
        [
            "public partial class NThingsSpineCreatureVisuals : NCreatureVisuals",
            "SpineBody.HasAnimation(animation)",
            "SpineBody.TryGetAnimationState()",
            'state.AddAnimation("idle_loop", delay: 0f, loop: true);',
        ],
        "single-CanvasItem native Spine creature-visual contract",
    )
    spine_visuals_text = source_text("Visuals/NThingsSpineCreatureVisuals.cs")
    animation_array = re.search(
        r"_requiredAnimations\s*=\s*\[(.*?)\];",
        spine_visuals_text,
        re.DOTALL,
    )
    declared_animations = (
        tuple(re.findall(r'"([^"]+)"', animation_array.group(1)))
        if animation_array is not None
        else ()
    )
    if declared_animations != required_spine_animations:
        fail(
            errors,
            "NThingsSpineCreatureVisuals animation list differs from generated Spine",
        )
    for legacy_canvas_type in ("Skeleton2D", "Bone2D", "Sprite2D", "Polygon2D"):
        if legacy_canvas_type in spine_visuals_text:
            fail(
                errors,
                "NThingsSpineCreatureVisuals reintroduced "
                f"{legacy_canvas_type} rendering",
            )

    require_snippets(
        "Monsters/ThingsSpineMonster.cs",
        [
            'var idle = new AnimState("idle_loop", isLooping: true);',
            'var attack = ReturnToIdle("attack", idle);',
            'var cast = ReturnToIdle("cast", idle);',
            'var hurt = ReturnToIdle("hurt", idle);',
            'var summon = ReturnToIdle("summon", idle);',
            'var powerUp = ReturnToIdle("power_up", idle);',
            'var revive = ReturnToIdle("revive", idle);',
            'var die = new AnimState("die");',
            "animator.AddAnyState(CreatureAnimator.idleTrigger, idle);",
            "animator.AddAnyState(CreatureAnimator.attackTrigger, attack);",
            "animator.AddAnyState(CreatureAnimator.castTrigger, cast);",
            "animator.AddAnyState(CreatureAnimator.hitTrigger, hurt);",
            "animator.AddAnyState(CreatureAnimator.deathTrigger, die);",
            'animator.AddAnyState("Summon", summon);',
            "animator.AddAnyState(CreatureAnimator.powerUpTrigger, powerUp);",
            "animator.AddAnyState(CreatureAnimator.reviveTrigger, revive);",
        ],
        "eight-trigger native CreatureAnimator-to-Spine mapping contract",
    )

    static_models = (
        "OriginFogmog",
        "BowlbugProgenitor",
        "ThingsScaleBeetle",
        "SoulRoe",
        "SoulRoes",
        "ThingsTheLegacy",
    )
    for model_name in static_models:
        relative = f"Monsters/{model_name}.cs"
        model_text = source_text(relative)
        if re.search(
            rf"public sealed class\s+{re.escape(model_name)}\s*:\s*MonsterModel\b",
            model_text,
        ) is None:
            fail(errors, f"{relative} does not inherit MonsterModel directly")
        if "ThingsSpineMonster" in model_text:
            fail(errors, f"{relative} still references ThingsSpineMonster")
        if "DeathAnimLengthOverride" in model_text:
            fail(errors, f"{relative} still waits for a removed death animation")

    death_padding_contracts = {
        "Monsters/OriginFogmog.cs": "new(1.45f, 1.75f)",
        "Monsters/BowlbugProgenitor.cs": "new(1.35f, 1.8f)",
        "Monsters/ThingsScaleBeetle.cs": "new(2.3f, 2.1f)",
        "Monsters/SoulRoe.cs": "new(2.2f, 5.0f)",
        "Monsters/SoulRoes.cs": "new(1.6f, 3.0f)",
        "Monsters/ThingsTheLegacy.cs": "new(1.4f, 1.7f)",
    }
    for relative, value in death_padding_contracts.items():
        require_snippets(
            relative,
            ["ExtraDeathVfxPadding", value],
            "static texture death VFX padding contract",
        )

    ai_cutout_builder_text = (
        ROOT / "scripts" / "build_ai_cutout_rigs.py"
    ).read_text(encoding="utf-8")
    for required_builder_snippet in (
        "never crops an assembled monster painting",
        'DEFAULT_OUTPUT_ROOT = ROOT / "images" / "monsters" / "ai_rig_parts"',
        'OUTPUT_PREFIX = "ai_"',
        '"ai_generated_complete_component": True',
        "validate_manifest_subset",
    ):
        if required_builder_snippet not in ai_cutout_builder_text:
            fail(
                errors,
                "AI cutout builder lost complete-component provenance contract: "
                f"{required_builder_snippet!r}",
            )

    exclude_match = re.search(
        r'^exclude_filter="([^"]*)"', export_preset, re.MULTILINE
    )
    export_excludes = (
        {item.strip() for item in exclude_match.group(1).split(",") if item.strip()}
        if exclude_match is not None
        else set()
    )
    for required_exclude in (
        "tools/**",
        "manifests/**",
        "source_assets/**",
        "addons/spine/**",
        "animations/monsters/sts2_things/**",
        "images/monsters/ai_rig_parts/**",
    ):
        if required_exclude not in export_excludes:
            fail(
                errors,
                f"PCK export must exclude build-time asset {required_exclude}",
            )

    # Origin Fogmog's summoned eyes intentionally retain the shipped native
    # Spine scene and animator rather than joining the nine custom atlases.
    require_snippets(
        "Monsters/OriginEyeWithTeeth.cs",
        [
            'SceneHelper.GetScenePath("creature_visuals/eye_with_teeth")',
            "visuals.Modulate = Colors.White;",
            'new AnimState("idle_loop", true)',
            'creatureAnimator.AddAnyState("Attack"',
            'creatureAnimator.AddAnyState("Dead"',
        ],
        "native Spine Eye material/animation contract",
    )

    # EncounterModel scene/slot contract. Exact equality catches both missing runtime markers and
    # stale markers that are not represented by EncounterModel.Slots.
    encounter_slots = {
        "origin_fogmog_boss_encounter.tscn": {"fogmog", "illusion1", "illusion2"},
        "soul_roes_encounter.tscn": {"soul_roes", *(f"soul_roe_{i}" for i in range(1, 9))},
        "the_legacy_boss_encounter.tscn": {"the_legacy"},
        "scale_beetle_boss_encounter.tscn": {"scale_beetle"},
        "bowlbug_progenitor_boss_encounter.tscn": {
            "bowlbug_progenitor",
            *(f"bowlbug_{i}" for i in range(1, 17)),
        },
    }
    for name, expected in encounter_slots.items():
        path = ROOT / "scenes" / "encounters" / name
        if not path.is_file():
            fail(errors, f"encounter scene missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        root_block = text.split("[node name=", 2)[1]
        if (
            "anchors_preset = 15" not in root_block
            or "anchor_right = 1.0" not in root_block
            or "anchor_bottom = 1.0" not in root_block
            or re.search(r"^offset_(?:left|top|right|bottom)\s*=", root_block, re.MULTILINE)
        ):
            fail(errors, f"{path.relative_to(ROOT)} root Control is not full-rect")
        actual = set(re.findall(r'\[node name="([^"]+)" type="Marker2D"', text))
        if actual != expected:
            fail(
                errors,
                f"{path.relative_to(ROOT)} marker mismatch: "
                f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}",
            )

    # Native custom background contract used by EncounterModel.CreateBackground/BackgroundAssets.
    boss_backgrounds = {
        "gravetide_slug_boss_encounter",
        "origin_fogmog_boss_encounter",
        "scale_beetle_boss_encounter",
        "the_legacy_boss_encounter",
        "bowlbug_progenitor_boss_encounter",
    }
    for slug in sorted(boss_backgrounds):
        directory = ROOT / "scenes" / "backgrounds" / slug
        main_scene = directory / f"{slug}_background.tscn"
        layer_dir = directory / "layers"
        bg_layers = sorted(layer_dir.glob(f"{slug}_bg_*.tscn")) if layer_dir.is_dir() else []
        if not main_scene.is_file():
            fail(errors, f"native background scene missing: {main_scene.relative_to(ROOT)}")
        elif "NThingsCombatBackground.cs" not in main_scene.read_text(encoding="utf-8"):
            fail(errors, f"{main_scene.relative_to(ROOT)} does not use NThingsCombatBackground")
        if not bg_layers:
            fail(errors, f"native background layers missing for {slug}")

    gravetide_background = ROOT / "scenes/backgrounds/gravetide_slug_boss_encounter"
    gravetide_main = gravetide_background / "gravetide_slug_boss_encounter_background.tscn"
    gravetide_expected_layers = {
        "gravetide_slug_boss_encounter_bg_00_a.tscn",
        "gravetide_slug_boss_encounter_bg_01_a.tscn",
        "gravetide_slug_boss_encounter_bg_02_a.tscn",
        "gravetide_slug_boss_encounter_bg_03_a.tscn",
        "gravetide_slug_boss_encounter_fg_a.tscn",
    }
    gravetide_layer_dir = gravetide_background / "layers"
    if gravetide_layer_dir.is_dir():
        gravetide_actual_layers = {path.name for path in gravetide_layer_dir.iterdir()}
        if gravetide_actual_layers != gravetide_expected_layers:
            fail(
                errors,
                "Gravetide native layer set differs: "
                f"missing={sorted(gravetide_expected_layers - gravetide_actual_layers)} "
                f"extra={sorted(gravetide_actual_layers - gravetide_expected_layers)}",
            )
    if gravetide_main.is_file():
        gravetide_main_text = gravetide_main.read_text(encoding="utf-8")
        if "NGravetideSlugCombatBackground" in gravetide_main_text:
            fail(errors, "Gravetide background still uses manual _Ready layer assembly")
        for container in ("Layer_00", "Layer_01", "Layer_02", "Layer_03", "Foreground"):
            if f'[node name="{container}"' not in gravetide_main_text:
                fail(errors, f"Gravetide native background is missing {container}")

    gravetide_water_material = (
        ROOT / "materials/backgrounds/gravetide_slug_water_reflection.tres"
    )
    if not gravetide_water_material.is_file():
        fail(errors, "Gravetide water reflection material is missing")
    elif "hint_screen_texture" not in gravetide_water_material.read_text(encoding="utf-8"):
        fail(errors, "Gravetide water material does not implement background reflection")

    gravetide_art_contract = {
        "gravetide_slug_far.png": False,
        "gravetide_slug_water.png": True,
    }
    for art_name, expects_transparency in gravetide_art_contract.items():
        art_path = ROOT / "images/backgrounds/gravetide_slug" / art_name
        if not art_path.is_file():
            fail(errors, f"Gravetide background art is missing: {art_path.relative_to(ROOT)}")
            continue
        with Image.open(art_path) as image:
            image.load()
            if image.mode != "RGBA" or image.size != (2768, 1296):
                fail(
                    errors,
                    f"{art_path.relative_to(ROOT)} must be RGBA (2768, 1296), "
                    f"got {image.mode} {image.size}",
                )
                continue
            alpha_extrema = image.getchannel("A").getextrema()
            if expects_transparency and alpha_extrema == (255, 255):
                fail(errors, f"{art_path.relative_to(ROOT)} must retain transparent padding")
            if expects_transparency and image.getchannel("A").getbbox() is None:
                fail(errors, f"{art_path.relative_to(ROOT)} is fully transparent")
            if not expects_transparency and alpha_extrema != (255, 255):
                fail(errors, f"{art_path.relative_to(ROOT)} must be an opaque base layer")

    gravetide_ui_contract = {
        ROOT / "images/map/gravetide_slug_boss_icon.png": (352, 300),
        ROOT / "images/map/gravetide_slug_boss_icon_outline.png": (352, 300),
        ROOT / "images/ui/run_history/gravetide_slug_boss_encounter.png": (88, 88),
        ROOT / "images/ui/run_history/gravetide_slug_boss_encounter_outline.png": (88, 88),
        ROOT / "images/powers/gravetide_digestion_power.png": (256, 256),
        ROOT / "images/powers/gravetide_digestion_power_packed.png": (64, 64),
    }
    for ui_path, expected_size in gravetide_ui_contract.items():
        if not ui_path.is_file():
            fail(errors, f"Gravetide UI asset is missing: {ui_path.relative_to(ROOT)}")
            continue
        with Image.open(ui_path) as image:
            if image.mode != "RGBA" or image.size != expected_size:
                fail(
                    errors,
                    f"{ui_path.relative_to(ROOT)} must be RGBA {expected_size}, "
                    f"got {image.mode} {image.size}",
                )

    # 全部 Boss 遭遇的 run-history 图标契约（88x88 RGBA；缺文件会在真实游戏里报
    # “No loader found for resource: res://images/ui/run_history/<slug>_boss_encounter.png”）。
    boss_run_history_slugs = (
        "bowlbug_progenitor",
        "cave_god",
        "gravetide_slug",
        "living_rock",
        "origin_fogmog",
        "scale_beetle",
        "the_legacy",
    )
    for slug in boss_run_history_slugs:
        for variant in ("", "_outline"):
            icon_path = ROOT / "images/ui/run_history" / f"{slug}_boss_encounter{variant}.png"
            if not icon_path.is_file():
                fail(errors, f"boss run-history icon is missing: {icon_path.relative_to(ROOT)}")
                continue
            with Image.open(icon_path) as image:
                if image.mode != "RGBA" or image.size != (88, 88):
                    fail(
                        errors,
                        f"{icon_path.relative_to(ROOT)} must be RGBA (88, 88), "
                        f"got {image.mode} {image.size}",
                    )

    gravetide_atlas = ROOT / "STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.png"
    if gravetide_atlas.is_file():
        with Image.open(gravetide_atlas) as image:
            if image.mode != "RGBA" or image.size != (3132, 608):
                fail(
                    errors,
                    "Gravetide Spine atlas must be RGBA (3132, 608) after 4x supersampling, "
                    f"got {image.mode} {image.size}",
                )
    gravetide_power = ROOT / "images/powers/gravetide_digestion_power.png"
    vanilla_power = ROOT.parent / "STS2-V111/images/powers/ravenous_power.png"
    if gravetide_power.is_file() and vanilla_power.is_file():
        if hashlib.sha256(gravetide_power.read_bytes()).digest() == hashlib.sha256(vanilla_power.read_bytes()).digest():
            fail(errors, "Gravetide digestion Power icon still reuses the vanilla Ravenous texture")

    gravetide_music = ROOT / "music/gravetide_slug/gravetide_slug_boss_theme.wav"
    gravetide_sfx = ROOT / "sfx/gravetide_slug"
    if not gravetide_music.is_file():
        fail(errors, "Gravetide dedicated boss theme is missing")
    expected_sfx_prefixes = {
        "gravetide_slug_attack_light": 3,
        "gravetide_slug_attack": 2,
        "gravetide_slug_hurt": 4,
        "gravetide_slug_die": 2,
        "gravetide_slug_devour": 2,
        "gravetide_slug_devour_end": 2,
    }
    for prefix, expected_count in expected_sfx_prefixes.items():
        actual_count = len(list(gravetide_sfx.glob(f"{prefix}-*.wav")))
        if actual_count != expected_count:
            fail(
                errors,
                f"Gravetide SFX variant count for {prefix} is {actual_count}, "
                f"expected {expected_count}",
            )

    # Native background foregrounds rely on tree ordering. Explicit z-index values
    # raise them above the creature containers and obscure the monsters.
    for path in sorted((ROOT / "scenes" / "backgrounds").rglob("*.tscn")):
        if path.name.endswith("_background.tscn") or "_fg_" in path.name:
            if re.search(r"^z_index\s*=", path.read_text(encoding="utf-8"), re.MULTILINE):
                fail(errors, f"{path.relative_to(ROOT)} overrides native background z-order")

    # Bestiary strips the _MOVE suffix before localization lookup. Verify every concrete
    # MoveState has an eng/zhs title under that normalized key and reject stale title keys.
    monster_loc_paths = [localization / lang / "monsters.json" for lang in ("eng", "zhs")]
    monster_locs = [json.loads(path.read_text(encoding="utf-8")) for path in monster_loc_paths]
    expected_move_keys: set[str] = set()
    for path in sorted((SOURCE / "Monsters").glob("*.cs")):
        text = path.read_text(encoding="utf-8")
        class_match = re.search(r"public sealed class\s+(\w+)\s*:\s*MonsterModel", text)
        if not class_match:
            continue
        entry = re.sub(r"(?<!^)(?=[A-Z])", "_", class_match.group(1)).upper()
        string_constants = dict(
            re.findall(
                r'(?:public|private|protected|internal)\s+const\s+string\s+(\w+)\s*=\s*"([A-Z0-9_]+)"',
                text,
            )
        )
        state_args = re.findall(r'new MoveState\(\s*(?:"([A-Z0-9_]+)"|(\w+))', text)
        for literal, identifier in state_args:
            state_id = literal or string_constants.get(identifier)
            if not state_id:
                continue
            move_id = state_id[:-5] if state_id.endswith("_MOVE") else state_id
            expected_move_keys.add(f"{entry}.moves.{move_id}.title")
    for key in sorted(expected_move_keys):
        for lang, table in zip(("eng", "zhs"), monster_locs, strict=True):
            if key not in table:
                fail(errors, f"{lang}/monsters.json missing bestiary move key {key}")
    custom_entries = {key.split(".moves.", 1)[0] for key in expected_move_keys}
    for lang, table in zip(("eng", "zhs"), monster_locs, strict=True):
        stale = {
            key
            for key in table
            if key.endswith(".title")
            and ".moves." in key
            and key.split(".moves.", 1)[0] in custom_entries
            and key not in expected_move_keys
        }
        if stale:
            fail(errors, f"{lang}/monsters.json has stale move title keys: {sorted(stale)}")

    catalog = SOURCE / "Hooks" / "MonsterContentPatches.cs"
    catalog_text = catalog.read_text(encoding="utf-8") if catalog.is_file() else ""
    for encounter_type in (
        "GravetideSlugBossEncounter",
        "OriginFogmogBossEncounter",
        "QuirkyHopperWeak",
        "ScaleBeetleBossEncounter",
        "SoulRoesEncounter",
        "TheLegacyBossEncounter",
        "BowlbugProgenitorBossEncounter",
    ):
        if f"ModelDb.Encounter<{encounter_type}>()" not in catalog_text:
            fail(errors, f"Act encounter catalog is missing {encounter_type}")

    overgrowth_catalog = re.search(
        r"AddOvergrowthEncounters\(.*?\)\s*\{(?P<body>.*?)\n\s*\}",
        catalog_text,
        re.DOTALL,
    )
    underdocks_catalog = re.search(
        r"AddUnderdocksEncounters\(.*?\)\s*\{(?P<body>.*?)\n\s*\}",
        catalog_text,
        re.DOTALL,
    )
    hive_catalog = re.search(
        r"AddHiveEncounters\(.*?\)\s*\{(?P<body>.*?)\n\s*\}",
        catalog_text,
        re.DOTALL,
    )
    quirky_registration = "ModelDb.Encounter<QuirkyHopperWeak>()"
    if overgrowth_catalog and quirky_registration in overgrowth_catalog.group("body"):
        fail(errors, "Quirky Hopper is incorrectly registered in Act 1 Overgrowth")
    if underdocks_catalog and quirky_registration in underdocks_catalog.group("body"):
        fail(errors, "Quirky Hopper is incorrectly registered outside Act 2 Hive")
    if not hive_catalog or quirky_registration not in hive_catalog.group("body"):
        fail(errors, "Quirky Hopper is not registered in the Act 2 Hive encounter catalog")
    for boss_catalog_name in (
        "AddOvergrowthBosses",
        "AddUnderdocksBosses",
        "AddHiveBosses",
    ):
        boss_catalog = re.search(
            rf"{boss_catalog_name}\(.*?\)\s*\{{(?P<body>.*?)\n\s*\}}",
            catalog_text,
            re.DOTALL,
        )
        if boss_catalog and quirky_registration in boss_catalog.group("body"):
            fail(errors, f"Quirky Hopper is incorrectly registered in {boss_catalog_name}")
    require_snippets(
        "Encounters/QuirkyHopperWeak.cs",
        [
            "public override RoomType RoomType => RoomType.Monster;",
            "public override bool IsWeak => true;",
        ],
        "Act 2 weak hallway encounter classification",
    )

    gravetide_registration = "ModelDb.Encounter<GravetideSlugBossEncounter>()"
    if not underdocks_catalog or gravetide_registration not in underdocks_catalog.group("body"):
        fail(errors, "Gravetide Slug is not registered in the Underdocks encounter catalog")
    for wrong_catalog_name, wrong_catalog in (
        ("Overgrowth", overgrowth_catalog),
        ("Hive", hive_catalog),
    ):
        if wrong_catalog and gravetide_registration in wrong_catalog.group("body"):
            fail(errors, f"Gravetide Slug is incorrectly registered in {wrong_catalog_name}")
    underdocks_boss_catalog = re.search(
        r"AddUnderdocksBosses\(.*?\)\s*\{(?P<body>.*?)\n\s*\}",
        catalog_text,
        re.DOTALL,
    )
    if (
        not underdocks_boss_catalog
        or gravetide_registration not in underdocks_boss_catalog.group("body")
    ):
        fail(errors, "Gravetide Slug is not registered in the Underdocks boss pool")

    require_snippets(
        "Encounters/GravetideSlugBossEncounter.cs",
        [
            "public const int CorpseSlugSlotCount = 6;",
            "private static readonly int[] OpeningSlotIndices = [0, 5];",
            "GetVacantCorpseSlugSlots(ICombatState combatState)",
            "public override RoomType RoomType => RoomType.Boss;",
            "[BossSlot, .. Enumerable.Range(0, CorpseSlugSlotCount)",
            "ModelDb.Monster<GravetideSlug>()",
            "ModelDb.Monster<GravetideCorpseSlug>()",
            "ModelDb.Monster<GravetideSlugCorpse>()",
        ],
        "one-boss/six-slot/two-attendant Gravetide encounter contract",
    )
    require_snippets(
        "Monsters/GravetideCorpseSlug.cs",
        [
            "public override int MinInitialHp => 7;",
            "public override int MaxInitialHp => 12;",
            "PowerCmd.Apply<GravetideMinionPower>",
            "PowerCmd.Apply<RavenousPower>",
            "CreatureCmd.Add<GravetideSlugCorpse>",
            "CombatState, Creature.SlotName",
        ],
        "7-12-HP, same-slot corpse replacement contract",
    )
    require_snippets(
        "Powers/GravetideRavenousPowerPatch.cs",
        [
            "[HarmonyPatch(typeof(RavenousPower), nameof(RavenousPower.AfterDeath))]",
            "__instance.Owner.Monster is not GravetideCorpseSlug",
            "GravetideSlugBase.DevourStartTrigger",
            "PowerCmd.Apply<StrengthPower>",
        ],
        "native Ravenous compatibility contract",
    )
    require_snippets(
        "Monsters/GravetideSlugCorpse.cs",
        [
            "public override int MinInitialHp => 6;",
            "public override int MaxInitialHp => 6;",
            "PowerCmd.Apply<GravetideMinionPower>",
            "[SavedProperty]",
            "public bool DelayDigestionUntilNextEnemyTurn",
            'new AnimState("die")',
        ],
        "native-scaled 6-base-HP final-death-pose corpse contract",
    )
    require_snippets(
        "Monsters/GravetideSlug.cs",
        [
            "decimal.Ceiling(Creature.MaxHp * 0.05m)",
            "PowerCmd.Apply<GravetideDigestionPower>",
            "ModelDb.Monster<GravetideCorpseSlug>().AssetPaths",
            "GoopAndCreateCorpseMove",
            "DelayDigestionUntilNextEnemyTurn = true;",
            "CreatureCmd.Add(corpse, CombatState, slotName: slot)",
            "CreatureCmd.Add<GravetideCorpseSlug>",
            "new MoveState(\n            \"GROW_MOVE\"",
            "new DefendIntent(), new BuffIntent()",
            "summon.FollowUpState = growth;",
            "growth.FollowUpState = whipSlap;",
            "PowerCmd.Apply<StrengthPower>",
            "CreatureCmd.GainBlock(Creature, 10m, ValueProp.Move, null)",
        ],
        "Gravetide digestion, corpse, summon, and Growth contract",
    )
    require_snippets(
        "Powers/GravetideDigestionPower.cs",
        [
            "public override PowerStackType StackType => PowerStackType.None;",
            "side != CombatSide.Enemy || Owner.IsDead",
            "creature.IsAlive && creature.Monster is GravetideSlugCorpse",
            "DelayDigestionUntilNextEnemyTurn",
            "foreach (Creature deferredCorpse in allCorpses)",
            "CorpseGatherDuration = 0.45f",
            "CorpseGatherOffset = new(-70f, 10f)",
            "GatherCorpseVisuals(corpses);",
            "await Cmd.CustomScaledWait(CorpseGatherDuration, CorpseGatherDuration);",
            '"global_position"',
            "bossNode.GlobalPosition + CorpseGatherOffset",
            "RemoveCreatureWithoutDeathOrEscape(corpse)",
            "DevourDownDuration = 0.5f",
            "DevourUpDuration = 0.5f",
            "await CreatureCmd.Heal(Owner, Amount);",
            "PowerCmd.Apply<StrengthPower>",
            "choiceContext, Owner, 1m, Owner, null",
        ],
        "stackless single-trigger clear-all/heal/Strength Digestion contract",
    )
    digestion_source = source_text("Powers/GravetideDigestionPower.cs")
    gather_call_index = digestion_source.index("GatherCorpseVisuals(corpses);")
    gather_wait_index = digestion_source.index(
        "await Cmd.CustomScaledWait(CorpseGatherDuration, CorpseGatherDuration);"
    )
    devour_start_index = digestion_source.index("GravetideSlugBase.DevourStartTrigger")
    if not gather_call_index < gather_wait_index < devour_start_index:
        fail(
            errors,
            "Digestion must gather corpse visuals before waiting, then start the devour animation",
        )
    if "corpse.SlotName =" in digestion_source:
        fail(errors, "Digestion corpse gather must not mutate encounter slot state")
    require_snippets(
        "Powers/GravetideMinionPower.cs",
        [
            "protected override bool IsVisibleInternal => false;",
            "public override bool OwnerIsSecondaryEnemy => true;",
            "public override bool ShouldOwnerDeathTriggerFatal() => false;",
        ],
        "non-blocking attendant/corpse combat-end contract",
    )
    require_snippets(
        "Compatibility/Sts2VersionCompatibility.cs",
        [
            "RemoveCreatureWithoutDeathOrEscape(Creature creature)",
            "creature.RemoveAllPowersInternalExcept();",
            "CombatManager.Instance.RemoveCreature(creature);",
            "combatState.RemoveCreature(creature);",
        ],
        "dual-version corpse consumption without death or escape hooks",
    )

    require_snippets(
        "Monsters/QuirkyHopper.cs",
        [
            "await quirk.ResolveEscape();",
            "await CreatureCmd.Escape(Creature);",
        ],
        "Quirky Hopper escape-loss contract",
    )
    require_snippets(
        "Powers/ThingsQuirkPower.cs",
        [
            "public void RecordTheft()",
            "history?.MarkLootStolen();",
            "public async Task ResolveEscape()",
            "history.MarkLootReturned();",
        ],
        "Quirky Hopper killed/escaped reward-header split",
    )

    # Dynamic summons must preload every possible model through the summoner AssetPaths.
    dynamic_preload_contracts = {
        "Monsters/GravetideSlug.cs": [
            "ModelDb.Monster<GravetideCorpseSlug>().AssetPaths",
            "ModelDb.Monster<GravetideSlugCorpse>().AssetPaths",
        ],
        "Monsters/OriginFogmog.cs": ["ModelDb.Monster<OriginEyeWithTeeth>().AssetPaths"],
        "Monsters/SoulRoes.cs": ["ModelDb.Monster<SoulRoe>().AssetPaths"],
        "Monsters/BowlbugProgenitor.cs": [
            f"ModelDb.Monster<{name}>().AssetPaths"
            for name in ("BowlbugEgg", "BowlbugNectar", "BowlbugRock", "BowlbugSilk")
        ],
    }
    for relative, snippets in dynamic_preload_contracts.items():
        text = source_text(relative)
        for snippet in snippets:
            if snippet not in text:
                fail(errors, f"{relative} does not preload dynamic summon asset: {snippet}")

    # Power hover tips request the unpacked big icon through PreloadManager.Cache.
    # Mod textures are not part of the vanilla common set, so each owning monster
    # must contribute every visible custom power icon to the combat-room asset set.
    power_icon_preload_contracts = {
        "Monsters/GravetideSlug.cs": [
            "GravetideDigestionPower", "RavenousPower", "StrengthPower"
        ],
        "Monsters/OriginFogmog.cs": [
            "ThingsOriginPower", "OriginGainEnergyPower", "IllusionPower", "MinionPower", "StrengthPower"
        ],
        "Monsters/SoulRoes.cs": ["SoulRoesPower", "IntangiblePower", "StrengthPower"],
        "Monsters/ThingsScaleBeetle.cs": ["ThingsScaleBeetlePower", "ThingsScaleUpPower", "ThingsScaleDownPower"],
        "Monsters/QuirkyHopper.cs": [
            "ThingsQuirkPower", "QuirkyFlutterPower", "EscapeArtistPower"
        ],
        "Monsters/ThingsTheLegacy.cs": [
            "LegacyBeatOfDeathPower", "ThingsDazedPower", "HardenedShellPower",
            "ArtifactPower", "StrengthPower"
        ],
        "Monsters/BowlbugProgenitor.cs": [
            "BowlbugProgenitorPower", "ProtectTheMasterPower", "MinionPower",
            "WeakPower", "StrengthPower"
        ],
    }
    for relative, power_types in power_icon_preload_contracts.items():
        text = source_text(relative)
        for power_type in power_types:
            snippet = f"ModelDb.Power<{power_type}>().ResolvedBigIconPath"
            if snippet not in text:
                fail(errors, f"{relative} does not preload visible custom power icon: {power_type}")

    require_snippets(
        "Monsters/QuirkyHopper.cs",
        [
            'SceneHelper.GetScenePath("creature_visuals/quirky_hopper")',
            "AscensionLevel.ToughEnemies, 72, 68",
            "AscensionLevel.DeadlyEnemies, 22, 20",
            "AscensionLevel.DeadlyEnemies, 27, 25",
            "AscensionLevel.DeadlyEnemies, 20, 18",
            "new CardDebuffIntent()",
            "card.Type == CardType.Curse",
            'entry.StartsWith("STRIKE_", StringComparison.Ordinal)',
            'entry.StartsWith("DEFEND_", StringComparison.Ordinal)',
            "card.Rarity == CardRarity.Common",
            "card.Rarity == CardRarity.Uncommon",
            "card.Rarity == CardRarity.Rare",
            "RunRng.CombatCardGeneration.NextItem",
            "RunRng.CombatPotionGeneration.NextItem",
            "player.DiscardPotionInternal(potion);",
            "loot.Card?.DeckVersion,",
            "loot.Potion);",
            "potionState.RecordTheft();",
            "cardState.RecordTheft();",
            "Creature.GetPowerInstances<ThingsQuirkPower>().ToList()",
            "await quirk.ResolveEscape();",
            "await CreatureCmd.Escape(Creature);",
        ],
        "Quirky Hopper priority theft/kill-return contract",
    )
    quirky_hopper_text = source_text("Monsters/QuirkyHopper.cs")
    if not re.search(
        r"PowerCmd\.Apply<QuirkyFlutterPower>\(\s*"
        r"new ThrowingPlayerChoiceContext\(\),\s*Creature,\s*3m,",
        quirky_hopper_text,
    ):
        fail(errors, "Quirky Hopper Flutter must apply exactly three base stacks")
    theft_priority_markers = (
        "card => card.Type == CardType.Curse",
        "IsStarterStrikeOrDefend,",
        "card => card.Rarity == CardRarity.Common",
        "card => card.Rarity == CardRarity.Uncommon",
        "card => card.Rarity == CardRarity.Rare",
    )
    theft_priority_positions = [quirky_hopper_text.index(marker) for marker in theft_priority_markers]
    if theft_priority_positions != sorted(theft_priority_positions):
        fail(
            errors,
            "Quirky Hopper theft tiers must be Curse, starter Strike/Defend, Common, Uncommon, Rare",
        )
    for forbidden in ("MarkLootStolen", "MarkLootReturned", "QuirkTint", ".Modulate"):
        if forbidden in quirky_hopper_text:
            fail(errors, f"Quirky Hopper still contains obsolete loot/tint behavior: {forbidden}")
    if quirky_hopper_text.index("await quirk.ResolveEscape();") > quirky_hopper_text.index(
        "await CreatureCmd.Escape(Creature);"
    ):
        fail(errors, "Quirky Hopper commits stolen loot after it has already escaped")
    if quirky_hopper_text.index("ConfigurePotionState(") > quirky_hopper_text.index(
        "ConfigureCardState("
    ):
        fail(errors, "Quirky Hopper applies visible loot state before hidden potion state")

    require_snippets(
        "Powers/ThingsQuirkPower.cs",
        [
            "private const int PotionStateOffset = 500_000_000;",
            "protected override bool IsVisibleInternal => !IsPotionState;",
            "PotionModel? potion = _stolenPotion",
            "public int ConfigureCardState(Player player, CardModel? deckCard, PotionModel? potion)",
            "if (!IsMutable || _resolved)",
            "? RestoreStolenPotion()",
            ": ResolveStolenDeckCard()?.Pile?.Type == PileType.Deck;",
            "await CardPileCmd.RemoveFromDeck(stolenCard, showPreview: false);",
            "player.AddPotionInternal(potion, state.PotionSlotIndex)",
            "room.AddExtraReward(player, new PotionReward(potion, player));",
            "if (!IsPotionState || _stolenPotion != null)",
            "return _stolenPotion;",
        ],
        "Quirk Power synchronized card/potion resolution contract",
    )
    quirk_power_text = source_text("Powers/ThingsQuirkPower.cs")
    for forbidden in (
        "PileType.Hand",
        "CombatState.CloneCard",
        "TryModifyRewardsLate",
        "PotionFactory",
        "MarkLootReturned(history.StolenLoot)",
        "ReturnStolenItem",
        "MarkEscapeOutcome",
    ):
        if forbidden in quirk_power_text:
            fail(errors, f"Quirk Power still contains obsolete return/reward behavior: {forbidden}")

    require_snippets(
        "Modifiers/QuirkyHopperRewardPolicy.cs",
        [
            "class QuirkyHopperRewardPolicy : ModifierModel",
            "public override bool TryModifyRewardsLate(",
            "combatRoom.ExtraRewards.TryGetValue(",
            "List<PotionReward> returnedPotionRewards",
            "if (returnedPotionRewards.Count == 0)",
            "ReferenceEquals(returned, reward)",
            "rewards.Remove(reward)",
        ],
        "Quirky Hopper exact-potion reward policy",
    )
    require_snippets(
        "STS2_ThingsInit.cs",
        [
            "ModHelper.SubscribeForRunStateHooks(",
            '"Adnermo.STS2_Things.QuirkyHopperRewardPolicy"',
            "static _ => [ModelDb.Modifier<QuirkyHopperRewardPolicy>()]",
        ],
        "Quirky Hopper exact-return reward policy subscription",
    )
    init_text = source_text("STS2_ThingsInit.cs")
    if "ModelDb.Power<ThingsQuirkPower>()" in init_text:
        fail(errors, "canonical ThingsQuirkPower is still registered as a global run hook")
    quirk_localization_contracts = {
        "eng": ("deck", "potion belt", "hand", "killed", "escapes"),
        "zhs": ("\u724c\u5e93", "\u836f\u6c34\u680f", "\u624b\u724c", "\u51fb\u6740", "\u9003\u8dd1"),
    }
    for lang, (
        card_destination,
        potion_destination,
        forbidden_destination,
        killed_outcome,
        escaped_outcome,
    ) in quirk_localization_contracts.items():
        table = json.loads((localization / lang / "powers.json").read_text(encoding="utf-8"))
        for key in ("THINGS_QUIRK_POWER.description", "THINGS_QUIRK_POWER.smartDescription"):
            value = table.get(key, "")
            if card_destination not in value or potion_destination not in value:
                fail(errors, f"{lang}/{key} does not describe both stolen-item destinations")
            if killed_outcome not in value or escaped_outcome not in value:
                fail(errors, f"{lang}/{key} does not distinguish kill-return from escape-loss")
            if forbidden_destination in value:
                fail(errors, f"{lang}/{key} still returns the stolen card to the hand")
    card_state_max = ((3 * 8193 + 8192) * 8193) + 8192 + 1
    potion_state_max = 500_000_000 + ((3 * 33 + 32) * 8193) + 8192 + 1
    if card_state_max >= 500_000_000:
        fail(errors, "Quirk card-state encoding overlaps the hidden potion-state range")
    if potion_state_max > 999_999_999:
        fail(errors, "Quirk potion-state encoding exceeds PowerModel.Amount's clamp")

    require_snippets(
        "Powers/QuirkyFlutterPower.cs",
        [
            "#if STS2_V107_1",
            "public override decimal ModifyDamageMultiplicative(",
            "await PowerCmd.Decrement(this);",
            "await CreatureCmd.Stun(Owner, StunnedMove, nextState);",
            "hopper.IsHovering = false;",
        ],
        "dual-version native Flutter behavior contract",
    )

    # Stateful monster-chain regressions. These assertions intentionally pin the
    # V110 lifecycle details that previously produced lost summons or skipped phases.
    require_snippets(
        "Powers/SoulRoesPower.cs",
        [
            "i < SoulRoesEncounter.SoulRoeSlotCount && spawned < spawnCount",
            "c.IsAlive && c.SlotName == slotName",
            "soulRoe.StartMovePhase = spawned % 3",
            "spawned++;",
            "TaskHelper.RunSafely(RevealAfterDeathAnimation",
        ],
        "eight-slot/alive-only Soul Roes death-wave contract",
    )
    require_snippets(
        "Powers/ThingsOriginPower.cs",
        [
            "target != Owner || Owner.CurrentHp > Amount",
            "result.UnblockedDamage <= 0",
            "origin.NextMove.StateId == OriginFogmog.IllusionMoveId",
            "origin.PerformInterruptedOpeningIllusionMove",
            "CreatureCmd.Stun(Owner, phaseSummon, OriginFogmog.SwipeMoveId)",
            "origin.NextMove.StateId != MonsterModel.stunnedMoveId",
            "origin.NextMove.FollowUpStateId != OriginFogmog.SwipeMoveId",
        ],
        "current-HP/interrupted-opening Origin phase threshold contract",
    )
    origin_transition = source_text("Monsters/OriginEyeWithTeeth.cs")
    if not re.search(
        r"__instance is OriginFogmog\s*"
        r"&& state\.StateId == MonsterModel\.stunnedMoveId\s*"
        r"&& state\.FollowUpStateId == OriginFogmog\.SwipeMoveId\)\s*"
        r"forceTransition = true;",
        origin_transition,
    ):
        fail(errors, "Origin Fogmog forced phase-two stun transition contract is missing")
    require_snippets(
        "Monsters/OriginFogmog.cs",
        [
            'private const string _trackName = "the_kin_progress";',
            "return SummonIllusions(2);",
            "combatState.Enemies.All(c => c.SlotName != s)",
        ],
        "The Kin music, interrupted-opening double summon and revive-reserved slot contract",
    )
    require_snippets(
        "Monsters/SoulRoes.cs",
        ["CombatState.Enemies.Any(c => c.IsAlive && c.SlotName == slotName)"],
        "alive-only Soul Roe summon-slot contract",
    )
    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        ["enemy => !enemy.IsAlive || enemy.SlotName != candidate"],
        "alive-only Bowlbug summon-slot contract",
    )

    # V110 MultiplayerScalingModel scales enemy ValueProp.Move block. Supplying an
    # already player-count-scaled amount would multiply it a second time, while
    # ValueProp.Unpowered would skip the native 3/4-player act scaling entirely.
    for relative in (
        "Monsters/OriginFogmog.cs",
        "Monsters/BowlbugProgenitor.cs",
        "Monsters/ThingsScaleBeetle.cs",
    ):
        text = source_text(relative)
        if re.search(
            r"GainBlock\([^;\n]*(?:Players\.Count|PlayerCount)[^;\n]*ValueProp\.Move",
            text,
        ):
            fail(errors, f"{relative} pre-scales native enemy move block by player count")
    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        [
            "GainBlock(Creature, 20, ValueProp.Move",
            "GainBlock(Creature, 16, ValueProp.Move",
        ],
        "native multiplayer enemy-block scaling contract",
    )
    require_snippets(
        "Monsters/ThingsScaleBeetle.cs",
        ["GainBlock(Creature, MoltBlock, ValueProp.Move"],
        "native multiplayer Scale Beetle move-block scaling contract",
    )
    require_snippets(
        "Monsters/ThingsTheLegacy.cs",
        ["var target = Creature.MaxHp / divisor;"],
        "integer Hardened Shell divisor contract",
    )

    # Sprite2D creature scenes do not create a CreatureAnimator, so vanilla never
    # reaches SfxCmd.PlayDeath. Keep the narrow mod-only fallback and verified V110
    # event reuse explicit; invented event names fail silently at runtime.
    require_snippets(
        "Audio/SfxHooks.cs",
        [
            "monster.GetType().Assembly == typeof(SfxHooks).Assembly",
            "!monster.HasDeathSfx || __instance.HasSpineAnimation",
            "SfxCmd.PlayDeath(monster);",
            "private const float OriginFogmogHurtChance = 0.35f;",
            "NativeSfxPlayer.RollChance(OriginFogmogHurtChance)",
        ],
        "no-Spine death lifecycle and probabilistic Origin Fogmog hurt-SFX contract",
    )
    require_snippets(
        "Audio/NativeSfxPlayer.cs",
        [
            "public static bool RollChance(float chance)",
            "if (!float.IsFinite(chance) || chance <= 0f) return false;",
            "if (chance >= 1f) return true;",
            "_variantRng.Randf() < chance",
        ],
        "presentation-only audio probability contract",
    )
    require_snippets(
        "Audio/CustomMusicHooks.cs",
        [
            "StartAfterCombatSetup = true;",
            "nameof(NRunMusicController.UpdateTrack)",
            "!CombatManager.Instance.IsInProgress",
            'NativeSfxPlayer.PlayMusic(CustomMusicPlayPatch.GravetideTheme, "Master", -2f);',
        ],
        "Gravetide post-combat-setup music routing contract",
    )
    if not re.search(
        r'if \(entry == "origin_fogmog" && '
        r'!NativeSfxPlayer\.RollChance\(OriginFogmogHurtChance\)\)\s*'
        r'return true;',
        source_text("Audio/SfxHooks.cs"),
    ):
        fail(errors, "Origin Fogmog hurt-SFX miss must fall back to its native material impact")

    verified_death_sfx = {
        "Monsters/OriginFogmog.cs": "origin_fogmog/origin_fogmog_die",
        "Monsters/SoulRoe.cs": "soul_fysh/soul_fysh_die",
        "Monsters/SoulRoes.cs": "soul_fysh/soul_fysh_die",
        "Monsters/ThingsTheLegacy.cs": "vantom/vantom_die",
        "Monsters/ThingsScaleBeetle.cs": "shrinker_beetle/shrinker_beetle_die",
        "Monsters/BowlbugProgenitor.cs": "egg_layer/egg_layer_die",
    }
    for relative, event_suffix in verified_death_sfx.items():
        text = source_text(relative)
        if not re.search(
            r"public override string DeathSfx\s*=>\s*"
            + re.escape(f'"event:/sfx/enemy/enemy_attacks/{event_suffix}"'),
            text,
        ):
            fail(errors, f"{relative} lacks its verified explicit V110 DeathSfx event")
    for invalid_event in ("kaiser_crab/kaiser_crab_die", "soul_fysh/soul_fysh_summon"):
        for path in sorted((SOURCE / "Monsters").glob("*.cs")):
            if invalid_event in path.read_text(encoding="utf-8"):
                fail(errors, f"{path.relative_to(ROOT)} references nonexistent V110 event {invalid_event}")

    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        [
            "egg_layer/egg_layer_attack",
            "egg_layer/egg_layer_lay",
            "egg_layer/egg_layer_die",
        ],
        "Bowlbug Progenitor insect egg-layer sound palette",
    )
    require_snippets(
        "Monsters/ThingsScaleBeetle.cs",
        [
            "shrinker_beetle/shrinker_beetle_attack",
            "shrinker_beetle/shrinker_beetle_cast",
            "shrinker_beetle/shrinker_beetle_die",
        ],
        "Scale Beetle vanilla beetle sound palette",
    )
    if "soul_fysh/" in source_text("Monsters/BowlbugProgenitor.cs"):
        fail(errors, "Bowlbug Progenitor still reuses the spectral Soul Fysh sound palette")
    if "kaiser_crab/" in source_text("Monsters/ThingsScaleBeetle.cs"):
        fail(errors, "Scale Beetle still reuses the oversized Kaiser Crab sound palette")

    verified_damage_sfx = {
        "Monsters/OriginFogmog.cs": "Plant",
        "Monsters/OriginEyeWithTeeth.cs": "Magic",
        "Monsters/SoulRoe.cs": "Magic",
        "Monsters/SoulRoes.cs": "Magic",
        "Monsters/ThingsTheLegacy.cs": "Magic",
        "Monsters/ThingsScaleBeetle.cs": "Insect",
        "Monsters/BowlbugProgenitor.cs": "Insect",
    }
    for relative, damage_type in verified_damage_sfx.items():
        if not re.search(
            r"public override DamageSfxType TakeDamageSfxType\s*=>\s*"
            + re.escape(f"DamageSfxType.{damage_type}"),
            source_text(relative),
        ):
            fail(errors, f"{relative} lacks its style-matched {damage_type} impact sound")

    eng_files = {path.name: path for path in (localization / "eng").glob("*.json")}
    zhs_files = {path.name: path for path in (localization / "zhs").glob("*.json")}
    if eng_files.keys() != zhs_files.keys():
        fail(errors, "eng/zhs localization table sets differ")
    for name in sorted(eng_files.keys() & zhs_files.keys()):
        eng = json.loads(eng_files[name].read_text(encoding="utf-8"))
        zhs = json.loads(zhs_files[name].read_text(encoding="utf-8"))
        if eng.keys() != zhs.keys():
            fail(errors, f"eng/zhs keys differ in {name}")
        for lang, table in (("eng", eng), ("zhs", zhs)):
            placeholders = sorted(
                key
                for key, value in table.items()
                if isinstance(value, str)
                and (re.fullmatch(r"\?+", value.strip()) or "TODO" in value.upper())
            )
            if placeholders:
                fail(errors, f"{lang}/{name} has placeholder values: {placeholders}")

    required_assets = [
        ROOT / "images/events/cutting_it_close.png",
        ROOT / "images/enchantments/things_split.png",
        ROOT / "images/map/scale_beetle_boss_icon.png",
        ROOT / "images/map/scale_beetle_boss_icon_outline.png",
        ROOT / "images/atlases/relic_atlas.sprites/things_almond_water.tres",
        ROOT / "images/atlases/power_atlas.sprites/things_quirk_power.tres",
        ROOT / "images/atlases/power_atlas.sprites/quirky_flutter_power.tres",
        ROOT / "images/powers/things_quirk_power.png",
        ROOT / "images/powers/things_quirk_power_packed.png",
        ROOT / "images/powers/quirky_flutter_power.png",
        ROOT / "images/powers/quirky_flutter_power_packed.png",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.atlas",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.png",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_bow.png",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.skel",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.spatlas",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.spskel",
        ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_skel_data.tres",
        ROOT / "scenes/creature_visuals/quirky_hopper.tscn",
        ROOT / "scripts/build_quirky_hopper_texture.py",
        ROOT / "source_assets/monsters/quirky_hopper_bow/bow_transparent_full.png",
        ROOT / "source_assets/monsters/quirky_hopper_bow/thievinghopper_source.png",
        ROOT / "STS2_Things/Visuals/NQuirkyHopperVisuals.cs",
        ROOT / "STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs",
        ROOT / "STS2_Things/Visuals/NThingsCombatBackground.cs",
    ]
    for path in required_assets:
        if not path.is_file():
            fail(errors, f"required asset missing: {path.relative_to(ROOT)}")

    cutting_event_art = ROOT / "images" / "events" / "cutting_it_close.png"
    if cutting_event_art.is_file():
        with Image.open(cutting_event_art) as image:
            image.load()
            if image.mode != "RGBA" or image.size != (3440, 1616):
                fail(
                    errors,
                    f"{cutting_event_art.relative_to(ROOT)} must be RGBA (3440, 1616), "
                    f"got {image.mode} {image.size}",
                )
            elif image.getchannel("A").getextrema() != (255, 255):
                fail(errors, "Cutting It Close event art must be fully opaque RGBA")

    split_icon = ROOT / "images" / "enchantments" / "things_split.png"
    if split_icon.is_file():
        with Image.open(split_icon) as image:
            image.load()
            if image.mode != "RGBA" or image.size != (64, 64):
                fail(
                    errors,
                    f"{split_icon.relative_to(ROOT)} must be RGBA (64, 64), "
                    f"got {image.mode} {image.size}",
                )
            elif image.getchannel("A").getextrema() == (255, 255):
                fail(errors, "Things Split enchantment icon must retain transparent padding")
            elif image.getchannel("A").getbbox() is None:
                fail(errors, "Things Split enchantment icon is fully transparent")

    power_icon_sizes = {
        "things_quirk_power.png": (256, 256),
        "things_quirk_power_packed.png": (64, 64),
        "quirky_flutter_power.png": (256, 256),
        "quirky_flutter_power_packed.png": (64, 64),
    }
    for name, expected_size in power_icon_sizes.items():
        path = ROOT / "images" / "powers" / name
        if not path.is_file():
            continue
        with Image.open(path) as image:
            if image.mode != "RGBA" or image.size != expected_size:
                fail(
                    errors,
                    f"{path.relative_to(ROOT)} must be RGBA {expected_size}, "
                    f"got {image.mode} {image.size}",
                )
            if image.getbbox() is None:
                fail(errors, f"{path.relative_to(ROOT)} is fully transparent")

    quirky_texture = ROOT / "STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.png"
    if quirky_texture.is_file():
        with Image.open(quirky_texture) as image:
            rgba = image.convert("RGBA")
            if rgba.size != (1269, 269):
                fail(errors, f"Quirky Hopper atlas must be 1269x269, got {rgba.size}")

            color_regions = {
                "blue bod 1": ((931, 54, 1055, 112), "blue"),
                "orange bod 2": ((1205, 47, 1244, 79), "orange"),
                "blue bod 3": ((1216, 81, 1261, 119), "blue"),
                "orange bod 4": ((1211, 184, 1259, 223), "orange"),
            }
            for label, (box, expected_family) in color_regions.items():
                opaque = [
                    pixel
                    for pixel in rgba.crop(box).get_flattened_data()
                    if pixel[3] >= 128
                ]
                if not opaque:
                    fail(errors, f"Quirky Hopper {label} region is empty")
                    continue
                mean_red = sum(pixel[0] for pixel in opaque) / len(opaque)
                mean_green = sum(pixel[1] for pixel in opaque) / len(opaque)
                mean_blue = sum(pixel[2] for pixel in opaque) / len(opaque)
                if expected_family == "blue" and not (
                    mean_blue > mean_red * 1.45 and mean_blue > mean_green * 1.15
                ):
                    fail(errors, f"Quirky Hopper {label} is not distinctly blue")
                if expected_family == "orange" and not (
                    mean_red > mean_blue * 1.65 and mean_red > mean_green * 1.15
                ):
                    fail(errors, f"Quirky Hopper {label} is not distinctly orange")

            native_texture_path = (
                ROOT
                / "source_assets/monsters/quirky_hopper_bow/thievinghopper_source.png"
            )
            if native_texture_path.is_file():
                native_digest = hashlib.sha256(native_texture_path.read_bytes()).hexdigest()
                if native_digest != (
                    "af9800cc5b70ea7f6efa8f0fa346169ce03d62d4a1ff0c7748128e3df9b07636"
                ):
                    fail(errors, "Quirky Hopper native texture source hash changed")
                with Image.open(native_texture_path) as native_texture_source:
                    native_head = native_texture_source.convert("RGBA").crop(
                        (1071, 2, 1132, 84)
                    )
                if rgba.crop((1071, 2, 1132, 84)).tobytes() != native_head.tobytes():
                    fail(errors, "Quirky Hopper atlas still paints the bow over its face")

    quirky_bow = (
        ROOT
        / "STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_bow.png"
    )
    if quirky_bow.is_file():
        with Image.open(quirky_bow) as image:
            bow = image.convert("RGBA")
            if bow.size != (141, 91):
                fail(errors, f"Quirky Hopper rear bow must be 141x91, got {bow.size}")
            pink_pixels = sum(
                1
                for red, green, blue, alpha in bow.get_flattened_data()
                if alpha >= 128
                and red >= 160
                and red > green * 1.6
                and blue > green * 1.1
            )
            if pink_pixels < 5_000:
                fail(errors, "Quirky Hopper rear bow lacks a visible pink silhouette")

    quirky_scene_text = (ROOT / "scenes/creature_visuals/quirky_hopper.tscn").read_text(
        encoding="utf-8"
    )
    for snippet in (
        'path="res://STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_bow.png"',
        '[node name="BowBoneNode" type="SpineBoneNode" parent="Visuals"]',
        'bone_name = "head"',
        'show_behind_parent = true',
        '[node name="Bow" type="Sprite2D" parent="Visuals/BowBoneNode"]',
        'position = Vector2(-45, 90)',
    ):
        if snippet not in quirky_scene_text:
            fail(errors, f"Quirky Hopper rear-bow scene contract missing {snippet!r}")

    quirky_asset_root = ROOT / "STS2_Things/animations/monsters/quirky_hopper"
    quirky_atlas = quirky_asset_root / "quirkyhopper.atlas"
    quirky_spatlas = quirky_asset_root / "quirkyhopper.spatlas"
    if quirky_atlas.is_file() and quirky_spatlas.is_file():
        imported_atlas = json.loads(quirky_spatlas.read_text(encoding="utf-8"))
        if imported_atlas.get("atlas_data") != quirky_atlas.read_text(encoding="utf-8"):
            fail(errors, "Quirky Hopper .spatlas payload differs from its source atlas")
        if imported_atlas.get("source_path") != (
            "res://STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.atlas"
        ):
            fail(errors, "Quirky Hopper .spatlas source_path is incorrect")
    quirky_skel = quirky_asset_root / "quirkyhopper.skel"
    quirky_spskel = quirky_asset_root / "quirkyhopper.spskel"
    if quirky_skel.is_file() and quirky_spskel.is_file():
        if quirky_skel.read_bytes() != quirky_spskel.read_bytes():
            fail(errors, "Quirky Hopper imported skeleton differs from its source skeleton")
    native_flutter_sha256 = "06335e7ae5f46500c6d6f5e4fa9ba8136b7d0cb0e263af22dee8f8a0a54265eb"
    flutter_alias = ROOT / "images" / "powers" / "quirky_flutter_power.png"
    if flutter_alias.is_file() and hashlib.sha256(flutter_alias.read_bytes()).hexdigest() != native_flutter_sha256:
        fail(errors, "Quirky Flutter big icon is not the byte-exact native Flutter icon")

    for icon_name in ("origin_fogmog", "scale_beetle", "the_legacy", "bowlbug_progenitor"):
        icon = ROOT / "images" / "map" / f"{icon_name}_boss_icon.png"
        outline = ROOT / "images" / "map" / f"{icon_name}_boss_icon_outline.png"
        if icon.is_file() and outline.is_file():
            if hashlib.sha256(icon.read_bytes()).digest() == hashlib.sha256(outline.read_bytes()).digest():
                fail(errors, f"{outline.relative_to(ROOT)} duplicates the icon and cannot render an outline")

    stale_paths = [
        ROOT / "images/map/scale_bettle_boss_icon.png",
        ROOT / "images/map/scale_bettle_boss_icon_outline.png",
        ROOT / "images/atlases/relic_atlas.sprites/almod_water.tres",
        SOURCE / ".godot",
        SOURCE / "Monsters/MonsterRegistrar.cs",
    ]
    for path in stale_paths:
        if path.exists():
            fail(errors, f"stale path must not exist: {path.relative_to(ROOT)}")

    if errors:
        print("STS2_Things source audit failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("STS2_Things source audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
