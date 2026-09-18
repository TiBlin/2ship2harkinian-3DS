#!/usr/bin/env python3
"""Exercise real bundled bannertool, without an ARM/game build or game assets."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_3ds as p


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="2ship-artwork-") as directory:
        work = Path(directory)
        sdk = p.default_devkitpro()
        default_icon, default_banner = p.create_artwork(work / "defaults", sdk)
        icon_png, banner_png = work / "custom-icon.png", work / "custom-banner.png"
        p.write_art_png(icon_png, 48, 48, "3D", "2S", 4)
        p.write_art_png(banner_png, 256, 128, "TEST 3DS", "TEST", 4)
        before = (p.sha256(icon_png), p.sha256(banner_png))
        icon, banner = p.create_artwork(work / "custom", sdk, icon_png, banner_png)
        p.require(icon.read_bytes() != default_icon.read_bytes(), "Custom icon not reflected in SMDH")
        p.require(banner.read_bytes() != default_banner.read_bytes(), "Custom banner not reflected in CBMD")
        p.require(before == (p.sha256(icon_png), p.sha256(banner_png)), "Input PNG changed")
        print("PASS: real custom PNG -> SMDH/CBMD; source images unchanged")
        icon2, banner2 = p.create_artwork(work / "compiled", sdk, icon, banner)
        p.require(icon.read_bytes() == icon2.read_bytes(), "Compiled icon changed")
        p.require(banner.read_bytes() == banner2.read_bytes(), "Compiled banner changed")
        print("PASS: compiled SMDH/CBMD preserved byte-for-byte")
    print("No GUI, ARM game build, or hardware validation is implied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
