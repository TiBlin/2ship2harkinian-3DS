#!/usr/bin/env python3
"""Offline CMake orchestration from the public CLI and devkitPro tool layout."""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from build_clock import check_lus_ninja_manifest, prepare_source_clock

SOURCE_ROOT = Path(__file__).resolve().parents[1]
PINNED_INPUTS = {
    "IMGUI": "imgui/imgui.cpp", "PRISM": "prism/CMakeLists.txt",
    "MONOCYPHER": "monocypher/src/monocypher.c",
    "THREADPOOL": "threadpool/include/BS_thread_pool.hpp",
}
LUS_ARCHIVES = ("src/libultraship.a", "libImGui.a", "libstb.a", "libmonocypher.a",
                "_deps/prism-build/libprism.a")

def default_devkitpro():
    configured = Path(os.environ.get("DEVKITPRO", "/opt/devkitpro"))
    native_windows = Path("C:/devkitPro")
    return native_windows if os.name == "nt" and (native_windows / "devkitARM").is_dir() else configured

def build_environment(devkitpro):
    root = Path(devkitpro).expanduser().resolve()
    if not (root / "devkitARM").is_dir():
        raise RuntimeError(f"devkitARM missing under {root}")
    environment = dict(os.environ, DEVKITPRO=root.as_posix(), DEVKITARM=(root / "devkitARM").as_posix())
    candidates = [root / p for p in ("msys2/mingw64/bin", "devkitARM/bin", "tools/bin")]
    environment["PATH"] = os.pathsep.join([str(p) for p in candidates if p.is_dir()] + [environment.get("PATH", "")])
    required = {name: shutil.which(name, path=environment["PATH"]) for name in ("cmake", "ninja")}
    if not all(required.values()):
        raise RuntimeError("Install native CMake and Ninja (MinGW64 on Windows)")
    python = root / "msys2/mingw64/bin/python.exe"
    return environment, Path(required["cmake"]), python if python.is_file() else Path(sys.executable)

@dataclass(frozen=True)
class BuildTools:
    root: Path
    env: dict
    cmake: Path
    python: Path

    @classmethod
    def discover(cls, devkitpro):
        return cls(Path(devkitpro).expanduser().resolve(), *build_environment(devkitpro))

    def configure(self, source, output, settings=None):
        cache = {
            "DEVKITPRO": self.root.as_posix(), "CMAKE_BUILD_TYPE": "Release",
            "CMAKE_MAKE_PROGRAM": shutil.which("ninja", path=self.env["PATH"]),
            "CMAKE_TOOLCHAIN_FILE": (SOURCE_ROOT / "cmake/3DS.cmake").as_posix(),
            "Python3_EXECUTABLE": self.python.as_posix(), "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        }
        cache.update(settings or {})
        command = [str(self.cmake), "-S", str(source), "-B", str(output), "-G", "Ninja"]
        command.extend(f"-D{key}={value}" for key, value in cache.items())
        subprocess.run(command, env=self.env, check=True)

    def build(self, directory, jobs, target=None):
        arguments = [str(self.cmake), "--build", str(directory), "--parallel", str(jobs)]
        if target:
            arguments.extend(("--target", target))
        subprocess.run(arguments, env=self.env, check=True)

def build_lus(devkitpro, jobs=4, configure_only=False, *, clock_checked=False):
    if jobs not in range(1, 65):
        raise RuntimeError("jobs must be between 1 and 64")
    sdk = BuildTools.discover(devkitpro)
    if not clock_checked:
        prepare_source_clock(SOURCE_ROOT)
    dependencies = SOURCE_ROOT / "third_party/build-deps"
    for relative in (*PINNED_INPUTS.values(), "stb/stb_image.h"):
        if not (dependencies / relative).is_file():
            raise RuntimeError(f"Pinned source missing: {dependencies / relative}")
    settings = {
        "CMAKE_POLICY_VERSION_MINIMUM": "3.10", "BUILD_SHARED_LIBS": "OFF",
        "CMAKE_PREFIX_PATH": (sdk.root / "portlibs/3ds").as_posix(),
        "GBI_UCODE:STRING": "F3DEX_GBI_2", "INCLUDE_MPQ_SUPPORT": "OFF",
        "GFX_DEBUG_DISASSEMBLER": "OFF", "DISABLE_DLL_LOADER": "ON", "ENABLE_SCRIPTING": "OFF",
        "FETCHCONTENT_UPDATES_DISCONNECTED": "ON", "FETCHCONTENT_FULLY_DISCONNECTED": "ON",
        "LUS_STB_SOURCE_DIR": (dependencies / "stb").as_posix(),
    }
    settings.update({"FETCHCONTENT_SOURCE_DIR_" + key: (dependencies / Path(value).parts[0]).as_posix()
                     for key, value in PINNED_INPUTS.items()})
    source = SOURCE_ROOT / "third_party/libultraship"
    destination = source / "build-3ds"
    sdk.configure(source, destination, settings)
    if not configure_only:
        check_lus_ninja_manifest(destination, sdk.env)
        sdk.build(destination, jobs)
        for relative in LUS_ARCHIVES:
            artifact = destination / relative
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise RuntimeError(f"LUS output missing or empty: {artifact}")
    return destination

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    try:
        print(build_lus(args.devkitpro, args.jobs, args.configure_only))
    except (RuntimeError, OSError, subprocess.SubprocessError) as failure:
        print(str(failure), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())