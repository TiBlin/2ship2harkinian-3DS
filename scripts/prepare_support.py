#!/usr/bin/env python3
"""Update the official 5.0.1 support archive to the pinned 2Ship source revision.

Only homebrew support resources are handled here; no ROM is read.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA256 = '69b615ba25c6788bd1e4e120608d28e56e99fa6c2d9553d61d722a4457ad109a'
COMMIT = '6bfd6a35a0e0d8900273e61ce85cb038d4f4a528'
ADDITIONS = [
    f'objects/object_gi_key/gGi{name}{suffix}'
    for name in ('DungeonBossKeyDL', 'DungeonSmallKeyDL', 'GreatBayKeyEmblemDL',
                 'SnowheadKeyEmblemDL', 'StoneTowerKeyEmblemDL', 'WoodfallKeyEmblemDL')
    for suffix in ('', '_vtx_0')
] + [f'shaders/flatavg.{suffix}' for suffix in ('glsl', 'hlsl', 'metal')]


def prepare(base: Path, output: Path) -> dict:
    if base.resolve() == output.resolve():
        raise ValueError('Use a separate output archive to preserve the release input')
    digest = hashlib.sha256(base.read_bytes()).hexdigest()
    if digest != BASE_SHA256:
        raise ValueError(f'Expected the unmodified official Windows 5.0.1 support archive; got {digest}')
    custom = ROOT / 'third_party/2ship/mm/assets/custom'
    additions = {name: (custom / name).read_bytes() for name in ADDITIONS}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(base) as original:
        if original.testzip() is not None:
            raise ValueError('Corrupt release archive')
        if original.read('portVersion') != bytes.fromhex('01000500000001'):
            raise ValueError('Unexpected support archive version')
        if len(set(original.namelist())) != len(original.namelist()):
            raise ValueError('Duplicate release entries')
        if set(original.namelist()) & additions.keys():
            raise ValueError('An expected new resource already exists')
        # These new display lists/vertices and shaders are raw resources, just
        # like their peers in the official archive. Converted PNG resources
        # remain exactly as supplied by the release extractor.
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as result:
            for entry in sorted(original.namelist()):
                info = zipfile.ZipInfo(entry, date_time=(2026, 9, 15, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                result.writestr(info, original.read(entry))
            for entry, data in sorted(additions.items()):
                info = zipfile.ZipInfo(entry, date_time=(2026, 9, 15, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                result.writestr(info, data)
    with zipfile.ZipFile(output) as result:
        if result.testzip() is not None or len(result.namelist()) != 1017:
            raise ValueError('Output archive failed validation')
    report = {'base_release': '2Ship Battler Bravo Windows 5.0.1',
              'base_sha256': digest, 'source_commit': COMMIT,
              'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'added_raw_resources': ADDITIONS, 'files': 1017,
              'crc_verified': True, 'rom_data_included': False}
    output.with_suffix('.provenance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.base, args.output), indent=2))
