#!/usr/bin/env python3
"""Blinky package builder using the public 3dsxtool, bannertool and makerom CLIs.

The program owns staging and validation; the external tools retain their own
licenses and provenance. Binary offsets follow Project_CTR's public formats.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import wave
import zlib
from build_lus_3ds import SOURCE_ROOT, default_devkitpro

TITLE_ID = 0x0004000002534800
PRODUCT_CODE = b"CTR-P-2SH3"
NAME = "2ship-3ds"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    with Path(path).open("rb") as source:
        result = hashlib.sha256()
        while block := source.read(65536):
            result.update(block)
        return result.hexdigest()


def find_tool(name, devkitpro):
    executable = name + (".exe" if os.name == "nt" else "")
    platform = "windows" if os.name == "nt" else "linux"
    candidate = SOURCE_ROOT / "tools" / platform / executable
    if candidate.is_file():
        records = json.loads((SOURCE_ROOT / "tools/provenance.json").read_text(encoding="utf-8"))
        recorded = {entry["file"]: entry["sha256"] for entry in records}
        require(recorded.get(candidate.relative_to(SOURCE_ROOT).as_posix()) == sha256(candidate),
                f"Unverified bundled tool: {candidate}")
        return candidate
    candidate = Path(devkitpro) / "tools/bin" / executable
    if candidate.is_file():
        return candidate
    installed = shutil.which(executable)
    require(installed, f"Install {name} or supply the recorded tool in tools/{platform}")
    return Path(installed)


def run(arguments):
    print("Packaging: " + Path(arguments[0]).name, flush=True)
    subprocess.run([str(value) for value in arguments], check=True)


def write_art_png(path, width, height, main, subtitle, scale):
    """Generate a geometric two-sail emblem; no font or external artwork used."""
    require(width > 0 and height > 0, "Invalid artwork dimensions")
    variant = hashlib.sha256((main + "\0" + subtitle).encode("utf-8")).digest()
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            u, v = (x + 0.5) / width, (y + 0.5) / height
            color = (12, 26, 38)
            if 0.055 < u < 0.945 and 0.055 < v < 0.945:
                color = (18, 44, 59)
            # Two independently drawn sails above a shallow hull.
            if 0.20 < v < 0.64 and 0.23 < u < 0.48 and u > 0.48 - (v - 0.20) * 0.56:
                color = (239, 249, 252)
            if 0.25 < v < 0.64 and 0.53 < u < 0.79 and u < 0.53 + (v - 0.25) * 0.66:
                color = (50, 222, 190)
            if 0.68 < v < 0.79 and 0.18 + (v - 0.68) < u < 0.82 - (v - 0.68):
                color = (50, 222, 190)
            if 0.85 < v < 0.89 and 0.12 < u < 0.88:
                index = min(15, int((u - 0.12) / 0.76 * 16))
                if variant[index] & 1:
                    color = (90, 140, 163)
            row.extend(color)
        rows.append(row)
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    image = b"\x89PNG\r\n\x1a\n"
    image += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    image += chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(image)


def checked_artwork(path, kind):
    candidate = Path(path).expanduser().resolve()
    require(candidate.is_file() and candidate.stat().st_size <= 16 * 1024 * 1024,
            f"Missing or oversized {kind}: {candidate}")
    content = candidate.read_bytes()
    suffix = candidate.suffix.lower()
    if suffix == ".png":
        size = (48, 48) if kind == "icon" else (256, 128)
        require(len(content) >= 33 and content[:8] == b"\x89PNG\r\n\x1a\n" and content[12:16] == b"IHDR",
                f"Invalid {kind} PNG")
        require(struct.unpack_from(">II", content, 16) == size, f"{kind} PNG must be {size[0]}x{size[1]}")
    elif kind == "icon" and suffix == ".smdh":
        require(len(content) == 0x36C0 and content[:4] == b"SMDH", "Invalid SMDH")
    elif kind == "banner" and suffix in (".bnr", ".bin", ".banner"):
        require(len(content) > 256 and content[:4] == b"CBMD", "Invalid CBMD banner")
    else:
        raise RuntimeError(f"Unsupported {kind} format: {suffix}")
    return candidate


def create_artwork(directory, devkitpro, icon_source=None, banner_source=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tool = find_tool("bannertool", devkitpro)
    generated = {}
    for kind, supplied in (("icon", icon_source), ("banner", banner_source)):
        source = checked_artwork(supplied, kind) if supplied else None
        target = directory / ("icon.smdh" if kind == "icon" else "banner.bnr")
        if source and source.suffix.lower() != ".png":
            shutil.copyfile(source, target)
        else:
            png = directory / (kind + ".png")
            if source:
                shutil.copyfile(source, png)
            else:
                dimensions = (48, 48) if kind == "icon" else (256, 128)
                write_art_png(png, *dimensions, "2SHIP", "BLINKY", 1)
            if kind == "icon":
                run([tool, "makesmdh", "-s", "2Ship 3DS", "-l", "2Ship 3DS - Blinky native port",
                     "-p", "Blinky 3DS contributors", "-i", png, "-r", "regionfree",
                     "-f", "visible,allow3d,recordusage", "-o", target])
            else:
                audio = directory / "silence.wav"
                with wave.open(str(audio), "wb") as stream:
                    stream.setnchannels(1)
                    stream.setsampwidth(2)
                    stream.setframerate(32000)
                    stream.writeframes(bytes(6400))
                run([tool, "makebanner", "-i", png, "-a", audio, "-o", target])
        checked_artwork(target, kind)
        generated[kind] = target
    return generated["icon"], generated["banner"]


class BinaryView:
    """Every integer read and subsection is checked against the owning file."""
    def __init__(self, data, name):
        self.data, self.name = data, name
    def section(self, offset, size):
        require(offset >= 0 and size >= 0 and offset <= len(self.data) and size <= len(self.data) - offset,
                f"{self.name}: section exceeds file bounds")
        return self.data[offset:offset + size]
    def integer(self, offset, size=4, endian="little"):
        return int.from_bytes(self.section(offset, size), endian)
    def magic(self, offset, value):
        require(self.section(offset, len(value)) == value, f"{self.name}: invalid {value!r} signature")


def u32(data, offset): return BinaryView(data, "data").integer(offset)
def u64(data, offset): return BinaryView(data, "data").integer(offset, 8)
def align64(value): return ((value + 63) // 64) * 64


def validate_ncch(data, on_sd):
    content = BinaryView(data, "NCCH")
    content.magic(0x100, b"NCCH")
    unit = 512 << content.integer(0x18E, 1)
    require(content.integer(0x104) * unit == len(data), "NCCH length mismatch")
    require(all(content.integer(at, 8) == TITLE_ID for at in (0x108, 0x118)), "NCCH TitleID mismatch")
    require(content.section(0x150, 16).rstrip(b"\0") == PRODUCT_CODE, "NCCH product code mismatch")
    require(bool(content.integer(0x20D, 1) & 2) == on_sd, "NCCH SD/cart flag mismatch")
    require(content.integer(0x180) == 0x400, "NCCH exheader length mismatch")
    require(hashlib.sha256(content.section(0x200, 0x400)).digest() == content.section(0x160, 32),
            "NCCH exheader hash mismatch")
    sections = {}
    for name, table, expected_hash in (("ExeFS", 0x1A0, 0x1C0), ("RomFS", 0x1B0, 0x1E0)):
        start, length, hashed = [content.integer(table + field * 4) * unit for field in range(3)]
        require(start >= 0xA00 and 0 < hashed <= length, f"Invalid {name} table")
        data = content.section(start, length)
        require(hashlib.sha256(data[:hashed]).digest() == content.section(expected_hash, 32), f"{name} hash mismatch")
        if name == "RomFS":
            require(data[:4] == b"IVFC", "Invalid RomFS header")
        sections[name] = data
    return sections


def validate_packages(three_dsx, cia, cci, icon, banner):
    dsx = BinaryView(Path(three_dsx).read_bytes(), "3DSX")
    dsx.magic(0, b"3DSX")
    require(Path(icon).read_bytes() in dsx.data, "3DSX SMDH is missing")
    installed = BinaryView(Path(cia).read_bytes(), "CIA")
    require(installed.integer(0) == 0x2020, "Invalid CIA header size")
    cursor = align64(installed.integer(0))
    locations = {}
    for name, size_at in (("certificate", 8), ("ticket", 12), ("tmd", 16)):
        length = installed.integer(size_at)
        locations[name] = installed.section(cursor, length)
        cursor = align64(cursor + length)
    metadata = BinaryView(locations["tmd"], "TMD")
    signatures = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80,
                  0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}
    sig_size = signatures.get(metadata.integer(0, 4, "big"))
    require(sig_size is not None, "Unknown TMD signature kind")
    require(metadata.integer(sig_size + 0x4C, 8, "big") == TITLE_ID, "CIA install TitleID mismatch")
    cia_sections = validate_ncch(installed.section(cursor, installed.integer(24, 8)), True)
    cartridge = BinaryView(Path(cci).read_bytes(), "CCI")
    cartridge.magic(0x100, b"NCSD")
    require(cartridge.integer(0x108, 8) == TITLE_ID, "CCI TitleID mismatch")
    unit = 512 << cartridge.integer(0x18E, 1)
    offset, size = cartridge.integer(0x120) * unit, cartridge.integer(0x124) * unit
    require(offset >= 0x4000, "CCI partition overlaps header")
    cart_sections = validate_ncch(cartridge.section(offset, size), False)
    require(cia_sections == cart_sections, "CIA and CCI program/data mismatch")
    for artwork in (icon, banner):
        require(Path(artwork).read_bytes() in cia_sections["ExeFS"], "Packaged artwork mismatch")
    return {"title_id": f"{TITLE_ID:016X}", "product_code": PRODUCT_CODE.decode(),
            "cia_cci_sections_equal": True, "ncch_section_hashes_valid": True,
            "smdh_embedded_in_3dsx": True, "hardware_tested": False}


def package(elf, output, devkitpro, *, icon_source=None, banner_source=None, with_cia=True):
    elf, output, devkitpro = (Path(p).expanduser().resolve() for p in (elf, output, devkitpro))
    header = BinaryView(elf.read_bytes()[:52], "ELF")
    header.magic(0, b"\x7fELF\x01\x01\x01")
    require(header.integer(16, 2) == 2 and header.integer(18, 2) == 40, "Expected linked ARM ELF")
    scratch = SOURCE_ROOT / "work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="blinky-package-", dir=scratch) as temporary:
        workspace = Path(temporary).resolve()
        require(workspace.is_relative_to(scratch.resolve()), "Invalid packaging staging path")
        ready = workspace / "ready"
        paths = {"dsx": ready / f"SD/3ds/2ship/{NAME}.3dsx", "cia": ready / f"SD/cias/{NAME}.cia",
                 "cci": ready / f"{NAME}.3ds", "smdh": ready / f"SD/3ds/2ship/{NAME}.smdh",
                 "elf": ready / f"{NAME}.elf"}
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        romfs = workspace / "romfs"
        romfs.mkdir()
        (romfs / "README.txt").write_text("Blinky native 3DS port. Runtime data: sdmc:/3ds/2ship/\nNo game assets bundled.\n", encoding="utf-8")
        icon, banner = create_artwork(workspace / "artwork", devkitpro, icon_source, banner_source)
        run([find_tool("3dsxtool", devkitpro), elf, paths["dsx"], f"--smdh={icon}", f"--romfs={romfs}"])
        if with_cia:
            makerom = find_tool("makerom", devkitpro)
            descriptor = SOURCE_ROOT / "platform/3ds/cia/app.rsf"
            settings = descriptor.read_text(encoding="utf-8")
            require(re.search(r"UniqueId\s*:\s*0x25348\b", settings), "RSF UniqueId mismatch")
            cartridge_settings, changed = re.subn(r"(?m)^(\s*UseOnSD\s*:\s*)true\b", r"\g<1>false", settings)
            require(changed == 1, "RSF must declare one UseOnSD: true")
            cartridge_rsf = workspace / "cartridge.rsf"
            cartridge_rsf.write_text(cartridge_settings, encoding="utf-8")
            for format, target, rsf in (("cia", paths["cia"], descriptor), ("cci", paths["cci"], cartridge_rsf)):
                run([makerom, "-f", format, "-o", target, "-elf", elf, "-rsf", rsf, "-icon", icon,
                     "-banner", banner, f"-DROMFS_ROOT={romfs.as_posix()}", "-target", "t", "-exefslogo"])
            checks = validate_packages(paths["dsx"], paths["cia"], paths["cci"], icon, banner)
        else:
            dsx = paths["dsx"].read_bytes()
            require(dsx[:4] == b"3DSX" and icon.read_bytes() in dsx, "Invalid 3DSX or missing SMDH")
            checks = {"smdh_embedded_in_3dsx": True, "cia_generated": False, "hardware_tested": False}
        shutil.copyfile(icon, paths["smdh"])
        shutil.copyfile(elf, paths["elf"])
        manifest = {"name": "2Ship 3DS / Blinky", "elf_sha256": sha256(elf), "validation": checks,
                    "game_assets_bundled": False, "artwork": "Procedural two-sail emblem or user-supplied artwork",
                    "artwork_details": {"icon": {"custom": bool(icon_source), "sha256": sha256(icon)},
                                        "banner": {"custom": bool(banner_source), "sha256": sha256(banner)}}, "files": []}
        for path in sorted(ready.rglob("*")):
            if path.is_file():
                manifest["files"].append({"path": path.relative_to(ready).as_posix(), "size": path.stat().st_size,
                                          "sha256": sha256(path)})
        (ready / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for source in ready.rglob("*"):
            if source.is_file():
                destination = output / source.relative_to(ready)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    parser.add_argument("--icon", type=Path)
    parser.add_argument("--banner", type=Path)
    parser.add_argument("--artwork-only", action="store_true")
    parser.add_argument("--no-cia", action="store_true")
    args = parser.parse_args()
    if not args.artwork_only and not args.elf:
        parser.error("--elf is required unless --artwork-only is selected")
    try:
        if args.artwork_only:
            create_artwork(args.output, args.devkitpro, args.icon, args.banner)
        else:
            package(args.elf, args.output, args.devkitpro, icon_source=args.icon,
                    banner_source=args.banner, with_cia=not args.no_cia)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("Packaging stopped: " + str(error))
        return 1
    print(f"Validated output: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())