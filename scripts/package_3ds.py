#!/usr/bin/env python3
"""Package the linked 2Ship ARM ELF as 3DSX, CIA and CCI, without game assets."""
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

# Original 5x7 geometric letterforms. The icon/banner contain no borrowed art.
FONT = {
    "2": (14, 17, 1, 2, 4, 8, 31), "3": (30, 1, 1, 14, 1, 1, 30),
    "A": (14, 17, 17, 31, 17, 17, 17), "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31), "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (31, 4, 4, 4, 4, 4, 31), "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 25, 25, 21, 19, 19, 17),
    "P": (30, 17, 17, 30, 16, 16, 16), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30), "T": (31, 4, 4, 4, 4, 4, 4),
    "X": (17, 17, 10, 4, 10, 17, 17), " ": (0,) * 7,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_tool(name: str, devkitpro: Path) -> Path:
    system = "windows" if os.name == "nt" else "linux"
    filename = name + (".exe" if os.name == "nt" else "")
    bundled = SOURCE_ROOT / "tools" / system / filename
    if bundled.is_file():
        records = json.loads((SOURCE_ROOT / "tools/provenance.json").read_text(encoding="utf-8"))
        match = next((item for item in records if item["file"] == bundled.relative_to(SOURCE_ROOT).as_posix()), None)
        require(match is not None and sha256(bundled) == match["sha256"], f"Bundled {name} checksum mismatch")
        return bundled
    installed = devkitpro / "tools/bin" / filename
    if installed.is_file():
        return installed
    path = shutil.which(name)
    require(path is not None, f"{name} is required: install devkitPro tools or provide tools/{system}/{filename}")
    return Path(path)


def run(command: list[Path | str]) -> None:
    print(f"Packaging: {Path(command[0]).name}", flush=True)
    subprocess.run([str(arg) for arg in command], check=True)


