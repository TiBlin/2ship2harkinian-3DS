#!/usr/bin/env python3
"""Run production archive preflight against real files and libzip call doubles.

Tests our filesystem/header/version checks and libzip failure handling, not
libzip's own ZIP decoder. The ARM build continues to use the real library.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise SystemExit("A host C++ compiler is required (set CXX).")
    with tempfile.TemporaryDirectory(prefix="2ship-preflight-", dir=ROOT.parent) as tmp:
        tmp = Path(tmp)
        binary = tmp / ("preflight_test.exe" if os.name == "nt" else "preflight_test")
        subprocess.run([
            compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "tests/preflight_stubs"), "-I", str(ROOT / "src/port3ds"),
            str(ROOT / "tests/preflight_archive_test.cpp"), "-o", str(binary),
        ], check=True)
        environment = os.environ.copy()
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
        subprocess.run([str(binary), str(tmp)], check=True, env=environment)


if __name__ == "__main__":
    main()
