#!/usr/bin/env python3
"""Run maintained production regressions with a host C++ compiler."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# These tests execute production functions or validate observable file formats.
# Their upstream code remains attributed when extracted into temporary fixtures.
REGRESSIONS = (
    "test_2ship_preflight.py", "test_2ship_scene_eviction.py", "test_2ship_extension_index.py",
    "test_mm_control_merge.py", "test_context_teardown_3ds.py", "test_mm_crash26_resource_probe.py",
    "test_mm_note_address_gate.py", "test_stability_audit1.py",
    "test_mm_3ds_timing_audio.py", "test_mm_audio_specs.py", "test_mm_adpcm_boundaries.py",
    "test_mm_mixer_effects.py", "test_build_clock.py", "test_wizard_artwork.py",
)
BLINKY = (
    "test_blinky_startup.py", "test_blinky_backends.py", "test_blinky_render_math.py", "test_blinky_renderer.py",
    "test_blinky_archives.py", "test_blinky_crash28.py", "test_blinky_occlusion.py",
)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    args = parser.parse_args()
    compiler = shutil.which(args.cxx)
    if not compiler or "arm-none-eabi" in Path(compiler).name:
        parser.error("Choose a host C++ compiler with --cxx or CXX")
    environment = dict(os.environ, CXX=compiler, PYTHONUTF8="1")
    environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
    completed = []
    for test in (*REGRESSIONS, *BLINKY):
        invocation = [sys.executable, "-X", "utf8", str(ROOT / "tests" / test)]
        if test == "test_mm_note_address_gate.py":
            invocation.append("--require-fixed")
        if test in BLINKY:
            invocation.extend(("--cxx", compiler))
        print("Checking " + test, flush=True)
        result = subprocess.run(invocation, cwd=ROOT, env=environment)
        if result.returncode:
            return result.returncode
        completed.append(test)
    print(f"Passed {len(completed)} host regression programs. Physical GPU/audio results need console validation.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