def write_art_png(path: Path, width: int, height: int, main: str, subtitle: str, scale: int) -> None:
    dark, panel, aqua, white = (12, 24, 37), (18, 43, 56), (44, 219, 185), (242, 249, 250)
    pixels = bytearray(dark * (width * height))

    def rectangle(x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        row = bytes(color) * w
        for at in range(y, y + h):
            pixels[(at * width + x) * 3:(at * width + x + w) * 3] = row

    def label(text: str, y: int, size: int, color: tuple[int, int, int]) -> None:
        x = (width - (len(text) * 6 - 1) * size) // 2
        for letter in text:
            for row, bits in enumerate(FONT[letter]):
                for column in range(5):
                    if bits & (1 << (4 - column)):
                        rectangle(x + column * size, y + row * size, size, size, color)
            x += 6 * size

    rectangle(2, 2, width - 4, height - 4, panel)
    rectangle(2, 2, width - 4, 2, aqua)
    rectangle(2, height - 4, width - 4, 2, aqua)
    if width == 48:
        label(main, 7, scale, white)
        label(subtitle, 37, 1, aqua)
    else:
        label(main, 34, scale, white)
        label(subtitle, 87, 2, aqua)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    raw = b"".join(b"\0" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def checked_artwork(path: Path, kind: str) -> Path:
    """Accept normalized PNGs or compiled artwork; never alter the input file."""
    path = path.expanduser().resolve()
    require(path.is_file(), f"Missing {kind}: {path}")
    require(path.stat().st_size <= 16 * 1024 * 1024, f"{kind} exceeds 16 MiB")
    data = path.read_bytes()
    if path.suffix.lower() == ".png":
        size = (48, 48) if kind == "icon" else (256, 128)
        require(len(data) >= 33 and data[:8] == b"\x89PNG\r\n\x1a\n"
                and data[12:16] == b"IHDR", f"Invalid {kind} PNG")
        require(struct.unpack_from(">II", data, 16) == size,
                f"{kind} must be a {size[0]}x{size[1]} PNG (the wizard resizes images)")
    elif kind == "icon" and path.suffix.lower() == ".smdh":
        require(len(data) == 0x36C0 and data[:4] == b"SMDH", "Invalid custom SMDH")
    elif kind == "banner" and path.suffix.lower() in (".bnr", ".bin", ".banner"):
        require(len(data) > 0x100 and data[:4] == b"CBMD", "Invalid custom CBMD banner")
    else:
        raise RuntimeError(f"Unsupported {kind} format: {path.suffix}")
    return path


def create_artwork(directory: Path, devkitpro: Path, icon_source: Path | None = None,
                   banner_source: Path | None = None) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    icon_png, banner_png, audio = directory / "icon.png", directory / "banner.png", directory / "silence.wav"
    icon_source = checked_artwork(icon_source, "icon") if icon_source else None
    banner_source = checked_artwork(banner_source, "banner") if banner_source else None
    if icon_source and icon_source.suffix.lower() == ".png":
        shutil.copyfile(icon_source, icon_png)
    else:
        write_art_png(icon_png, 48, 48, "2S", "3DS", 4)
    if banner_source and banner_source.suffix.lower() == ".png":
        shutil.copyfile(banner_source, banner_png)
    else:
        write_art_png(banner_png, 256, 128, "2SHIP 3DS", "EXPERIMENTAL", 4)
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 32000, 3200, "NONE", "not compressed"))
        stream.writeframes(bytes(6400))
    bannertool = find_tool("bannertool", devkitpro)
    icon, banner = directory / "icon.smdh", directory / "banner.bnr"
    if icon_source and icon_source.suffix.lower() == ".smdh":
        shutil.copyfile(icon_source, icon)
    else:
        run([bannertool, "makesmdh", "-s", "2Ship 3DS", "-l", "2Ship 3DS - Experimental homebrew port",
             "-p", "2Ship-3DS community port", "-i", icon_png, "-r", "regionfree",
             "-f", "visible,allow3d,recordusage", "-o", icon])
    if banner_source and banner_source.suffix.lower() != ".png":
        shutil.copyfile(banner_source, banner)
    else:
        run([bannertool, "makebanner", "-i", banner_png, "-a", audio, "-o", banner])
    smdh = icon.read_bytes()
    require(len(smdh) == 0x36C0 and smdh[:4] == b"SMDH", "Invalid generated SMDH")
    if not icon_source or icon_source.suffix.lower() != ".smdh":
        require(b"2\x00S\x00h\x00i\x00p\x00" in smdh[:0x2000], "SMDH title is missing")
    require(banner.stat().st_size > 0x100, "Generated banner is empty")
    return icon, banner


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def align64(value: int) -> int:
    return (value + 63) & ~63


def validate_ncch(data: bytes, on_sd: bool) -> dict[str, bytes]:
    require(len(data) > 0xA00 and data[0x100:0x104] == b"NCCH", "Missing NCCH content")
    unit = 0x200 << data[0x18E]
    require(u32(data, 0x104) * unit == len(data), "NCCH size mismatch")
    require(u64(data, 0x108) == u64(data, 0x118) == TITLE_ID, "NCCH TitleID mismatch")
    require(data[0x150:0x160].rstrip(b"\0") == PRODUCT_CODE, "NCCH product code mismatch")
    require(bool(data[0x20D] & 2) == on_sd, "NCCH SD/cart flag mismatch")
    exheader_size = u32(data, 0x180)
    require(exheader_size == 0x400, "Unexpected exheader size")
    require(hashlib.sha256(data[0x200:0x200 + exheader_size]).digest() == data[0x160:0x180], "Exheader hash mismatch")
    sections = {}
    for name, info, digest in (("ExeFS", 0x1A0, 0x1C0), ("RomFS", 0x1B0, 0x1E0)):
        offset, size, hash_size = (u32(data, info + i * 4) * unit for i in range(3))
        require(offset >= 0xA00 and 0 < hash_size <= size and offset + size <= len(data), f"Invalid {name} bounds")
        section = data[offset:offset + size]
        require(hashlib.sha256(section[:hash_size]).digest() == data[digest:digest + 32], f"{name} hash mismatch")
        if name == "RomFS":
            require(section[:4] == b"IVFC", "Missing RomFS IVFC header")
        sections[name] = section
    return sections


