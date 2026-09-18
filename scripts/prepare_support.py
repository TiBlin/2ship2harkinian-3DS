#!/usr/bin/env python3
"""Add the pinned official MM support resources to its official 5.0.1 archive.

This utility is original Blinky tooling. Resource bytes remain HarbourMasters
content with their original attribution; it does not turn them into original art.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = "69b615ba25c6788bd1e4e120608d28e56e99fa6c2d9553d61d722a4457ad109a"
COMMIT = "6bfd6a35a0e0d8900273e61ce85cb038d4f4a528"
ADDITIONS = ["objects/object_gi_key/gGi" + name + suffix
             for name in ("DungeonBossKeyDL", "DungeonSmallKeyDL", "GreatBayKeyEmblemDL",
                          "SnowheadKeyEmblemDL", "StoneTowerKeyEmblemDL", "WoodfallKeyEmblemDL")
             for suffix in ("", "_vtx_0")]
ADDITIONS += ["shaders/flatavg." + extension for extension in ("glsl", "hlsl", "metal")]


def digest(path):
    with Path(path).open("rb") as stream:
        result = hashlib.sha256()
        while block := stream.read(65536):
            result.update(block)
        return result.hexdigest()


def prepare(base, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    if base == output:
        raise ValueError("The output must be separate from the release input")
    if digest(base) != BASE_SHA256:
        raise ValueError("The input is not the pinned official Windows 5.0.1 support archive")
    additions = {name: (ROOT / "third_party/2ship/mm/assets/custom" / name).read_bytes() for name in ADDITIONS}
    with zipfile.ZipFile(base) as release:
        names = release.namelist()
        if release.testzip() or len(names) != len(set(names)):
            raise ValueError("The input has duplicate names or invalid CRCs")
        if release.read("portVersion") != bytes((1, 0, 5, 0, 0, 0, 1)):
            raise ValueError("The input metadata is not 5.0.1")
        if set(names).intersection(additions):
            raise ValueError("The input already contains an expected new resource")
        output.parent.mkdir(parents=True, exist_ok=True)
        handle, filename = tempfile.mkstemp(prefix=".support-", suffix=".zip", dir=output.parent)
        os.close(handle)
        temporary = Path(filename)
        try:
            with zipfile.ZipFile(temporary, "w") as result:
                for name in sorted([*names, *additions]):
                    entry = zipfile.ZipInfo(name, date_time=(2026, 9, 15, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    result.writestr(entry, additions[name] if name in additions else release.read(name))
            with zipfile.ZipFile(temporary) as result:
                if result.testzip() or set(result.namelist()) != set(names).union(additions):
                    raise ValueError("Output archive failed verification")
                for name, expected in additions.items():
                    if result.read(name) != expected:
                        raise ValueError("Output resource mismatch: " + name)
            report = {"base_release": "2Ship Battler Bravo Windows 5.0.1", "base_sha256": BASE_SHA256,
                      "source_commit": COMMIT, "output_sha256": digest(temporary), "files": len(names) + len(additions),
                      "added_raw_resources": ADDITIONS, "crc_verified": True, "rom_data_included": False}
            os.replace(temporary, output)
        finally:
            if temporary.exists():
                temporary.unlink()
    output.with_suffix(".provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.base, args.output), indent=2))


if __name__ == "__main__":
    main()