#!/usr/bin/env python3
"""Rebuild the v7 libultraship sources for 2Ship's 32-bit controller ABI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


SOURCE_ROOT = Path(__file__).resolve().parents[1]


def default_devkitpro() -> Path:
    # A Windows launch may inherit /opt/devkitpro from an MSYS shell. Prefer
    # the native installation so CMake never combines POSIX and Windows paths.
    if os.name == "nt" and Path("C:/devkitPro/devkitARM").is_dir():
        return Path("C:/devkitPro")
    return Path(os.environ.get("DEVKITPRO", "/opt/devkitpro"))


def build_environment(devkitpro: Path) -> tuple[dict[str, str], Path, Path]:
    devkitpro = devkitpro.expanduser().resolve()
    if not (devkitpro / "devkitARM").is_dir():
        raise RuntimeError(f"devkitARM missing under {devkitpro}")
    env = os.environ.copy()
    env["DEVKITPRO"] = devkitpro.as_posix()
    env["DEVKITARM"] = (devkitpro / "devkitARM").as_posix()
    native_bin = devkitpro / "msys2/mingw64/bin"
    tool_dirs = [native_bin, devkitpro / "devkitARM/bin", devkitpro / "tools/bin"]
    env["PATH"] = os.pathsep.join(str(p) for p in tool_dirs if p.is_dir()) + os.pathsep + env.get("PATH", "")
    cmake = shutil.which("cmake", path=env["PATH"])
    ninja = shutil.which("ninja", path=env["PATH"])
    if not cmake or not ninja:
        raise RuntimeError("Native CMake and Ninja are required (MinGW64 versions on Windows).")
    python = native_bin / "python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    return env, Path(cmake), python


def build_lus(devkitpro: Path, jobs: int = 4, configure_only: bool = False) -> Path:
    if not 1 <= jobs <= 64:
        raise RuntimeError("jobs must be between 1 and 64")
    devkitpro = devkitpro.expanduser().resolve()
    env, cmake, python = build_environment(devkitpro)
    source = SOURCE_ROOT / "third_party/libultraship"
    build = source / "build-3ds"
    dependencies = SOURCE_ROOT / "third_party/build-deps"
    required = {
        "IMGUI": ("imgui", "imgui.cpp"),
        "PRISM": ("prism", "CMakeLists.txt"),
        "MONOCYPHER": ("monocypher", "src/monocypher.c"),
        "THREADPOOL": ("threadpool", "include/BS_thread_pool.hpp"),
    }
    for name, sentinel in required.values():
        if not (dependencies / name / sentinel).is_file():
            raise RuntimeError(f"Pinned dependency source missing: {dependencies / name / sentinel}")
    if not (dependencies / "stb/stb_image.h").is_file():
        raise RuntimeError("Pinned stb_image.h missing from third_party/build-deps/stb")
    command = [
        str(cmake), "-S", source.as_posix(), "-B", build.as_posix(), "-G", "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={shutil.which('ninja', path=env['PATH'])}",
        f"-DDEVKITPRO={devkitpro.as_posix()}",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_POLICY_VERSION_MINIMUM=3.10",
        f"-DCMAKE_TOOLCHAIN_FILE={(SOURCE_ROOT / 'cmake/3DS.cmake').as_posix()}",
        f"-DCMAKE_PREFIX_PATH={(devkitpro / 'portlibs/3ds').as_posix()}",
        f"-DPython3_EXECUTABLE={python.as_posix()}",
        "-DBUILD_SHARED_LIBS=OFF", "-DGBI_UCODE:STRING=F3DEX_GBI_2",
        "-DINCLUDE_MPQ_SUPPORT=OFF", "-DGFX_DEBUG_DISASSEMBLER=OFF",
        "-DDISABLE_DLL_LOADER=ON", "-DENABLE_SCRIPTING=OFF",
        "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        f"-DLUS_STB_SOURCE_DIR={(dependencies / 'stb').as_posix()}",
    ]
    command.extend(f"-DFETCHCONTENT_SOURCE_DIR_{key}={(dependencies / name).as_posix()}"
                   for key, (name, _) in required.items())
    subprocess.run(command, env=env, check=True)
    if not configure_only:
        subprocess.run([str(cmake), "--build", str(build), "--parallel", str(jobs)], env=env, check=True)
        for relative in ("src/libultraship.a", "libImGui.a", "libstb.a", "libmonocypher.a", "_deps/prism-build/libprism.a"):
            output = build / relative
            if not output.is_file() or not output.stat().st_size:
                raise RuntimeError(f"Expected archive missing or empty: {output}")
    return build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    try:
        result = build_lus(args.devkitpro, args.jobs, args.configure_only)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"2Ship-3DS LUS build failed: {error}", file=sys.stderr)
        return 1
    print(f"2Ship-3DS LUS build ready: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