def validate_packages(three_dsx: Path, cia: Path, cci: Path, icon: Path, banner: Path) -> dict:
    dsx = three_dsx.read_bytes()
    require(dsx[:4] == b"3DSX" and icon.read_bytes() in dsx, "3DSX header or embedded SMDH missing")
    cia_data = cia.read_bytes()
    require(len(cia_data) > 0x2020 and u32(cia_data, 0) == 0x2020, "Invalid CIA header")
    tmd_offset = align64(align64(align64(u32(cia_data, 0)) + u32(cia_data, 8)) + u32(cia_data, 12))
    require(tmd_offset + u32(cia_data, 16) <= len(cia_data), "CIA title metadata exceeds file bounds")
    signature = struct.unpack_from(">I", cia_data, tmd_offset)[0]
    # Nintendo RSA/ECDSA signature blocks include their type and padding.
    signature_sizes = {0x10000: 0x240, 0x10001: 0x140, 0x10002: 0x80,
                       0x10003: 0x240, 0x10004: 0x140, 0x10005: 0x80}
    require(signature in signature_sizes, "Unknown CIA TMD signature type")
    tmd_title = struct.unpack_from(">Q", cia_data, tmd_offset + signature_sizes[signature] + 0x4C)[0]
    require(tmd_title == TITLE_ID, "CIA install TitleID mismatch")
    content = align64(u32(cia_data, 0))
    for offset in (8, 12, 16):
        content = align64(content + u32(cia_data, offset))
    content_size = u64(cia_data, 24)
    require(content + content_size <= len(cia_data), "CIA content exceeds file bounds")
    cia_sections = validate_ncch(cia_data[content:content + content_size], True)
    cci_data = cci.read_bytes()
    require(len(cci_data) > 0x4000 and cci_data[0x100:0x104] == b"NCSD", "Invalid CCI/NCSD header")
    require(u64(cci_data, 0x108) == TITLE_ID, "CCI media TitleID mismatch")
    unit = 0x200 << cci_data[0x18E]
    part_offset, part_size = u32(cci_data, 0x120) * unit, u32(cci_data, 0x124) * unit
    require(part_offset >= 0x4000 and part_offset + part_size <= len(cci_data), "CCI partition exceeds file bounds")
    cci_sections = validate_ncch(cci_data[part_offset:part_offset + part_size], False)
    require(cia_sections == cci_sections, "CIA and CCI program/data sections differ")
    require(icon.read_bytes() in cia_sections["ExeFS"] and banner.read_bytes() in cia_sections["ExeFS"],
            "Generated icon/banner absent from ExeFS")
    return {"title_id": f"{TITLE_ID:016X}", "product_code": PRODUCT_CODE.decode(),
            "cia_cci_sections_equal": True, "ncch_section_hashes_valid": True,
            "smdh_embedded_in_3dsx": True, "hardware_tested": False}


