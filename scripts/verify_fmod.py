#!/usr/bin/env python3
"""Validate FMOD literals and custom encounter music against the target shipped banks."""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import sys
from pathlib import Path


FMOD_HEADER_VERSION = 0x00020306


class FmodError(RuntimeError):
    pass


class FmodCatalog:
    def __init__(self, game_dir: Path, bank_dir: Path) -> None:
        self._dll_dir = os.add_dll_directory(str(game_dir))
        self._dll = ctypes.WinDLL(str(game_dir / "fmodstudio.dll"))
        self._system = ctypes.c_void_p()
        self.events_by_bank: dict[str, set[str]] = {}

        void_p = ctypes.c_void_p
        int_t = ctypes.c_int
        uint_t = ctypes.c_uint

        self._create = self._bind(
            "FMOD_Studio_System_Create", [ctypes.POINTER(void_p), uint_t]
        )
        self._initialize = self._bind(
            "FMOD_Studio_System_Initialize",
            [void_p, int_t, uint_t, uint_t, void_p],
        )
        self._load_bank = self._bind(
            "FMOD_Studio_System_LoadBankFile",
            [void_p, ctypes.c_char_p, uint_t, ctypes.POINTER(void_p)],
        )
        self._get_event_count = self._bind(
            "FMOD_Studio_Bank_GetEventCount", [void_p, ctypes.POINTER(int_t)]
        )
        self._get_event_list = self._bind(
            "FMOD_Studio_Bank_GetEventList",
            [void_p, ctypes.POINTER(void_p), int_t, ctypes.POINTER(int_t)],
        )
        self._get_event_path = self._bind(
            "FMOD_Studio_EventDescription_GetPath",
            [void_p, ctypes.c_char_p, int_t, ctypes.POINTER(int_t)],
        )
        self._release = self._bind("FMOD_Studio_System_Release", [void_p])

        self._check(
            self._create(ctypes.byref(self._system), FMOD_HEADER_VERSION),
            "create Studio system",
        )
        self._check(
            self._initialize(self._system, 1024, 0, 0, None),
            "initialize Studio system",
        )

        # EventDescription.GetPath requires the master strings table to be loaded.
        self._load(bank_dir / "Master.bank")
        self._load(bank_dir / "Master.strings.bank")
        for path in sorted(bank_dir.glob("*.bank")):
            if path.name.startswith("Master"):
                continue
            bank = self._load(path)
            self.events_by_bank[f"res://banks/desktop/{path.name}"] = self._events(bank)

    def _bind(self, name: str, argtypes: list[object]):
        function = getattr(self._dll, name)
        function.argtypes = argtypes
        function.restype = ctypes.c_int
        return function

    @staticmethod
    def _check(result: int, operation: str) -> None:
        if result != 0:
            raise FmodError(f"FMOD result {result} while attempting to {operation}")

    def _load(self, path: Path) -> ctypes.c_void_p:
        bank = ctypes.c_void_p()
        self._check(
            self._load_bank(self._system, os.fsencode(path), 0, ctypes.byref(bank)),
            f"load {path}",
        )
        return bank

    def _events(self, bank: ctypes.c_void_p) -> set[str]:
        count = ctypes.c_int()
        self._check(self._get_event_count(bank, ctypes.byref(count)), "count events")
        if count.value == 0:
            return set()

        values = (ctypes.c_void_p * count.value)()
        retrieved = ctypes.c_int()
        self._check(
            self._get_event_list(
                bank, values, count.value, ctypes.byref(retrieved)
            ),
            "enumerate events",
        )

        result: set[str] = set()
        for event in values[: retrieved.value]:
            required = ctypes.c_int()
            self._get_event_path(event, None, 0, ctypes.byref(required))
            buffer = ctypes.create_string_buffer(max(required.value, 1024))
            self._check(
                self._get_event_path(
                    event, buffer, len(buffer), ctypes.byref(required)
                ),
                "read event path",
            )
            result.add(buffer.value.decode("utf-8"))
        return result

    def close(self) -> None:
        if self._system.value:
            self._release(self._system)
            self._system = ctypes.c_void_p()
        self._dll_dir.close()

    def __enter__(self) -> "FmodCatalog":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def quoted_values(text: str, prefix: str) -> list[str]:
    return re.findall(rf'"({re.escape(prefix)}[^"\r\n]+)"', text)


