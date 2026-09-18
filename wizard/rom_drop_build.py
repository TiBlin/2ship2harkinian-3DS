#!/usr/bin/env python3
"""Automatic Windows ROM-drop builder for 2Ship3DS.

A supported Majora's Mask ROM is supplied by the user. The script obtains the
unmodified official 2Ship 5.0.1 Windows extraction kit when needed, uses it only
to generate mm.o2r from that ROM, upgrades the official support 2ship.o2r with
the 3DS support resources already present in this source tree, rebuilds the
3DS port, and publishes a lowercase `sd` folder containing only the runtime
files requested by the drag-and-drop workflow.

No ROM bytes are copied into the output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT / "wizard"))
sys.path.insert(0, str(SCRIPTS))

import build_wizard as bw
import package_3ds as packager
from build_lus_3ds import build_environment, default_devkitpro
from prepare_support import BASE_SHA256 as SUPPORT_BASE_SHA256, prepare as prepare_support

VERSION = "1.0.6-EN-ROMDROP"
RELEASE_TAG = "5.0.1"
RELEASE_APIS = (
    "https://api.github.com/repos/2ship2harkinian/2ship2harkinian/releases/tags/5.0.1",
    "https://api.github.com/repos/HarbourMasters/2ship2harkinian/releases/tags/5.0.1",
)
DIRECT_RELEASE_URL = (
    "https://github.com/HarbourMasters/2ship2harkinian/releases/download/5.0.1/"
    "2Ship-Battler-Bravo-Win64.zip"
)
ROM_EXTENSIONS = {".z64", ".n64", ".v64"}
MAX_DOWNLOAD = 1024 * 1024 * 1024
BLOCK = 1024 * 1024


class RomDropError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RomDropError(message)


def sha(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            h.update(block)
    return h.hexdigest()


def load_supported_hashes() -> dict[str, str]:
    source = ROOT / "third_party/2ship/docs/supportedHashes.json"
    need(source.is_file(), f"Supported-ROM list is missing: {source}")
    data = json.loads(source.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("sha1"), str) and isinstance(item.get("name"), str):
            result[item["sha1"].lower()] = item["name"]
    need(bool(result), "The supported-ROM list is empty.")
    return result


def validate_rom(path: Path, supported: dict[str, str] | None = None) -> dict:
    path = path.expanduser().resolve()
    need(path.is_file(), f"ROM not found: {path}")
    need(path.suffix.lower() in ROM_EXTENSIONS,
         "Drop a supported Majora's Mask ROM (.z64, .n64, or .v64) onto START-WIZARD.bat.")
    size = path.stat().st_size
    need(8 * 1024 * 1024 <= size <= 64 * 1024 * 1024,
         f"Unexpected ROM size ({size} bytes). The file was not used.")
    rom_sha1 = sha(path, "sha1")
    supported = supported or load_supported_hashes()
    need(rom_sha1 in supported,
         "Unsupported ROM dump. SHA-1: " + rom_sha1 + "\nSupported dumps in this source tree: " +
         ", ".join(sorted(supported.values())))
    return {"path": str(path), "sha1": rom_sha1, "name": supported[rom_sha1], "size": size}


def local_cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "2Ship3DS-Wizard"
    return Path(tempfile.gettempdir()) / "2Ship3DS-Wizard"


def safe_extract_zip(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        need(bad is None, f"Downloaded release ZIP is corrupt at entry: {bad}")
        total = 0
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            need(not name.startswith("/") and ".." not in Path(name).parts,
                 f"Unsafe path in release ZIP: {info.filename}")
            # Reject Unix symlinks encoded in external attributes.
            mode = (info.external_attr >> 16) & 0xFFFF
            need((mode & 0o170000) != 0o120000, f"Symlink entry refused: {info.filename}")
            total += info.file_size
            need(total <= 2 * 1024 * 1024 * 1024, "Release ZIP expands beyond the 2 GiB safety limit.")
        zf.extractall(destination)


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": f"2Ship3DS-Wizard/{VERSION}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        need(getattr(response, "status", 200) == 200, f"HTTP {getattr(response, 'status', '?')} from GitHub API")
        data = response.read(4 * 1024 * 1024)
    obj = json.loads(data.decode("utf-8"))
    need(isinstance(obj, dict), "Unexpected GitHub API response.")
    return obj


def discover_release_url() -> str:
    errors = []
    for api in RELEASE_APIS:
        try:
            release = http_json(api)
            assets = release.get("assets", [])
            for asset in assets:
                name = str(asset.get("name", ""))
                url = str(asset.get("browser_download_url", ""))
                if name.lower().endswith("-win64.zip") and url.startswith("https://github.com/"):
                    return url
            errors.append(f"No Win64 ZIP in {api}")
        except Exception as error:  # network/API errors are summarized for the fallback path
            errors.append(f"{api}: {error}")
    # The known 5.0.1 release asset name is used only as a fallback; its
    # 2ship.o2r is still pinned by SHA-256 before it is accepted.
    return DIRECT_RELEASE_URL


def download(url: str, destination: Path, log=print) -> None:
    temp = destination.with_suffix(destination.suffix + ".part")
    temp.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": f"2Ship3DS-Wizard/{VERSION}"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("xb") as out:
            length = response.headers.get("Content-Length")
            if length:
                need(int(length) <= MAX_DOWNLOAD, "Release download is unexpectedly large.")
            copied = 0
            last = time.monotonic()
            while True:
                block = response.read(BLOCK)
                if not block:
                    break
                copied += len(block)
                need(copied <= MAX_DOWNLOAD, "Release download exceeded the 1 GiB safety limit.")
                out.write(block)
                if time.monotonic() - last >= 2:
                    log(f"Downloaded {copied // (1024 * 1024)} MiB...")
                    last = time.monotonic()
        os.replace(temp, destination)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def find_release_root(extracted: Path) -> Path:
    candidates = []
    for exe in extracted.rglob("2ship.exe"):
        root = exe.parent
        support = root / "2ship.o2r"
        assets = root / "assets"
        if support.is_file() and assets.is_dir():
            candidates.append(root)
    need(len(candidates) == 1,
         "The official Windows release layout was not recognized (expected one 2ship.exe + 2ship.o2r + assets folder).")
    return candidates[0]


def ensure_desktop_release(log=print, release_zip: Path | None = None) -> Path:
    cache = local_cache_root()
    cache.mkdir(parents=True, exist_ok=True)
    final = cache / f"desktop-2ship-{RELEASE_TAG}"
    marker = final / ".2ship3ds-wizard-release.json"
    if marker.is_file():
        try:
            meta = json.loads(marker.read_text(encoding="utf-8"))
            root = Path(meta["release_root"])
            support = root / "2ship.o2r"
            if root.is_dir() and (root / "2ship.exe").is_file() and support.is_file() and sha(support) == SUPPORT_BASE_SHA256:
                log(f"Using cached official 2Ship {RELEASE_TAG} extraction kit: {root}")
                return root
        except Exception:
            pass

    manual = release_zip
    if manual is None:
        manual_candidate = ROOT / "wizard/cache/2Ship-5.0.1-Win64.zip"
        if manual_candidate.is_file():
            manual = manual_candidate
    if manual is None:
        downloads = cache / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        manual = downloads / "2Ship-5.0.1-Win64.zip"
        if not manual.is_file():
            url = discover_release_url()
            log("Downloading the official 2Ship 5.0.1 Windows release used only for ROM extraction...")
            log(url)
            try:
                download(url, manual, log)
            except (OSError, urllib.error.URLError, RomDropError) as error:
                raise RomDropError(
                    "Could not download the official 2Ship 5.0.1 Windows release.\n"
                    "Download the official Win64 5.0.1 ZIP manually and place it at:\n"
                    f"{ROOT / 'wizard/cache/2Ship-5.0.1-Win64.zip'}\n"
                    f"Network error: {error}"
                ) from error

    manual = manual.expanduser().resolve()
    need(manual.is_file(), f"Release ZIP not found: {manual}")
    stage = cache / (".desktop-release-" + uuid.uuid4().hex[:8])
    try:
        safe_extract_zip(manual, stage)
        release_root = find_release_root(stage)
        support = release_root / "2ship.o2r"
        actual = sha(support)
        need(actual == SUPPORT_BASE_SHA256,
             "The release contains an unexpected 2ship.o2r.\n"
             f"Expected SHA-256: {SUPPORT_BASE_SHA256}\nActual: {actual}\n"
             "Use the unmodified official Windows 2Ship 5.0.1 release.")
        if final.exists():
            shutil.rmtree(final)
        stage.rename(final)
        # Resolve the root again because the stage prefix changed.
        release_root = find_release_root(final)
        marker = final / ".2ship3ds-wizard-release.json"
        marker.write_text(json.dumps({"release_root": str(release_root), "release_zip_sha256": sha(manual),
                                      "support_sha256": SUPPORT_BASE_SHA256}, indent=2) + "\n", encoding="utf-8")
        log(f"Official extraction kit cached at: {release_root}")
        return release_root
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def terminate_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def o2r_ready(path: Path, support: bool, log=lambda *_: None) -> bool:
    try:
        bw.inspect_archive(path, support=support, full_crc=False, log=log)
        return True
    except Exception:
        return False


def generate_mm_o2r(rom: Path, rom_info: dict, release_root: Path, log=print,
                    timeout: float = 1200) -> Path:
    cache = local_cache_root() / "generated-o2r"
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / f"mm-{rom_info['sha1']}.o2r"
    if cached.is_file() and o2r_ready(cached, False):
        log(f"Using cached mm.o2r for {rom_info['name']}.")
        return cached

    work_parent = local_cache_root() / "extract-sessions"
    work_parent.mkdir(parents=True, exist_ok=True)
    session = work_parent / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    # A separate copy keeps the official cached release immutable and prevents a
    # previous mm.o2r from being mistaken for this ROM's extraction.
    shutil.copytree(release_root, session)
    target = session / "mm.o2r"
    target.unlink(missing_ok=True)
    exe = session / "2ship.exe"
    need(exe.is_file(), f"2ship.exe missing from extraction session: {exe}")
    log(f"Generating mm.o2r from: {rom}")
    log("The official extractor window may appear while this step runs; no game assets are bundled by the wizard.")
    options = {"cwd": session, "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        options["start_new_session"] = True
    proc = subprocess.Popen([str(exe), str(rom)], **options)
    deadline = time.monotonic() + timeout
    last_size = -1
    stable_since = None
    try:
        while time.monotonic() < deadline:
            if target.is_file():
                try:
                    size = target.stat().st_size
                    if size == last_size and size > 1024:
                        stable_since = stable_since or time.monotonic()
                    else:
                        stable_since = None
                        last_size = size
                    if stable_since and time.monotonic() - stable_since >= 1.5 and o2r_ready(target, False):
                        break
                except OSError:
                    pass
            if proc.poll() is not None and not target.is_file():
                raise RomDropError(f"The official extractor exited with code {proc.returncode} before creating mm.o2r.")
            time.sleep(0.5)
        else:
            raise RomDropError("Timed out waiting for the official extractor to create mm.o2r.")
    finally:
        terminate_tree(proc)

    # Full CRC validation occurs before caching or publishing.
    record = bw.inspect_archive(target, False, full_crc=True, log=log)
    temp = cached.with_suffix(".tmp.o2r")
    temp.unlink(missing_ok=True)
    shutil.copyfile(target, temp)
    need(sha(temp) == record["sha256"], "mm.o2r changed while it was being cached.")
    os.replace(temp, cached)
    shutil.rmtree(session, ignore_errors=True)
    return cached


def generate_support_o2r(release_root: Path, log=print) -> Path:
    base = release_root / "2ship.o2r"
    need(base.is_file(), f"Official 2ship.o2r is missing: {base}")
    need(sha(base) == SUPPORT_BASE_SHA256, "Official 2ship.o2r fingerprint changed; refusing to patch it.")
    cache = local_cache_root() / "generated-o2r"
    cache.mkdir(parents=True, exist_ok=True)
    output = cache / "2ship-3ds-5.0.1.o2r"
    if output.is_file():
        try:
            record = bw.inspect_archive(output, True, full_crc=False, log=lambda *_: None)
            if not record["missing_support_resources"]:
                log("Using cached 3DS support 2ship.o2r.")
                return output
        except Exception:
            pass
    temp = output.with_suffix(".tmp.o2r")
    temp.unlink(missing_ok=True)
    log("Preparing the 3DS support 2ship.o2r from the pinned official 5.0.1 archive...")
    prepare_support(base, temp)
    record = bw.inspect_archive(temp, True, full_crc=True, log=log)
    need(not record["missing_support_resources"], "Prepared 2ship.o2r is missing required 3DS support resources.")
    os.replace(temp, output)
    return output


def sdk_preflight(sdk: Path) -> tuple[dict, Path, Path]:
    sdk = sdk.expanduser().resolve()
    need(sdk.is_dir(), f"devkitPro folder not found: {sdk}")
    env, cmake, python = build_environment(sdk)
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
    required = [
        "libctru/include/3ds.h", "libctru/lib/libctru.a",
        "libctru/include/citro3d.h", "libctru/lib/libcitro3d.a",
        "portlibs/3ds/include/SDL2/SDL.h", "portlibs/3ds/include/zip.h",
        "portlibs/3ds/include/zlib.h", "portlibs/3ds/include/tinyxml2.h",
        "portlibs/3ds/include/spdlog/spdlog.h", "portlibs/3ds/include/nlohmann/json.hpp",
        "portlibs/3ds/lib/libSDL2.a", "portlibs/3ds/lib/libzip.a", "portlibs/3ds/lib/libzlibstatic.a",
        "portlibs/3ds/lib/libtinyxml2.a", "portlibs/3ds/lib/libspdlog.a",
    ]
    missing = [str(sdk / item) for item in required if not (sdk / item).is_file()]
    need(not missing, "Missing ARM/3DS dependencies:\n" + "\n".join(missing))
    packager.find_tool("3dsxtool", sdk)
    return env, cmake, python


def run(command: list[str | Path], *, env: dict | None = None, cwd: Path = ROOT, log=print,
        timeout: float = 7200) -> None:
    command = list(map(str, command))
    log("> " + subprocess.list2cmdline(command))
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=timeout)


def compatible_or_backup_caches(sdk: Path, log=print) -> None:
    try:
        bw.check_resume(ROOT, sdk)
    except bw.WizardError as error:
        suffix = time.strftime("%Y%m%d-%H%M%S") + "-romdrop"
        log(f"Existing build cache is not reusable ({error}). Preserving it and starting clean.")
        bw.backup_caches(ROOT, suffix, log)


def unique_backup(path: Path) -> Path:
    stem = path.name + ".backup-" + time.strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(stem)
    index = 1
    while candidate.exists():
        candidate = path.with_name(stem + f"-{index}")
        index += 1
    return candidate


def publish_sd(output: Path, three_dsx: Path, mm: Path, support: Path, report: dict, log=print) -> Path:
    output = output.expanduser().resolve()
    need(output.name.lower() == "sd", "ROM-drop output folder must be named exactly 'sd'.")
    stage = output.with_name(".sd-incomplete-" + uuid.uuid4().hex[:8])
    shutil.rmtree(stage, ignore_errors=True)
    target = stage / "3ds/2ship"
    target.mkdir(parents=True)
    for source, name in ((three_dsx, "2ship-3ds.3dsx"), (mm, "mm.o2r"), (support, "2ship.o2r")):
        need(source.is_file(), f"Required output is missing: {source}")
        shutil.copyfile(source, target / name)
    # Verify exact copied bytes before publication.
    for source, name in ((three_dsx, "2ship-3ds.3dsx"), (mm, "mm.o2r"), (support, "2ship.o2r")):
        need(sha(source) == sha(target / name), f"Copy verification failed for {name}.")
    report["output_files"] = [
        {"path": str((Path("3ds/2ship") / name).as_posix()), "size": (target / name).stat().st_size,
         "sha256": sha(target / name)}
        for name in ("2ship-3ds.3dsx", "mm.o2r", "2ship.o2r")
    ]
    backup = None
    if output.exists():
        backup = unique_backup(output)
        output.rename(backup)
        log(f"Existing sd folder preserved as: {backup}")
    try:
        stage.rename(output)
    except Exception:
        if backup and not output.exists() and backup.exists():
            backup.rename(output)
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--devkitpro", type=Path, default=default_devkitpro())
    parser.add_argument("--output", type=Path, default=ROOT / "sd")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--release-zip", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64:
        parser.error("--jobs must be between 1 and 64")

    log_dir = ROOT / "wizard-logs" / (time.strftime("romdrop-%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "romdrop.log"

    def log(message=""):
        line = str(message)
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    report = {"wizard_version": VERSION, "mode": "rom-drop", "started": time.time(),
              "hardware_tested": False, "rom_bundled": False, "success": False}
    try:
        if os.name != "nt":
            log("WARNING: ROM-drop mode is intended for Windows; host tests may exercise individual functions elsewhere.")
        log(f"2Ship3DS ROM-drop builder {VERSION}")
        log(f"Source folder: {ROOT}")
        log(f"Log: {log_path}")
        log("\n=== Validating ROM ===")
        rom_info = validate_rom(args.rom)
        report["rom"] = {k: v for k, v in rom_info.items() if k != "path"}
        log(f"ROM: {rom_info['name']} | SHA-1 {rom_info['sha1']}")

        log("\n=== Checking devkitPro and source tree ===")
        bw.check_audio_fix()
        env, cmake, python = sdk_preflight(args.devkitpro)
        log(f"devkitPro: {args.devkitpro.resolve()}")
        log(f"Python: {python}")
        log(f"CMake: {cmake}")

        log("\n=== Preparing official desktop extractor ===")
        release_root = ensure_desktop_release(log, args.release_zip)
        report["desktop_release_support_sha256"] = sha(release_root / "2ship.o2r")

        log("\n=== Generating O2R archives ===")
        mm = generate_mm_o2r(args.rom.resolve(), rom_info, release_root, log)
        support = generate_support_o2r(release_root, log)
        mm_record = bw.inspect_archive(mm, False, full_crc=True, log=log)
        support_record = bw.inspect_archive(support, True, full_crc=True, log=log)
        report["o2r"] = {"mm": mm_record, "support": support_record}

        log("\n=== Building 2Ship3DS ===")
        with bw.project_lock(ROOT):
            compatible_or_backup_caches(args.devkitpro.resolve(), log)
            run([python, "-u", ROOT / "build.py", "--devkitpro", args.devkitpro.resolve(),
                 "--jobs", str(args.jobs), "--no-package"], env=env, log=log)
            elf = ROOT / "build-arm/2ship-3ds.elf"
            need(elf.is_file() and elf.stat().st_size > 0, "Build did not produce build-arm/2ship-3ds.elf.")
            package_stage = Path(tempfile.mkdtemp(prefix="2ship3ds-romdrop-package-", dir=local_cache_root()))
            try:
                run([python, "-u", ROOT / "scripts/package_3ds.py", "--elf", elf,
                     "--output", package_stage, "--devkitpro", args.devkitpro.resolve(), "--no-cia"],
                    env=env, log=log, timeout=600)
                three_dsx = package_stage / "SD/3ds/2ship/2ship-3ds.3dsx"
                need(three_dsx.is_file() and three_dsx.stat().st_size > 0, "3DSX packaging failed.")
                log("\n=== Publishing sd folder ===")
                final = publish_sd(args.output, three_dsx, mm, support, report, log)
            finally:
                shutil.rmtree(package_stage, ignore_errors=True)

        report["success"] = True
        report["finished"] = time.time()
        report["output"] = str(final)
        report["rom_bundled"] = False
        (log_dir / "romdrop-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        log("\nSUCCESS")
        log(f"SD-ready folder: {final}")
        log("Contains only: 2ship-3ds.3dsx, mm.o2r, and 2ship.o2r under sd/3ds/2ship/.")
        log("Copy the CONTENTS of the sd folder to the root of your SD card.")
        return 0
    except (RomDropError, bw.WizardError, OSError, subprocess.SubprocessError, zipfile.BadZipFile,
            json.JSONDecodeError) as error:
        report["error"] = str(error)
        report["finished"] = time.time()
        try:
            (log_dir / "romdrop-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
        log("\nERROR: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