def package(elf: Path, output: Path, devkitpro: Path, *, icon_source: Path | None = None,
            banner_source: Path | None = None, with_cia: bool = True) -> dict:
    elf, output, devkitpro = elf.expanduser().resolve(), output.expanduser().resolve(), devkitpro.expanduser().resolve()
    require(elf.is_file(), f"Linked ELF missing: {elf}")
    header = elf.read_bytes()[:52]
    require(len(header) == 52 and header[:7] == b"\x7fELF\x01\x01\x01", "Input is not a 32-bit little-endian ELF")
    require(struct.unpack_from("<HH", header, 16) == (2, 40), "Input must be a linked ARM executable")
    makerom = find_tool("makerom", devkitpro) if with_cia else None
    dsxtool = find_tool("3dsxtool", devkitpro)
    scratch = SOURCE_ROOT / "work"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-", dir=scratch) as temporary:
        stage = Path(temporary).resolve()
        require(stage.is_relative_to(scratch.resolve()), "Packaging temporary directory is outside source work/")
        icon, banner = create_artwork(stage / "artwork", devkitpro, icon_source, banner_source)
        romfs = stage / "romfs"
        romfs.mkdir()
        (romfs / "README.txt").write_text("2Ship 3DS experimental port. Runtime archives: sdmc:/3ds/2ship/\n"
                                         "No game assets are bundled.\n", encoding="utf-8")
        ready = stage / "ready"
        sd = ready / "SD/3ds/2ship"
        sd.mkdir(parents=True)
        (ready / "SD/cias").mkdir()
        three_dsx, cia, cci = sd / f"{NAME}.3dsx", ready / f"SD/cias/{NAME}.cia", ready / f"{NAME}.3ds"
        run([dsxtool, elf, three_dsx, f"--smdh={icon}", f"--romfs={romfs}"])
        if with_cia:
            rsf = SOURCE_ROOT / "platform/3ds/cia/app.rsf"
            rsf_text = rsf.read_text(encoding="utf-8")
            require(re.search(r"UniqueId\s*:\s*0x25348\b", rsf_text) is not None, "RSF UniqueId mismatch")
            cart_text, substitutions = re.subn(r"(?m)^(\s*UseOnSD\s*:\s*)true\b", r"\g<1>false", rsf_text)
            require(substitutions == 1, "RSF must contain one UseOnSD: true flag")
            cart_rsf = stage / "cartridge.rsf"
            cart_rsf.write_text(cart_text, encoding="utf-8")
            for fmt, target, descriptor in (("cia", cia, rsf), ("cci", cci, cart_rsf)):
                run([makerom, "-f", fmt, "-o", target, "-elf", elf, "-rsf", descriptor,
                     "-icon", icon, "-banner", banner, f"-DROMFS_ROOT={romfs.as_posix()}", "-target", "t", "-exefslogo"])
            validation = validate_packages(three_dsx, cia, cci, icon, banner)
        else:
            dsx = three_dsx.read_bytes()
            require(dsx[:4] == b"3DSX" and icon.read_bytes() in dsx,
                    "3DSX header or embedded SMDH missing")
            validation = {"smdh_embedded_in_3dsx": True, "cia_generated": False,
                          "hardware_tested": False}
        shutil.copyfile(icon, sd / f"{NAME}.smdh")
        shutil.copyfile(elf, ready / f"{NAME}.elf")
        manifest = {"name": "2Ship 3DS experimental", "elf_sha256": sha256(elf), "validation": validation,
                    "artwork": ("User-supplied artwork; original defaults used for empty selections" if icon_source or banner_source
                                else "Original procedural typography and rectangles; silent banner audio"),
                    "artwork_details": {"icon": {"custom": bool(icon_source), "sha256": sha256(icon)},
                                "banner": {"custom": bool(banner_source), "sha256": sha256(banner)},
                                "note": "Defaults are original procedural art; custom files are user supplied."},
                    "game_assets_bundled": False, "files": []}
        for file in sorted(ready.rglob("*")):
            if file.is_file():
                manifest["files"].append({"path": file.relative_to(ready).as_posix(), "size": file.stat().st_size,
                                          "sha256": sha256(file)})
        (ready / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for file in ready.rglob("*"):
            if file.is_file():
                destination = output / file.relative_to(ready)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, destination)
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    parser.add_argument("--artwork-only", action="store_true", help="Generate and validate original artwork without requiring an ELF")
    parser.add_argument("--icon", type=Path, help="48x48 PNG or compiled SMDH")
    parser.add_argument("--banner", type=Path, help="256x128 PNG or compiled CBMD banner")
    parser.add_argument("--no-cia", action="store_true", help="Produce only 3DSX/SMDH/ELF; skip CIA and CCI")
    args = parser.parse_args()
    if not args.artwork_only and args.elf is None:
        parser.error("--elf is required unless --artwork-only is set")
    try:
        if args.artwork_only:
            create_artwork(args.output.resolve(), args.devkitpro.resolve(), args.icon, args.banner)
        else:
            package(args.elf, args.output, args.devkitpro, icon_source=args.icon,
                    banner_source=args.banner, with_cia=not args.no_cia)
    except (RuntimeError, OSError, subprocess.CalledProcessError, struct.error) as error:
        print(f"2Ship-3DS packaging failed: {error}")
        return 1
    print(f"2Ship-3DS output ready: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
