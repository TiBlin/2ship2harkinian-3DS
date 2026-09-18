#!/usr/bin/env python3
"""Windows wizard worker. Standard library only; no source-code edits or downloads.

The UI runs this worker as a separate process and tails log files. Compilation
children inherit its output handles: there is no undrained PIPE while waiting.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_lus_3ds import build_environment
import package_3ds as packager
from prepare_support import ADDITIONS

VERSION = "1.0.6-EN-ROMDROP"
PLAYBACK = "third_party/2ship/mm/src/audio/lib/playback.c"
EXPECTED_PLAYBACK_SHA256 = "e462a5e0d6bb641e768f692c5c3f6da1ee306bdf6c5fb06b5ecb6605a24e0b18"
BLOCK = 1024 * 1024


class WizardError(RuntimeError):
    pass


class Cancelled(WizardError):
    pass


def need(condition: bool, text: str) -> None:
    if not condition:
        raise WizardError(text)


def digest(path: Path, cancel=lambda: None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(BLOCK), b""):
            cancel()
            h.update(block)
    return h.hexdigest()


def json_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    need(isinstance(config, dict), "Invalid JSON configuration.")
    need(type(config.get("jobs", 4)) is int and 1 <= config.get("jobs", 4) <= 64,
         "Choose between 1 and 64 parallel build jobs.")
    need(config.get("mode", "clean") in ("clean", "resume"), "Unknown build mode.")
    for key in ("copy_assets", "check_crc", "with_cia"):
        need(type(config.get(key, True if key != "copy_assets" else False)) is bool,
             f"Expected a boolean value for: {key}.")
    for key in ("devkitpro", "output_base"):
        need(isinstance(config.get(key), str) and config[key].strip(), f"Missing path: {key}.")
    return config


def valid_version(raw: bytes, support: bool) -> tuple[int, int, int]:
    need(len(raw) == 7 and raw[0] in (0, 1), "Invalid portVersion metadata.")
    result = struct.unpack((">" if raw[0] else "<") + "HHH", raw[1:])
    need(result[0] == 5 and (not support or result == (5, 0, 1)),
         f"Version {'.'.join(map(str, result))} incompatible : "
         + ("2ship.o2r must be version 5.0.1." if support else "mm.o2r must be a 5.x archive."))
    return result


def inspect_archive(path: Path, support: bool, full_crc: bool = True,
                    cancel=lambda: None, log=print) -> dict:
    """Mirror archive_checks.h version rules; add streamed CRC and SHA-256 checks.

    Does not claim to validate every resource semantically; no ZIP extraction.
    """
    path = path.expanduser().resolve()
    need(path.is_file(), f"Archive not found: {path}")
    need(path.suffix.lower() == ".o2r", f"Select an .o2r archive, not a ROM or .otr file: {path.name}")
    with path.open("rb") as stream:
        need(stream.read(4) == b"PK\x03\x04", f"{path.name} is not a valid ZIP-based .o2r archive.")
    log(f"Checking {path.name}...")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            need(len(infos) > 1, f"{path.name} is empty or incomplete.")
            need(len(set(names)) == len(names), f"{path.name} contains duplicate entry names.")
            need("portVersion" in names, f"portVersion is missing from {path.name}.")
            need(archive.getinfo("portVersion").file_size == 7, "Invalid portVersion size.")
            version = valid_version(archive.read("portVersion"), support)
            need(all(not i.flag_bits & 1 for i in infos), "Encrypted ZIP archives are not supported.")
            need(all(i.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in infos),
                 "Unsupported ZIP compression method; use Store or Deflate.")
            need(sum(i.file_size for i in infos) <= 16 * 1024**3,
                 "Archive is too large after decompression (16 GiB safety limit).")
            missing = [name for name in ADDITIONS if name not in names] if support else []
            if missing:
                log("WARNING: some 3DS support resources are missing. "
                    "Prefer the 2ship.o2r already used on the console. "
                    "No source archive will be modified automatically.")
                for name in missing:
                    log(f"  Missing resource: {name}")
            if full_crc:
                next_update = time.monotonic() + 2
                for index, item in enumerate(infos, 1):
                    cancel()
                    if not item.is_dir():
                        with archive.open(item) as stream:
                            while stream.read(BLOCK):
                                cancel()
                    if time.monotonic() >= next_update or index == len(infos):
                        log(f"CRC {path.name}: {index}/{len(infos)} entries")
                        next_update = time.monotonic() + 2
    except Cancelled:
        raise
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise WizardError(f"Archive rejected {path.name}: {error}") from error
    result = {"source": str(path), "name": "2ship.o2r" if support else "mm.o2r",
              "version": list(version), "entries": len(infos), "crc_checked": full_crc,
              "sha256": digest(path, cancel), "size": path.stat().st_size,
              "missing_support_resources": missing, "semantic_resources_validated": False}
    log(f"OK {path.name}: version {'.'.join(map(str, version))}, {len(infos)} entries.")
    return result


def check_audio_fix(root: Path = ROOT) -> dict:
    source = root / PLAYBACK
    need(source.is_file(), f"Incomplete sources: {PLAYBACK}")
    text = source.read_text(encoding="utf-8")
    start = text.find("void AudioPlayback_ProcessNotes(")
    need(start >= 0, "AudioPlayback_ProcessNotes was not found.")
    threshold = text.find("0x7FFFFFFF", start)
    need(threshold >= 0, "Unrecognized audio gate; verify this source version.")
    guard = re.search(r"#if\s+!defined\(__WIIU__\)\s*&&\s*!defined\(__3DS__\)", text[start:threshold])
    need(guard is not None, "3DS audio fix is missing. Use the AUDIO-FIX sources, not the older V2 archive.")
    actual = digest(source)
    return {"path": PLAYBACK, "sha256": actual, "guard_detected": True,
            "matches_supplied_audio_fix": actual == EXPECTED_PLAYBACK_SHA256}


def parse_cache(path: Path) -> dict[str, str]:
    result = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"([^/#][^:=]*):[^=]*=(.*)$", line)
            if match:
                result[match[1]] = match[2]
    return result


def caches(root: Path) -> tuple[tuple[Path, Path], ...]:
    return ((root / "build-arm", root),
            (root / "third_party/libultraship/build-3ds", root / "third_party/libultraship"))


def check_resume(root: Path, sdk: Path) -> None:
    for build, source in caches(root):
        if not build.exists():
            continue
        need(not build.is_symlink() and build.resolve().is_relative_to(root.resolve()),
             f"External cache or symlink refused: {build}")
        cache = parse_cache(build / "CMakeCache.txt")
        if not cache:
            need(not any(build.iterdir()), f"Incomplete cache in {build}. Choose Clean rebuild.")
            continue
        for key, expected in (("CMAKE_HOME_DIRECTORY", source), ("CMAKE_CACHEFILE_DIR", build),
                              ("DEVKITPRO", sdk)):
            need(key in cache and Path(cache[key]).resolve() == expected.resolve(),
                 f"Moved or incompatible cache ({key}): {build}. Choose Clean rebuild.")
        need(cache.get("CMAKE_GENERATOR") == "Ninja", "The existing cache uses a generator other than Ninja. Choose Clean rebuild.")
        for key, exe in (("CMAKE_C_COMPILER", "arm-none-eabi-gcc"), ("CMAKE_CXX_COMPILER", "arm-none-eabi-g++")):
            if key in cache:
                extension = ".exe" if os.name == "nt" else ""
                expected = sdk / "devkitARM/bin" / (exe + extension)
                need(Path(cache[key]).resolve() == expected.resolve(),
                     f"Compiler mismatch in cache: {key}. Choose Clean rebuild.")


def backup_caches(root: Path, suffix: str, log=print) -> list[dict]:
    pairs = caches(root)
    # Prevalidate every path before moving any of them. Nothing is deleted.
    for build, _ in pairs:
        need(not build.is_symlink() and build.resolve().is_relative_to(root.resolve()),
             f"External cache or symlink refused: {build}")
    backups = []
    for build, _ in pairs:
        if build.exists():
            destination = build.with_name(build.name + ".avant-wizard-" + suffix)
            need(not destination.exists(), f"Cache backup already exists: {destination}")
            build.rename(destination)
            backups.append({"from": str(build), "backup": str(destination)})
            log(f"Previous cache preserved: {destination}")
    return backups


@contextmanager
def project_lock(root: Path):
    """An OS-owned advisory lock releases even when the worker is terminated."""
    path = root / "wizard/build.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("a+b")
    try:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise WizardError("Another wizard instance is already using these sources.") from error
        else:
            import fcntl
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise WizardError("Another wizard instance is already using these sources.") from error
        yield
    finally:
        f.close()


def copy_checked(source: Path, destination: Path, expected: str, cancel=lambda: None) -> None:
    need(source.resolve() != destination.resolve(), "Copying onto the source file is not allowed.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with source.open("rb") as src, destination.open("xb") as dst:
        for data in iter(lambda: src.read(BLOCK), b""):
            cancel()
            dst.write(data)
            h.update(data)
    need(h.hexdigest() == expected, f"{source.name} changed while it was being copied. Output was not published.")
    need(digest(destination, cancel) == expected, f"Verification failed after copy: {destination}")


class Worker:
    def __init__(self, config_path: Path, config: dict):
        self.config_path = config_path
        self.config = config
        self.run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.cancel_file = config_path.with_suffix(".cancel")
        self.status_file = config_path.with_suffix(".status.json")
        self.state = {"status": "running", "stage": "Initializing", "version": VERSION,
                      "started": time.time(), "output": "", "run_id": self.run_id}
        self.env = None
        self.sdk = Path(config["devkitpro"]).expanduser().resolve()

    def status(self, **fields):
        self.state.update(fields)
        self.state["updated"] = time.time()
        try:
            json_write(self.status_file, self.state)
        except OSError:
            # A UI reader/antivirus may briefly hold a Windows handle. Logging
            # failure must not kill a successful compile; the next tick retries.
            pass

    def cancel(self):
        if self.cancel_file.exists():
            raise Cancelled("Operation cancelled by the user.")

    def log(self, text: str):
        print(text, flush=True)

    def stage(self, name: str):
        self.cancel()
        self.status(stage=name)
        self.log("\n=== " + name + " ===")

    def run(self, args: list[str | Path], timeout: float = 7200):
        self.cancel()
        command = list(map(str, args))
        self.log("> " + subprocess.list2cmdline(command))
        options = {"cwd": ROOT, "env": self.env, "stdin": subprocess.DEVNULL}
        if os.name != "nt":
            options["start_new_session"] = True
        proc = subprocess.Popen(command, **options)
        started, heartbeat = time.monotonic(), time.monotonic()
        try:
            while proc.poll() is None:
                self.cancel()
                if time.monotonic() - started > timeout:
                    raise WizardError("Process timeout reached; stopped without automatic retry.")
                if time.monotonic() - heartbeat >= 15:
                    self.status(child_pid=proc.pid)
                    heartbeat = time.monotonic()
                time.sleep(0.2)
            need(proc.returncode == 0, f"Command failed (exit code {proc.returncode}): {Path(command[0]).name}")
        except BaseException:
            if proc.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=15)
            raise

    def probe(self, command: list[str | Path]) -> str:
        self.cancel()
        try:
            result = subprocess.run(list(map(str, command)), env=self.env, cwd=ROOT,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=10, check=True, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as error:
            raise WizardError(f"Tool could not be used: {command[0]} ({error})") from error
        answer = (result.stdout or result.stderr).strip()
        need(bool(answer), f"No response from {command[0]}.")
        self.log(answer.splitlines()[0])
        return answer

    def preflight(self) -> dict:
        self.stage("Checking sources and devkitPro")
        need(sys.version_info >= (3, 10), "Python 3.10 or newer is required.")
        for name in ("build.py", "scripts/build_lus_3ds.py", "scripts/package_3ds.py", "scripts/build_clock.py", "cmake/3DS.cmake"):
            need((ROOT / name).is_file(), f"Missing source file: {name}")
        audio = check_audio_fix()
        self.log("3DS audio fix detected." + ("" if audio["matches_supplied_audio_fix"] else
                 " WARNING: playback.c contains additional differences from the supplied fix."))
        self.env, cmake, python = build_environment(self.sdk)
        self.env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
        native = self.sdk / "msys2/mingw64/bin"
        if os.name == "nt":
            for name in ("cmake.exe", "ninja.exe"):
                need((native / name).is_file(), f"Missing native Windows tool: {native / name}. See WIZARD-README.md.")
        required = ["libctru/include/3ds.h", "libctru/lib/libctru.a",
                    "libctru/include/citro3d.h", "libctru/lib/libcitro3d.a",
                    "portlibs/3ds/include/SDL2/SDL.h", "portlibs/3ds/include/zip.h",
                    "portlibs/3ds/include/zlib.h", "portlibs/3ds/include/tinyxml2.h",
                    "portlibs/3ds/include/spdlog/spdlog.h", "portlibs/3ds/include/nlohmann/json.hpp"]
        required += ["portlibs/3ds/lib/" + name for name in
                     ("libSDL2.a", "libzip.a", "libzlibstatic.a", "libtinyxml2.a", "libspdlog.a")]
        missing = [str(self.sdk / name) for name in required if not (self.sdk / name).is_file()]
        need(not missing, "Missing ARM/3DS dependencies (no automatic installation in this mode):\n" + "\n".join(missing))
        ext = ".exe" if os.name == "nt" else ""
        tools = {"gcc": self.sdk / "devkitARM/bin" / ("arm-none-eabi-gcc" + ext),
                 "g++": self.sdk / "devkitARM/bin" / ("arm-none-eabi-g++" + ext),
                 "picasso": self.sdk / "tools/bin" / ("picasso" + ext),
                 "3dsxtool": packager.find_tool("3dsxtool", self.sdk),
                 "bannertool": packager.find_tool("bannertool", self.sdk)}
        if self.config.get("with_cia", True):
            tools["makerom"] = packager.find_tool("makerom", self.sdk)
        for label, path in tools.items():
            need(path.is_file(), f"Missing tool: {path}")
            self.log(f"{label} : {path}")
        ninja = shutil.which("ninja", path=self.env["PATH"])
        need(ninja is not None, "Ninja was not found.")
        versions = {"cmake": self.probe([cmake, "--version"]),
                    "ninja": self.probe([ninja, "--version"]),
                    "python": self.probe([python, "--version"]),
                    "gcc": self.probe([tools["gcc"], "--version"]),
                    "g++": self.probe([tools["g++"], "--version"])}
        ver = re.search(r"cmake version (\d+)\.(\d+)", versions["cmake"])
        need(ver is not None and tuple(map(int, ver.groups())) >= (3, 26), "CMake 3.26 or newer is required.")
        ver = re.search(r"Python (\d+)\.(\d+)", versions["python"])
        need(ver is not None and tuple(map(int, ver.groups())) >= (3, 10), "Build Python must be version 3.10 or newer.")
        if self.config.get("mode", "clean") == "resume":
            check_resume(ROOT, self.sdk)
        output_base = Path(self.config["output_base"]).expanduser().resolve()
        for forbidden in (ROOT / "third_party", ROOT / "src", ROOT / "platform", ROOT / "cmake",
                          ROOT / "scripts", ROOT / "wizard", ROOT / "build-arm"):
            need(not output_base.is_relative_to(forbidden.resolve()), "Choose an output folder outside the source tree and build caches.")
        # Do not touch the chosen output or old caches during a check-only run.
        for key in ("icon",):
            if self.config.get(key):
                packager.checked_artwork(Path(self.config[key]), key)
        assets = []
        if self.config.get("copy_assets", False):
            self.stage("Validating selected archives")
            for key, support in (("mm_archive", False), ("support_archive", True)):
                need(bool(self.config.get(key)), "Select both mm.o2r and 2ship.o2r, or disable archive copying.")
                assets.append(inspect_archive(Path(self.config[key]), support,
                                             self.config.get("check_crc", True), self.cancel, self.log))
        else:
            self.log("Archives will not be copied; keep mm.o2r and 2ship.o2r on the SD card.")
        return {"wizard_version": VERSION, "audio_fix": audio, "tools": {k: str(v) for k, v in tools.items()},
                "tool_versions": versions, "devkitpro": str(self.sdk), "python_executable": str(python),
                "source_root": str(ROOT), "assets": assets}

    def build(self, report: dict):
        output_base = Path(self.config["output_base"]).expanduser().resolve()
        output_base.mkdir(parents=True, exist_ok=True)
        stage = output_base / (".incomplet-" + self.run_id)
        ready = output_base / ("BUILD-" + self.run_id)
        need(not stage.exists() and not ready.exists(), "Build identifier already exists; run the wizard again.")
        with project_lock(ROOT):
            if self.config.get("mode", "clean") == "clean":
                self.stage("Preserving previous build caches")
                report["cache_backups"] = backup_caches(ROOT, self.run_id, self.log)
            else:
                check_resume(ROOT, self.sdk)
            self.stage("Building libultraship and 2Ship 3DS")
            # Never skip LUS and never merely repackage an arbitrary old ELF.
            python = Path(report["python_executable"])
            self.run([python, "-u", ROOT / "build.py", "--devkitpro", self.sdk,
                      "--jobs", str(self.config.get("jobs", 4)), "--no-package"])
            elf = ROOT / "build-arm/2ship-3ds.elf"
            need(elf.is_file() and elf.stat().st_size > 0, "The build did not produce a usable ELF.")
            need(check_audio_fix()["sha256"] == report["audio_fix"]["sha256"],
                 "playback.c changed during the build. Output was not published; rebuild.")
            self.stage("Creating and validating output containers")
            stage.mkdir()
            args = [python, "-u", ROOT / "scripts/package_3ds.py", "--elf", elf,
                    "--output", stage, "--devkitpro", self.sdk]
            if not self.config.get("with_cia", True):
                args.append("--no-cia")
            for key in ("icon",):
                if self.config.get(key):
                    args += ["--" + key, self.config[key]]
            self.run(args, timeout=600)
            if report["assets"]:
                self.stage("Copying verified archives into the new output")
                for record in report["assets"]:
                    copy_checked(Path(record["source"]), stage / "SD/3ds/2ship" / record["name"],
                                 record["sha256"], self.cancel)
            self.stage("Finalizing output")
            report.update({"build_succeeded": True, "hardware_tested": False,
                           "run_id": self.run_id, "mode": self.config.get("mode", "clean"),
                           "configuration": self.config, "elf_sha256": digest(elf, self.cancel),
                           "source_base_manifest_sha256": digest(ROOT / "source-manifest.json"),
                           "files": []})
            for file in sorted(stage.rglob("*")):
                if file.is_file():
                    report["files"].append({"path": file.relative_to(stage).as_posix(),
                                            "size": file.stat().st_size, "sha256": digest(file, self.cancel)})
            json_write(stage / "wizard-build-report.json", report)
            (stage / "INSTALLATION.txt").write_text(
                "2Ship3DS - local build\n\n"
                "Copy the CONTENTS of the SD folder to the root of the SD card.\n"
                "3DSX: /3ds/2ship/2ship-3ds.3dsx\n"
                + ("CIA: /cias/2ship-3ds.cia; install this new CIA with your usual installer.\n"
                   if self.config.get("with_cia", True) else "CIA not requested: no CIA was generated in this output.\n")
                + "Keep mm.o2r + 2ship.o2r in /3ds/2ship/.\n"
                "Do not delete saves, settings, or mods.\n"
                "The wizard does not write directly to the SD card. No hardware test was performed.\n",
                encoding="utf-8")
            self.cancel()
            stage.rename(ready)
        self.status(status="success", stage="Complete", output=str(ready))
        self.log("\nOUTPUT: " + str(ready))
        self.log("Build complete. Audio and runtime behavior still require hardware testing.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--action", choices=("check", "build"), default="build")
    args = parser.parse_args()
    worker = None
    try:
        config = read_config(args.config)
        worker = Worker(args.config.resolve(), config)
        worker.status()
        report = worker.preflight()
        json_write(args.config.with_suffix(".preflight.json"), report)
        if args.action == "check":
            worker.status(status="checked", stage="Checks passed")
            worker.log("\nChecks passed. No compilation was run and existing build caches were not modified.")
        else:
            worker.build(report)
        return 0
    except Cancelled as error:
        if worker:
            worker.status(status="cancelled", stage="Cancelled", error=str(error))
        print(str(error), file=sys.stderr, flush=True)
        return 130
    except Exception as error:
        if worker:
            worker.status(status="error", stage="Failed", error=str(error))
        print("\nERROR: " + str(error), file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
