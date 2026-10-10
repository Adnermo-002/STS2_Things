"""Package only verified runtime files and record this small event update."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/merchant-pair-attack-split-20261010"
PAYLOAD = ("STS2_Things.json", "STS2_Things.dll", "STS2_Things.pck", "STS2_Things.BaseLibBridge.dll")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record(path):
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}


def main():
    package = BUILD / "package"
    version = json.loads((package / "STS2_Things.json").read_text(encoding="utf-8"))["version"]
    destination = ROOT / "dist" / ("v" + version)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ("STS2_Things-v" + version + ".zip")
    if archive.exists():
        raise FileExistsError("Keep existing package: " + str(archive))
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name in PAYLOAD:
            bundle.write(package / name, "STS2_Things/" + name)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert sorted(bundle.namelist()) == sorted("STS2_Things/" + name for name in PAYLOAD)
        for name in PAYLOAD:
            assert hashlib.sha256(bundle.read("STS2_Things/" + name)).hexdigest() == digest(package / name)
    sums = digest(archive) + "  " + archive.name + "\n"
    sums += "".join(digest(package / name) + "  STS2_Things/" + name + "\n" for name in PAYLOAD)
    (destination / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
    result = {"date": "2026-10-10", "version": version, "archive": record(archive),
              "runtime": [record(package / name) for name in PAYLOAD], "zip_crc_and_entry_hashes": "PASS",
              "native_pair_models": {target: json.loads((BUILD / "native" / target / "report.json").read_text())
                                     for target in ("v107.1", "v111")},
              "split_probe": {target: "PASS" if "Things Split behavior probe: PASS" in
                              (BUILD / ("split-" + target + ".log")).read_text(encoding="utf-8") else "FAIL"
                              for target in ("v107.1", "v111")},
              "publication": "Not published"}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (BUILD / "delivery.json").write_text(text, encoding="utf-8")
    (destination / "verification.json").write_text(text, encoding="utf-8")
    print("MERCHANT_PAIR_ATTACK_SPLIT_PACKAGE_PASS " + str(archive))
    print("sha256=" + digest(archive))


if __name__ == "__main__":
    main()