def act_bank_paths(source_root: Path, act_name: str) -> list[str]:
    path = source_root / "src" / "Core" / "Models" / "Acts" / f"{act_name}.cs"
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"MusicBankPaths\s*=>\s*new\s+string\[[^\]]*\]\s*\{(?P<body>[^}]*)\}",
        text,
        re.DOTALL,
    )
    if not match:
        raise ValueError(f"could not parse MusicBankPaths from {path}")
    return quoted_values(match.group("body"), "res://banks/")


def encounter_acts(source: Path) -> dict[str, set[str]]:
    text = (source / "Hooks" / "MonsterContentPatches.cs").read_text(encoding="utf-8")
    result: dict[str, set[str]] = {}
    method_pattern = re.compile(
        r"Add(?P<act>Overgrowth|Underdocks|Hive)(?:Encounters|Bosses)"
        r"\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s*\}",
        re.DOTALL,
    )
    for match in method_pattern.finditer(text):
        act = match.group("act")
        for encounter in re.findall(
            r"ModelDb\.Encounter<([A-Za-z0-9_]+)>\(\)", match.group("body")
        ):
            result.setdefault(encounter, set()).add(act)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = root / "STS2_Things"
    bank_dir = args.source_root / "banks" / "desktop"
    errors: list[str] = []

    required = [
        args.game_dir / "fmodstudio.dll",
        args.game_dir / "fmod.dll",
        bank_dir / "Master.bank",
        bank_dir / "Master.strings.bank",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"required FMOD file missing: {path}")
    if errors:
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    try:
        with FmodCatalog(args.game_dir, bank_dir) as catalog:
            all_events = set().union(*catalog.events_by_bank.values())

            custom_sfx_text = (source / "Audio" / "CustomSfxMonsters.cs").read_text(
                encoding="utf-8"
            )
            custom_sfx_entries = set(
                re.findall(r'^\s*"([a-z0-9_]+)"\s*,?\s*$', custom_sfx_text, re.MULTILINE)
            )

            used_events: dict[str, set[Path]] = {}
            for path in sorted(source.rglob("*.cs")):
                for event in quoted_values(path.read_text(encoding="utf-8"), "event:/"):
                    used_events.setdefault(event, set()).add(path.relative_to(root))

            for event, paths in sorted(used_events.items()):
                if event in all_events:
                    continue
                if any(entry in event for entry in custom_sfx_entries):
                    continue
                rendered = ", ".join(str(path) for path in sorted(paths))
                errors.append(f"unknown FMOD event {event} in {rendered}")

            acts_by_encounter = encounter_acts(source)
            bank_paths_by_act = {
                act: act_bank_paths(args.source_root, act)
                for act in ("Overgrowth", "Underdocks", "Hive")
            }
            for path in sorted((source / "Encounters").glob("*.cs")):
                text = path.read_text(encoding="utf-8")
                bgm = re.search(r'CustomBgm\s*=>\s*"([^"]+)"', text)
                class_name = re.search(r"public sealed class\s+(\w+)", text)
                if not bgm or not class_name:
                    continue
                encounter = class_name.group(1)
                track = bgm.group(1)
                acts = acts_by_encounter.get(encounter, set())
                if not acts:
                    errors.append(f"custom BGM encounter is not registered to an Act: {encounter}")
                    continue
                for act in sorted(acts):
                    for bank_path in bank_paths_by_act[act]:
                        events = catalog.events_by_bank.get(bank_path)
                        if events is None:
                            errors.append(f"{act} references an unknown bank: {bank_path}")
                        elif track not in events:
                            errors.append(
                                f"{encounter} uses {track}, which is absent from "
                                f"{act}'s possible bank {bank_path}"
                            )
    except (FmodError, OSError, ValueError) as error:
        errors.append(str(error))

    if errors:
        print("STS2_Things FMOD audit failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("STS2_Things FMOD audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
