#!/usr/bin/env python3
"""Blinky build driver: configure pinned sources, link ARM, verify packages."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_lus_3ds import BuildTools, build_lus, default_devkitpro
from build_clock import prepare_source_clock

def options(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    cli.add_argument("--output", type=Path, default=ROOT / "dist")
    cli.add_argument("--jobs", type=int, default=4)
    cli.add_argument("--occlusion", choices=("off", "on"), default="off")
    cli.add_argument("--render-stats", action="store_true")
    cli.add_argument("--occlusion-debug", action="store_true")
    for name, help_text in {
        "skip-lus": "Reuse LUS archives when source timestamps are stable",
        "no-package": "Stop after linking the ARM ELF and basic 3DSX",
        "emulator-safe": "Disable the hardware CPU-speed service",
        "memory-watch": "Enable the optional libc bulk-write diagnostic",
    }.items():
        cli.add_argument("--" + name, action="store_true", help=help_text)
    values = cli.parse_args(argv)
    if values.jobs not in range(1, 65):
        cli.error("--jobs must be between 1 and 64")
    return values

def main(argv=None):
    args = options(argv)
    build_dir = ROOT / "build-arm"
    started = time.monotonic()
    report = {
        "source": "HarbourMasters/2ship2harkinian", "version": "5.0.1",
        "commit": "6bfd6a35a0e0d8900273e61ce85cb038d4f4a528",
        "base": "official MM/LUS with separately documented Blinky integration",
        "window": "GfxWindowBackendBlinky3DS", "audio": "BlinkyNdspAudioPlayer",
        "renderer": "GfxRenderingAPIBlinkyCitro3D", "input": "Blinky HID",
        "lower_ui": "Blinky native diagnostics and remapping",
        "emulator_safe": args.emulator_safe, "memory_watch": args.memory_watch,
        "occlusion": args.occlusion, "render_stats": args.render_stats,
        "occlusion_debug": args.occlusion_debug,
        "hardware_tested": False, "gameplay_tested": False,
        "soh_removal_complete": False, "whole_source_original": False,
        "cleanroom_certified": False, "success": False, "completed_phases": [],
    }
    try:
        sdk = BuildTools.discover(args.devkitpro)
        report["source_clock"] = prepare_source_clock(ROOT)
        if not args.skip_lus or report["source_clock"]["changed_count"]:
            build_lus(args.devkitpro, args.jobs, clock_checked=True)
        archive = ROOT / "third_party/libultraship/build-3ds/src/libultraship.a"
        if not archive.is_file() or archive.stat().st_size == 0:
            raise RuntimeError("No usable LUS archive; build without --skip-lus")
        report["completed_phases"].append("libultraship")
        sdk.configure(ROOT, build_dir, {
            "TWOSHIP3DS_EMULATOR_SAFE": "ON" if args.emulator_safe else "OFF",
            "TWOSHIP3DS_MEMORY_WATCH": "ON" if args.memory_watch else "OFF",
            "BLINKY_OCCLUSION_CULLING": args.occlusion.upper(),
            "BLINKY_RENDER_STATS": "ON" if args.render_stats else "OFF",
            "BLINKY_OCCLUSION_DEBUG": "ON" if args.occlusion_debug else "OFF",
        })
        report["completed_phases"].append("configure")
        sdk.build(build_dir, args.jobs, "2ship_3ds")
        report["completed_phases"].append("link")
        if not args.no_package:
            subprocess.run([str(sdk.python), str(ROOT / "scripts/package_3ds.py"),
                            "--elf", str(build_dir / "2ship-3ds.elf"), "--output", str(args.output),
                            "--devkitpro", str(sdk.root)], env=sdk.env, check=True)
            report["completed_phases"].append("package")
        report["success"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        print("Build stopped: " + str(error), file=sys.stderr)
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 1)
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(not report["success"])

if __name__ == "__main__":
    raise SystemExit(main())
